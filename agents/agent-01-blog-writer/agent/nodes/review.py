"""review node — structured LLM quality evaluation (DESIGN §1.2, §6, §7, §9).

Eighth repair pass:
- is_mock now derived via resolve_is_mock(cfg) — validates provider/mock consistency.

Seventh repair pass:
- Replaced ad-hoc ceiling check + compute_max_tokens with authorize_call().
  review has no mandatory downstream stages (it is the last billable stage).
  max_tokens is derived from the returned CallAuthorization (eighth repair: now correctly
  computed as ceiling - current - 0 for review, since no downstream reserve).
  CostCeilingExceeded propagates to _node_with_error_guard → cost_gate_ok=False.
- is_mock read from config; authorize_call skips fail-closed zero-pricing check for mock.

Sixth repair pass (intact):
- max_tokens=0 guard — subsumed by authorize_call's CostCeilingExceeded.

Media trust boundary:
- Text review compares against raw_input.
- Voice/video review compares against the transcript, because a media filename contains
  none of the spoken source needed for injection, copying, or claim checks.
"""
from __future__ import annotations
from typing import Any
from core.cost import CostCeilingExceeded, authorize_call, estimate_prompt_tokens, resolve_is_mock, usage_cost_inr
from core.interfaces import Telemetry
from core.interfaces.errors import BillableProviderError
from core.interfaces.llm import LLMProvider
from core.interfaces.base import CoreContractModel
from ..prompts import build_system, review_prompt
from ..schemas import (
    BillableNodeError,
    BlogPlan,
    ExtractedIdeas,
    QualityReport,
    StageCost,
    SubScores,
    _HARD_FAIL_CODES,
    _SUBSCORE_FIELDS,
    _TERMINAL_HARD_FAIL_CODES,
    _sum_sub_scores,
)
from ..state import BlogState


class RawQualityReport(CoreContractModel):
    """LLM-facing review schema.

    The final QualityReport has derived invariants that are safer to compute in
    code than to ask a model to reproduce exactly (for example, overall_score is
    the sum of subscores and pass_flag is a boolean formula).  This raw schema
    collects only model judgments; _build_quality_report derives the contract
    fields deterministically.
    """

    sub_scores: SubScores
    hard_fail_flags: tuple[str, ...] = ()
    revision_notes: str = ""
    improvement_suggestions: tuple[str, ...] = ()


def _build_quality_report(raw: RawQualityReport) -> QualityReport:
    known_flags: list[str] = []
    unknown_flags: list[str] = []
    for flag in raw.hard_fail_flags:
        if flag in _HARD_FAIL_CODES:
            known_flags.append(flag)
        else:
            unknown_flags.append(flag)

    if unknown_flags and "not_review_ready" not in known_flags:
        known_flags.append("not_review_ready")

    hard_fail_flags = tuple(dict.fromkeys(known_flags))
    overall_score = _sum_sub_scores(raw.sub_scores)
    pass_flag = overall_score >= 80 and not hard_fail_flags
    needs_human = any(flag in _TERMINAL_HARD_FAIL_CODES for flag in hard_fail_flags)

    revision_notes = raw.revision_notes.strip()
    suggestions = tuple(s.strip() for s in raw.improvement_suggestions if s.strip())
    if unknown_flags:
        unknown_msg = "Review returned unrecognized hard-fail flags; revise and re-review conservatively."
        revision_notes = (revision_notes + "\n" + unknown_msg).strip() if revision_notes else unknown_msg
        suggestions = suggestions + ("Use only registered hard-fail categories in the next review.",)
    if not pass_flag and not revision_notes:
        revision_notes = "Improve the draft according to the lowest-scoring review dimensions."
    if not pass_flag and not suggestions:
        suggestions = ("Revise the structure, coverage, clarity, and evidence before finalizing.",)

    return QualityReport(
        overall_score=overall_score,
        sub_scores=raw.sub_scores,
        pass_flag=pass_flag,
        hard_fail_flags=hard_fail_flags,
        revision_notes=revision_notes,
        needs_human=needs_human,
        improvement_suggestions=suggestions,
    )


