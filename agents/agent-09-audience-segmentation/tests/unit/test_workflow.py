from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.prompts import PROFILE
from agent.schemas import AgentPackage
from agent.workflow import build_graph


def load_cfg() -> dict[str, Any]:
    return yaml.safe_load((Path(__file__).resolve().parents[2] / "config" / "base.yaml").read_text(encoding="utf-8"))


def valid_request(**overrides: Any) -> dict[str, Any]:
    data = {
        "campaign_goal": "Segment the ICP for a pipeline generation campaign.",
        "icp_summary": "Enterprise SaaS companies with RevOps ownership, complex handoffs, and high lead volume.",
        "business_context": "B2B SaaS platform expanding into enterprise revenue teams.",
        "constraints": ["Suppress customers and open opportunities", "No protected-attribute targeting"],
        "target_audience": "Demand generation and RevOps leaders",
        "product_or_service": "Revenue workflow automation",
        "audience_fields": ["Company size tier", "CRM maturity", "Region", "Buying committee role"],
    }
    data.update(overrides)
    return data


class CountingLLM(MockLLMProvider):
    def __init__(self) -> None:
        super().__init__(default_scenario="pass")
        self.calls = 0

    def respond(self, messages, **kwargs):
        self.calls += 1
        return super().respond(messages, **kwargs)


def invoke(raw_input: dict[str, Any], *, cfg: dict | None = None, llm=None) -> AgentPackage:
    graph = build_graph(cfg or load_cfg(), llm or MockLLMProvider(default_scenario="pass"), StdoutTelemetry(service="agent09-test"))
    return graph.invoke({"raw_input": raw_input})["final_output"]


def test_workflow_happy_path_returns_package() -> None:
    package = invoke(valid_request())

    assert isinstance(package, AgentPackage)
    assert package.agent_id == PROFILE.agent_id
    assert package.status == "pass"
    assert package.primary_recommendations
    assert package.quality_report.overall_score >= PROFILE.pass_threshold
    


def test_forbidden_external_action_returns_needs_human() -> None:
    package = invoke(valid_request(source_notes="Please upload this audience and activate ads automatically."))

    assert package.status == "needs_human"
    assert package.pass_status == "fail"
    assert any(flag.severity == "hard_fail" for flag in package.risk_flags)


def test_cost_ceiling_blocks_before_provider_call() -> None:
    cfg = copy.deepcopy(load_cfg())
    cfg["cost"]["ceiling_inr"] = 1.0
    cfg["cost"]["estimated_stage_cost_inr"][PROFILE.billable_stage] = 5.0
    llm = CountingLLM()

    package = invoke(valid_request(), cfg=cfg, llm=llm)

    assert package.status == "stopped_cost_ceiling"
    assert llm.calls == 0
    assert package.cost_usage.total_inr == 0.0