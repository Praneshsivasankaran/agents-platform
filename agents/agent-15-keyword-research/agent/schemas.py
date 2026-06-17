"""Typed contracts for Agent 15 - Keyword Research Agent."""

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


class KeywordResearchRequest(DigitalMarketingRequest):
    """Agent 15 request contract."""


class KeywordResearchPackage(DigitalMarketingPackage):
    """Agent 15 response contract."""


Agent15Request = KeywordResearchRequest
Agent15Package = KeywordResearchPackage
AgentRequest = KeywordResearchRequest
AgentPackage = KeywordResearchPackage

__all__ = [
    "Agent15Package",
    "Agent15Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DigitalMarketingHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "KeywordResearchPackage",
    "KeywordResearchRequest",
    "MetricInput",
    "MetricInsight",
    "OutputSection",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
