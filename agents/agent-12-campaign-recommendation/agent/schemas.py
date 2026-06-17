"""Typed contracts for Agent 12 - Campaign Recommendation Agent."""

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


class CampaignRecommendationRequest(DemandGenRequest):
    """Agent 12 request contract."""


class CampaignRecommendationPackage(DemandGenPackage):
    """Agent 12 response contract."""


Agent12Request = CampaignRecommendationRequest
Agent12Package = CampaignRecommendationPackage
AgentRequest = CampaignRecommendationRequest
AgentPackage = CampaignRecommendationPackage

__all__ = [
    "Agent12Package",
    "Agent12Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DemandGenHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "CampaignRecommendationPackage",
    "CampaignRecommendationRequest",
    "MetricInput",
    "MetricInsight",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]