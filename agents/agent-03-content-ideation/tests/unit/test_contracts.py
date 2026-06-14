from __future__ import annotations

import pytest

from agent.contracts import (
    BlogBriefForAgent01,
    ContentIdeationPackage,
    ContentIdeationRequest,
    CostUsage,
    HardFail,
    PlatformDirection,
    QualityReport,
    QualitySubScores,
    RepurposingBriefForAgent02,
    StageCost,
)


def test_content_ideation_request_coerces_optional_sequences() -> None:
    request = ContentIdeationRequest(
        campaign_goal=" Build awareness ",
        product_or_service="ContentIQ",
        target_audience="B2B marketers",
        industry="B2B SaaS",
        brand_tone="clear",
        key_message="Turn context into ideas",
        optional_keywords="AI agents, content planning\ncampaigns",
        optional_constraints=["Avoid unsupported claims", "Avoid unsupported claims"],
        number_of_ideas=6,
    )

    assert request.campaign_goal == "Build awareness"
    assert request.optional_keywords == ("AI agents", "content planning", "campaigns")
    assert request.optional_constraints == ("Avoid unsupported claims",)


def test_request_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError):
        ContentIdeationRequest(
            campaign_goal="",
            product_or_service="ContentIQ",
            target_audience="B2B marketers",
            industry="B2B SaaS",
            brand_tone="clear",
            key_message="Turn context into ideas",
        )


def test_cost_usage_total_must_match_ledger() -> None:
    stage = StageCost(stage="generate_content_ideas", cost_inr=1.0, tier="cheap")
    with pytest.raises(ValueError, match="total_inr"):
        CostUsage(stage_costs=(stage,), total_inr=0.0)


def test_quality_report_enforces_score_and_pass_contract() -> None:
    sub = QualitySubScores(
        relevance_to_goal=25,
        audience_fit=20,
        specificity=15,
        downstream_usability=15,
        originality=10,
        brand_fit=10,
        risk_handling=5,
    )
    with pytest.raises(ValueError, match="passed"):
        QualityReport(
            overall_score=100,
            sub_scores=sub,
            passed=True,
            hard_fails=(
                HardFail(code="too_generic", severity="retriable", reason="Generic phrasing."),
            ),
        )


def test_passed_package_requires_downstream_briefs() -> None:
    sub = QualitySubScores(
        relevance_to_goal=25,
        audience_fit=20,
        specificity=15,
        downstream_usability=15,
        originality=10,
        brand_fit=10,
        risk_handling=5,
    )
    quality = QualityReport(overall_score=100, sub_scores=sub, passed=True)
    with pytest.raises(ValueError, match="content_ideas"):
        ContentIdeationPackage(
            status="pass",
            quality_score=100,
            quality_report=quality,
            cost=CostUsage(stage_costs=(), total_inr=0.0),
        )


def test_hard_fail_severity_must_match_code() -> None:
    with pytest.raises(ValueError, match="terminal"):
        HardFail(
            code="unsupported_numerical_claim",
            severity="warning",
            reason="Unsupported metric.",
        )


def test_handoff_contracts_are_strict_and_frozen() -> None:
    blog = BlogBriefForAgent01(
        selected_idea_id="idea_001",
        suggested_title="How AI Agents Improve Content Planning",
        title_options=("How AI Agents Improve Content Planning",),
        target_audience="B2B marketers",
        content_angle="Educational article",
        core_message="AI agents structure content ideas",
        suggested_outline=("Problem", "Solution", "CTA"),
        tone="clear",
        cta="Explore the workflow",
    )
    repurpose = RepurposingBriefForAgent02(
        core_message="AI agents structure content ideas",
        target_audience="B2B marketers",
        recommended_platforms=("LinkedIn",),
        platform_direction=(
            PlatformDirection(platform="LinkedIn", direction="Use a professional point of view."),
        ),
        hooks=("Most teams do not have an idea problem.",),
        cta="Explore the workflow",
        tone_rules=("Use a clear tone.",),
        content_pillars=("Planning",),
        message_guardrails=("Do not invent proof.",),
        repurposing_focus="Preserve the same message per platform.",
    )

    assert blog.selected_idea_id == "idea_001"
    assert repurpose.core_message
    with pytest.raises(Exception):
        blog.cta = "mutate"
