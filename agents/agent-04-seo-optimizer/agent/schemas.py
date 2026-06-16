"""Typed contracts for Agent 04 - SEO Optimization Agent.

All provider-facing and terminal payloads subclass CoreContractModel so the
shared structured-output validator can enforce strict, frozen, deeply immutable
schemas before provider calls. Use tuples and nested CoreContractModel objects,
never mutable list/dict/set fields, in structured contracts.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from core import CoreContractModel


Agent04Status = Literal["pass", "needs_more_input", "needs_human", "stopped_cost_ceiling", "error"]
PassStatus = Literal["pass", "fail"]
CostTier = Literal["cheap", "strong", "stt", "none"]
HeadingLevel = Literal["h1", "h2", "h3"]
RiskSeverity = Literal["hard_fail", "warning"]

QUALITY_PASS_THRESHOLD = 80

RiskCode = Literal[
    "keyword_stuffing",
    "missing_primary_keyword",
    "missing_metadata",
    "weak_heading_structure",
    "weak_cta",
    "unsupported_claims",
    "prompt_injection_marker",
    "empty_faq_output",
    "overly_generic_output",
    "excessive_repetition",
    "meaning_drift_warning",
    "missing_optimized_draft",
    "missing_title_options",
    "missing_meta_description",
    "missing_slug",
    "empty_or_invalid_output",
]

HARD_FAIL_CODES: frozenset[str] = frozenset(
    {
        "missing_primary_keyword",
        "unsupported_claims",
        "meaning_drift_warning",
        "missing_optimized_draft",
        "missing_title_options",
        "missing_meta_description",
        "missing_slug",
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


class Agent04Request(CoreContractModel):
    draft_content: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    primary_keyword: str = Field(min_length=1)
    secondary_keywords: tuple[str, ...] = ()
    target_audience: str = Field(default="")
    content_goal: str = Field(default="")
    brand_tone: str = Field(default="clear, practical, confident")
    constraints: tuple[str, ...] = ()
    cta_direction: str = Field(default="")

    @field_validator("draft_content", "topic", "primary_keyword", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> str:
        return _clean_text(value)

    @field_validator("target_audience", "content_goal", "brand_tone", "cta_direction", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: object) -> str:
        return _clean_text(value)

    @field_validator("secondary_keywords", "constraints", mode="before")
    @classmethod
    def _coerce_tuple(cls, value: object) -> tuple[str, ...]:
        return _tuple_from_any(value)


class DraftAnalysis(CoreContractModel):
    word_count: int = Field(ge=0)
    existing_headings: tuple[str, ...] = ()
    current_title: str = Field(default="")
    intro_present: bool = False
    cta_present: bool = False
    primary_keyword_present: bool = False
    primary_keyword_density: float = Field(ge=0.0)
    readability_score: int = Field(ge=0, le=100)
    summary: str = Field(default="")
    issues: tuple[str, ...] = ()


class KeywordPlacement(CoreContractModel):
    keyword: str = Field(min_length=1)
    present: bool
    density: float = Field(ge=0.0)
    suggested_locations: tuple[str, ...] = ()


class KeywordPlan(CoreContractModel):
    primary_keyword: str = Field(min_length=1)
    secondary_keywords: tuple[str, ...] = ()
    placements: tuple[KeywordPlacement, ...] = ()
    natural_usage_notes: tuple[str, ...] = ()


class MetadataPackage(CoreContractModel):
    seo_title_options: tuple[str, ...] = Field(min_length=1)
    meta_description: str = Field(min_length=1)
    url_slug: str = Field(min_length=1)
    recommended_h1: str = Field(min_length=1)


class HeadingItem(CoreContractModel):
    level: HeadingLevel
    text: str = Field(min_length=1)
    reason: str = Field(default="")


class HeadingPlan(CoreContractModel):
    recommended_h1: str = Field(min_length=1)
    h2_h3_plan: tuple[HeadingItem, ...] = Field(min_length=1)
    notes: tuple[str, ...] = ()


class ReadabilityReport(CoreContractModel):
    readability_score: int = Field(ge=0, le=100)
    reading_level: str = Field(min_length=1)
    fixes: tuple[str, ...] = ()
    intro_improvement: str = Field(default="")
    conclusion_improvement: str = Field(default="")
    cta_suggestion: str = Field(default="")


class FAQItem(CoreContractModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)


class FAQBundle(CoreContractModel):
    faqs: tuple[FAQItem, ...] = Field(min_length=1)


class OptimizedDraftPackage(CoreContractModel):
    optimized_draft: str = Field(min_length=1)
    editor_notes: tuple[str, ...] = ()


class RiskFlag(CoreContractModel):
    code: RiskCode
    severity: RiskSeverity
    message: str = Field(min_length=1)

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


class SEOScore(CoreContractModel):
    metadata_quality: int = Field(ge=0, le=20)
    keyword_usage: int = Field(ge=0, le=20)
    heading_structure: int = Field(ge=0, le=15)
    readability: int = Field(ge=0, le=15)
    content_goal_alignment: int = Field(ge=0, le=10)
    faq_usefulness: int = Field(ge=0, le=10)
    risk_safety: int = Field(ge=0, le=10)
    total_score: int = Field(ge=0, le=100)
    passed: bool
    hard_fail_codes: tuple[RiskCode, ...] = ()

    @model_validator(mode="after")
    def _score_contract(self) -> "SEOScore":
        expected = (
            self.metadata_quality
            + self.keyword_usage
            + self.heading_structure
            + self.readability
            + self.content_goal_alignment
            + self.faq_usefulness
            + self.risk_safety
        )
        if self.total_score != expected:
            raise ValueError("SEOScore.total_score must equal subscore sum")
        expected_pass = self.total_score >= QUALITY_PASS_THRESHOLD and not self.hard_fail_codes
        if self.passed != expected_pass:
            raise ValueError("SEOScore.passed contradicts threshold/hard-fail contract")
        return self


class SEOOptimizationPackage(CoreContractModel):
    status: Agent04Status
    package_id: str = Field(default="")
    seo_score: SEOScore | None = None
    pass_status: PassStatus = "fail"
    title_options: tuple[str, ...] = ()
    meta_description: str = Field(default="")
    url_slug: str = Field(default="")
    recommended_h1: str = Field(default="")
    heading_plan: tuple[HeadingItem, ...] = ()
    keyword_placement: tuple[KeywordPlacement, ...] = ()
    readability_fixes: tuple[str, ...] = ()
    intro_improvement: str = Field(default="")
    conclusion_improvement: str = Field(default="")
    cta_suggestion: str = Field(default="")
    faq_suggestions: tuple[FAQItem, ...] = ()
    risk_flags: tuple[RiskFlag, ...] = ()
    editor_notes: tuple[str, ...] = ()
    optimized_draft: str = Field(default="")
    cost: CostUsage
    notes: str = Field(default="")
    generation_used_llm: bool = False

    @model_validator(mode="after")
    def _package_contract(self) -> "SEOOptimizationPackage":
        if self.seo_score is not None:
            expected_status = "pass" if self.seo_score.passed else "fail"
            if self.pass_status != expected_status:
                raise ValueError("pass_status must mirror seo_score.passed")
        if self.status == "pass":
            if self.seo_score is None or not self.seo_score.passed:
                raise ValueError("Passed package requires a passing SEOScore")
            required = (
                self.title_options,
                self.meta_description,
                self.url_slug,
                self.recommended_h1,
                self.heading_plan,
                self.optimized_draft,
            )
            if not all(required):
                raise ValueError("Passed package is missing required SEO output fields")
        return self


class BillableNodeError(Exception):
    """A node failed after a billable provider call and must preserve cost."""

    def __init__(self, stage_cost: StageCost, cause: Exception) -> None:
        self.stage_cost = stage_cost
        self.cause = cause
        super().__init__(f"BillableNodeError wrapping {type(cause).__name__}")


# Compatibility alias following generated scaffold naming.
SeoOptimizerPackage = SEOOptimizationPackage
