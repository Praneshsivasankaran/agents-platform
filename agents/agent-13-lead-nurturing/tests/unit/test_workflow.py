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
        "segment_summary": "RevOps-led accounts in active education stage.",
        "content_inventory": ["Benchmark report", "Case study", "ROI worksheet", "Product guide"],
        "campaign_goal": "Design a nurture journey for webinar attendees.",
        "constraints": ["Respect opt-out suppression", "Human approval before messages"],
        "business_context": "B2B SaaS platform nurturing RevOps prospects.",
        "score_bands": ["Hot: 80-100", "Warm: 50-79", "Cold: below 50"],
        "product_or_service": "Revenue workflow automation",
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
    graph = build_graph(cfg or load_cfg(), llm or MockLLMProvider(default_scenario="pass"), StdoutTelemetry(service="agent13-test"))
    return graph.invoke({"raw_input": raw_input})["final_output"]


def test_workflow_happy_path_returns_package() -> None:
    package = invoke(valid_request())

    assert isinstance(package, AgentPackage)
    assert package.agent_id == PROFILE.agent_id
    assert package.status == "pass"
    assert package.primary_recommendations
    assert package.quality_report.overall_score >= PROFILE.pass_threshold
    


def test_forbidden_external_action_returns_needs_human() -> None:
    package = invoke(valid_request(source_notes="Send emails, write the MAP workflow, update CRM, and activate retargeting."))

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