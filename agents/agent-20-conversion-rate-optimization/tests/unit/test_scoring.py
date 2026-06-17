from __future__ import annotations

from agent.prompts import PROFILE
from agent.schemas import AgentRequest
from agent.scoring import score_quality
from digital_marketing.tools import build_evidence, build_metric_insights, build_output_sections, build_recommendations, detect_risks


def valid_request() -> AgentRequest:
    return AgentRequest(
        conversion_goal="Increase demo request submissions",
        target_audience="RevOps leaders",
        page_notes="Users drop near the proof and pricing section.",
        metric_summary="Visitors 1000, form starts 120, submissions 45.",
        funnel_stages=[
            {"stage": "Visitors", "count": 1000},
            {"stage": "Form starts", "count": 120},
            {"stage": "Submissions", "count": 45},
        ],
        source_notes="Supplied landing page findings and funnel summary.",
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


def test_launch_request_fails_quality_gate() -> None:
    request = valid_request().validated_copy(source_notes="Launch experiment and change website automatically.")
    risks = detect_risks(PROFILE, request)
    quality = score_quality(profile=PROFILE, request=request, recommendations=(), risks=risks)
    assert any(flag.category == "external_action" for flag in risks)
    assert quality.passed is False
