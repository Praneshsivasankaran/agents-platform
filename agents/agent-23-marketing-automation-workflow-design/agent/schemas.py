"""Typed contracts for Agent 23 - Marketing Automation Workflow Design Agent."""

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


class MarketingAutomationWorkflowDesignRequest(MarketingOperationsRequest):
    """Agent 23 request contract."""


class MarketingAutomationWorkflowDesignPackage(MarketingOperationsPackage):
    """Agent 23 response contract."""


agent23Request = MarketingAutomationWorkflowDesignRequest
agent23Package = MarketingAutomationWorkflowDesignPackage
AgentRequest = MarketingAutomationWorkflowDesignRequest
AgentPackage = MarketingAutomationWorkflowDesignPackage

__all__ = [
    "agent23Package",
    "agent23Request",
    "AgentPackage",
    "AgentRequest",
    "CostUsage",
    "MarketingOperationsHandoff",
    "EvidenceItem",
    "FunnelStageInput",
    "GeneratedRecommendation",
    "MarketingAutomationWorkflowDesignPackage",
    "MarketingAutomationWorkflowDesignRequest",
    "MetricInput",
    "MetricInsight",
    "OutputSection",
    "QualityDimensionScore",
    "QualityReport",
    "RiskFlag",
    "StageCost",
]
