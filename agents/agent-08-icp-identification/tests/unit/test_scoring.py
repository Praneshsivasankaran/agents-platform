from __future__ import annotations

from agent.prompts import PROFILE
from agent.schemas import AgentRequest
from agent.scoring import score_quality
from demand_generation.tools import build_evidence, build_metric_insights, build_recommendations, detect_risks


def valid_request() -> AgentRequest:
    return AgentRequest(
        business_context="B2B SaaS workflow platform for revenue operations teams.",
        product_or_service="Revenue workflow automation",
        source_notes="Wins cluster in SaaS companies with complex lead handoffs and multi-step approvals.",
        campaign_goal="Define enterprise ICP for pipeline generation.",
        target_audience="RevOps and demand generation leaders",
    )


def test_complete_request_scores_above_pass_threshold() -> None:
    request = valid_request()
    risks = detect_risks(PROFILE, request)
    evidence = build_evidence(request)
    metrics = build_metric_insights(PROFILE, request)
    recs = build_recommendations(PROFILE, request, evidence, risks, metrics)
    quality = score_quality(
        profile=PROFILE,
        request=request,
        recommendations=recs,
        risks=risks,
        metric_insights=metrics,
    )

    assert quality.overall_score >= PROFILE.pass_threshold
    assert quality.passed is True


def test_protected_attribute_request_fails_quality_gate() -> None:
    request = valid_request().validated_copy(source_notes="Target based on age and gender.")
    risks = detect_risks(PROFILE, request)
    quality = score_quality(
        profile=PROFILE,
        request=request,
        recommendations=(),
        risks=risks,
    )

    assert any(flag.category == "protected_attribute" for flag in risks)
    assert quality.passed is False

