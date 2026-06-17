from __future__ import annotations

from agent.prompts import PROFILE
from agent.schemas import AgentRequest
from agent.scoring import score_quality
from digital_marketing.tools import build_evidence, build_metric_insights, build_output_sections, build_recommendations, detect_risks


def valid_request() -> AgentRequest:
    return AgentRequest(
        product_or_service="Revenue workflow automation",
        campaign_goal="Build paid search plan",
        target_audience="RevOps leaders",
        keywords=["lead routing automation", "revops workflow", "crm handoff"],
        metrics=[{"label": "Search volume", "value": "500/month", "source": "User spreadsheet"}],
        source_notes="User supplied keyword spreadsheet and ICP notes.",
    )


def test_complete_request_scores_above_pass_threshold() -> None:
    request = valid_request()
    risks = detect_risks(PROFILE, request)
    evidence = build_evidence(request)
    metrics = build_metric_insights(PROFILE, request)
    sections = build_output_sections(PROFILE, request, evidence, risks)
    recs = build_recommendations(PROFILE, request, evidence, risks, metrics)
    quality = score_quality(
        profile=PROFILE,
        request=request,
        recommendations=recs,
        output_sections=sections,
        risks=risks,
        metric_insights=metrics,
    )

    assert quality.overall_score >= PROFILE.pass_threshold
    assert quality.passed is True


def test_protected_attribute_request_fails_quality_gate() -> None:
    request = valid_request().validated_copy(source_notes="Prioritize by age and gender.")
    risks = detect_risks(PROFILE, request)
    quality = score_quality(profile=PROFILE, request=request, recommendations=(), risks=risks)

    assert any(flag.category == "protected_attribute" for flag in risks)
    assert quality.passed is False
