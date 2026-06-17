"""Typed contracts for Agent 08 - ICP Identification Agent."""

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


class ICPIdentificationRequest(DemandGenRequest):
    """Agent 08 request contract."""


class ICPIdentificationPackage(DemandGenPackage):
    """Agent 08 response contract."""


Agent08Request = ICPIdentificationRequest
Agent08Package = ICPIdentificationPackage
AgentRequest = ICPIdentificationRequest
AgentPackage = ICPIdentificationPackage

__all__ = [
    "Agent08Package",
    "Agent08Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DemandGenHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "ICPIdentificationPackage",
    "ICPIdentificationRequest",
    "MetricInput",
    "MetricInsight",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]

