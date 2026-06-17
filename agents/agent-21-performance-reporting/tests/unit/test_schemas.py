from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.prompts import PROFILE
from agent.schemas import AgentPackage, AgentRequest, CostUsage, QualityDimensionScore, QualityReport, RiskFlag


def test_request_coerces_metric_fields() -> None:
    request = AgentRequest(
        campaign_goal="Report paid search launch performance",
        reporting_period="May 2026",
        metrics=[{"label": "Clicks", "value": "500", "source": "User report"}],
    )
    assert request.metrics[0].label == "Clicks"


def test_cost_usage_total_must_match_stage_ledger() -> None:
    with pytest.raises(ValidationError):
        CostUsage(stage_costs=(), total_inr=1.0, cost_ceiling_inr=PROFILE.cost_ceiling_inr)


def test_package_with_hard_fail_cannot_pass() -> None:
    quality = QualityReport(
        overall_score=90,
        dimension_scores=(QualityDimensionScore(name="x", score=90, max_score=100),),
        approval_reason="Looks good",
        passed=True,
    )
    with pytest.raises(ValidationError):
        AgentPackage(
            request_id="r1",
            agent_id=PROFILE.agent_id,
            agent_name=PROFILE.title,
            status="pass",
            terminal_status="pass",
            quality_status="approve",
            pass_status="pass",
            summary="Invalid package",
            risk_flags=(RiskFlag(category="misrepresentation", severity="hard_fail", message="Forbidden"),),
            quality_report=quality,
            cost_usage=CostUsage(stage_costs=(), total_inr=0.0, cost_ceiling_inr=PROFILE.cost_ceiling_inr),
        )
