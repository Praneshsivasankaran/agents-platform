from __future__ import annotations

from agent.state import Agent04State


def test_state_has_agent04_fields() -> None:
    ann = Agent04State.__annotations__
    for field in (
        "raw_input",
        "request",
        "analysis",
        "keyword_plan",
        "metadata",
        "heading_plan",
        "readability",
        "faq_bundle",
        "optimized",
        "risk_report",
        "seo_score",
        "cost_usage",
        "final_output",
    ):
        assert field in ann
