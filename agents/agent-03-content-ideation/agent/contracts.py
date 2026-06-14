"""Typed contracts for Agent 03 - Content Ideation Agent.

Agent 03 produces a structured strategy package for downstream content agents.
Contracts use ``CoreContractModel`` so provider-facing and terminal payloads are
strict, frozen, and safe for the shared structured-output path.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from core import CoreContractModel


Agent03Status = Literal["pass", "needs_more_input", "needs_human", "stopped_cost_ceiling", "error"]
FailureSeverity = Literal["terminal", "retriable", "warning"]
FunnelStage = Literal["awareness", "consideration", "conversion", "retention"]
RecommendedAgent = Literal[
    "Agent 01 - Blog Creation",
    "Agent 02 - Content Repurposing",
    "Agent 04 - Editorial Planning",
    "Human Review",
]
CostTier = Literal["cheap", "strong", "stt", "none"]

QUALITY_PASS_THRESHOLD = 80


TerminalHardFailCode = Literal[
    "missing_required_context",
    "unsupported_numerical_claim",
    "unsafe_marketing_claim",
    "no_usable_idea",
    "missing_blog_brief",
    "missing_repurposing_brief",
    "external_research_claimed",
    "direct_cloud_sdk_import",
]
RetriableFailureCode = Literal[
    "too_generic",
    "duplicate_ideas",
    "weak_cta",
    "weak_audience_fit",
    "low_specificity",
    "low_quality_score",
]
WarningCode = Literal[
    "prompt_injection_attempt",
    "confidential_context_supplied",
    "evidence_placeholder_needed",
    "constraints_present",
]
RiskCode = TerminalHardFailCode | RetriableFailureCode | WarningCode

TERMINAL_HARD_FAIL_CODES: frozenset[str] = frozenset(
    {
        "missing_required_context",
        "unsupported_numerical_claim",
        "unsafe_marketing_claim",
        "no_usable_idea",
        "missing_blog_brief",
        "missing_repurposing_brief",
        "external_research_claimed",
        "direct_cloud_sdk_import",
    }
)
RETRIABLE_FAILURE_CODES: frozenset[str] = frozenset(
    {
        "too_generic",
        "duplicate_ideas",
        "weak_cta",
        "weak_audience_fit",
        "low_specificity",
        "low_quality_score",
    }
)


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _tuple_from_any(value: object) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        raw = value.replace("\n", ",").replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set, frozenset)):
        raw = list(value)
    else:
        raw = (value,)
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = _clean_text(item)
        key = text.lower()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return tuple(cleaned)


class ContentIdeationRequest(CoreContractModel):
    campaign_goal: str = Field(min_length=1)
    product_or_service: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    brand_tone: str = Field(min_length=1)
    key_message: str = Field(min_length=1)
    optional_notes: str | None = None
    optional_keywords: tuple[str, ...] = ()
    optional_content_type_preference: tuple[str, ...] = ()
    optional_constraints: tuple[str, ...] = ()
    number_of_ideas: int = Field(default=8, ge=1, le=20)

    @field_validator(
        "campaign_goal",
        "product_or_service",
        "target_audience",
        "industry",
        "brand_tone",
        "key_message",
        mode="before",
    )
    @classmethod
    def _strip_required(cls, value: object) -> str:
        return _clean_text(value)

    @field_validator("optional_notes", mode="before")
    @classmethod
    def _strip_optional_notes(cls, value: object) -> str | None:
        text = _clean_text(value)
        return text or None

    @field_validator(
        "optional_keywords",
        "optional_content_type_preference",
        "optional_constraints",
        mode="before",
    )
    @classmethod
    def _coerce_tuple(cls, value: object) -> tuple[str, ...]:
        return _tuple_from_any(value)


class CampaignSummary(CoreContractModel):
    campaign_goal: str = Field(default="")
    product_or_service: str = Field(default="")
    industry: str = Field(default="")
    key_message: str = Field(default="")
    brand_tone: str = Field(default="")
    campaign_objective: str = Field(default="")
    value_proposition: str = Field(default="")
    keywords: tuple[str, ...] = ()
    preferred_formats: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()


class AudienceInsights(CoreContractModel):
    target_audience: str = Field(default="")
    pain_points: tuple[str, ...] = ()
    desired_outcome: str = Field(default="")
    awareness_level: str = Field(default="")
    likely_objections: tuple[str, ...] = ()
    content_expectations: tuple[str, ...] = ()


class ContentTheme(CoreContractModel):
    theme_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    strategic_role: str = Field(default="")
    keywords: tuple[str, ...] = ()


class ContentIdea(CoreContractModel):
    idea_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(default="")
    theme_id: str = Field(default="")
    angle: str = Field(min_length=1)
    recommended_format: str = Field(min_length=1)
    funnel_stage: FunnelStage = "awareness"
    audience_fit_reason: str = Field(min_length=1)
    originality_note: str = Field(default="")
    priority_score: int = Field(ge=0, le=100)
    risk_flags: tuple[str, ...] = ()


class LLMContentIdea(CoreContractModel):
    title: str = Field(min_length=1)
    description: str = Field(default="")
    angle: str = Field(min_length=1)
    recommended_format: str = Field(min_length=1)
    funnel_stage: FunnelStage = "awareness"
    audience_fit_reason: str = Field(min_length=1)
    originality_note: str = Field(default="")


class LLMIdeaBundle(CoreContractModel):
    ideas: tuple[LLMContentIdea, ...] = Field(default=())


class CtaSuggestion(CoreContractModel):
    cta_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    fit_reason: str = Field(default="")
    funnel_stage: FunnelStage = "conversion"


class BlogBriefForAgent01(CoreContractModel):
    selected_idea_id: str = Field(min_length=1)
    suggested_title: str = Field(min_length=1)
    title_options: tuple[str, ...] = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    campaign_goal: str = Field(default="")
    content_angle: str = Field(min_length=1)
    core_message: str = Field(min_length=1)
    pain_points: tuple[str, ...] = ()
    value_proposition: str = Field(default="")
    suggested_outline: tuple[str, ...] = Field(min_length=1)
    proof_points_or_placeholders: tuple[str, ...] = ()
    tone: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    keywords: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()


class PlatformDirection(CoreContractModel):
    platform: str = Field(min_length=1)
    direction: str = Field(min_length=1)


class RepurposingBriefForAgent02(CoreContractModel):
    core_message: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    recommended_platforms: tuple[str, ...] = Field(min_length=1)
    platform_direction: tuple[PlatformDirection, ...] = Field(min_length=1)
    hooks: tuple[str, ...] = Field(min_length=1)
    cta: str = Field(min_length=1)
    tone_rules: tuple[str, ...] = Field(min_length=1)
    content_pillars: tuple[str, ...] = Field(min_length=1)
    message_guardrails: tuple[str, ...] = Field(min_length=1)
    repurposing_focus: str = Field(min_length=1)
    risk_flags: tuple[str, ...] = ()


class HardFail(CoreContractModel):
    code: RiskCode
    severity: FailureSeverity
    reason: str = Field(min_length=1)
    idea_id: str | None = None

    @model_validator(mode="after")
    def _severity_matches_code(self) -> "HardFail":
        if self.code in TERMINAL_HARD_FAIL_CODES and self.severity != "terminal":
            raise ValueError(f"{self.code} must be severity='terminal'")
        if self.code in RETRIABLE_FAILURE_CODES and self.severity != "retriable":
            raise ValueError(f"{self.code} must be severity='retriable'")
        if self.code not in TERMINAL_HARD_FAIL_CODES and self.code not in RETRIABLE_FAILURE_CODES:
            if self.severity != "warning":
                raise ValueError(f"{self.code} must be severity='warning'")
        return self


class QualitySubScores(CoreContractModel):
    relevance_to_goal: int = Field(ge=0, le=25)
    audience_fit: int = Field(ge=0, le=20)
    specificity: int = Field(ge=0, le=15)
    downstream_usability: int = Field(ge=0, le=15)
    originality: int = Field(ge=0, le=10)
    brand_fit: int = Field(ge=0, le=10)
    risk_handling: int = Field(ge=0, le=5)


def sum_quality_subscores(sub_scores: QualitySubScores) -> int:
    return (
        sub_scores.relevance_to_goal
        + sub_scores.audience_fit
        + sub_scores.specificity
        + sub_scores.downstream_usability
        + sub_scores.originality
        + sub_scores.brand_fit
        + sub_scores.risk_handling
    )


class QualityReport(CoreContractModel):
    overall_score: int = Field(ge=0, le=100)
    sub_scores: QualitySubScores
    passed: bool
    hard_fails: tuple[HardFail, ...] = ()
    risk_flags: tuple[str, ...] = ()
    improvement_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _score_and_pass_contract(self) -> "QualityReport":
        expected_score = sum_quality_subscores(self.sub_scores)
        if self.overall_score != expected_score:
            raise ValueError("QualityReport.overall_score must equal sub_scores sum")
        expected_pass = self.overall_score >= QUALITY_PASS_THRESHOLD and not self.hard_fails
        if self.passed != expected_pass:
            raise ValueError("QualityReport.passed contradicts threshold/hard-fail contract")
        return self


class StageCost(CoreContractModel):
    stage: str = Field(min_length=1)
    cost_inr: float = Field(ge=0.0)
    tier: CostTier
    tokens_prompt: int = Field(default=0, ge=0)
    tokens_completion: int = Field(default=0, ge=0)


class CostUsage(CoreContractModel):
    stage_costs: tuple[StageCost, ...] = ()
    total_inr: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _total_matches_ledger(self) -> "CostUsage":
        computed = sum(stage.cost_inr for stage in self.stage_costs)
        if abs(computed - self.total_inr) > 0.01:
            raise ValueError("CostUsage.total_inr must equal sum(stage_costs.cost_inr)")
        return self


class ContentIdeationPackage(CoreContractModel):
    status: Agent03Status
    package_id: str = Field(default="")
    campaign_summary: CampaignSummary | None = None
    audience_insights: AudienceInsights | None = None
    content_themes: tuple[ContentTheme, ...] = ()
    content_ideas: tuple[ContentIdea, ...] = ()
    hooks: tuple[str, ...] = ()
    cta_suggestions: tuple[CtaSuggestion, ...] = ()
    recommended_formats: tuple[str, ...] = ()
    quality_score: int = Field(default=0, ge=0, le=100)
    quality_notes: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    blog_brief_for_agent_01: BlogBriefForAgent01 | None = None
    repurposing_brief_for_agent_02: RepurposingBriefForAgent02 | None = None
    recommended_next_agent: RecommendedAgent = "Human Review"
    quality_report: QualityReport | None = None
    cost: CostUsage
    notes: str = Field(default="")
    generation_used_llm: bool = False

    @model_validator(mode="after")
    def _package_contract(self) -> "ContentIdeationPackage":
        if self.quality_report is not None and self.quality_score != self.quality_report.overall_score:
            raise ValueError("quality_score must mirror quality_report.overall_score")
        if self.status == "pass":
            if not self.content_ideas:
                raise ValueError("Passed package requires content_ideas")
            if self.blog_brief_for_agent_01 is None:
                raise ValueError("Passed package requires blog_brief_for_agent_01")
            if self.repurposing_brief_for_agent_02 is None:
                raise ValueError("Passed package requires repurposing_brief_for_agent_02")
            if self.quality_report is None or not self.quality_report.passed:
                raise ValueError("Passed package requires passing quality_report")
        return self


class BillableNodeError(Exception):
    """A node failed after a billable provider call and must preserve cost."""

    def __init__(self, stage_cost: StageCost, cause: Exception) -> None:
        self.stage_cost = stage_cost
        self.cause = cause
        super().__init__(f"BillableNodeError wrapping {type(cause).__name__}")


# Compatibility aliases for scaffold-style imports.
Agent03Request = ContentIdeationRequest
Agent03Package = ContentIdeationPackage
