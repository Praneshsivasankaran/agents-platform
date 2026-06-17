"""Typed contracts for Agent 26 - Lead Routing & SLA Design Agent."""

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


class LeadRoutingSLADesignRequest(MarketingOperationsRequest):
    """Agent 26 request contract."""


class LeadRoutingSLADesignPackage(MarketingOperationsPackage):
    """Agent 26 response contract."""


agent26Request = LeadRoutingSLADesignRequest
agent26Package = LeadRoutingSLADesignPackage
AgentRequest = LeadRoutingSLADesignRequest
AgentPackage = LeadRoutingSLADesignPackage

__all__ = [
    "agent26Package",
    "agent26Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "MarketingOperationsHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "LeadRoutingSLADesignPackage",
    "LeadRoutingSLADesignRequest",
    "MetricInput",
    "MetricInsight",
    "OutputSection",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
