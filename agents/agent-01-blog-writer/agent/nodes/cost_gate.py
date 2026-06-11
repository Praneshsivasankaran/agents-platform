"""cost_gate node — pre-draft budget check (DESIGN §1.3, §8).

Repair (Increment 3 — Issue #5):
- Checks COMBINED draft + review cost before every cycle (initial AND revision), not just draft.
- Uses estimate_for_stage which fails closed on missing stage names (no 0.0 default).
- Uses the same "draft" and "review" config keys for both initial drafts and revisions
  (costs are identical; a separate revise_draft / revise_review config key would only add churn).
"""
from __future__ import annotations
from typing import Any
from core.cost import estimate_for_stage, total_cost_inr, within_ceiling
from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider
from ..schemas import StageCost
from ..state import BlogState


def make_cost_gate_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    cost_cfg: dict = cfg.get("cost", {})
    ceiling_inr: float = float(cost_cfg.get("ceiling_inr", 50.0))
    estimated_costs: dict[str, float] = {
        k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()
    }

    def cost_gate(state: BlogState) -> dict[str, Any]:
        stage_costs: list[StageCost] = state.get("cost_usage", [])  # type: ignore[assignment]
        current_total = total_cost_inr(stage_costs)

        # Check COMBINED draft + review estimate before every cycle (Issue #5 repair).
        # estimate_for_stage raises ValueError if a key is absent (fail-closed).
        draft_est = estimate_for_stage("draft", estimated_costs)
        review_est = estimate_for_stage("review", estimated_costs)
        combined_est = draft_est + review_est

        ok = within_ceiling(current_total, combined_est, ceiling_inr=ceiling_inr)

        with tel.span("cost_gate") as span_id:
            tel.metric("total.cost_inr", current_total, node="cost_gate")
            tel.log(
                "cost_gate.checked", span_id=span_id,
                current_total_inr=current_total, ceiling_inr=ceiling_inr,
                estimated_draft_inr=draft_est, estimated_review_inr=review_est,
                combined_est_inr=combined_est, gate_passed=ok,
            )

        return {"cost_gate_ok": ok}

    return cost_gate
