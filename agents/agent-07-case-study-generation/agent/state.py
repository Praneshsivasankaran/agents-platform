"""LangGraph state for Agent 07 - Case Study Generation Agent."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from .schemas import (
    CaseStudyDraft,
    CaseStudyPackage,
    CaseStudyPlan,
    CaseStudyRequest,
    CostUsage,
    EvidenceMap,
    MissingInfoWarning,
    NormalizedCaseStudyContext,
    QualityReport,
    QuoteCtaPackage,
    RiskFlag,
    StageCost,
)


class Agent07State(TypedDict, total=False):
    raw_input: dict[str, Any]
    request_id: str
    request: CaseStudyRequest
    normalized_context: NormalizedCaseStudyContext
    evidence_map: EvidenceMap
    missing_information_warnings: tuple[MissingInfoWarning, ...]
    plan: CaseStudyPlan
    draft: CaseStudyDraft
    quote_cta_package: QuoteCtaPackage
    risk_flags: tuple[RiskFlag, ...]
    quality_report: QualityReport
    validation_errors: tuple[str, ...]
    revision_attempted: bool
    generation_used_llm: bool
    budget_limited: bool
    cost_usage: Annotated[list[StageCost], operator.add]
    cost: CostUsage
    cost_gate_ok: bool
    status: str
    notes: str
    error_state: dict[str, Any]
    final_output: CaseStudyPackage


CaseStudyState = Agent07State
