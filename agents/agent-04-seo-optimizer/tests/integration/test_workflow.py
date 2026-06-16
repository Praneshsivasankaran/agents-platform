from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from core.interfaces import BillableProviderError
from core.interfaces.usage import Usage
from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.schemas import SEOOptimizationPackage
from agent.workflow import build_graph


def load_cfg() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "config" / "base.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def valid_request(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "draft_content": (
            "AI content agents help marketing teams turn scattered campaign notes into "
            "clear drafts, review packages, and repeatable workflows. A strong workflow "
            "keeps human editors in control while reducing repetitive checks. Teams can "
            "use AI content agents to structure ideas, improve drafts, and prepare content "
            "for search review without inventing claims or removing editorial judgment. "
            "The practical starting point is one approved article, a clear target audience, "
            "and a human review step before any final use."
        ),
        "topic": "AI agents for content teams",
        "primary_keyword": "AI content agents",
        "secondary_keywords": ["content automation", "SEO workflow"],
        "target_audience": "marketing managers",
        "content_goal": "educate and generate demo interest",
        "brand_tone": "professional and clear",
        "constraints": ["Do not mention pricing"],
        "cta_direction": "Book a demo",
    }
    data.update(overrides)
    return data


def _invoke(raw_input: dict[str, Any], *, cfg: dict | None = None, llm=None) -> SEOOptimizationPackage:
    graph = build_graph(
        cfg or load_cfg(),
        llm or MockLLMProvider(default_scenario="pass"),
        StdoutTelemetry(service="agent04-test"),
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


def test_workflow_happy_path_returns_seo_package() -> None:
    package = _invoke(valid_request())

    assert isinstance(package, SEOOptimizationPackage)
    assert package.status == "pass"
    assert package.seo_score is not None
    assert package.seo_score.total_score >= 80
    assert package.title_options
    assert package.meta_description
    assert package.url_slug
    assert package.heading_plan
    assert package.faq_suggestions
    assert package.optimized_draft


def test_invalid_input_routes_to_needs_more_input() -> None:
    package = _invoke({"draft_content": "", "topic": "", "primary_keyword": ""})

    assert package.status == "needs_more_input"
    assert "Missing or invalid" in package.notes
    assert package.cost.total_inr == 0.0


def test_cost_ceiling_blocks_before_provider_call() -> None:
    cfg = copy.deepcopy(load_cfg())
    cfg["cost"]["estimated_stage_cost_inr"]["generate_metadata"] = 21.0
    llm = CountingLLM()

    package = _invoke(valid_request(), cfg=cfg, llm=llm)

    assert package.status == "stopped_cost_ceiling"
    assert llm.calls == 0
    assert package.cost.total_inr == 0.0


def test_billable_provider_failures_preserve_cost_and_fallback() -> None:
    package = _invoke(valid_request(), llm=BillingFailureLLM(default_scenario="pass"))

    assert package.cost.total_inr > 0.0
    assert package.optimized_draft
    assert package.status in {"pass", "needs_human", "stopped_cost_ceiling"}
