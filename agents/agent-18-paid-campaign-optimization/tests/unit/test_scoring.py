from __future__ import annotations

from agent.prompts import PROFILE
from agent.schemas import AgentRequest
from agent.scoring import score_quality
from digital_marketing.tools import build_evidence, build_metric_insights, build_output_sections, build_recommendations, detect_risks


def valid_request() -> AgentRequest:
    return AgentRequest(
        campaign_goal="Improve paid search CPA",
        platforms=["Google Ads"],
        metric_summary="Spend Rs 120000, clicks 3200, conversions 80, CPA Rs 1500.",
        metrics=[
            {"label": "Spend", "value": "Rs 120000", "source": "User export"},
            {"label": "Conversions", "value": "80", "source": "User export"},
        ],
        source_notes="User supplied paid search export summary.",
    )


def test_complete_request_scores_above_pass_threshold() -> None:
    request = valid_request()
    risks = detect_risks(PROFILE, request)
    evidence = build_evidence(request)
    metrics = build_metric_insights(PROFILE, request)
    sections = build_output_sections(PROFILE, request, evidence, risks)
    recs = build_recommendations(PROFILE, request, evidence, risks, metrics)
    quality = score_quality(profile=PROFILE, request=request, recommendations=recs, output_sections=sections, risks=risks, metric_insights=metrics)
    assert quality.overall_score >= PROFILE.pass_threshold
    assert quality.passed is True


def test_budget_change_request_fails_quality_gate() -> None:
    request = valid_request().validated_copy(source_notes="Change budget and pause campaign automatically.")
    risks = detect_risks(PROFILE, request)
    quality = score_quality(profile=PROFILE, request=request, recommendations=(), risks=risks)
    assert any(flag.category == "external_action" for flag in risks)
    assert quality.passed is False
