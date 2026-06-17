"""Shared LangGraph state for Digital Marketing Agents 15-21."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from .schemas import (
    CostUsage,
    DigitalMarketingPackage,
    DigitalMarketingRequest,
    EvidenceItem,
    GeneratedRecommendation,
    MetricInsight,
    OutputSection,
    QualityReport,
    RiskFlag,
    StageCost,
)


class DigitalMarketingState(TypedDict, total=False):
    raw_input: dict
    request_id: str
    request: DigitalMarketingRequest
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
    final_output: DigitalMarketingPackage
