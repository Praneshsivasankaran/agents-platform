"""Typed contracts for Agent 19 - Multi-Channel Campaign Planning Agent."""

from __future__ import annotations

from digital_marketing.schemas import (
    CostUsage,
    DigitalMarketingHandoff,
    DigitalMarketingPackage,
    DigitalMarketingRequest,
    EvidenceItem,
    FunnelStageInput,
    GeneratedRecommendation,
    MetricInput,
    MetricInsight,
    OutputSection,
    QualityDimensionScore,
    QualityReport,
    RiskFlag,
    StageCost,
)


class MultiChannelCampaignPlanningRequest(DigitalMarketingRequest):
    """Agent 19 request contract."""


class MultiChannelCampaignPlanningPackage(DigitalMarketingPackage):
    """Agent 19 response contract."""


Agent19Request = MultiChannelCampaignPlanningRequest
Agent19Package = MultiChannelCampaignPlanningPackage
AgentRequest = MultiChannelCampaignPlanningRequest
AgentPackage = MultiChannelCampaignPlanningPackage

__all__ = [
    "Agent19Package",
    "Agent19Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DigitalMarketingHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "MetricInput",
    "MetricInsight",
    "MultiChannelCampaignPlanningPackage",
    "MultiChannelCampaignPlanningRequest",
    "OutputSection",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
