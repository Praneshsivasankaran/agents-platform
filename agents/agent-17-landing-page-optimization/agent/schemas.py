"""Typed contracts for Agent 17 - Landing Page Optimization Agent."""

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


class LandingPageOptimizationRequest(DigitalMarketingRequest):
    """Agent 17 request contract."""


class LandingPageOptimizationPackage(DigitalMarketingPackage):
    """Agent 17 response contract."""


Agent17Request = LandingPageOptimizationRequest
Agent17Package = LandingPageOptimizationPackage
AgentRequest = LandingPageOptimizationRequest
AgentPackage = LandingPageOptimizationPackage

__all__ = [
    "Agent17Package",
    "Agent17Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DigitalMarketingHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "LandingPageOptimizationPackage",
    "LandingPageOptimizationRequest",
    "MetricInput",
    "MetricInsight",
    "OutputSection",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
