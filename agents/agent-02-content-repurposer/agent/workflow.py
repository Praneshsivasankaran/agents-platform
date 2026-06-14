"""LangGraph workflow for Agent 02 - Content Repurposing Agent."""
from __future__ import annotations

import math
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from core.cost import CostCeilingExceeded, total_cost_inr
from core.interfaces import LLMProvider, ObjectStorage, Telemetry

from .nodes import (
    make_check_factual_consistency_node,
    make_extract_audience_value_node,
    make_extract_core_message_node,
    make_finalize_node,
    make_generate_content_angles_node,
    make_generate_platform_drafts_node,
    make_intake_node,
    make_load_platform_rules_node,
    make_parse_source_node,
    make_review_quality_node,
    make_revise_weak_outputs_node,
    make_select_platform_strategy_node,
    make_usefulness_review_node,
    make_validate_platform_fit_node,
    make_validate_source_node,
)
from .schemas import BillableNodeError, CostUsage, RepurposedContentPackage
from .state import Agent02State
from .validators import hard_fail_status


def _node_with_error_guard(
    node_name: str,
    node_fn: Callable,
    *,
    ceiling_inr: float = math.inf,
    tel: Telemetry | None = None,
) -> Callable:
    """Wrap a graph node so every failure reaches finalize with a structured status."""

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
        except Exception as exc:  # noqa: BLE001
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
            pkg = RepurposedContentPackage(
                status="error",
                cost=cost,
                notes=f"Fatal error in finalize ({type(exc).__name__})",
            )
            return {"final_output": pkg, "status": "error"}

    safe_finalize.__name__ = "safe_finalize"
    return safe_finalize


