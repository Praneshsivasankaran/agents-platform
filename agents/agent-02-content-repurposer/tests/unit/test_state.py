from __future__ import annotations

from typing import get_args, get_origin, get_type_hints

from agent.state import Agent02State


def test_state_has_agent02_workflow_fields() -> None:
    fields = Agent02State.__annotations__
    expected = {
        "raw_input",
        "request",
        "parsed_source",
        "core_message",
        "audience_value",
        "content_angles",
        "platform_strategy",
        "platform_rules",
        "platform_drafts",
        "platform_validation_report",
        "factual_consistency_report",
        "usefulness_report",
        "quality_report",
        "cost_usage",
        "hard_fails",
        "final_output",
    }
    assert expected.issubset(fields)


def test_cost_and_hard_fail_accumulators_use_langgraph_add_reducer() -> None:
    hints = get_type_hints(Agent02State, include_extras=True)
    cost_ann = hints["cost_usage"]
    fail_ann = hints["hard_fails"]

    assert getattr(get_origin(cost_ann), "__name__", "") == "Annotated"
    assert getattr(get_origin(fail_ann), "__name__", "") == "Annotated"
    assert len(get_args(cost_ann)) == 2
    assert len(get_args(fail_ann)) == 2