def make_review_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    cost_cfg = cfg.get("cost", {})
    fx_rates: dict[str, float] = cost_cfg.get("fx_rates", {"USD": 83.0})
    ceiling_inr: float = float(cost_cfg.get("ceiling_inr", 50.0))
    estimated_costs: dict[str, float] = {
        k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()
    }
    # Eighth repair: derive is_mock from provider config key, not just cost.is_mock.
    is_mock: bool = resolve_is_mock(cfg)
    _strong_cpt: float = float(cost_cfg.get("output_cost_per_token_inr", {}).get("strong", 0.0))
    # Eleventh repair: actual prompt tokens counted from constructed messages.
    _input_cpt: float = float(cost_cfg.get("input_cost_per_token_inr", {}).get("strong", 0.0))
    _max_prompt: int = int(cost_cfg.get("max_prompt_tokens", {}).get("strong", 4096))
    _fixed_cost: float = float(cost_cfg.get("fixed_cost_inr", {}).get("strong", 0.0))
    _max_output_tokens: int = int(cost_cfg.get("max_output_tokens", {}).get("review", 0))

    def review(state: BlogState) -> dict[str, Any]:
        draft_body: str = state.get("draft", "")  # type: ignore[assignment]
        blog_plan: BlogPlan | None = state.get("blog_plan")  # type: ignore[assignment]
        # For media, the transcript is the original source material. Passing the file
        # reference would make spoken injection/copying invisible to the reviewer.
        raw_input: str = state.get("raw_input", "")  # type: ignore[assignment]
        input_type: str = state.get("input_type", "text") or "text"  # type: ignore[assignment]
        transcript: str = state.get("transcript", "")  # type: ignore[assignment]
        source_material = transcript if input_type in ("voice", "video") else raw_input

        plan_summary = _format_plan_summary(blog_plan) if blog_plan else "(no plan)"
        key_points = _format_key_points(blog_plan) if blog_plan else "(none)"

        # Item 3: build extracted_ideas_summary from state for richer review context.
        extracted: ExtractedIdeas | None = state.get("extracted_ideas")  # type: ignore[assignment]
        extracted_ideas_summary = _format_extracted_ideas(extracted) if extracted else ""

        # ── Build messages ─────────────────────────────────────────────────────
        system = build_system(cfg)
        user_msg = review_prompt(
            plan_summary, draft_body, key_points,
            source_material=source_material,
            extracted_ideas_summary=extracted_ideas_summary,
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_msg}]

        # Pass response_schema so the schema's JSON overhead is included in the estimate.
        prompt_tokens_est: int = estimate_prompt_tokens(messages, response_schema=RawQualityReport)
        if prompt_tokens_est > _max_prompt:
            raise CostCeilingExceeded(
                f"review: conservative prompt estimate {prompt_tokens_est} bytes "
                f"exceeds max_prompt_tokens={_max_prompt}; provider call blocked"
            )

        # ── Centralized pre-call budget authorization ─────────────────────────
        # review is the last billable stage: no downstream reserves needed.
        auth = authorize_call(
            stage_name="review",
            stage_costs=state.get("cost_usage", []),  # type: ignore[arg-type]
            ceiling_inr=ceiling_inr,
            estimated_costs=estimated_costs,
            downstream_stages=(),
            output_cost_per_token_inr=_strong_cpt,
            input_cost_per_token_inr=_input_cpt,
            prompt_tokens_estimate=prompt_tokens_est,
            fixed_cost_inr=_fixed_cost,
            is_mock=is_mock,
        )
        if auth.max_tokens is not None:
            max_tokens = min(auth.max_tokens, _max_output_tokens) if _max_output_tokens > 0 else auth.max_tokens
            params: dict[str, Any] = {"max_tokens": max_tokens}
        else:
            params = {}
        # Always pass the authorized prompt estimate so _conservative_usage uses it exactly.
        params["_authorized_prompt_tokens"] = prompt_tokens_est

        stage_cost: StageCost | None = None
        try:
            with tel.span("review") as span_id:
                try:
                    response = llm.respond(
                        messages, tier="strong", response_schema=RawQualityReport,
                        params=params,
                    )
                except BillableProviderError as bpe:
                    # Pass ONLY the content-free category + usage-derived stage cost.
                    _stage_cost_bpe = StageCost(
                        stage="review",
                        cost_inr=usage_cost_inr(bpe.usage, fx_rates=fx_rates),
                        tier="strong",
                        tokens_prompt=bpe.usage.prompt_tokens,
                        tokens_completion=bpe.usage.completion_tokens,
                    )
                    stage_cost = _stage_cost_bpe
                    raise BillableNodeError(
                        _stage_cost_bpe,
                        RuntimeError(f"billable-provider-failure:{bpe.category}"),
                    ) from None
                cost_inr = usage_cost_inr(response.usage, fx_rates=fx_rates)
                stage_cost = StageCost(
                    stage="review", cost_inr=cost_inr, tier="strong",
                    tokens_prompt=response.usage.prompt_tokens,
                    tokens_completion=response.usage.completion_tokens,
                )
                try:
                    tel.record_usage(response.usage, node="review", tier="strong", span_id=span_id)
                    report = _build_quality_report(response.structured)  # type: ignore[arg-type]
                    tel.metric("stage.cost_inr", cost_inr, node="review")
                    tel.metric("quality.overall_score", report.overall_score, node="review")
                    for field in _SUBSCORE_FIELDS:
                        tel.metric(f"quality.{field}", getattr(report.sub_scores, field, 0), node="review")
                    tel.log("review.complete", span_id=span_id, overall_score=report.overall_score,
                            pass_flag=report.pass_flag, needs_human=report.needs_human,
                            hard_fail_count=len(report.hard_fail_flags))
                    update: dict[str, Any] = {"quality": report, "cost_usage": [stage_cost]}
                    if report.hard_fail_flags:
                        update["hard_fail_flags"] = list(report.hard_fail_flags)
                    return update
                except Exception as exc:
                    raise BillableNodeError(stage_cost, exc) from exc
        except BillableNodeError:
            raise
        except Exception as exc:
            if stage_cost is not None:
                raise BillableNodeError(stage_cost, exc) from exc
            raise

    return review


