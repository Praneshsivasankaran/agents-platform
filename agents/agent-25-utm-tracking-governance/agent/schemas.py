"""Typed contracts for Agent 25 - UTM & Tracking Governance Agent."""

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


class UTMTrackingGovernanceRequest(MarketingOperationsRequest):
    """Agent 25 request contract."""


class UTMTrackingGovernancePackage(MarketingOperationsPackage):
    """Agent 25 response contract."""


agent25Request = UTMTrackingGovernanceRequest
agent25Package = UTMTrackingGovernancePackage
AgentRequest = UTMTrackingGovernanceRequest
AgentPackage = UTMTrackingGovernancePackage

__all__ = [
    "agent25Package",
    "agent25Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "MarketingOperationsHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "UTMTrackingGovernancePackage",
    "UTMTrackingGovernanceRequest",
    "MetricInput",
    "MetricInsight",
    "OutputSection",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
