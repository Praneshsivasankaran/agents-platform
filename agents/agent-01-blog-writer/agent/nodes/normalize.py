"""normalize node — LLM-assisted cleaning of raw input (DESIGN §1.2, §6).

Eighth repair pass:
- is_mock now derived via resolve_is_mock(cfg) — validates provider/mock consistency.
  A non-mock cloud provider with cost.is_mock=True raises ValueError at build time.
- auth result captured and max_tokens passed to LLM call (cheap tier; None for mock).

Seventh repair pass:
- Replaced ad-hoc ceiling check with authorize_call() from packages/core.
  authorize_call reserves budget for all mandatory downstream stages
  (extract_ideas, plan, draft, review) before making the LLM call.
  CostCeilingExceeded propagates to _node_with_error_guard → cost_gate_ok=False
  → status='stopped_cost_ceiling' (not 'error').
- is_mock read from cost.is_mock in config; used by authorize_call to bypass
  the fail-closed zero-pricing check for offline/mock runs.

Sixth repair pass (intact):
- Pre-call ceiling check changed from strictly-greater-than (>) to
  greater-than-or-equal (>=) — superseded by authorize_call in this repair.
"""
from __future__ import annotations
from typing import Any
from core.cost import CostCeilingExceeded, authorize_call, estimate_prompt_tokens, resolve_is_mock, usage_cost_inr
from core.interfaces import Telemetry
from core.interfaces.errors import BillableProviderError
from core.interfaces.llm import LLMProvider
from ..prompts import build_system, normalize_prompt
from ..schemas import BillableNodeError, StageCost
from ..state import BlogState


def make_normalize_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    cost_cfg = cfg.get("cost", {})
    fx_rates: dict[str, float] = cost_cfg.get("fx_rates", {"USD": 83.0})
    ceiling_inr: float = float(cost_cfg.get("ceiling_inr", 50.0))
    estimated_costs: dict[str, float] = {
        k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()
    }
    # Eighth repair: derive is_mock from provider config key, not just cost.is_mock.
    # Raises ValueError at build time if provider is non-mock but cost.is_mock=True.
    is_mock: bool = resolve_is_mock(cfg)
    _cheap_cpt: float = float(cost_cfg.get("output_cost_per_token_inr", {}).get("cheap", 0.0))
    # Eleventh repair: input-token cost, prompt-size limit, and flat request cost.
    # Nodes build messages first, count actual prompt tokens, enforce the limit, then
    # pass the actual count to authorize_call instead of the config ceiling.
    _input_cpt: float = float(cost_cfg.get("input_cost_per_token_inr", {}).get("cheap", 0.0))
    _max_prompt: int = int(cost_cfg.get("max_prompt_tokens", {}).get("cheap", 2048))
    _fixed_cost: float = float(cost_cfg.get("fixed_cost_inr", {}).get("cheap", 0.0))

    def normalize(state: BlogState) -> dict[str, Any]:
        # Increment 6: if a transcript is present (voice/video path), normalize it.
        # Otherwise fall back to raw_input (text path).  The transcript is treated
        # as untrusted data by normalize_prompt (DESIGN §6.1).
        transcript: str | None = state.get("transcript")  # type: ignore[assignment]
        raw_input: str = state.get("raw_input", "")  # type: ignore[assignment]
        content_to_normalize: str = transcript if transcript else raw_input

        # ── Build messages first (eleventh repair) ────────────────────────────
        # Prompt is constructed before authorization so the actual token count can
        # be measured and enforced against max_prompt_tokens.
        system = build_system(cfg)
        user_msg = normalize_prompt(content_to_normalize)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_msg}]

        # Enforce prompt-size limit.  If the actual prompt exceeds max_prompt_tokens,
        # raise CostCeilingExceeded before the provider is called — input charges for
        # an oversized prompt would exceed the reserved input cost.
        prompt_tokens_est: int = estimate_prompt_tokens(messages)
        if prompt_tokens_est > _max_prompt:
            raise CostCeilingExceeded(
                f"normalize: conservative prompt estimate {prompt_tokens_est} bytes "
                f"exceeds max_prompt_tokens={_max_prompt}; "
                f"provider call blocked to prevent input charges above reserved budget"
            )

        # ── Centralized pre-call budget authorization ─────────────────────────
        # Raises CostCeilingExceeded if the full pipeline cannot fit in remaining
        # headroom — propagates to _node_with_error_guard → cost_gate_ok=False.
        auth = authorize_call(
            stage_name="normalize",
            stage_costs=state.get("cost_usage", []),  # type: ignore[arg-type]
            ceiling_inr=ceiling_inr,
            estimated_costs=estimated_costs,
            downstream_stages=("extract_ideas", "plan", "draft", "review"),
            output_cost_per_token_inr=_cheap_cpt,
            input_cost_per_token_inr=_input_cpt,
            prompt_tokens_estimate=prompt_tokens_est,
            fixed_cost_inr=_fixed_cost,
            is_mock=is_mock,
        )
        params: dict[str, Any] = {"max_tokens": auth.max_tokens} if auth.max_tokens is not None else {}
        # Always pass the authorized prompt estimate so _conservative_usage uses it exactly.
        params["_authorized_prompt_tokens"] = prompt_tokens_est

        # stage_cost is initialised to None before the span so the outer except can
        # detect whether the LLM call completed (and a cost was incurred) before
        # re-raising as BillableNodeError.  This closes the span-exit gap: if
        # tel.span().__exit__ raises after the LLM call, the incurred cost is still
        # preserved rather than silently dropped.
        stage_cost: StageCost | None = None
        try:
            with tel.span("normalize") as span_id:
                try:
                    response = llm.respond(messages, tier="cheap", params=params)
                except BillableProviderError as bpe:
                    # Real call was made and cost was incurred; preserve it before propagating.
                    # Pass ONLY the content-free category and usage-derived stage cost — never
                    # an exception object, never a raw message. bpe itself is content-free
                    # (only category + usage, __cause__/__context__ are None from the provider
                    # fix), so even though `from None` leaves __context__=bpe, nothing leaks.
                    _stage_cost_bpe = StageCost(
                        stage="normalize",
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
                    stage="normalize", cost_inr=cost_inr, tier="cheap",
                    tokens_prompt=response.usage.prompt_tokens,
                    tokens_completion=response.usage.completion_tokens,
                )
                try:
                    tel.record_usage(response.usage, node="normalize", tier="cheap", span_id=span_id)
                    normalized = response.text or content_to_normalize
                    tel.metric("stage.cost_inr", cost_inr, node="normalize")
                    tel.log("normalize.complete", span_id=span_id, output_chars=len(normalized))
                    return {"normalized_content": normalized, "cost_usage": [stage_cost]}
                except Exception as exc:
                    raise BillableNodeError(stage_cost, exc) from exc
        except BillableNodeError:
            raise  # already carries stage_cost; do not double-wrap
        except Exception as exc:
            if stage_cost is not None:
                # LLM call completed (cost incurred) but span.__exit__ or something
                # outside the inner try raised — preserve the cost.
                raise BillableNodeError(stage_cost, exc) from exc
            raise  # pre-LLM failure; no cost to preserve

    return normalize
