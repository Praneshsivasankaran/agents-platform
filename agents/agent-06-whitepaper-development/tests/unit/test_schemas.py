from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.schemas import (
    Agent06Request,
    ClaimEvidence,
    CostUsage,
    RiskFlag,
    WhitepaperDevelopmentPackage,
    WhitepaperQualityScore,
)


def test_request_coerces_optional_text_lists() -> None:
    request = Agent06Request(
        topic="AI governance",
        company_context="Acme builds policy workflow software.",
        target_audience="CIOs",
        industry="Financial services",
        problem="Manual governance reviews are slow.",
        solution="Policy workflow automation",
        tone="executive and practical",
        target_depth="detailed",
        cta="Book a workshop",
        proof_points="Pilot reduced review queues; Internal SME quote",
    )

    assert request.proof_points == ("Pilot reduced review queues", "Internal SME quote")


def test_cost_usage_total_must_match_stage_ledger() -> None:
    with pytest.raises(ValidationError):
        CostUsage(stage_costs=(), total_inr=1.0)


def test_risk_flag_severity_matches_hard_fail_code() -> None:
    with pytest.raises(ValidationError):
        RiskFlag(code="generic_content", severity="warning", message="too generic")


def test_passed_package_requires_passing_quality_and_supported_claims() -> None:
    cost = CostUsage(stage_costs=(), total_inr=0.0)
    score = WhitepaperQualityScore(
        input_completeness=10,
        specificity=15,
        audience_fit=10,
        structure_completeness=15,
        problem_solution_logic=15,
        evidence_discipline=15,
        depth_actionability=10,
        tone_clarity=5,
        risk_review_readiness=5,
        total_score=100,
        passed=True,
    )

    package = WhitepaperDevelopmentPackage(
        status="pass",
        cost=cost,
        quality_score=score,
        pass_status="pass",
        title_options=("A", "B", "C"),
        recommended_angle="Specific angle",
        executive_summary="Summary",
        problem_statement="Problem",
        proposed_solution="Solution",
        key_claims=(
            ClaimEvidence(
                claim="Acme helps CIOs structure governance review.",
                evidence_status="general_reasoning",
            ),
        ),
    )

    assert package.status == "pass"


def test_passed_package_cannot_contain_unsupported_claim() -> None:
    cost = CostUsage(stage_costs=(), total_inr=0.0)
    score = WhitepaperQualityScore(
        input_completeness=10,
        specificity=15,
        audience_fit=10,
        structure_completeness=15,
        problem_solution_logic=15,
        evidence_discipline=15,
        depth_actionability=10,
        tone_clarity=5,
        risk_review_readiness=5,
        total_score=100,
        passed=True,
    )

    with pytest.raises(ValidationError):
        WhitepaperDevelopmentPackage(
            status="pass",
            cost=cost,
            quality_score=score,
            pass_status="pass",
            title_options=("A", "B", "C"),
            recommended_angle="Specific angle",
            executive_summary="Summary",
            problem_statement="Problem",
            proposed_solution="Solution",
            key_claims=(ClaimEvidence(claim="Acme improves revenue 45%.", evidence_status="unsupported"),),
        )
