"""finalize node — assemble the terminal Package; the error/ceiling funnel ends here (generated)."""
from __future__ import annotations

from typing import Any

from core.cost import total_cost_inr
from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider

from ..schemas import CostUsage, ReportWriterPackage
from ..state import ReportWriterState


def make_finalize_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = llm
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 50.0))

    def finalize(state: ReportWriterState) -> dict[str, Any]:
        # Cost ledger is computed first and always preserved (truthful total_inr).
        stage_costs = list(state.get("cost_usage", []))
        total = round(total_cost_inr(stage_costs), 6)
        cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total)

        error_state = state.get("error_state")
        cost_gate_ok = state.get("cost_gate_ok", True)
        # Ceiling first (pre- or post-call breach), then error, then pass.
        if not cost_gate_ok or total > ceiling_inr:
            status, notes, result = (
                "stopped_cost_ceiling",
                "Cost ceiling reached; run stopped to protect budget.",
                "",
            )
        elif error_state:
            status = "error"
            notes = f"Error in {error_state.get('node', 'unknown')} ({error_state.get('kind', 'Error')})"
            result = ""
        else:
            status, notes, result = "pass", "ok", state.get("result", "")

        pkg = ReportWriterPackage(status=status, cost=cost, result=result, notes=notes)
        with tel.span("finalize") as span_id:
            tel.metric("total.cost_inr", total, node="finalize")
            tel.log("finalize.complete", span_id=span_id, status=status)
        return {"final_output": pkg, "status": status}

    return finalize
