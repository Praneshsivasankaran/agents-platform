"""extract_ideas node — structured LLM extraction of core ideas (DESIGN §1.2, §6, §7).

Eighth repair pass:
- is_mock now derived via resolve_is_mock(cfg) — validates provider/mock consistency.
- auth result captured; max_tokens passed to structured LLM call (cheap tier; None for mock).

Seventh repair pass:
- Replaced ad-hoc ceiling check with authorize_call() from packages/core.
  Downstream reserves: plan, draft, review.
  CostCeilingExceeded propagates to _node_with_error_guard → cost_gate_ok=False.
- Updated log event to reference key_points (replaces ideas from old schema).
- is_mock read from config for authorize_call.

Sixth repair pass (intact):
- Pre-call ceiling check changed from > to >= — superseded by authorize_call.
"""
from __future__ import annotations
from typing import Any
from core.cost import CostCeilingExceeded, authorize_call, estimate_prompt_tokens, resolve_is_mock, usage_cost_inr
from core.interfaces import Telemetry
from core.interfaces.errors import BillableProviderError
from core.interfaces.llm import LLMProvider
from ..prompts import build_system, extract_ideas_prompt
from ..schemas import Agent03BlogBrief, BillableNodeError, ExtractedIdeas, StageCost
from ..state import BlogState


def _ideas_from_agent03_blog_brief(brief: Agent03BlogBrief) -> ExtractedIdeas:
    main_idea = (
        brief.core_message
        or brief.selected_idea_title
        or brief.suggested_title
        or brief.value_proposition
    )
    key_points: list[str] = []
    for value in (brief.value_proposition, brief.campaign_goal, brief.cta):
        if value and value not in key_points:
            key_points.append(value)
    for values in (
        brief.pain_points,
        brief.suggested_outline,
        brief.proof_points_or_placeholders,
        brief.constraints,
        brief.risk_flags,
    ):
        for value in values:
            if value not in key_points:
                key_points.append(value)

    return ExtractedIdeas(
        main_idea=main_idea,
        key_points=tuple(key_points[:8]),
        suggested_angle=brief.content_angle or None,
        source_notes=(),
        usable=True,
        thin_reason=None,
    )


def make_extract_ideas_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    cost_cfg = cfg.get("cost", {})
    fx_rates: dict[str, float] = cost_cfg.get("fx_rates", {"USD": 83.0})
    ceiling_inr: float = float(cost_cfg.get("ceiling_inr", 50.0))
    estimated_costs: dict[str, float] = {
        k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()
    }
    # Eighth repair: derive is_mock from provider config key, not just cost.is_mock.
    is_mock: bool = resolve_is_mock(cfg)
    _cheap_cpt: float = float(cost_cfg.get("output_cost_per_token_inr", {}).get("cheap", 0.0))
    # Eleventh repair: actual prompt tokens counted from constructed messages.
    _input_cpt: float = float(cost_cfg.get("input_cost_per_token_inr", {}).get("cheap", 0.0))
    _max_prompt: int = int(cost_cfg.get("max_prompt_tokens", {}).get("cheap", 2048))
    _fixed_cost: float = float(cost_cfg.get("fixed_cost_inr", {}).get("cheap", 0.0))
    _max_output_tokens: int = int(cost_cfg.get("max_output_tokens", {}).get("extract_ideas", 0))

    def extract_ideas(state: BlogState) -> dict[str, Any]:
        normalized_content: str = state.get("normalized_content", "")  # type: ignore[assignment]
        blog_brief: Agent03BlogBrief | None = state.get("blog_brief_from_agent_03")  # type: ignore[assignment]
        if blog_brief is not None:
            tel.log("extract_ideas.agent03_blog_brief")
            return {"extracted_ideas": _ideas_from_agent03_blog_brief(blog_brief)}

        # ── Build messages first, enforce prompt-size limit ───────────────────
        system = build_system(cfg)
        user_msg = extract_ideas_prompt(normalized_content)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_msg}]

        # Pass response_schema so the schema's JSON overhead is included in the estimate.
        prompt_tokens_est: int = estimate_prompt_tokens(messages, response_schema=ExtractedIdeas)
        if prompt_tokens_est > _max_prompt:
            raise CostCeilingExceeded(
                f"extract_ideas: conservative prompt estimate {prompt_tokens_est} bytes "
                f"exceeds max_prompt_tokens={_max_prompt}; provider call blocked"
            )

        # ── Pre-call budget authorization ─────────────────────────────────────
        auth = authorize_call(
            stage_name="extract_ideas",
            stage_costs=state.get("cost_usage", []),  # type: ignore[arg-type]
            ceiling_inr=ceiling_inr,
            estimated_costs=estimated_costs,
            downstream_stages=("plan", "draft", "review"),
            output_cost_per_token_inr=_cheap_cpt,
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
            with tel.span("extract_ideas") as span_id:
                try:
                    response = llm.respond(
                        messages, tier="cheap", response_schema=ExtractedIdeas,
                        params=params,
                    )
                except BillableProviderError as bpe:
                    # Pass ONLY the content-free category + usage-derived stage cost.
                    _stage_cost_bpe = StageCost(
                        stage="extract_ideas",
                        cost_inr=usage_cost_inr(bpe.usage, fx_rates=fx_rates),
                        tier="cheap",
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
                    stage="extract_ideas", cost_inr=cost_inr, tier="cheap",
                    tokens_prompt=response.usage.prompt_tokens,
                    tokens_completion=response.usage.completion_tokens,
                )
                try:
                    tel.record_usage(response.usage, node="extract_ideas", tier="cheap", span_id=span_id)
                    ideas: ExtractedIdeas = response.structured  # type: ignore[assignment]
                    tel.metric("stage.cost_inr", cost_inr, node="extract_ideas")
                    tel.log(
                        "extract_ideas.complete", span_id=span_id,
                        key_point_count=len(ideas.key_points),
                        usable=ideas.usable,
                    )
                    return {"extracted_ideas": ideas, "cost_usage": [stage_cost]}
                except Exception as exc:
                    raise BillableNodeError(stage_cost, exc) from exc
        except BillableNodeError:
            raise
        except Exception as exc:
            if stage_cost is not None:
                raise BillableNodeError(stage_cost, exc) from exc
            raise

    return extract_ideas
