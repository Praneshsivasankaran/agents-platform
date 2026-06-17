"""Typed contracts for Agent 10 - Lead Generation Agent."""

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


class LeadGenerationRequest(DemandGenRequest):
    """Agent 10 request contract."""


class LeadGenerationPackage(DemandGenPackage):
    """Agent 10 response contract."""


Agent10Request = LeadGenerationRequest
Agent10Package = LeadGenerationPackage
AgentRequest = LeadGenerationRequest
AgentPackage = LeadGenerationPackage

__all__ = [
    "Agent10Package",
    "Agent10Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DemandGenHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "LeadGenerationPackage",
    "LeadGenerationRequest",
    "MetricInput",
    "MetricInsight",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]