def build_graph(
    cfg: dict,
    llm: LLMProvider,
    tel: Telemetry,
    object_storage: ObjectStorage | None = None,
) -> Any:
    """Compile Agent 02's LangGraph workflow."""

    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 30.0))
    max_cycles = int(cfg.get("graph", {}).get("max_revision_cycles", 2))

    nodes = {
        "intake": _node_with_error_guard("intake", make_intake_node(cfg, llm, tel), tel=tel),
        "validate_source": _node_with_error_guard(
            "validate_source", make_validate_source_node(cfg, llm, tel), tel=tel
        ),
        "parse_source": _node_with_error_guard("parse_source", make_parse_source_node(cfg, llm, tel), tel=tel),
        "extract_core_message": _node_with_error_guard(
            "extract_core_message", make_extract_core_message_node(cfg, llm, tel), tel=tel
        ),
        "extract_audience_value": _node_with_error_guard(
            "extract_audience_value", make_extract_audience_value_node(cfg, llm, tel), tel=tel
        ),
        "generate_content_angles": _node_with_error_guard(
            "generate_content_angles", make_generate_content_angles_node(cfg, llm, tel), tel=tel
        ),
        "select_platform_strategy": _node_with_error_guard(
            "select_platform_strategy", make_select_platform_strategy_node(cfg, llm, tel), tel=tel
        ),
        "load_platform_rules": _node_with_error_guard(
            "load_platform_rules", make_load_platform_rules_node(cfg, llm, tel), tel=tel
        ),
        "generate_platform_drafts": _node_with_error_guard(
            "generate_platform_drafts",
            make_generate_platform_drafts_node(cfg, llm, tel),
            ceiling_inr=ceiling_inr,
            tel=tel,
        ),
        "validate_platform_fit": _node_with_error_guard(
            "validate_platform_fit", make_validate_platform_fit_node(cfg, llm, tel), tel=tel
        ),
        "check_factual_consistency": _node_with_error_guard(
            "check_factual_consistency",
            make_check_factual_consistency_node(cfg, llm, tel),
            ceiling_inr=ceiling_inr,
            tel=tel,
        ),
        "usefulness_review": _node_with_error_guard(
            "usefulness_review", make_usefulness_review_node(cfg, llm, tel), tel=tel
        ),
        "review_quality": _node_with_error_guard(
            "review_quality",
            make_review_quality_node(cfg, llm, tel),
            ceiling_inr=ceiling_inr,
            tel=tel,
        ),
        "revise_weak_outputs": _node_with_error_guard(
            "revise_weak_outputs",
            make_revise_weak_outputs_node(cfg, llm, tel),
            ceiling_inr=ceiling_inr,
            tel=tel,
        ),
        "finalize": _safe_finalize_wrapper(make_finalize_node(cfg, llm, tel, object_storage)),
    }

    def _emit_route(node: str, decision: str, target: str) -> None:
        try:
            tel.log("route.decision", node=node, decision=decision, target=target)
        except Exception:
            pass

    def route_basic(node: str, target: str):
        def route(state: Agent02State) -> str:
            if state.get("error_state") is not None:
                _emit_route(node, "error", "finalize")
                return "finalize"
            if not state.get("cost_gate_ok", True):
                _emit_route(node, "cost_ceiling", "finalize")
                return "finalize"
            _emit_route(node, "ok", target)
            return target

        return route

    def route_after_validate_source(state: Agent02State) -> str:
        if state.get("error_state") is not None:
            _emit_route("validate_source", "error", "finalize")
            return "finalize"
        if state.get("status") == "needs_more_input":
            _emit_route("validate_source", "needs_more_input", "finalize")
            return "finalize"
        _emit_route("validate_source", "ok", "parse_source")
        return "parse_source"

    def route_after_review_quality(state: Agent02State) -> str:
        if state.get("error_state") is not None:
            _emit_route("review_quality", "error", "finalize")
            return "finalize"
        if not state.get("cost_gate_ok", True):
            _emit_route("review_quality", "cost_ceiling", "finalize")
            return "finalize"
        decision = hard_fail_status(state.get("quality_report"))
        if decision == "pass":
            _emit_route("review_quality", "pass", "finalize")
            return "finalize"
        if decision == "needs_human":
            _emit_route("review_quality", "terminal_hard_fail", "finalize")
            return "finalize"
        if decision == "revise" and int(state.get("revision_count", 0)) < max_cycles:
            _emit_route("review_quality", "revise", "revise_weak_outputs")
            return "revise_weak_outputs"
        _emit_route("review_quality", "needs_human", "finalize")
        return "finalize"

    graph = StateGraph(Agent02State)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.set_entry_point("intake")
    graph.add_conditional_edges("intake", route_basic("intake", "validate_source"), {"validate_source": "validate_source", "finalize": "finalize"})
    graph.add_conditional_edges(
        "validate_source",
        route_after_validate_source,
        {"parse_source": "parse_source", "finalize": "finalize"},
    )
    graph.add_conditional_edges("parse_source", route_basic("parse_source", "extract_core_message"), {"extract_core_message": "extract_core_message", "finalize": "finalize"})
    graph.add_conditional_edges("extract_core_message", route_basic("extract_core_message", "extract_audience_value"), {"extract_audience_value": "extract_audience_value", "finalize": "finalize"})
    graph.add_conditional_edges("extract_audience_value", route_basic("extract_audience_value", "generate_content_angles"), {"generate_content_angles": "generate_content_angles", "finalize": "finalize"})
    graph.add_conditional_edges("generate_content_angles", route_basic("generate_content_angles", "select_platform_strategy"), {"select_platform_strategy": "select_platform_strategy", "finalize": "finalize"})
    graph.add_conditional_edges("select_platform_strategy", route_basic("select_platform_strategy", "load_platform_rules"), {"load_platform_rules": "load_platform_rules", "finalize": "finalize"})
    graph.add_conditional_edges("load_platform_rules", route_basic("load_platform_rules", "generate_platform_drafts"), {"generate_platform_drafts": "generate_platform_drafts", "finalize": "finalize"})
    graph.add_conditional_edges("generate_platform_drafts", route_basic("generate_platform_drafts", "validate_platform_fit"), {"validate_platform_fit": "validate_platform_fit", "finalize": "finalize"})
    graph.add_conditional_edges("validate_platform_fit", route_basic("validate_platform_fit", "check_factual_consistency"), {"check_factual_consistency": "check_factual_consistency", "finalize": "finalize"})
    graph.add_conditional_edges("check_factual_consistency", route_basic("check_factual_consistency", "usefulness_review"), {"usefulness_review": "usefulness_review", "finalize": "finalize"})
    graph.add_conditional_edges("usefulness_review", route_basic("usefulness_review", "review_quality"), {"review_quality": "review_quality", "finalize": "finalize"})
    graph.add_conditional_edges(
        "review_quality",
        route_after_review_quality,
        {"revise_weak_outputs": "revise_weak_outputs", "finalize": "finalize"},
    )
    graph.add_conditional_edges("revise_weak_outputs", route_basic("revise_weak_outputs", "validate_platform_fit"), {"validate_platform_fit": "validate_platform_fit", "finalize": "finalize"})
    graph.add_edge("finalize", END)

    return graph.compile()
