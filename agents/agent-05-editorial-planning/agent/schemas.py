"""Typed contracts for Agent 05 - Editorial Planning Agent.

All provider-facing and terminal payloads subclass CoreContractModel so the
shared structured-output validator can enforce strict, frozen, deeply immutable
schemas before provider calls. Use tuples and nested CoreContractModel objects,
never mutable list/dict/set fields, in structured contracts.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from core import CoreContractModel


Agent05Status = Literal[
    "pass",
    "needs_more_input",
    "needs_human",
    "needs_review_budget_limited",
    "stopped_cost_ceiling",
    "error",
]
PassStatus = Literal["pass", "fail"]
CostTier = Literal["cheap", "strong", "stt", "none"]
RiskSeverity = Literal["hard_fail", "warning"]
Priority = Literal["high", "medium", "low"]
Cadence = Literal["daily", "weekly", "monthly", "custom"]

QUALITY_PASS_THRESHOLD = 80

RiskCode = Literal[
    "missing_editorial_calendar",
    "missing_content_briefs",
    "platform_list_ignored",
    "date_range_not_respected",
    "posting_frequency_not_respected",
    "external_action_claimed",
    "fabricated_analytics",
    "prompt_injection_marker",
    "unsafe_or_unsupported_claims",
    "empty_or_invalid_output",
    "impossible_or_overdense_cadence",
    "date_range_gaps",
    "missing_platform_coverage",
    "platform_overuse",
    "underused_content_pillars",
    "duplicated_topics",
    "missing_cta_direction",
    "weak_goal_alignment",
    "vague_or_unactionable_briefs",
    "sensitive_topic_review",
    "thin_repurposing_map",
]

HARD_FAIL_CODES: frozenset[str] = frozenset(
    {
        "missing_editorial_calendar",
        "missing_content_briefs",
        "platform_list_ignored",
        "date_range_not_respected",
        "posting_frequency_not_respected",
        "external_action_claimed",
        "fabricated_analytics",
        "unsafe_or_unsupported_claims",
        "empty_or_invalid_output",
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
        raw = tuple(value)
    else:
        raw = (value,)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = _clean_text(item)
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return tuple(out)


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


class DateRange(CoreContractModel):
    start: str = Field(min_length=10, max_length=10)
    end: str = Field(min_length=10, max_length=10)

    @field_validator("start", "end", mode="before")
    @classmethod
    def _strip_date(cls, value: object) -> str:
        return _clean_text(value)


class PostingFrequency(CoreContractModel):
    cadence: Cadence = "weekly"
    count_per_week: int = Field(default=3, ge=0, le=21)
    count_per_month: int = Field(default=8, ge=0, le=120)
    total_posts: int = Field(default=0, ge=0, le=365)


class Agent05Request(CoreContractModel):
    brand_name: str = Field(min_length=1)
    business_goal: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    campaign_theme: str = Field(min_length=1)
    platforms: tuple[str, ...] = Field(min_length=1)
    date_range: DateRange
    posting_frequency: PostingFrequency = PostingFrequency()
    brand_voice: str = Field(min_length=1)
    content_pillars: tuple[str, ...] = Field(min_length=1)
    existing_ideas: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    priority_platforms: tuple[str, ...] = ()
    excluded_topics: tuple[str, ...] = ()
    key_products: tuple[str, ...] = ()
    important_dates: tuple[str, ...] = ()
    approval_lead_time_days: int = Field(default=5, ge=0, le=60)
    production_capacity_per_week: int = Field(default=0, ge=0, le=100)
    regional_preferences: tuple[str, ...] = ()

    @field_validator(
        "brand_name",
        "business_goal",
        "target_audience",
        "campaign_theme",
        "brand_voice",
        mode="before",
    )
    @classmethod
    def _strip_required(cls, value: object) -> str:
        return _clean_text(value)

    @field_validator(
        "platforms",
        "content_pillars",
        "existing_ideas",
        "constraints",
        "priority_platforms",
        "excluded_topics",
        "key_products",
        "important_dates",
        "regional_preferences",
        mode="before",
    )
    @classmethod
    def _coerce_tuple(cls, value: object) -> tuple[str, ...]:
        return _tuple_from_any(value)


class CalendarSlot(CoreContractModel):
    slot_id: str = Field(min_length=1)
    planned_date: str = Field(min_length=10)
    platform: str = Field(min_length=1)
    pillar: str = Field(min_length=1)
    sequence: int = Field(ge=1)


class PlatformPlan(CoreContractModel):
    platform: str = Field(min_length=1)
    role: str = Field(min_length=1)
    recommended_content_types: tuple[str, ...] = Field(min_length=1)
    cadence_notes: str = Field(min_length=1)
    cta_guidance: str = Field(min_length=1)


class PlatformStrategyPackage(CoreContractModel):
    platform_plans: tuple[PlatformPlan, ...] = Field(min_length=1)
    notes: tuple[str, ...] = ()


class TopicPlanItem(CoreContractModel):
    slot_id: str = Field(min_length=1)
    planned_date: str = Field(min_length=10)
    platform: str = Field(min_length=1)
    pillar: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    suggested_title: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    primary_cta: str = Field(min_length=1)
    priority: Priority
    rationale: str = Field(default="")


class TopicPlanPackage(CoreContractModel):
    items: tuple[TopicPlanItem, ...] = Field(min_length=1)


class ContentBrief(CoreContractModel):
    brief_id: str = Field(min_length=1)
    calendar_item_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    key_message: str = Field(min_length=1)
    outline: tuple[str, ...] = Field(min_length=1)
    cta_suggestions: tuple[str, ...] = Field(min_length=1)
    constraints: tuple[str, ...] = ()
    review_notes: tuple[str, ...] = ()


class ContentBriefPackage(CoreContractModel):
    briefs: tuple[ContentBrief, ...] = Field(min_length=1)


class EditorialCalendarItem(CoreContractModel):
    brief_id: str = Field(min_length=1)
    planned_date: str = Field(min_length=10)
    internal_due_date: str = Field(min_length=10)
    platform: str = Field(min_length=1)
    pillar: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    suggested_title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    primary_cta: str = Field(min_length=1)
    priority: Priority


class CTARecommendation(CoreContractModel):
    calendar_item_id: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    reason: str = Field(default="")


class RepurposingMapItem(CoreContractModel):
    source_brief_id: str = Field(min_length=1)
    source_platform: str = Field(min_length=1)
    target_platform: str = Field(min_length=1)
    repurposed_format: str = Field(min_length=1)
    adaptation_note: str = Field(min_length=1)


class RepurposingMapPackage(CoreContractModel):
    items: tuple[RepurposingMapItem, ...] = ()


class CountItem(CoreContractModel):
    name: str = Field(min_length=1)
    count: int = Field(ge=0)


class PeriodPlan(CoreContractModel):
    period_label: str = Field(min_length=1)
    start_date: str = Field(min_length=10)
    end_date: str = Field(min_length=10)
    planned_items: int = Field(ge=0)
    focus: str = Field(min_length=1)
    platforms: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class PlatformPlanSummary(CoreContractModel):
    platform: str = Field(min_length=1)
    planned_count: int = Field(ge=0)
    primary_objective: str = Field(min_length=1)
    content_types: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class BalanceGapAnalysis(CoreContractModel):
    pillar_counts: tuple[CountItem, ...] = ()
    platform_counts: tuple[CountItem, ...] = ()
    content_type_counts: tuple[CountItem, ...] = ()
    pillar_balance_notes: tuple[str, ...] = ()
    platform_balance_notes: tuple[str, ...] = ()
    content_type_notes: tuple[str, ...] = ()
    gap_summary: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()


class RiskFlag(CoreContractModel):
    code: RiskCode
    severity: RiskSeverity
    message: str = Field(min_length=1)
    affected_items: tuple[str, ...] = ()
    recommended_fix: str = Field(default="")

    @model_validator(mode="after")
    def _severity_matches_code(self) -> "RiskFlag":
        if self.code in HARD_FAIL_CODES and self.severity != "hard_fail":
            raise ValueError(f"{self.code} must use severity='hard_fail'")
        if self.code not in HARD_FAIL_CODES and self.severity != "warning":
            raise ValueError(f"{self.code} must use severity='warning'")
        return self


class RiskReport(CoreContractModel):
    risk_flags: tuple[RiskFlag, ...] = ()
    hard_fail_codes: tuple[RiskCode, ...] = ()
    passed: bool

    @model_validator(mode="after")
    def _passed_contract(self) -> "RiskReport":
        expected = tuple(flag.code for flag in self.risk_flags if flag.severity == "hard_fail")
        if self.hard_fail_codes != expected:
            raise ValueError("RiskReport.hard_fail_codes must mirror hard-fail risk flags")
        if self.passed != (not expected):
            raise ValueError("RiskReport.passed contradicts hard-fail risks")
        return self


class EditorialQualityScore(CoreContractModel):
    input_completeness: int = Field(ge=0, le=10)
    calendar_coverage: int = Field(ge=0, le=15)
    audience_goal_alignment: int = Field(ge=0, le=15)
    platform_fit: int = Field(ge=0, le=15)
    pillar_balance: int = Field(ge=0, le=10)
    brief_actionability: int = Field(ge=0, le=15)
    repurposing_usefulness: int = Field(ge=0, le=10)
    risk_safety: int = Field(ge=0, le=10)
    total_score: int = Field(ge=0, le=100)
    passed: bool
    hard_fail_codes: tuple[RiskCode, ...] = ()

    @model_validator(mode="after")
    def _score_contract(self) -> "EditorialQualityScore":
        expected = (
            self.input_completeness
            + self.calendar_coverage
            + self.audience_goal_alignment
            + self.platform_fit
            + self.pillar_balance
            + self.brief_actionability
            + self.repurposing_usefulness
            + self.risk_safety
        )
        if self.total_score != expected:
            raise ValueError("EditorialQualityScore.total_score must equal subscore sum")
        expected_pass = self.total_score >= QUALITY_PASS_THRESHOLD and not self.hard_fail_codes
        if self.passed != expected_pass:
            raise ValueError("EditorialQualityScore.passed contradicts threshold/hard-fail contract")
        return self


class EditorialPlanningPackage(CoreContractModel):
    status: Agent05Status
    package_id: str = Field(default="")
    request_summary: str = Field(default="")
    quality_score: EditorialQualityScore | None = None
    pass_status: PassStatus = "fail"
    editorial_calendar: tuple[EditorialCalendarItem, ...] = ()
    weekly_plan: tuple[PeriodPlan, ...] = ()
    monthly_plan: tuple[PeriodPlan, ...] = ()
    platform_plan: tuple[PlatformPlanSummary, ...] = ()
    content_briefs: tuple[ContentBrief, ...] = ()
    cta_recommendations: tuple[CTARecommendation, ...] = ()
    repurposing_map: tuple[RepurposingMapItem, ...] = ()
    balance_gap_analysis: BalanceGapAnalysis | None = None
    risk_flags: tuple[RiskFlag, ...] = ()
    review_notes: tuple[str, ...] = ()
    cost: CostUsage
    notes: str = Field(default="")
    generation_used_llm: bool = False

    @model_validator(mode="after")
    def _package_contract(self) -> "EditorialPlanningPackage":
        if self.quality_score is not None:
            expected_status = "pass" if self.quality_score.passed else "fail"
            if self.pass_status != expected_status:
                raise ValueError("pass_status must mirror quality_score.passed")
        if self.status == "pass":
            if self.quality_score is None or not self.quality_score.passed:
                raise ValueError("Passed package requires a passing EditorialQualityScore")
            required = (
                self.editorial_calendar,
                self.weekly_plan,
                self.platform_plan,
                self.content_briefs,
            )
            if not all(required):
                raise ValueError("Passed package is missing required editorial planning output fields")
        return self


class BillableNodeError(Exception):
    """A node failed after a billable provider call and must preserve cost."""

    def __init__(self, stage_cost: StageCost, cause: Exception) -> None:
        self.stage_cost = stage_cost
        self.cause = cause
        super().__init__(f"BillableNodeError wrapping {type(cause).__name__}")


# Compatibility aliases following generated scaffold naming.
EditorialPlannerPackage = EditorialPlanningPackage

