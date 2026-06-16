from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.schemas import CaseStudyPackage
from agent.workflow import build_graph


EVAL_DIR = Path(__file__).resolve().parent
AGENT_DIR = EVAL_DIR.parents[1]


def _load_cfg() -> dict[str, Any]:
    return yaml.safe_load((AGENT_DIR / "config" / "base.yaml").read_text(encoding="utf-8"))


def _invoke(raw_input: dict[str, Any]) -> CaseStudyPackage:
    graph = build_graph(_load_cfg(), MockLLMProvider(default_scenario="pass"), StdoutTelemetry(service="agent07-eval"))
    return graph.invoke({"raw_input": raw_input})["final_output"]


def test_eval_cases_and_thresholds_are_well_formed() -> None:
    cases = json.loads((EVAL_DIR / "cases.v1.json").read_text(encoding="utf-8"))
    thresholds = yaml.safe_load((EVAL_DIR / "thresholds.yaml").read_text(encoding="utf-8"))

    assert len(cases) == 6
    assert thresholds["pass_threshold"] == 80
    assert thresholds["cost_ceiling_inr"] == 25
    required_metrics = set(thresholds["metrics"])
    for case in cases:
        assert case["id"]
        assert set(case["expected"]).issubset(required_metrics)


def test_eval_cases_match_expected_behavior() -> None:
    cases = json.loads((EVAL_DIR / "cases.v1.json").read_text(encoding="utf-8"))

    for case in cases:
        package = _invoke(case["input"])
        expected = case["expected"]
        assert isinstance(package, CaseStudyPackage)
        assert package.cost_usage.total_inr <= package.cost_usage.cost_ceiling_inr
        assert package.final_markdown_draft or package.status == "reject"
        if "status" in expected:
            assert package.status == expected["status"], case["id"]
        if "pass_status" in expected:
            assert package.pass_status == expected["pass_status"], case["id"]
        if "warning_field" in expected:
            assert any(warning.field == expected["warning_field"] for warning in package.missing_information_warnings), case["id"]
        if "risk_category" in expected:
            assert any(flag.category == expected["risk_category"] for flag in package.risk_flags), case["id"]
        if expected.get("requires_metric_highlights"):
            assert package.metric_highlights, case["id"]
        if expected.get("requires_quote_placeholders"):
            assert package.customer_quote_placeholders, case["id"]
