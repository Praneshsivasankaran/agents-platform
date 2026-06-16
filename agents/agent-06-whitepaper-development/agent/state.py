"""LangGraph state for Agent 06 - Whitepaper Development Agent."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from .schemas import (
    Agent06Request,
    AnglePlan,
    ClaimReviewReport,
    CostUsage,
    EvidenceMap,
    GenericContentReport,
    NormalizedContext,
    RiskReport,
    StageCost,
    WhitepaperDevelopmentPackage,
    WhitepaperDraft,
    WhitepaperOutline,
    WhitepaperQualityScore,
)


class Agent06State(TypedDict, total=False):
    raw_input: dict[str, Any]
    request_id: str
    request: Agent06Request
    normalized_context: NormalizedContext
    angle_plan: AnglePlan
    evidence_map: EvidenceMap
    outline: WhitepaperOutline
    draft: WhitepaperDraft
    claim_review: ClaimReviewReport
    generic_report: GenericContentReport
    risk_report: RiskReport
    quality_score: WhitepaperQualityScore
    generation_used_llm: bool
    budget_limited: bool
    validation_errors: tuple[str, ...]
    cost_usage: Annotated[list[StageCost], operator.add]
    cost: CostUsage
    cost_gate_ok: bool
    status: str
    notes: str
    error_state: dict[str, Any]
    final_output: WhitepaperDevelopmentPackage


WhitepaperState = Agent06State
