from __future__ import annotations

from agent.prompts import PROFILE
from agent.schemas import AgentRequest
from agent.scoring import score_quality
from demand_generation.tools import build_evidence, build_metric_insights, build_recommendations, detect_risks


def valid_request() -> AgentRequest:
    return AgentRequest(
        product_or_service="Revenue workflow automation",
        target_audience="RevOps and demand generation leaders",
        business_context="B2B SaaS platform selling to revenue operations teams.",
        icp_summary="Mid-market and enterprise SaaS companies with complex handoffs.",
        segment_summary="RevOps-led accounts with growing SDR teams and documented funnel leakage.",
        constraints=["No purchased contact lists", "Human review before launch"],
        offer="Benchmark assessment for lead handoff maturity",
        campaign_goal="Create a lead generation campaign blueprint for Q3 pipeline.",
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
    request = valid_request().validated_copy(source_notes="Target leads based on age and race.")
    risks = detect_risks(PROFILE, request)
    quality = score_quality(
        profile=PROFILE,
        request=request,
        recommendations=(),
        risks=risks,
    )

    assert any(flag.category == "protected_attribute" for flag in risks)
    assert quality.passed is False
