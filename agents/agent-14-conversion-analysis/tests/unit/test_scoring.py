from __future__ import annotations

from agent.prompts import PROFILE
from agent.schemas import AgentRequest
from agent.scoring import score_quality
from demand_generation.tools import build_evidence, build_metric_insights, build_recommendations, detect_risks


def valid_request() -> AgentRequest:
    return AgentRequest(
        metrics=[{"label": "Spend", "source": "Campaign report", "value": "INR 6 lakh"}],
        campaign_goal="Analyze conversion drop-offs and recommend optimization priorities.",
        constraints=["Planning guidance only", "Use supplied counts only"],
        business_context="B2B SaaS platform analyzing webinar funnel performance.",
        funnel_stages=[
            {"count": 1000, "stage": "Visitors"},
            {"count": 120, "stage": "Registrations"},
            {"count": 75, "stage": "Attendees"},
            {"count": 15, "stage": "Demo requests"},
        ],
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
    request = valid_request().validated_copy(source_notes="Analyze conversion by caste.")
    risks = detect_risks(PROFILE, request)
    quality = score_quality(
        profile=PROFILE,
        request=request,
        recommendations=(),
        risks=risks,
    )

    assert any(flag.category == "protected_attribute" for flag in risks)
    assert quality.passed is False
