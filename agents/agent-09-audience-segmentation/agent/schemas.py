"""Typed contracts for Agent 09 - Audience Segmentation Agent."""

from __future__ import annotations

from demand_generation.schemas import (
    CostUsage,
    DemandGenHandoff,
    DemandGenPackage,
    DemandGenRequest,
    EvidenceItem,
    FunnelStageInput,
    GeneratedRecommendation,
    MetricInput,
    MetricInsight,
    QualityDimensionScore,
    QualityReport,
    RiskFlag,
    StageCost,
)


class AudienceSegmentationRequest(DemandGenRequest):
    """Agent 09 request contract."""


class AudienceSegmentationPackage(DemandGenPackage):
    """Agent 09 response contract."""


Agent09Request = AudienceSegmentationRequest
Agent09Package = AudienceSegmentationPackage
AgentRequest = AudienceSegmentationRequest
AgentPackage = AudienceSegmentationPackage

__all__ = [
    "Agent09Package",
    "Agent09Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "DemandGenHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "AudienceSegmentationPackage",
    "AudienceSegmentationRequest",
    "MetricInput",
    "MetricInsight",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]