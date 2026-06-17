"""Typed contracts for Agent 13 - Lead Nurturing Agent."""

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


class LeadNurturingRequest(DemandGenRequest):
    """Agent 13 request contract."""


class LeadNurturingPackage(DemandGenPackage):
    """Agent 13 response contract."""


Agent13Request = LeadNurturingRequest
Agent13Package = LeadNurturingPackage
AgentRequest = LeadNurturingRequest
AgentPackage = LeadNurturingPackage

__all__ = [
    "Agent13Package",
    "Agent13Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DemandGenHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "LeadNurturingPackage",
    "LeadNurturingRequest",
    "MetricInput",
    "MetricInsight",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]