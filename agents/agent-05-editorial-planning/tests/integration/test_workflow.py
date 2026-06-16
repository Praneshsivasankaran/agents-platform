from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from core.interfaces import BillableProviderError
from core.interfaces.usage import Usage
from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.schemas import EditorialPlanningPackage
from agent.workflow import build_graph


def load_cfg() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "config" / "base.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def valid_request(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "brand_name": "Northstar Wellness",
        "business_goal": "Drive qualified leads for a corporate wellness program",
        "target_audience": "HR leaders at mid-market companies",
        "campaign_theme": "Burnout prevention for distributed teams",
        "platforms": ["blog", "linkedin", "email"],
        "date_range": {"start": "2026-07-01", "end": "2026-07-31"},
        "posting_frequency": {"cadence": "weekly", "count_per_week": 3},
        "brand_voice": "warm, expert, practical",
        "content_pillars": ["education", "proof", "conversion"],
        "existing_ideas": ["Checklist for spotting team burnout"],
        "constraints": ["Avoid medical diagnosis claims"],
    }
    data.update(overrides)
    return data


def _invoke(raw_input: dict[str, Any], *, cfg: dict | None = None, llm=None) -> EditorialPlanningPackage:
    graph = build_graph(
        cfg or load_cfg(),
        llm or MockLLMProvider(default_scenario="pass"),
        StdoutTelemetry(service="agent05-test"),
    )
    return graph.invoke({"raw_input": raw_input})["final_output"]


class CountingLLM(MockLLMProvider):
    def __init__(self) -> None:
        super().__init__(default_scenario="pass")
        self.calls = 0

    def respond(self, messages, **kwargs):
        self.calls += 1
        return super().respond(messages, **kwargs)


class BillingFailureLLM(MockLLMProvider):
    def respond(self, messages, **kwargs):
        raise BillableProviderError(
            Usage(prompt_tokens=10, completion_tokens=5, cost_native=0.01, currency="USD", synthetic=False),
            "provider_call_failed",
        )


def test_workflow_happy_path_returns_editorial_planning_package() -> None:
    package = _invoke(valid_request())

    assert isinstance(package, EditorialPlanningPackage)
    assert package.status == "pass"
    assert package.quality_score is not None
    assert package.quality_score.total_score >= 80
    assert package.editorial_calendar
    assert package.weekly_plan
    assert package.platform_plan
    assert package.content_briefs
    assert package.repurposing_map


def test_invalid_input_routes_to_needs_more_input() -> None:
    package = _invoke({"brand_name": "", "platforms": []})

    assert package.status == "needs_more_input"
    assert "Missing or invalid" in package.notes
    assert package.cost.total_inr == 0.0


def test_cost_ceiling_blocks_before_provider_call() -> None:
    # When every billable stage is unaffordable, the pre-call gate blocks each one before any
    # provider call. The run degrades gracefully to deterministic output (partial but useful)
    # rather than billing and then hard-stopping.
    cfg = copy.deepcopy(load_cfg())
    for stage in (
        "map_platform_strategy",
        "generate_topic_plan",
        "generate_content_briefs",
        "build_repurposing_map",
    ):
        cfg["cost"]["estimated_stage_cost_inr"][stage] = 100.0
    llm = CountingLLM()

    package = _invoke(valid_request(), cfg=cfg, llm=llm)

    assert package.status == "needs_review_budget_limited"
    assert llm.calls == 0  # blocked before any provider call → no spend
    assert package.cost.total_inr == 0.0
    # Partial but useful, and still schema-valid.
    assert package.editorial_calendar
    assert package.content_briefs


def test_billable_provider_failures_preserve_cost_and_fallback() -> None:
    package = _invoke(valid_request(), llm=BillingFailureLLM(default_scenario="pass"))

    assert package.cost.total_inr > 0.0
    assert package.editorial_calendar
    assert package.status in {"pass", "needs_human", "stopped_cost_ceiling"}

