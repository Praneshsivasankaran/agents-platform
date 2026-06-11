"""draft node — LLM blog drafting / revision (DESIGN §1.2, §6).

Eighth repair pass:
- is_mock now derived via resolve_is_mock(cfg) — validates provider/mock consistency.
  A non-mock cloud provider with cost.is_mock=True raises ValueError at build time.

Seventh repair pass:
- Replaced ad-hoc ceiling check + compute_max_tokens with authorize_call().
  authorize_call reserves review budget before calling the LLM (draft reserves review).
  max_tokens is derived from the returned CallAuthorization (eighth repair: now correctly
  computed as ceiling - current - downstream_reserve, not ceiling - current).
  CostCeilingExceeded propagates to _node_with_error_guard → cost_gate_ok=False.
- is_mock read from config; authorize_call skips fail-closed zero-pricing check for mock.

Sixth repair pass (intact):
- max_tokens=0 guard (was: block when compute_max_tokens returns 0) — this guard is
  now subsumed by authorize_call: if remaining headroom cannot cover draft+review, the
  call is rejected before reaching the provider.

Fifth repair pass (intact):
- Pre-call ceiling check and compute_max_tokens — superseded by authorize_call.

Previous repair notes (intact):
- Initial draft does NOT increment revision_count (which tracks completed revisions).
- Revision calls increment revision_count by 1 each time.
- Uses reviewer_feedback_block for safe injection of revision notes.
"""
from __future__ import annotations
from typing import Any
from core.cost import CostCeilingExceeded, authorize_call, estimate_prompt_tokens, resolve_is_mock, usage_cost_inr
from core.interfaces import Telemetry
from core.interfaces.errors import BillableProviderError
from core.interfaces.llm import LLMProvider
from ..prompts import build_system, draft_prompt
from ..schemas import BillableNodeError, BlogPlan, QualityReport, StageCost
from ..state import BlogState


def make_draft_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
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

    def draft(state: BlogState) -> dict[str, Any]:
        normalized_content: str = state.get("normalized_content", "")  # type: ignore[assignment]
        blog_plan: BlogPlan = state.get("blog_plan")  # type: ignore[assignment]
        quality: QualityReport | None = state.get("quality")  # type: ignore[assignment]
        revision_count: int = state.get("revision_count", 0)  # type: ignore[assignment]

        # Initial draft:  quality is None  → revision_count stays at 0.
        # Revision draft: quality is set   → revision_count increments.
        is_revision = quality is not None
        new_revision_count = revision_count + 1 if is_revision else revision_count

        plan_summary = _format_plan(blog_plan) if blog_plan else "(no plan available)"
        revision_notes = quality.revision_notes if quality and is_revision else ""
        # Item 3: pass improvement_suggestions alongside revision_notes.
        improvement_suggestions = ""
        if quality and is_revision and quality.improvement_suggestions:
            improvement_suggestions = "\n".join(quality.improvement_suggestions)
        prompt_cycle = new_revision_count if is_revision else 0

        # ── Build messages first ───────────────────────────────────────────────
        system = build_system(cfg)
        user_msg = draft_prompt(
            normalized_content, plan_summary,
            revision_notes=revision_notes,
            improvement_suggestions=improvement_suggestions,
            revision_cycle=prompt_cycle,
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_msg}]

        prompt_tokens_est: int = estimate_prompt_tokens(messages)
        if prompt_tokens_est > _max_prompt:
            raise CostCeilingExceeded(
                f"draft: conservative prompt estimate {prompt_tokens_est} bytes "
                f"exceeds max_prompt_tokens={_max_prompt}; provider call blocked"
            )

        # ── Centralized pre-call budget authorization ─────────────────────────
        auth = authorize_call(
            stage_name="draft",
            stage_costs=state.get("cost_usage", []),  # type: ignore[arg-type]
            ceiling_inr=ceiling_inr,
            estimated_costs=estimated_costs,
            downstream_stages=("review",),
            output_cost_per_token_inr=_strong_cpt,
            input_cost_per_token_inr=_input_cpt,
            prompt_tokens_estimate=prompt_tokens_est,
            fixed_cost_inr=_fixed_cost,
            is_mock=is_mock,
        )
        params: dict[str, Any] = {"max_tokens": auth.max_tokens} if auth.max_tokens is not None else {}
        # Always pass the authorized prompt estimate so _conservative_usage uses it exactly.
        params["_authorized_prompt_tokens"] = prompt_tokens_est

        stage_cost: StageCost | None = None
        try:
            with tel.span("draft") as span_id:
                try:
                    response = llm.respond(messages, tier="strong", params=params)
                except BillableProviderError as bpe:
                    # Pass ONLY the content-free category + usage-derived stage cost.
                    _stage_cost_bpe = StageCost(
                        stage="draft",
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
                    stage="draft", cost_inr=cost_inr, tier="strong",
                    tokens_prompt=response.usage.prompt_tokens,
                    tokens_completion=response.usage.completion_tokens,
                )
                try:
                    tel.record_usage(response.usage, node="draft", tier="strong", span_id=span_id)
                    body = response.text or ""
                    tel.metric("stage.cost_inr", cost_inr, node="draft")
                    tel.metric("revision.count", new_revision_count, node="draft")
                    tel.log("draft.complete", span_id=span_id,
                            revision_count=new_revision_count, body_chars=len(body))
                    return {"draft": body, "revision_count": new_revision_count, "cost_usage": [stage_cost]}
                except Exception as exc:
                    raise BillableNodeError(stage_cost, exc) from exc
        except BillableNodeError:
            raise
        except Exception as exc:
            if stage_cost is not None:
                raise BillableNodeError(stage_cost, exc) from exc
            raise

    return draft


def _format_plan(plan: BlogPlan) -> str:
    """Format the full blog plan for the draft prompt (Item 3: all planning fields)."""
    lines = [
        f"Title: {plan.title}",
        f"Tone: {plan.tone}",
        f"Audience: {plan.audience}",
        f"Angle: {plan.angle}",
        f"Target word count: {plan.target_word_count}",
        "Sections:",
    ]
    for section in plan.sections:
        lines.append(f"  - {section}")
    if plan.key_points:
        lines.append("Key points:")
        for point in plan.key_points:
            lines.append(f"  - {point}")
    if plan.target_keywords:
        lines.append("Target keywords: " + ", ".join(plan.target_keywords))
    if plan.title_candidates:
        lines.append("Title candidates considered:")
        for t in plan.title_candidates:
            lines.append(f"  - {t}")
    return "\n".join(lines)
