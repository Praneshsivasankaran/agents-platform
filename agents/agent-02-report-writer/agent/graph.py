"""LangGraph StateGraph wiring for Report Writing Agent (generated skeleton).

Minimal spine::

    intake --(ok)--> process --> finalize --> END
    intake --(error)-----------> finalize   (any node error funnels here)

The error guard preserves incurred cost on BillableNodeError, maps CostCeilingExceeded to a
budget-stop, and does a post-call ceiling check — so the FIXED ₹50 ceiling and honest accounting
are inherited by every generated agent. Add stages between intake and finalize as the agent grows;
keep everything here cloud-neutral (import only ``core``).
"""
from __future__ import annotations

import math
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from core.cost import CostCeilingExceeded, total_cost_inr
from core.interfaces import LLMProvider, Telemetry

from .nodes import make_finalize_node, make_intake_node, make_process_node
from .schemas import BillableNodeError, CostUsage, ReportWriterPackage
from .state import ReportWriterState


def _node_with_error_guard(node_name: str, node_fn: Callable, *, ceiling_inr: float = math.inf, tel=None) -> Callable:
    """Wrap a node so failures funnel to finalize WITHOUT losing incurred cost.

    - normal return: if cumulative cost now exceeds the ceiling, flag cost_gate_ok=False;
    - CostCeilingExceeded (pre-call reject): cost_gate_ok=False, no cost incurred;
    - BillableNodeError (post-billing failure): append the incurred StageCost, then error_state;
    - any other Exception: sanitized error_state (type name only — no raw message/traceback).
    """
    def guarded(state: dict) -> dict[str, Any]:
        try:
            result = node_fn(state)
            new_costs = result.get("cost_usage")
            if new_costs and math.isfinite(ceiling_inr):
                prior = state.get("cost_usage") or []
                if total_cost_inr(list(prior) + list(new_costs)) > ceiling_inr:
                    return {**result, "cost_gate_ok": False}
            return result
        except CostCeilingExceeded:
            return {"cost_gate_ok": False}
        except BillableNodeError as be:
            if tel is not None:
                try:
                    tel.log("node.error", node=node_name, kind=type(be.cause).__name__)
                except Exception:
                    pass
            return {
                "cost_usage": [be.stage_cost],
                "error_state": {
                    "node": node_name,
                    "kind": type(be.cause).__name__,
                    "message": f"{type(be.cause).__name__} in {node_name}",
                },
            }
        except Exception as exc:  # noqa: BLE001 — funnel every failure to finalize
            if tel is not None:
                try:
                    tel.log("node.error", node=node_name, kind=type(exc).__name__)
                except Exception:
                    pass
            return {
                "error_state": {
                    "node": node_name,
                    "kind": type(exc).__name__,
                    "message": f"{type(exc).__name__} in {node_name}",
                }
            }

    guarded.__name__ = f"guarded_{node_name}"
    return guarded


def _safe_finalize_wrapper(finalize_fn: Callable) -> Callable:
    """Last-resort guard: finalize must always return a structured Package — and preserve spend."""

    def safe_finalize(state: dict) -> dict[str, Any]:
        try:
            return finalize_fn(state)
        except Exception as exc:  # noqa: BLE001
            try:
                stage_costs = state.get("cost_usage", [])
                total = round(total_cost_inr(stage_costs), 6)
                cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total)
            except Exception:
                cost = CostUsage(stage_costs=(), total_inr=0.0)
            pkg = ReportWriterPackage(
                status="error",
                cost=cost,
                notes=f"Fatal error in finalize ({type(exc).__name__})",
            )
            return {"final_output": pkg, "status": "error"}

    safe_finalize.__name__ = "safe_finalize"
    return safe_finalize


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile and return the agent's LangGraph graph.

    Invoke with::

        result = graph.invoke({"raw_input": "...", "input_type": "text"})
        package = result["final_output"]
    """
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 50.0))
    intake_node = _node_with_error_guard("intake", make_intake_node(cfg, llm, tel), tel=tel)
    process_node = _node_with_error_guard(
        "process", make_process_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
    )
    finalize_node = _safe_finalize_wrapper(make_finalize_node(cfg, llm, tel))

    def route_after_intake(state: ReportWriterState) -> str:
        if state.get("error_state") is not None:
            return "finalize"
        return "process"

    graph = StateGraph(ReportWriterState)
    graph.add_node("intake", intake_node)
    graph.add_node("process", process_node)
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("intake")
    graph.add_conditional_edges(
        "intake", route_after_intake, {"process": "process", "finalize": "finalize"}
    )
    # process always flows to finalize; finalize derives status from cost_gate_ok / error_state.
    graph.add_edge("process", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()
