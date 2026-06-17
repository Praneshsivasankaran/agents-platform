"""Typed contracts for Agent 21 - Performance Reporting Agent."""

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


class PerformanceReportingRequest(DigitalMarketingRequest):
    """Agent 21 request contract."""


class PerformanceReportingPackage(DigitalMarketingPackage):
    """Agent 21 response contract."""


Agent21Request = PerformanceReportingRequest
Agent21Package = PerformanceReportingPackage
AgentRequest = PerformanceReportingRequest
AgentPackage = PerformanceReportingPackage

__all__ = [
    "Agent21Package",
    "Agent21Request",
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
    "PerformanceReportingPackage",
    "PerformanceReportingRequest",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
