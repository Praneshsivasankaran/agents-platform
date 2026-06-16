"""LangGraph state for Agent 04 - SEO Optimization Agent."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from .schemas import (
    Agent04Request,
    CostUsage,
    DraftAnalysis,
    FAQBundle,
    HeadingPlan,
    KeywordPlan,
    MetadataPackage,
    OptimizedDraftPackage,
    ReadabilityReport,
    RiskReport,
    SEOOptimizationPackage,
    SEOScore,
    StageCost,
)


class Agent04State(TypedDict, total=False):
    raw_input: dict[str, Any]
    request_id: str
    request: Agent04Request
    normalized_draft: str
    analysis: DraftAnalysis
    keyword_plan: KeywordPlan
    metadata: MetadataPackage
    heading_plan: HeadingPlan
    readability: ReadabilityReport
    faq_bundle: FAQBundle
    optimized: OptimizedDraftPackage
    risk_report: RiskReport
    seo_score: SEOScore
    generation_used_llm: bool
    cost_usage: Annotated[list[StageCost], operator.add]
    cost: CostUsage
    cost_gate_ok: bool
    status: str
    notes: str
    validation_errors: tuple[str, ...]
    error_state: dict[str, Any]
    final_output: SEOOptimizationPackage


# Compatibility alias following generated scaffold naming.
SeoOptimizerState = Agent04State
