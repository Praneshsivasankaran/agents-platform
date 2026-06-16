from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from core.interfaces import BillableProviderError
from core.interfaces.usage import Usage
from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.schemas import CaseStudyPackage
from agent.workflow import build_graph


def load_cfg() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "config" / "base.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def valid_request(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "customer_name": "Acme Bank",
        "industry": "Financial services",
        "target_audience": "CIOs and operations leaders",
        "challenge": "Manual onboarding reviews delayed enterprise account launches and scattered approval evidence.",
        "solution_summary": "A workflow automation program centralized onboarding tasks, approval routing, and evidence capture.",
        "product_or_service": "LaunchFlow onboarding automation",
        "implementation_notes": "The rollout started with one business unit, mapped approval steps, and trained operations managers.",
        "results": "Enterprise account launch time decreased and operations teams gained a clearer audit trail.",
        "metrics": [
            {
                "label": "Launch cycle reduction",
                "value": "32%",
                "baseline": "Average launch cycle before rollout",
                "after": "Average launch cycle after rollout",
                "source": "Internal implementation report",
            }
        ],
        "customer_quotes": ["The workflow gave our operations leads one place to manage launch evidence."],
        "source_notes": "Internal implementation report and customer interview notes.",
        "brand_voice": "clear executive practical",
        "tone": "executive",
        "cta_goal": "Book an onboarding workflow assessment",
    }
    data.update(overrides)
    return data


def _invoke(raw_input: dict[str, Any], *, cfg: dict | None = None, llm=None) -> CaseStudyPackage:
    graph = build_graph(
        cfg or load_cfg(),
        llm or MockLLMProvider(default_scenario="pass"),
        StdoutTelemetry(service="agent07-test"),
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
    def __init__(self) -> None:
        super().__init__(default_scenario="pass")

    def respond(self, messages, **kwargs):
        raise BillableProviderError(
            Usage(prompt_tokens=10, completion_tokens=5, cost_native=0.01, currency="USD", synthetic=False),
            "provider_call_failed",
        )


def test_workflow_happy_path_returns_case_study_package() -> None:
    package = _invoke(valid_request())

    assert isinstance(package, CaseStudyPackage)
    assert package.status == "approve"
    assert package.pass_status == "pass"
    assert package.quality_report.overall_score >= 85
    assert package.recommended_title
    assert package.final_markdown_draft
    assert package.metric_highlights


def test_missing_metrics_routes_to_revise_without_inventing_numbers() -> None:
    package = _invoke(valid_request(metrics=(), results="Teams reported better consistency and ownership."))

    assert package.status == "revise"
    assert package.final_markdown_draft
    assert any(warning.field == "metrics" for warning in package.missing_information_warnings)
    assert not package.metric_highlights


def test_unsupported_claim_routes_to_reject() -> None:
    package = _invoke(
        valid_request(
            metrics=(),
            source_notes="",
            results="The solution guaranteed 10x ROI with no evidence and was legally approved.",
        )
    )

    assert package.status == "reject"
    assert package.pass_status == "fail"
    assert any(flag.category == "unsupported_claim" for flag in package.risk_flags)


def test_invalid_input_routes_to_reject() -> None:
    package = _invoke({"industry": "", "target_audience": ""})

    assert package.status == "reject"
    assert package.pass_status == "fail"
    assert "Missing or invalid" in package.notes
    assert package.cost_usage.total_inr == 0.0


def test_cost_ceiling_blocks_provider_calls_and_uses_fallback() -> None:
    cfg = copy.deepcopy(load_cfg())
    cfg["provider"] = "litellm"
    cfg["llm"]["provider"] = "litellm"
    cfg["cost"]["is_mock"] = False
    for stage in ("plan_case_study", "draft_case_study"):
        cfg["cost"]["estimated_stage_cost_inr"][stage] = 100.0
    llm = CountingLLM()

    package = _invoke(valid_request(), cfg=cfg, llm=llm)

    assert package.status == "revise"
    assert llm.calls == 0
    assert package.cost_usage.total_inr == 0.0
    assert package.final_markdown_draft
    assert "Budget limit reached" in package.notes


def test_billable_provider_failures_preserve_cost_and_fallback() -> None:
    package = _invoke(valid_request(), llm=BillingFailureLLM())

    assert package.cost_usage.total_inr > 0.0
    assert package.final_markdown_draft
    assert package.status in {"approve", "revise", "reject"}
