"""Shared Demand Generation support for Agents 08-14.

This package contains cloud-neutral helpers only. Agents still expose their own
schemas, prompts, scoring, workflow, and service files, but the repeated
Demand Generation family mechanics live here to keep Phase 3 consistent.
"""

from __future__ import annotations

from .profiles import AgentProfile, get_profile
from .schemas import (
    CostUsage,
    DemandGenHandoff,
    DemandGenPackage,
    DemandGenRequest,
    EvidenceItem,
    FunnelStageInput,
    MetricInsight,
    MetricInput,
    QualityReport,
    RiskFlag,
    StageCost,
)
from .workflow import build_graph

__all__ = [
    "AgentProfile",
    "CostUsage",
    "DemandGenHandoff",
    "DemandGenPackage",
    "DemandGenRequest",
    "EvidenceItem",
    "FunnelStageInput",
    "MetricInsight",
    "MetricInput",
    "QualityReport",
    "RiskFlag",
    "StageCost",
    "build_graph",
    "get_profile",
]

