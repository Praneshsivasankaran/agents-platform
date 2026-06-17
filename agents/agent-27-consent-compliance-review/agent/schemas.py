"""Typed contracts for Agent 27 - Consent & Compliance Review Agent."""

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


class ConsentComplianceReviewRequest(MarketingOperationsRequest):
    """Agent 27 request contract."""


class ConsentComplianceReviewPackage(MarketingOperationsPackage):
    """Agent 27 response contract."""


agent27Request = ConsentComplianceReviewRequest
agent27Package = ConsentComplianceReviewPackage
AgentRequest = ConsentComplianceReviewRequest
AgentPackage = ConsentComplianceReviewPackage

__all__ = [
    "agent27Package",
    "agent27Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "MarketingOperationsHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "ConsentComplianceReviewPackage",
    "ConsentComplianceReviewRequest",
    "MetricInput",
    "MetricInsight",
    "OutputSection",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
