"""Typed contracts for Agent 11 - Lead Scoring Agent."""

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


class LeadScoringRequest(DemandGenRequest):
    """Agent 11 request contract."""


class LeadScoringPackage(DemandGenPackage):
    """Agent 11 response contract."""


Agent11Request = LeadScoringRequest
Agent11Package = LeadScoringPackage
AgentRequest = LeadScoringRequest
AgentPackage = LeadScoringPackage

__all__ = [
    "Agent11Package",
    "Agent11Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DemandGenHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "LeadScoringPackage",
    "LeadScoringRequest",
    "MetricInput",
    "MetricInsight",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]