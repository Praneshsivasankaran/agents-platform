"""Typed contracts for Agent 20 - Conversion Rate Optimization Agent."""

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


class ConversionRateOptimizationRequest(DigitalMarketingRequest):
    """Agent 20 request contract."""


class ConversionRateOptimizationPackage(DigitalMarketingPackage):
    """Agent 20 response contract."""


Agent20Request = ConversionRateOptimizationRequest
Agent20Package = ConversionRateOptimizationPackage
AgentRequest = ConversionRateOptimizationRequest
AgentPackage = ConversionRateOptimizationPackage

__all__ = [
    "Agent20Package",
    "Agent20Request",
    "AgentPackage",
    "AgentRequest",
    "ConversionRateOptimizationPackage",
    "ConversionRateOptimizationRequest",
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
