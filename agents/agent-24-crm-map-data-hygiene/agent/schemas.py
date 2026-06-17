"""Typed contracts for Agent 24 - CRM/MAP Data Hygiene Agent."""

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


class CRMMAPDataHygieneRequest(MarketingOperationsRequest):
    """Agent 24 request contract."""


class CRMMAPDataHygienePackage(MarketingOperationsPackage):
    """Agent 24 response contract."""


agent24Request = CRMMAPDataHygieneRequest
agent24Package = CRMMAPDataHygienePackage
AgentRequest = CRMMAPDataHygieneRequest
AgentPackage = CRMMAPDataHygienePackage

__all__ = [
    "agent24Package",
    "agent24Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "MarketingOperationsHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "CRMMAPDataHygienePackage",
    "CRMMAPDataHygieneRequest",
    "MetricInput",
    "MetricInsight",
    "OutputSection",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
