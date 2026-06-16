from __future__ import annotations

import pytest

from agent.schemas import (
    Agent05Request,
    CostUsage,
    EditorialPlanningPackage,
    EditorialQualityScore,
    StageCost,
)


def test_request_cleans_and_coerces_fields() -> None:
    req = Agent05Request.model_validate(
        {
            "brand_name": "  Northstar  ",
            "business_goal": " Drive leads ",
            "target_audience": " HR leaders ",
            "campaign_theme": " Burnout prevention ",
            "platforms": "blog, linkedin; blog",
            "date_range": {"start": "2026-07-01", "end": "2026-07-31"},
            "posting_frequency": {"cadence": "weekly", "count_per_week": 3},
            "brand_voice": " warm, expert ",
            "content_pillars": "education, proof, conversion",
            "existing_ideas": "Checklist, webinar recap",
        }
    )

    assert req.brand_name == "Northstar"
    assert req.platforms == ("blog", "linkedin")
    assert req.content_pillars == ("education", "proof", "conversion")
    assert req.existing_ideas == ("Checklist", "webinar recap")


def test_required_request_fields_are_enforced() -> None:
    with pytest.raises(Exception):
        Agent05Request.model_validate({"brand_name": "", "platforms": []})


def test_cost_usage_total_must_match_ledger() -> None:
    stage = StageCost(stage="generate_topic_plan", cost_inr=1.0, tier="strong")
    with pytest.raises(Exception):
        CostUsage(stage_costs=(stage,), total_inr=2.0)


def test_quality_score_pass_contract() -> None:
    score = EditorialQualityScore(
        input_completeness=10,
        calendar_coverage=15,
        audience_goal_alignment=15,
        platform_fit=15,
        pillar_balance=10,
        brief_actionability=15,
        repurposing_usefulness=10,
        risk_safety=10,
        total_score=100,
        passed=True,
    )

    assert score.passed


def test_passed_package_requires_core_outputs() -> None:
    score = EditorialQualityScore(
        input_completeness=10,
        calendar_coverage=15,
        audience_goal_alignment=15,
        platform_fit=15,
        pillar_balance=10,
        brief_actionability=15,
        repurposing_usefulness=10,
        risk_safety=10,
        total_score=100,
        passed=True,
    )
    with pytest.raises(Exception):
        EditorialPlanningPackage(
            status="pass",
            quality_score=score,
            pass_status="pass",
            cost=CostUsage(stage_costs=(), total_inr=0.0),
        )


def test_package_is_frozen() -> None:
    pkg = EditorialPlanningPackage(status="error", cost=CostUsage(stage_costs=(), total_inr=0.0))
    with pytest.raises(Exception):
        pkg.status = "pass"

