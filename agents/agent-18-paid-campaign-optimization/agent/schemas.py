"""Typed contracts for Agent 18 - Paid Campaign Optimization Agent."""

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


class PaidCampaignOptimizationRequest(DigitalMarketingRequest):
    """Agent 18 request contract."""


class PaidCampaignOptimizationPackage(DigitalMarketingPackage):
    """Agent 18 response contract."""


Agent18Request = PaidCampaignOptimizationRequest
Agent18Package = PaidCampaignOptimizationPackage
AgentRequest = PaidCampaignOptimizationRequest
AgentPackage = PaidCampaignOptimizationPackage

__all__ = [
    "Agent18Package",
    "Agent18Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DigitalMarketingHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "MetricInput",
    "MetricInsight",
    "OutputSection",
    "PaidCampaignOptimizationPackage",
    "PaidCampaignOptimizationRequest",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
