from __future__ import annotations

import pytest

from agent.schemas import (
    Agent04Request,
    CostUsage,
    HeadingItem,
    SEOOptimizationPackage,
    SEOScore,
    StageCost,
)


def test_request_cleans_and_coerces_keywords() -> None:
    req = Agent04Request.model_validate(
        {
            "draft_content": "  Draft body  ",
            "topic": "  SEO for agents  ",
            "primary_keyword": " AI content agents ",
            "secondary_keywords": "automation, SEO workflow; automation",
        }
    )

    assert req.draft_content == "Draft body"
    assert req.topic == "SEO for agents"
    assert req.primary_keyword == "AI content agents"
    assert req.secondary_keywords == ("automation", "SEO workflow")


def test_required_request_fields_are_enforced() -> None:
    with pytest.raises(Exception):
        Agent04Request.model_validate({"draft_content": "", "topic": "", "primary_keyword": ""})


def test_cost_usage_total_must_match_ledger() -> None:
    stage = StageCost(stage="generate_metadata", cost_inr=1.0, tier="cheap")
    with pytest.raises(Exception):
        CostUsage(stage_costs=(stage,), total_inr=2.0)


def test_seo_score_pass_contract() -> None:
    score = SEOScore(
        metadata_quality=20,
        keyword_usage=20,
        heading_structure=15,
        readability=15,
        content_goal_alignment=10,
        faq_usefulness=10,
        risk_safety=10,
        total_score=100,
        passed=True,
    )

    assert score.passed


def test_passed_package_requires_core_outputs() -> None:
    score = SEOScore(
        metadata_quality=20,
        keyword_usage=20,
        heading_structure=15,
        readability=15,
        content_goal_alignment=10,
        faq_usefulness=10,
        risk_safety=10,
        total_score=100,
        passed=True,
    )
    with pytest.raises(Exception):
        SEOOptimizationPackage(
            status="pass",
            seo_score=score,
            pass_status="pass",
            cost=CostUsage(stage_costs=(), total_inr=0.0),
        )


def test_package_is_frozen() -> None:
    pkg = SEOOptimizationPackage(status="error", cost=CostUsage(stage_costs=(), total_inr=0.0))
    with pytest.raises(Exception):
        pkg.status = "pass"


def test_heading_item_schema() -> None:
    item = HeadingItem(level="h2", text="How AI content agents support SEO")
    assert item.level == "h2"
