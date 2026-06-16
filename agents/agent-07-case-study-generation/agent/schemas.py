"""Typed contracts for Agent 07 - Case Study Generation Agent."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from core import CoreContractModel


Agent07Status = Literal["approve", "revise", "reject"]
PassStatus = Literal["pass", "fail"]
CostTier = Literal["cheap", "strong", "stt", "none"]
RiskSeverity = Literal["low", "medium", "high", "hard_fail"]
OutputLength = Literal["short", "standard", "long"]
Tone = Literal["professional", "executive", "technical", "conversational"]
MetricConfidence = Literal["high", "medium", "low"]

QUALITY_PASS_THRESHOLD = 80
APPROVE_THRESHOLD = 85
REVISE_MIN_THRESHOLD = 65

RiskCategory = Literal[
    "unsupported_claim",
    "invented_metric",
    "quote_risk",
    "confidentiality",
    "pii",
    "legal_review",
    "brand_risk",
    "missing_required_context",
    "external_action",
    "prompt_injection",
]


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
    cost_ceiling_inr: float = Field(default=25.0, ge=0.0)

    @model_validator(mode="after")
    def _total_matches_ledger(self) -> "CostUsage":
        computed = sum(stage.cost_inr for stage in self.stage_costs)
        if abs(computed - self.total_inr) > 0.01:
            raise ValueError("CostUsage.total_inr must equal sum(stage_costs.cost_inr)")
        if self.total_inr > self.cost_ceiling_inr + 0.01:
            raise ValueError("CostUsage.total_inr cannot exceed cost_ceiling_inr")
        return self


class MetricInput(CoreContractModel):
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    baseline: str | None = None
    after: str | None = None
    source: str | None = None

    @field_validator("label", "value", "baseline", "after", "source", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str | None:
        cleaned = _clean_text(value)
        return cleaned or None


class CaseStudyRequest(CoreContractModel):
    customer_name: str | None = None
    anonymize_customer: bool = False
    industry: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    challenge: str = Field(min_length=1)
    solution_summary: str = Field(min_length=1)
    results: str = Field(min_length=1)
    product_or_service: str | None = None
    implementation_notes: str | None = None
    metrics: tuple[MetricInput, ...] = ()
    customer_quotes: tuple[str, ...] = ()
    source_notes: str | None = None
    brand_voice: str | None = None
    tone: Tone = "professional"
    cta_goal: str | None = None
    output_length: OutputLength = "standard"
    provider: str | None = None
    max_cost_rs: float | None = Field(default=None, ge=0.0)

    @field_validator(
        "customer_name",
        "industry",
        "target_audience",
        "challenge",
        "solution_summary",
        "results",
        "product_or_service",
        "implementation_notes",
        "source_notes",
        "brand_voice",
        "cta_goal",
        "provider",
        mode="before",
    )
    @classmethod
    def _strip_strings(cls, value: object) -> str | None:
        cleaned = _clean_text(value)
        return cleaned or None

    @field_validator("customer_quotes", mode="before")
    @classmethod
    def _coerce_quotes(cls, value: object) -> tuple[str, ...]:
        return _tuple_from_any(value)

    @field_validator("metrics", mode="before")
    @classmethod
    def _coerce_metrics(cls, value: object) -> tuple[MetricInput, ...]:
        if value is None or value == "":
            return ()
        if isinstance(value, MetricInput):
            return (value,)
        if isinstance(value, dict):
            return (MetricInput.model_validate(value),)
        if isinstance(value, (list, tuple)):
            return tuple(MetricInput.model_validate(item) for item in value)
        raise ValueError("metrics must be an object or a list of metric objects")


class NormalizedCaseStudyContext(CoreContractModel):
    customer_label: str = Field(min_length=1)
    public_customer_usage: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    challenge_summary: str = Field(min_length=1)
    solution_summary: str = Field(min_length=1)
    results_summary: str = Field(min_length=1)
    implementation_summary: str = Field(min_length=1)
    tone: Tone
    cta_goal: str = Field(min_length=1)
    confidentiality_note: str = Field(default="")


class MetricHighlight(CoreContractModel):
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    evidence: str | None = None
    confidence: MetricConfidence


class EvidenceMap(CoreContractModel):
    metric_highlights: tuple[MetricHighlight, ...] = ()
    supplied_quotes: tuple[str, ...] = ()
    evidence_notes: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()


class MissingInfoWarning(CoreContractModel):
    field: str = Field(min_length=1)
    severity: Literal["low", "medium", "high"]
    message: str = Field(min_length=1)


class RiskFlag(CoreContractModel):
    category: RiskCategory
    severity: RiskSeverity
    message: str = Field(min_length=1)
    evidence_needed: str | None = None


class OutlineSection(CoreContractModel):
    section_id: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    evidence_needed: tuple[str, ...] = ()


class CaseStudyPlan(CoreContractModel):
    story_angle: str = Field(min_length=1)
    narrative_thesis: str = Field(min_length=1)
    recommended_title: str = Field(min_length=1)
    title_options: tuple[str, ...] = Field(min_length=3)
    outline_sections: tuple[OutlineSection, ...] = Field(min_length=6)


class CaseStudyDraft(CoreContractModel):
    executive_summary: str = Field(min_length=1)
    customer_background: str = Field(min_length=1)
    challenge_section: str = Field(min_length=1)
    solution_section: str = Field(min_length=1)
    implementation_section: str = Field(min_length=1)
    results_section: str = Field(min_length=1)
    cta_section: str = Field(min_length=1)
    final_markdown_draft: str = Field(min_length=1)


class QuoteCtaPackage(CoreContractModel):
    pull_quotes: tuple[str, ...] = ()
    customer_quote_placeholders: tuple[str, ...] = ()
    cta_suggestions: tuple[str, ...] = ()


class QualityDimensionScore(CoreContractModel):
    name: str = Field(min_length=1)
    score: int = Field(ge=0)
    max_score: int = Field(gt=0)

    @model_validator(mode="after")
    def _score_not_over_max(self) -> "QualityDimensionScore":
        if self.score > self.max_score:
            raise ValueError("dimension score cannot exceed max_score")
        return self


class QualityReport(CoreContractModel):
    overall_score: int = Field(ge=0, le=100)
    dimension_scores: tuple[QualityDimensionScore, ...] = Field(min_length=8)
    approval_reason: str = Field(min_length=1)
    revision_notes: tuple[str, ...] = ()
    passed: bool

    @model_validator(mode="after")
    def _score_contract(self) -> "QualityReport":
        total = sum(item.score for item in self.dimension_scores)
        if total != self.overall_score:
            raise ValueError("QualityReport.overall_score must equal dimension score sum")
        if self.passed != (self.overall_score >= QUALITY_PASS_THRESHOLD):
            raise ValueError("QualityReport.passed must mirror the numeric pass threshold")
        return self


class CaseStudyPackage(CoreContractModel):
    request_id: str = Field(min_length=1)
    status: Agent07Status
    pass_status: PassStatus
    recommended_title: str | None = None
    title_options: tuple[str, ...] = ()
    executive_summary: str | None = None
    customer_background: str | None = None
    challenge_section: str | None = None
    solution_section: str | None = None
    implementation_section: str | None = None
    results_section: str | None = None
    metric_highlights: tuple[MetricHighlight, ...] = ()
    pull_quotes: tuple[str, ...] = ()
    customer_quote_placeholders: tuple[str, ...] = ()
    cta_suggestions: tuple[str, ...] = ()
    final_markdown_draft: str | None = None
    missing_information_warnings: tuple[MissingInfoWarning, ...] = ()
    risk_flags: tuple[RiskFlag, ...] = ()
    quality_report: QualityReport
    cost_usage: CostUsage
    notes: str = Field(default="")
    improvement_suggestions: tuple[str, ...] = ()
    generation_used_llm: bool = False

    @model_validator(mode="after")
    def _package_contract(self) -> "CaseStudyPackage":
        expected_pass = "pass" if self.quality_report.passed and not _has_hard_fail(self.risk_flags) else "fail"
        if self.pass_status != expected_pass:
            raise ValueError("pass_status must mirror quality_report.passed and hard-fail risks")
        if _has_hard_fail(self.risk_flags) and self.status != "reject":
            raise ValueError("hard-fail risks require status='reject'")
        if self.status == "approve":
            if self.pass_status != "pass":
                raise ValueError("approved package must pass the quality gate")
            if _has_high_or_hard_risk(self.risk_flags):
                raise ValueError("approved package cannot contain high or hard-fail risks")
            if _has_high_missing_info(self.missing_information_warnings):
                raise ValueError("approved package cannot contain high-severity missing information")
            required = (
                self.recommended_title,
                self.title_options,
                self.executive_summary,
                self.customer_background,
                self.challenge_section,
                self.solution_section,
                self.results_section,
                self.final_markdown_draft,
            )
            if not all(required):
                raise ValueError("approved package is missing required case study output fields")
        return self


def _has_hard_fail(flags: tuple[RiskFlag, ...]) -> bool:
    return any(flag.severity == "hard_fail" for flag in flags)


def _has_high_or_hard_risk(flags: tuple[RiskFlag, ...]) -> bool:
    return any(flag.severity in {"high", "hard_fail"} for flag in flags)


def _has_high_missing_info(warnings: tuple[MissingInfoWarning, ...]) -> bool:
    return any(warning.severity == "high" for warning in warnings)


class BillableNodeError(Exception):
    """A node failed after a billable provider call and must preserve cost."""

    def __init__(self, stage_cost: StageCost, cause: Exception) -> None:
        self.stage_cost = stage_cost
        self.cause = cause
        super().__init__(f"BillableNodeError wrapping {type(cause).__name__}")


Agent07Package = CaseStudyPackage
