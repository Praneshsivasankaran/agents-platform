from __future__ import annotations

from agent.prompts import PROFILE
from agent.schemas import AgentRequest
from agent.scoring import score_quality
from demand_generation.tools import build_evidence, build_metric_insights, build_recommendations, detect_risks


def valid_request() -> AgentRequest:
    return AgentRequest(
        segment_summary="Enterprise RevOps accounts with multi-team lead routing pain.",
        campaign_goal="Recommend the best demand generation campaign for next quarter.",
        budget="INR 12 lakh planning budget, not approved spend",
        constraints=["No automatic launch", "Use existing webinar and benchmark assets"],
        business_context="B2B SaaS platform entering enterprise RevOps.",
        target_audience="RevOps and demand generation leaders",
        product_or_service="Revenue workflow automation",
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
    request = valid_request().validated_copy(source_notes="Recommend campaign targeting by religion.")
    risks = detect_risks(PROFILE, request)
    quality = score_quality(
        profile=PROFILE,
        request=request,
        recommendations=(),
        risks=risks,
    )

    assert any(flag.category == "protected_attribute" for flag in risks)
    assert quality.passed is False