def _format_plan_summary(plan: BlogPlan) -> str:
    """Format plan for the review prompt (Item 3: all planning fields)."""
    lines = [
        f"Title: {plan.title}",
        f"Tone: {plan.tone}",
        f"Audience: {plan.audience}",
        f"Angle: {plan.angle}",
        f"Target word count: {plan.target_word_count}",
        "Sections: " + ", ".join(plan.sections),
    ]
    if plan.target_keywords:
        lines.append("Target keywords: " + ", ".join(plan.target_keywords))
    if plan.campaign_goal:
        lines.append(f"Campaign goal: {plan.campaign_goal}")
    if plan.value_proposition:
        lines.append(f"Value proposition: {plan.value_proposition}")
    if plan.cta:
        lines.append(f"Suggested CTA: {plan.cta}")
    if plan.proof_points_or_placeholders:
        lines.append("Proof points or evidence placeholders: " + "; ".join(plan.proof_points_or_placeholders))
    if plan.constraints:
        lines.append("Constraints and things to avoid: " + "; ".join(plan.constraints))
    if plan.risk_flags:
        lines.append("Risk flags: " + "; ".join(plan.risk_flags))
    return "\n".join(lines)


def _format_key_points(plan: BlogPlan) -> str:
    lines = [f"- {p}" for p in plan.key_points]
    for label, values in (
        ("Proof placeholders", plan.proof_points_or_placeholders),
        ("Constraints", plan.constraints),
        ("Risk flags", plan.risk_flags),
    ):
        if values:
            lines.append(f"{label}:")
            lines.extend(f"- {value}" for value in values)
    if not lines:
        return "(not specified)"
    return "\n".join(lines)


def _format_extracted_ideas(extracted: ExtractedIdeas) -> str:
    """Format extracted ideas for the review prompt (Item 3)."""
    if not extracted or not extracted.main_idea.strip():
        return ""
    parts = [f"Main idea: {extracted.main_idea}"]
    if extracted.key_points:
        parts.append("Key points: " + "; ".join(extracted.key_points))
    if extracted.suggested_angle:
        parts.append(f"Suggested angle: {extracted.suggested_angle}")
    return "\n".join(parts)
