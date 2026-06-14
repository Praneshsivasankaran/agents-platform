from __future__ import annotations

import copy
from typing import Any, cast

from core.interfaces import BillableProviderError, LLMResponse
from core.interfaces.llm import Tier
from core.interfaces.usage import Usage
from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.contracts import ContentIdeationPackage
from agent.graph import build_graph

from tests.support import LLM_IDEA_SENTINEL, ScriptedIdeationLLM, load_cfg, valid_campaign


def _invoke(raw_input: dict[str, Any], *, cfg: dict | None = None, llm=None) -> ContentIdeationPackage:
    graph = build_graph(cfg or load_cfg(), llm or MockLLMProvider("pass"), StdoutTelemetry(service="agent03-test"))
    return graph.invoke({"raw_input": raw_input})["final_output"]


class CountingLLM(MockLLMProvider):
    def __init__(self) -> None:
        super().__init__("pass")
        self.calls = 0

    def respond(self, messages, **kwargs):
        self.calls += 1
        return super().respond(messages, **kwargs)


class TextOnlyLLM(MockLLMProvider):
    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type | None = None,
    ) -> LLMResponse:
        return LLMResponse(text="text-only fallback", usage=Usage(prompt_tokens=10, completion_tokens=2, synthetic=True))


class BillingFailureLLM(MockLLMProvider):
    def respond(self, messages, **kwargs):
        raise BillableProviderError(
            Usage(prompt_tokens=10, completion_tokens=5, cost_native=0.05, currency="USD", synthetic=False),
            "provider_call_failed",
        )


def test_workflow_happy_path_returns_content_ideation_package() -> None:
    package = _invoke(valid_campaign())

    assert isinstance(package, ContentIdeationPackage)
    assert package.status == "pass"
    assert package.quality_score >= 80
    assert len(package.content_ideas) == 8
    assert package.campaign_summary is not None
    assert package.audience_insights is not None
    assert package.blog_brief_for_agent_01 is not None
    assert package.repurposing_brief_for_agent_02 is not None
    assert package.recommended_next_agent in {
        "Agent 01 - Blog Creation",
        "Agent 02 - Content Repurposing",
    }


def test_invalid_input_routes_to_needs_more_input() -> None:
    package = _invoke({"campaign_goal": "  "})

    assert package.status == "needs_more_input"
    assert package.content_ideas == ()
    assert "Missing or invalid" in package.notes


def test_content_ideas_output_structure_and_priority_sort() -> None:
    package = _invoke(valid_campaign(number_of_ideas=5))

    assert len(package.content_ideas) == 5
    assert all(idea.idea_id.startswith("idea_") for idea in package.content_ideas)
    assert all(idea.priority_score >= 0 for idea in package.content_ideas)
    scores = [idea.priority_score for idea in package.content_ideas]
    assert scores == sorted(scores, reverse=True)
    assert package.recommended_formats


def test_blog_brief_for_agent_01_is_complete() -> None:
    package = _invoke(valid_campaign())
    brief = package.blog_brief_for_agent_01

    assert brief is not None
    assert brief.selected_idea_id == package.content_ideas[0].idea_id
    assert brief.suggested_outline
    assert brief.proof_points_or_placeholders
    assert "unsupported metrics" in " ".join(brief.constraints).lower()


def test_repurposing_brief_for_agent_02_is_complete() -> None:
    package = _invoke(valid_campaign(optional_content_type_preference=["Blog", "LinkedIn", "Short Video"]))
    brief = package.repurposing_brief_for_agent_02

    assert brief is not None
    assert "LinkedIn" in brief.recommended_platforms
    assert brief.platform_direction
    assert brief.hooks
    assert brief.message_guardrails


def test_unsupported_metric_request_routes_to_needs_human_with_risk_flag() -> None:
    package = _invoke(
        valid_campaign(
            key_message="ContentIQ will guarantee a 300% increase in campaign output.",
        )
    )

    assert package.status == "needs_human"
    assert "unsupported_numerical_claim" in package.risk_flags
    assert package.quality_report is not None
    assert any(fail.code == "unsupported_numerical_claim" for fail in package.quality_report.hard_fails)


def test_guardrail_against_guaranteed_roi_does_not_route_to_needs_human() -> None:
    package = _invoke(
        valid_campaign(
            key_message=(
                "AI agents help marketing teams turn campaign context, briefs, and source material into "
                "structured content ideas faster while keeping humans in control of quality and accuracy."
            ),
            optional_constraints=[
                "Do not invent statistics. Do not claim guaranteed ROI. Do not imply the product publishes automatically.",
                "Keep evidence placeholders visible when proof is missing.",
            ],
            optional_notes=(
                "Focus on practical workflows, human review, quality control, and avoiding generic AI content."
            ),
        )
    )

    assert package.status == "pass"
    assert "unsafe_marketing_claim" not in package.risk_flags
    assert package.quality_report is not None
    assert not any(fail.code == "unsafe_marketing_claim" for fail in package.quality_report.hard_fails)
    assert package.blog_brief_for_agent_01 is not None
    assert package.repurposing_brief_for_agent_02 is not None


def test_llm_structured_ideas_can_be_used() -> None:
    package = _invoke(valid_campaign(number_of_ideas=4), llm=ScriptedIdeationLLM("pass"))

    assert package.status == "pass"
    assert package.generation_used_llm
    assert any(LLM_IDEA_SENTINEL in idea.title for idea in package.content_ideas)


def test_invalid_llm_structured_output_falls_back_to_deterministic_ideas() -> None:
    package = _invoke(valid_campaign(number_of_ideas=4), llm=TextOnlyLLM("pass"))

    assert package.status == "pass"
    assert not package.generation_used_llm
    assert package.content_ideas


def test_billable_provider_failure_preserves_incurred_cost_and_falls_back() -> None:
    package = _invoke(valid_campaign(number_of_ideas=4), llm=BillingFailureLLM("pass"))

    assert package.status == "pass"
    assert package.cost.total_inr > 0.0
    assert package.content_ideas


def test_cost_ceiling_blocks_before_provider_call() -> None:
    cfg = cast(dict[str, Any], copy.deepcopy(load_cfg()))
    cfg["cost"]["estimated_stage_cost_inr"]["generate_content_ideas"] = 21.0
    llm = CountingLLM()

    package = _invoke(valid_campaign(), cfg=cfg, llm=llm)

    assert package.status == "stopped_cost_ceiling"
    assert llm.calls == 0
    assert package.cost.total_inr == 0.0

