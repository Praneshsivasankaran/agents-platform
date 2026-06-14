"""LangGraph state for Agent 02 - Content Repurposing Agent."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from .schemas import (
    Agent02Request,
    AudienceValue,
    ContentAngle,
    CoreMessage,
    FactualConsistencyReport,
    HardFail,
    ParsedSource,
    PlatformDraft,
    PlatformRules,
    PlatformStrategy,
    PlatformValidationResult,
    QualityReport,
    RepurposedContentPackage,
    StageCost,
    UsefulnessReport,
)


class Agent02State(TypedDict, total=False):
    raw_input: Any
    input_type: str
    request_id: str
    request: Agent02Request

    parsed_source: ParsedSource
    core_message: CoreMessage
    audience_value: AudienceValue
    content_angles: tuple[ContentAngle, ...]
    platform_strategy: tuple[PlatformStrategy, ...]
    platform_rules: tuple[PlatformRules, ...]
    platform_drafts: tuple[PlatformDraft, ...]
    platform_validation_report: tuple[PlatformValidationResult, ...]
    factual_consistency_report: FactualConsistencyReport
    usefulness_report: UsefulnessReport
    quality_report: QualityReport
    markdown_review_package: str
    output_package_uri: str | None

    revision_count: int
    status: str
    notes: str
    cost_gate_ok: bool
    error_state: dict[str, Any]

    hard_fails: Annotated[list[HardFail], operator.add]
    cost_usage: Annotated[list[StageCost], operator.add]

    final_output: RepurposedContentPackage


# Compatibility alias with the generated scaffold naming.
ContentRepurposerState = Agent02State
