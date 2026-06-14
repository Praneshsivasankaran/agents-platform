"""LangGraph state for Agent 03 - Content Ideation Agent."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from .contracts import (
    AudienceInsights,
    BlogBriefForAgent01,
    CampaignSummary,
    ContentIdea,
    ContentIdeationPackage,
    ContentIdeationRequest,
    ContentTheme,
    CtaSuggestion,
    HardFail,
    QualityReport,
    RepurposingBriefForAgent02,
    StageCost,
)


class Agent03State(TypedDict, total=False):
    raw_input: Any
    request_id: str
    request: ContentIdeationRequest

    campaign_summary: CampaignSummary
    audience_insights: AudienceInsights
    content_themes: tuple[ContentTheme, ...]
    content_ideas: tuple[ContentIdea, ...]
    hooks: tuple[str, ...]
    cta_suggestions: tuple[CtaSuggestion, ...]
    blog_brief_for_agent_01: BlogBriefForAgent01
    repurposing_brief_for_agent_02: RepurposingBriefForAgent02
    quality_report: QualityReport
    recommended_next_agent: str
    generation_used_llm: bool

    status: str
    notes: str
    cost_gate_ok: bool
    error_state: dict[str, Any]
    validation_errors: tuple[str, ...]
    request_risk_flags: tuple[str, ...]

    hard_fails: Annotated[list[HardFail], operator.add]
    cost_usage: Annotated[list[StageCost], operator.add]

    final_output: ContentIdeationPackage


ContentIdeationState = Agent03State
