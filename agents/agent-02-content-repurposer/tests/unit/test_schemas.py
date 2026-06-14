from __future__ import annotations

import pytest

from agent.schemas import (
    Agent02Request,
    CostUsage,
    HardFail,
    PlatformScore,
    QualityReport,
    QualitySubScores,
    RepurposedContentPackage,
    SourceContent,
    StageCost,
)
from agent.validators import selected_platforms


def _passing_quality() -> QualityReport:
    sub = QualitySubScores(
        audience_relevance=14,
        usefulness=15,
        factual_consistency=15,
        platform_fit=15,
        hook_strength=10,
        message_clarity=9,
        cta_quality=10,
        brand_tone_alignment=5,
        readability_polish=5,
    )
    return QualityReport(
        overall_score=98,
        sub_scores=sub,
        platform_scores=(PlatformScore(platform="linkedin", score=95),),
        hard_fails=(),
        pass_flag=True,
        needs_revision=False,
    )


def test_source_content_accepts_agent01_serialized_contract_only_when_passed() -> None:
    source = SourceContent(
        source_type="agent01_blog_package",
        title="Repurposing approved content",
        blog_body="A complete approved blog body.",
        source_status="pass",
    )
    assert source.source_status == "pass"

    with pytest.raises(ValueError, match="source_status='pass'"):
        SourceContent(
            source_type="agent01_blog_package",
            title="Draft",
            blog_body="not ready",
            source_status="needs_human",
        )


def test_request_defaults_to_core_platforms_and_adds_newsletter_when_enabled() -> None:
    request = Agent02Request(
        source=SourceContent(source_type="raw_article_text", full_text=" ".join(["content"] * 90)),
        include_newsletter=True,
    )
    assert selected_platforms(request) == (
        "linkedin",
        "instagram",
        "x_twitter",
        "short_video",
        "newsletter",
    )


def test_cost_usage_total_must_match_ledger() -> None:
    stage = StageCost(stage="generate_platform_drafts", cost_inr=1.25, tier="strong")
    with pytest.raises(ValueError, match="total_inr"):
        CostUsage(stage_costs=(stage,), total_inr=2.0)


def test_quality_report_enforces_score_and_hard_fail_contract() -> None:
    sub = QualitySubScores(
        audience_relevance=14,
        usefulness=15,
        factual_consistency=15,
        platform_fit=15,
        hook_strength=10,
        message_clarity=9,
        cta_quality=10,
        brand_tone_alignment=5,
        readability_polish=5,
    )
    with pytest.raises(ValueError, match="pass_flag"):
        QualityReport(
            overall_score=98,
            sub_scores=sub,
            platform_scores=(PlatformScore(platform="linkedin", score=95),),
            hard_fails=(HardFail(code="generic_content", severity="retriable", reason="generic"),),
            pass_flag=True,
            needs_revision=True,
        )


def test_quality_report_rejects_passing_report_that_requests_revision() -> None:
    sub = QualitySubScores(
        audience_relevance=14,
        usefulness=15,
        factual_consistency=15,
        platform_fit=15,
        hook_strength=10,
        message_clarity=9,
        cta_quality=10,
        brand_tone_alignment=5,
        readability_polish=5,
    )
    with pytest.raises(ValueError, match="needs_revision"):
        QualityReport(
            overall_score=98,
            sub_scores=sub,
            platform_scores=(PlatformScore(platform="linkedin", score=95),),
            hard_fails=(),
            pass_flag=True,
            needs_revision=True,
        )


def test_quality_report_rejects_vacuous_pass_without_platform_scores() -> None:
    sub = QualitySubScores(
        audience_relevance=14,
        usefulness=15,
        factual_consistency=15,
        platform_fit=15,
        hook_strength=10,
        message_clarity=9,
        cta_quality=10,
        brand_tone_alignment=5,
        readability_polish=5,
    )
    with pytest.raises(ValueError, match="platform score"):
        QualityReport(
            overall_score=98,
            sub_scores=sub,
            platform_scores=(),
            hard_fails=(),
            pass_flag=True,
            needs_revision=False,
        )


def test_passed_package_requires_outputs_and_quality_report() -> None:
    with pytest.raises(ValueError, match="platform_outputs"):
        RepurposedContentPackage(
            status="pass",
            cost=CostUsage(stage_costs=(), total_inr=0.0),
            quality_report=_passing_quality(),
            markdown_review_package="# Package\n",
        )


def test_package_models_are_frozen() -> None:
    package = RepurposedContentPackage(
        status="needs_more_input",
        cost=CostUsage(stage_costs=(), total_inr=0.0),
        notes="need more source content",
    )
    with pytest.raises(Exception):
        package.status = "error"
