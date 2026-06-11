"""plan node — structured LLM generation of the blog content plan (DESIGN §1.2, §6, §7).

Eighth repair pass:
- is_mock now derived via resolve_is_mock(cfg) — validates provider/mock consistency.
- auth result captured; max_tokens passed to structured LLM call (cheap tier; None for mock).
- Removed title=blog_plan.title from plan.complete telemetry — generated content must not
  flow through telemetry (rely on redaction is not safe enough per DESIGN §10).

Seventh repair pass:
- Replaced ad-hoc ceiling check with authorize_call() from packages/core.
  Downstream reserves: draft, review.
  CostCeilingExceeded propagates to _node_with_error_guard → cost_gate_ok=False,
  then route_after_plan routes to finalize (not cost_gate) so cost_gate cannot
  incorrectly override cost_gate_ok=False.
- Updated ideas_summary to use ExtractedIdeas.main_idea + key_points (seventh repair
  schema change: ideas field removed).
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
from ..prompts import build_system, plan_prompt
from ..schemas import BillableNodeError, BlogPlan, ExtractedIdeas, StageCost
from ..state import BlogState


def make_plan_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
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

    def plan(state: BlogState) -> dict[str, Any]:
        normalized_content: str = state.get("normalized_content", "")  # type: ignore[assignment]
        extracted: ExtractedIdeas = state.get("extracted_ideas")  # type: ignore[assignment]

        # Seventh repair: build ideas_summary from main_idea + key_points.
        if extracted and extracted.main_idea.strip():
            lines = [f"Main idea: {extracted.main_idea}"]
            if extracted.key_points:
                lines.append("Key points:")
                lines.extend(f"  - {kp}" for kp in extracted.key_points)
            if extracted.suggested_angle:
                lines.append(f"Suggested angle: {extracted.suggested_angle}")
            ideas_summary = "\n".join(lines)
        else:
            ideas_summary = "(none extracted)"

        # ── Build messages first (eleventh repair) ────────────────────────────
        system = build_system(cfg)
        user_msg = plan_prompt(normalized_content, ideas_summary)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_msg}]

        # Pass response_schema so the schema's JSON overhead is included in the estimate.
        prompt_tokens_est: int = estimate_prompt_tokens(messages, response_schema=BlogPlan)
        if prompt_tokens_est > _max_prompt:
            raise CostCeilingExceeded(
                f"plan: conservative prompt estimate {prompt_tokens_est} bytes "
                f"exceeds max_prompt_tokens={_max_prompt}; provider call blocked"
            )

        # ── Centralized pre-call budget authorization ─────────────────────────
        auth = authorize_call(
            stage_name="plan",
            stage_costs=state.get("cost_usage", []),  # type: ignore[arg-type]
            ceiling_inr=ceiling_inr,
            estimated_costs=estimated_costs,
            downstream_stages=("draft", "review"),
            output_cost_per_token_inr=_cheap_cpt,
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
            with tel.span("plan") as span_id:
                try:
                    response = llm.respond(
                        messages, tier="cheap", response_schema=BlogPlan,
                        params=params,
                    )
                except BillableProviderError as bpe:
                    # Pass ONLY the content-free category + usage-derived stage cost.
                    _stage_cost_bpe = StageCost(
                        stage="plan",
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
                    stage="plan", cost_inr=cost_inr, tier="cheap",
                    tokens_prompt=response.usage.prompt_tokens,
                    tokens_completion=response.usage.completion_tokens,
                )
                try:
                    tel.record_usage(response.usage, node="plan", tier="cheap", span_id=span_id)
                    blog_plan: BlogPlan = response.structured  # type: ignore[assignment]
                    tel.metric("stage.cost_inr", cost_inr, node="plan")
                    tel.log("plan.complete", span_id=span_id,
                            section_count=len(blog_plan.sections), target_words=blog_plan.target_word_count)
                    return {"blog_plan": blog_plan, "cost_usage": [stage_cost]}
                except Exception as exc:
                    raise BillableNodeError(stage_cost, exc) from exc
        except BillableNodeError:
            raise
        except Exception as exc:
            if stage_cost is not None:
                raise BillableNodeError(stage_cost, exc) from exc
            raise

    return plan
