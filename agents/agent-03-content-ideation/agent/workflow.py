"""LangGraph workflow for Agent 03 - Content Ideation Agent."""
from __future__ import annotations

import math
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from core.cost import CostCeilingExceeded, total_cost_inr
from core.interfaces import LLMProvider, Telemetry

from .contracts import BillableNodeError, ContentIdeationPackage, CostUsage
from .nodes import (
    make_analyze_audience_node,
    make_assemble_package_node,
    make_create_blog_brief_node,
    make_create_repurposing_brief_node,
    make_generate_content_ideas_node,
    make_generate_content_themes_node,
    make_generate_hooks_node,
    make_intake_node,
    make_quality_scoring_node,
    make_validate_campaign_brief_node,
)
from .state import Agent03State


def _node_with_error_guard(
    node_name: str,
    node_fn: Callable,
    *,
    ceiling_inr: float = math.inf,
    tel: Telemetry | None = None,
) -> Callable:
    """Wrap a graph node so every failure reaches assemble with a structured status."""

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


def _safe_assemble_wrapper(assemble_fn: Callable) -> Callable:
    def safe_assemble(state: dict) -> dict[str, Any]:
        try:
            return assemble_fn(state)
        except Exception as exc:  # noqa: BLE001
            try:
                stage_costs = state.get("cost_usage", [])
                total = round(total_cost_inr(stage_costs), 6)
                cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total)
            except Exception:
                cost = CostUsage(stage_costs=(), total_inr=0.0)
            pkg = ContentIdeationPackage(
                status="error",
                cost=cost,
                notes=f"Fatal error in assemble_content_ideation_package ({type(exc).__name__})",
            )
            return {"final_output": pkg, "status": "error"}

    safe_assemble.__name__ = "safe_assemble_content_ideation_package"
    return safe_assemble


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile Agent 03's cloud-neutral LangGraph workflow."""

    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 20.0))
    nodes = {
        "intake": _node_with_error_guard("intake", make_intake_node(cfg, llm, tel), tel=tel),
        "validate_campaign_brief": _node_with_error_guard(
            "validate_campaign_brief",
            make_validate_campaign_brief_node(cfg, llm, tel),
            tel=tel,
        ),
        "analyze_audience": _node_with_error_guard(
            "analyze_audience", make_analyze_audience_node(cfg, llm, tel), tel=tel
        ),
        "generate_content_themes": _node_with_error_guard(
            "generate_content_themes",
            make_generate_content_themes_node(cfg, llm, tel),
            tel=tel,
        ),
        "generate_content_ideas": _node_with_error_guard(
            "generate_content_ideas",
            make_generate_content_ideas_node(cfg, llm, tel),
            ceiling_inr=ceiling_inr,
            tel=tel,
        ),
        "generate_hooks": _node_with_error_guard(
            "generate_hooks", make_generate_hooks_node(cfg, llm, tel), tel=tel
        ),
        "create_blog_brief_for_agent_01": _node_with_error_guard(
            "create_blog_brief_for_agent_01",
            make_create_blog_brief_node(cfg, llm, tel),
            tel=tel,
        ),
        "create_repurposing_brief_for_agent_02": _node_with_error_guard(
            "create_repurposing_brief_for_agent_02",
            make_create_repurposing_brief_node(cfg, llm, tel),
            tel=tel,
        ),
        "quality_scoring": _node_with_error_guard(
            "quality_scoring",
            make_quality_scoring_node(cfg, llm, tel),
            ceiling_inr=ceiling_inr,
            tel=tel,
        ),
        "assemble_content_ideation_package": _safe_assemble_wrapper(
            make_assemble_package_node(cfg, llm, tel)
        ),
    }

    def _emit_route(node: str, decision: str, target: str) -> None:
        try:
            tel.log("route.decision", node=node, decision=decision, target=target)
        except Exception:
            pass

    def route_basic(node: str, target: str):
        def route(state: Agent03State) -> str:
            if state.get("error_state") is not None:
                _emit_route(node, "error", "assemble_content_ideation_package")
                return "assemble_content_ideation_package"
            if not state.get("cost_gate_ok", True):
                _emit_route(node, "cost_ceiling", "assemble_content_ideation_package")
                return "assemble_content_ideation_package"
            _emit_route(node, "ok", target)
            return target

        return route

    def route_after_intake(state: Agent03State) -> str:
        if state.get("error_state") is not None:
            _emit_route("intake", "error", "assemble_content_ideation_package")
            return "assemble_content_ideation_package"
        if state.get("status") == "needs_more_input":
            _emit_route("intake", "needs_more_input", "assemble_content_ideation_package")
            return "assemble_content_ideation_package"
        _emit_route("intake", "ok", "validate_campaign_brief")
        return "validate_campaign_brief"

    def route_after_validate(state: Agent03State) -> str:
        if state.get("error_state") is not None:
            _emit_route("validate_campaign_brief", "error", "assemble_content_ideation_package")
            return "assemble_content_ideation_package"
        if state.get("status") == "needs_more_input":
            _emit_route(
                "validate_campaign_brief",
                "needs_more_input",
                "assemble_content_ideation_package",
            )
            return "assemble_content_ideation_package"
        _emit_route("validate_campaign_brief", "ok", "analyze_audience")
        return "analyze_audience"

    graph = StateGraph(Agent03State)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.set_entry_point("intake")
    graph.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "validate_campaign_brief": "validate_campaign_brief",
            "assemble_content_ideation_package": "assemble_content_ideation_package",
        },
    )
    graph.add_conditional_edges(
        "validate_campaign_brief",
        route_after_validate,
        {
            "analyze_audience": "analyze_audience",
            "assemble_content_ideation_package": "assemble_content_ideation_package",
        },
    )
    graph.add_conditional_edges(
        "analyze_audience",
        route_basic("analyze_audience", "generate_content_themes"),
        {
            "generate_content_themes": "generate_content_themes",
            "assemble_content_ideation_package": "assemble_content_ideation_package",
        },
    )
    graph.add_conditional_edges(
        "generate_content_themes",
        route_basic("generate_content_themes", "generate_content_ideas"),
        {
            "generate_content_ideas": "generate_content_ideas",
            "assemble_content_ideation_package": "assemble_content_ideation_package",
        },
    )
    graph.add_conditional_edges(
        "generate_content_ideas",
        route_basic("generate_content_ideas", "generate_hooks"),
        {
            "generate_hooks": "generate_hooks",
            "assemble_content_ideation_package": "assemble_content_ideation_package",
        },
    )
    graph.add_conditional_edges(
        "generate_hooks",
        route_basic("generate_hooks", "create_blog_brief_for_agent_01"),
        {
            "create_blog_brief_for_agent_01": "create_blog_brief_for_agent_01",
            "assemble_content_ideation_package": "assemble_content_ideation_package",
        },
    )
    graph.add_conditional_edges(
        "create_blog_brief_for_agent_01",
        route_basic("create_blog_brief_for_agent_01", "create_repurposing_brief_for_agent_02"),
        {
            "create_repurposing_brief_for_agent_02": "create_repurposing_brief_for_agent_02",
            "assemble_content_ideation_package": "assemble_content_ideation_package",
        },
    )
    graph.add_conditional_edges(
        "create_repurposing_brief_for_agent_02",
        route_basic("create_repurposing_brief_for_agent_02", "quality_scoring"),
        {
            "quality_scoring": "quality_scoring",
            "assemble_content_ideation_package": "assemble_content_ideation_package",
        },
    )
    graph.add_conditional_edges(
        "quality_scoring",
        route_basic("quality_scoring", "assemble_content_ideation_package"),
        {"assemble_content_ideation_package": "assemble_content_ideation_package"},
    )
    graph.add_edge("assemble_content_ideation_package", END)

    return graph.compile()

