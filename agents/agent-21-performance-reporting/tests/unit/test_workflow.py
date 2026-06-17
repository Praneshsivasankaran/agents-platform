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
        "campaign_goal": "Report paid search launch performance",
        "reporting_period": "May 2026",
        "metric_summary": "Impressions 10000, clicks 500, conversions 40, spend Rs 60000.",
        "metrics": [
            {"label": "Impressions", "value": "10000", "source": "User report"},
            {"label": "Clicks", "value": "500", "source": "User report"},
            {"label": "Conversions", "value": "40", "source": "User report"},
        ],
        "channel_summaries": "Paid search performed steadily; LinkedIn volume was lower than expected.",
        "source_notes": "User supplied campaign report summary.",
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
    graph = build_graph(cfg or load_cfg(), llm or MockLLMProvider(default_scenario="pass"), StdoutTelemetry(service="agent21-test"))
    return graph.invoke({"raw_input": raw_input})["final_output"]


def test_workflow_happy_path_returns_package() -> None:
    package = invoke(valid_request())
    assert isinstance(package, AgentPackage)
    assert package.agent_id == PROFILE.agent_id
    assert package.status == "pass"
    assert package.metric_insights
    # Deterministic KPI derivation from supplied counts (no live lookup, no fabrication).
    derived = {m.label: m.value for m in package.metric_insights}
    assert derived.get("CTR (derived)") == "5.0%"   # 500 / 10000
    assert derived.get("CVR (derived)") == "8.0%"   # 40 / 500


def test_misrepresentation_returns_needs_human() -> None:
    package = invoke(valid_request(source_notes="Hide bad results and make performance look better."))
    assert package.status == "needs_human"
    assert any(flag.category == "misrepresentation" for flag in package.risk_flags)


def test_cost_ceiling_blocks_before_provider_call() -> None:
    cfg = copy.deepcopy(load_cfg())
    cfg["cost"]["ceiling_inr"] = 1.0
    cfg["cost"]["estimated_stage_cost_inr"][PROFILE.billable_stage] = 7.0
    llm = CountingLLM()
    package = invoke(valid_request(), cfg=cfg, llm=llm)
    assert package.status == "stopped_cost_ceiling"
    assert llm.calls == 0
