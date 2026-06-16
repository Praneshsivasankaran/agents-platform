from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.schemas import (
    CaseStudyPackage,
    CaseStudyRequest,
    CostUsage,
    MetricInput,
    QualityDimensionScore,
    QualityReport,
    RiskFlag,
)


def _quality(score: int = 100, passed: bool = True) -> QualityReport:
    dimensions = (
        QualityDimensionScore(name="challenge_clarity", score=15, max_score=15),
        QualityDimensionScore(name="solution_specificity", score=15, max_score=15),
        QualityDimensionScore(name="evidence_backed_results", score=20, max_score=20),
        QualityDimensionScore(name="credibility_claim_safety", score=15, max_score=15),
        QualityDimensionScore(name="structure_completeness", score=10, max_score=10),
        QualityDimensionScore(name="brand_tone_fit", score=10, max_score=10),
        QualityDimensionScore(name="readability", score=10, max_score=10),
        QualityDimensionScore(name="cta_usefulness", score=5, max_score=5),
    )
    if score != 100:
        dimensions = (
            QualityDimensionScore(name="challenge_clarity", score=10, max_score=15),
            QualityDimensionScore(name="solution_specificity", score=10, max_score=15),
            QualityDimensionScore(name="evidence_backed_results", score=10, max_score=20),
            QualityDimensionScore(name="credibility_claim_safety", score=10, max_score=15),
            QualityDimensionScore(name="structure_completeness", score=8, max_score=10),
            QualityDimensionScore(name="brand_tone_fit", score=7, max_score=10),
            QualityDimensionScore(name="readability", score=7, max_score=10),
            QualityDimensionScore(name="cta_usefulness", score=3, max_score=5),
        )
    return QualityReport(
        overall_score=score,
        dimension_scores=dimensions,
        approval_reason="ok",
        passed=passed,
    )


def test_request_coerces_quotes_and_metric_objects() -> None:
    request = CaseStudyRequest(
        customer_name="Acme Bank",
        industry="Financial services",
        target_audience="CIOs",
        challenge="Manual onboarding delayed enterprise account launches.",
        solution_summary="Workflow automation for onboarding tasks.",
        results="Launch time decreased after teams centralized approvals.",
        customer_quotes="Helpful rollout, Practical support",
        metrics=[{"label": "Launch time reduction", "value": "32%", "source": "Internal report"}],
    )

    assert request.customer_quotes == ("Helpful rollout", "Practical support")
    assert request.metrics == (
        MetricInput(label="Launch time reduction", value="32%", source="Internal report"),
    )


def test_cost_usage_total_must_match_stage_ledger() -> None:
    with pytest.raises(ValidationError):
        CostUsage(stage_costs=(), total_inr=1.0, cost_ceiling_inr=25.0)


def test_quality_report_total_must_match_dimensions() -> None:
    with pytest.raises(ValidationError):
        _quality(score=99, passed=True)


def test_approved_package_requires_passing_quality_and_required_sections() -> None:
    package = CaseStudyPackage(
        request_id="run-1",
        status="approve",
        pass_status="pass",
        recommended_title="Acme Bank Case Study",
        title_options=("A", "B", "C"),
        executive_summary="Summary",
        customer_background="Background",
        challenge_section="Challenge",
        solution_section="Solution",
        implementation_section="Implementation",
        results_section="Results",
        final_markdown_draft="# Draft",
        quality_report=_quality(),
        cost_usage=CostUsage(stage_costs=(), total_inr=0.0, cost_ceiling_inr=25.0),
    )

    assert package.status == "approve"


def test_hard_fail_risk_requires_reject_status() -> None:
    with pytest.raises(ValidationError):
        CaseStudyPackage(
            request_id="run-1",
            status="revise",
            pass_status="fail",
            quality_report=_quality(),
            risk_flags=(
                RiskFlag(
                    category="unsupported_claim",
                    severity="hard_fail",
                    message="unsupported claim",
                ),
            ),
            cost_usage=CostUsage(stage_costs=(), total_inr=0.0, cost_ceiling_inr=25.0),
        )
