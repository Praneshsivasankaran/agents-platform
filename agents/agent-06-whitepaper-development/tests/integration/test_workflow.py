from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from core.interfaces import BillableProviderError
from core.interfaces.usage import Usage
from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.schemas import WhitepaperDevelopmentPackage
from agent.workflow import build_graph


def load_cfg() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "config" / "base.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def valid_request(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "topic": "AI governance operating model",
        "company_context": "Acme PolicyOS helps compliance teams manage AI policy reviews.",
        "target_audience": "CIOs and compliance leaders",
        "industry": "Financial services",
        "problem": "AI initiatives are slowed by manual policy review and unclear ownership.",
        "solution": "A workflow platform for AI policy intake, review routing, evidence capture, and approval tracking.",
        "tone": "executive, precise, and practical",
        "target_depth": "detailed B2B whitepaper package",
        "cta": "Book a governance readiness workshop",
        "proof_points": ["Internal pilot centralized review evidence across three policy teams"],
        "source_notes": ["Internal product brief approved by compliance SME"],
        "differentiators": ["role-based review routing", "evidence capture"],
        "objections": ["Buyers may worry about adoption effort"],
        "compliance_constraints": ["Avoid legal advice claims"],
    }
    data.update(overrides)
    return data


def _invoke(raw_input: dict[str, Any], *, cfg: dict | None = None, llm=None) -> WhitepaperDevelopmentPackage:
    graph = build_graph(
        cfg or load_cfg(),
        llm or MockLLMProvider(default_scenario="pass"),
        StdoutTelemetry(service="agent06-test"),
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


def test_workflow_happy_path_returns_whitepaper_package() -> None:
    package = _invoke(valid_request())

    assert isinstance(package, WhitepaperDevelopmentPackage)
    assert package.status == "pass"
    assert package.quality_score is not None
    assert package.quality_score.total_score >= 80
    assert package.title_options
    assert package.executive_summary
    assert package.key_claims
    assert all(claim.evidence_status for claim in package.key_claims)


def test_invalid_input_routes_to_needs_more_input() -> None:
    package = _invoke({"topic": "", "company_context": ""})

    assert package.status == "needs_more_input"
    assert "Missing or invalid" in package.notes
    assert package.cost.total_inr == 0.0


def test_cost_ceiling_blocks_before_provider_call() -> None:
    cfg = copy.deepcopy(load_cfg())
    for stage in ("normalize_context", "plan_angle", "generate_outline", "draft_sections"):
        cfg["cost"]["estimated_stage_cost_inr"][stage] = 100.0
    llm = CountingLLM()

    package = _invoke(valid_request(), cfg=cfg, llm=llm)

    assert package.status == "needs_review_budget_limited"
    assert llm.calls == 0
    assert package.cost.total_inr == 0.0
    assert package.executive_summary
    assert package.key_claims


def test_billable_provider_failures_preserve_cost_and_fallback() -> None:
    package = _invoke(valid_request(), llm=BillingFailureLLM())

    assert package.cost.total_inr > 0.0
    assert package.executive_summary
    assert package.key_claims
    assert package.status in {"pass", "needs_human", "stopped_cost_ceiling"}
