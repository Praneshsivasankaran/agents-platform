"""Typed contracts for Agent 14 - Conversion Analysis Agent."""

from __future__ import annotations

from demand_generation.schemas import (
    CostUsage,
    DemandGenHandoff,
    DemandGenPackage,
    DemandGenRequest,
    EvidenceItem,
    FunnelStageInput,
    GeneratedRecommendation,
    MetricInput,
    MetricInsight,
    QualityDimensionScore,
    QualityReport,
    RiskFlag,
    StageCost,
)


class ConversionAnalysisRequest(DemandGenRequest):
    """Agent 14 request contract."""


class ConversionAnalysisPackage(DemandGenPackage):
    """Agent 14 response contract."""


Agent14Request = ConversionAnalysisRequest
Agent14Package = ConversionAnalysisPackage
AgentRequest = ConversionAnalysisRequest
AgentPackage = ConversionAnalysisPackage

__all__ = [
    "Agent14Package",
    "Agent14Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DemandGenHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "ConversionAnalysisPackage",
    "ConversionAnalysisRequest",
    "MetricInput",
    "MetricInsight",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]