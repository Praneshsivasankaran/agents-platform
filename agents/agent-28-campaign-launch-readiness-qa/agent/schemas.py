"""Typed contracts for Agent 28 - Campaign Launch Readiness QA Agent."""

from __future__ import annotations

from marketing_operations.schemas import (
    CostUsage,
    MarketingOperationsHandoff,
    MarketingOperationsPackage,
    MarketingOperationsRequest,
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


class CampaignLaunchReadinessQARequest(MarketingOperationsRequest):
    """Agent 28 request contract."""


class CampaignLaunchReadinessQAPackage(MarketingOperationsPackage):
    """Agent 28 response contract."""


agent28Request = CampaignLaunchReadinessQARequest
agent28Package = CampaignLaunchReadinessQAPackage
AgentRequest = CampaignLaunchReadinessQARequest
AgentPackage = CampaignLaunchReadinessQAPackage

__all__ = [
    "agent28Package",
    "agent28Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "MarketingOperationsHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "CampaignLaunchReadinessQAPackage",
    "CampaignLaunchReadinessQARequest",
    "MetricInput",
    "MetricInsight",
    "OutputSection",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
