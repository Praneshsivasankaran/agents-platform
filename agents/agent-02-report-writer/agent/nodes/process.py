"""process node — single budgeted model call (generated skeleton; specialize into real stages).

This is where a new agent grows its pipeline. The skeleton makes ONE cheap-tier call but already
enforces the platform's load-bearing guarantees so every agent inherits them:
  - PRE-CALL ceiling gate: estimate_prompt_tokens + max_prompt_tokens + authorize_call. If the
    budget is insufficient, CostCeilingExceeded is raised BEFORE the provider is called.
  - COST PRESERVATION: a BillableProviderError (failure after the provider may have billed) is
    converted to a BillableNodeError carrying the usage-derived StageCost, so the ledger stays
    truthful. Post-response failures are likewise wrapped.
Replace/extend with your agent's stages; keep this gating in every billable node.
"""
from __future__ import annotations

from typing import Any

from core.cost import (
    CostCeilingExceeded,
    authorize_call,
    estimate_prompt_tokens,
    resolve_is_mock,
    usage_cost_inr,
)
from core.interfaces import BillableProviderError, Telemetry
from core.interfaces.llm import LLMProvider

from ..prompts import build_system, process_prompt
from ..schemas import BillableNodeError, StageCost
from ..state import ReportWriterState


def make_process_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    cost_cfg = cfg.get("cost", {})
    fx_rates: dict[str, float] = cost_cfg.get("fx_rates", {"USD": 83.0})
    ceiling_inr = float(cost_cfg.get("ceiling_inr", 50.0))
    estimated_costs = {k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()}
    is_mock = resolve_is_mock(cfg)
    _out_cpt = float(cost_cfg.get("output_cost_per_token_inr", {}).get("cheap", 0.0))
    _in_cpt = float(cost_cfg.get("input_cost_per_token_inr", {}).get("cheap", 0.0))
    _fixed = float(cost_cfg.get("fixed_cost_inr", {}).get("cheap", 0.0))
    _max_prompt = int(cost_cfg.get("max_prompt_tokens", {}).get("cheap", 16384))

    def process(state: ReportWriterState) -> dict[str, Any]:
        content = state.get("raw_input", "")
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": process_prompt(content)},
        ]
        # ── Pre-call budget authorization (raises CostCeilingExceeded → stopped_cost_ceiling) ──
        prompt_tokens_est = estimate_prompt_tokens(messages)
        if prompt_tokens_est > _max_prompt:
            raise CostCeilingExceeded(
                f"process: prompt estimate {prompt_tokens_est} exceeds max_prompt_tokens={_max_prompt}"
            )
        auth = authorize_call(
            stage_name="process",
            stage_costs=state.get("cost_usage", []),
            ceiling_inr=ceiling_inr,
            estimated_costs=estimated_costs,
            downstream_stages=(),
            output_cost_per_token_inr=_out_cpt,
            input_cost_per_token_inr=_in_cpt,
            prompt_tokens_estimate=prompt_tokens_est,
            fixed_cost_inr=_fixed,
            is_mock=is_mock,
        )
        params: dict[str, Any] = {"max_tokens": auth.max_tokens} if auth.max_tokens is not None else {}
        params["_authorized_prompt_tokens"] = prompt_tokens_est

        stage_cost: StageCost | None = None
        try:
            with tel.span("process") as span_id:
                try:
                    resp = llm.respond(messages, tier="cheap", params=params)
                except BillableProviderError as bpe:
                    # The provider may have billed before failing; preserve the incurred cost.
                    _sc = StageCost(
                        stage="process",
                        cost_inr=usage_cost_inr(bpe.usage, fx_rates=fx_rates),
                        tier="cheap",
                        tokens_prompt=bpe.usage.prompt_tokens,
                        tokens_completion=bpe.usage.completion_tokens,
                    )
                    stage_cost = _sc
                    raise BillableNodeError(
                        _sc, RuntimeError(f"billable-provider-failure:{bpe.category}")
                    ) from None
                cost_inr = usage_cost_inr(resp.usage, fx_rates=fx_rates)
                stage_cost = StageCost(
                    stage="process",
                    cost_inr=cost_inr,
                    tier="cheap",
                    tokens_prompt=resp.usage.prompt_tokens,
                    tokens_completion=resp.usage.completion_tokens,
                )
                try:
                    text = resp.text or content
                    tel.record_usage(resp.usage, node="process", tier="cheap", span_id=span_id)
                    tel.metric("stage.cost_inr", cost_inr, node="process")
                    tel.log("process.complete", span_id=span_id)
                    return {"result": text, "cost_usage": [stage_cost]}
                except Exception as exc:
                    # Post-response failure after a billed call; preserve the cost in the ledger.
                    raise BillableNodeError(stage_cost, exc) from exc
        except BillableNodeError:
            raise
        except Exception as exc:
            # Includes telemetry span.__exit__ failures after a successful, billable call.
            if stage_cost is not None:
                raise BillableNodeError(stage_cost, exc) from exc
            raise

    return process
