"""Shared LangGraph state for Marketing Operations Agents 22-28."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from .schemas import (
    CostUsage,
    MarketingOperationsPackage,
    MarketingOperationsRequest,
    EvidenceItem,
    GeneratedRecommendation,
    MetricInsight,
    OutputSection,
    QualityReport,
    RiskFlag,
    StageCost,
)


class MarketingOperationsState(TypedDict, total=False):
    raw_input: dict
    request_id: str
    request: MarketingOperationsRequest
    validation_errors: tuple[str, ...]
    risk_flags: tuple[RiskFlag, ...]
    evidence: tuple[EvidenceItem, ...]
    metric_insights: tuple[MetricInsight, ...]
    output_sections: tuple[OutputSection, ...]
    recommendations: tuple[GeneratedRecommendation, ...]
    assumptions: tuple[str, ...]
    quality_report: QualityReport
    cost_usage: Annotated[list[StageCost], operator.add]
    cost: CostUsage
    cost_ceiling_inr: float
    budget_limited: bool
    generation_used_llm: bool
    error_state: dict
    status: str
    final_output: MarketingOperationsPackage
