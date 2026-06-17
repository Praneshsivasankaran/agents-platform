from __future__ import annotations

from agent.prompts import PROFILE
from agent.schemas import AgentRequest
from agent.scoring import score_quality
from marketing_operations.tools import build_evidence, build_metric_insights, build_output_sections, build_recommendations, detect_risks
from tests.unit.test_workflow import PROTECTED_TEXT, valid_request


def test_complete_request_scores_above_pass_threshold() -> None:
    request = AgentRequest(**valid_request())
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
    request = AgentRequest(**valid_request(source_notes=PROTECTED_TEXT[PROFILE.agent_id]))
    risks = detect_risks(PROFILE, request)
    quality = score_quality(profile=PROFILE, request=request, recommendations=(), risks=risks)

    assert any(flag.category == "protected_attribute" for flag in risks)
    assert quality.passed is False