"""Typed contracts for Agent 22 - Campaign Intake & Brief QA Agent."""

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


class CampaignIntakeBriefQARequest(MarketingOperationsRequest):
    """Agent 22 request contract."""


class CampaignIntakeBriefQAPackage(MarketingOperationsPackage):
    """Agent 22 response contract."""


agent22Request = CampaignIntakeBriefQARequest
agent22Package = CampaignIntakeBriefQAPackage
AgentRequest = CampaignIntakeBriefQARequest
AgentPackage = CampaignIntakeBriefQAPackage

__all__ = [
    "agent22Package",
    "agent22Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "MarketingOperationsHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "CampaignIntakeBriefQAPackage",
    "CampaignIntakeBriefQARequest",
    "MetricInput",
    "MetricInsight",
    "OutputSection",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
