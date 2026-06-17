"""Typed contracts for Agent 16 - Ad Copy Creation Agent."""

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


class AdCopyCreationRequest(DigitalMarketingRequest):
    """Agent 16 request contract."""


class AdCopyCreationPackage(DigitalMarketingPackage):
    """Agent 16 response contract."""


Agent16Request = AdCopyCreationRequest
Agent16Package = AdCopyCreationPackage
AgentRequest = AdCopyCreationRequest
AgentPackage = AdCopyCreationPackage

__all__ = [
    "AdCopyCreationPackage",
    "AdCopyCreationRequest",
    "Agent16Package",
    "Agent16Request",
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
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
