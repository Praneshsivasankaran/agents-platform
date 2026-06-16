"""LangGraph state for Agent 05 - Editorial Planning Agent."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from .schemas import (
    Agent05Request,
    BalanceGapAnalysis,
    CalendarSlot,
    ContentBriefPackage,
    CostUsage,
    EditorialPlanningPackage,
    EditorialQualityScore,
    PeriodPlan,
    PlatformPlanSummary,
    PlatformStrategyPackage,
    RepurposingMapPackage,
    RiskReport,
    StageCost,
    TopicPlanPackage,
)


class Agent05State(TypedDict, total=False):
    raw_input: dict[str, Any]
    request_id: str
    request: Agent05Request
    normalized_request: dict[str, Any]
    validation_errors: tuple[str, ...]
    calendar_skeleton: tuple[CalendarSlot, ...]
    platform_strategy: PlatformStrategyPackage
    topic_plan: TopicPlanPackage
    content_briefs: ContentBriefPackage
    repurposing: RepurposingMapPackage
    weekly_plan: tuple[PeriodPlan, ...]
    monthly_plan: tuple[PeriodPlan, ...]
    platform_plan_summary: tuple[PlatformPlanSummary, ...]
    balance_gap_analysis: BalanceGapAnalysis
    risk_report: RiskReport
    quality_score: EditorialQualityScore
    generation_used_llm: bool
    budget_limited: bool
    cost_usage: Annotated[list[StageCost], operator.add]
    cost: CostUsage
    cost_gate_ok: bool
    status: str
    notes: str
    error_state: dict[str, Any]
    final_output: EditorialPlanningPackage


# Compatibility alias following generated scaffold naming.
EditorialPlannerState = Agent05State

