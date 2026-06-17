from __future__ import annotations

from agent.prompts import PROFILE
from agent.schemas import AgentRequest
from agent.scoring import score_quality
from digital_marketing.tools import build_evidence, build_metric_insights, build_output_sections, build_recommendations, detect_risks


def valid_request() -> AgentRequest:
    return AgentRequest(
        campaign_goal="Increase demo requests",
        target_audience="RevOps leaders",
        offer="Workflow assessment",
        page_copy="Hero: Fix handoff delays. CTA: Book an assessment. Proof: customer operations quote.",
        form_fields=["name", "work email", "company"],
        source_notes="Supplied page copy and campaign brief.",
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


def test_url_only_request_fails_quality_gate() -> None:
    request = AgentRequest(
        campaign_goal="Increase demo requests",
        target_audience="RevOps leaders",
        offer="Workflow assessment",
        page_notes="Review https://example.com/landing-page",
    )
    risks = detect_risks(PROFILE, request)
    quality = score_quality(profile=PROFILE, request=request, recommendations=(), risks=risks)
    assert any(flag.category == "live_platform_access" for flag in risks)
    assert quality.passed is False
