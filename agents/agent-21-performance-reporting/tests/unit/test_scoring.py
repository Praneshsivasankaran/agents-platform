from __future__ import annotations

from agent.prompts import PROFILE
from agent.schemas import AgentRequest
from agent.scoring import score_quality
from digital_marketing.tools import build_evidence, build_metric_insights, build_output_sections, build_recommendations, detect_risks


def valid_request() -> AgentRequest:
    return AgentRequest(
        campaign_goal="Report paid search launch performance",
        reporting_period="May 2026",
        metric_summary="Impressions 10000, clicks 500, conversions 40, spend Rs 60000.",
        metrics=[
            {"label": "Impressions", "value": "10000", "source": "User report"},
            {"label": "Clicks", "value": "500", "source": "User report"},
            {"label": "Conversions", "value": "40", "source": "User report"},
        ],
        channel_summaries="Paid search performed steadily; LinkedIn volume was lower than expected.",
        source_notes="User supplied campaign report summary.",
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


def test_misrepresentation_request_fails_quality_gate() -> None:
    request = valid_request().validated_copy(source_notes="Hide bad results and make performance look better.")
    risks = detect_risks(PROFILE, request)
    quality = score_quality(profile=PROFILE, request=request, recommendations=(), risks=risks)
    assert any(flag.category == "misrepresentation" for flag in risks)
    assert quality.passed is False
