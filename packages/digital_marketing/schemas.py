"""Shared typed contracts for Digital Marketing Agents 15-21."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from core import CoreContractModel


TerminalStatus = Literal["pass", "needs_human", "stopped_cost_ceiling", "error"]
QualityStatus = Literal["approve", "revise", "reject"]
PassStatus = Literal["pass", "fail"]
RiskSeverity = Literal["low", "medium", "high", "hard_fail"]
RiskCategory = Literal[
    "activation_request",
    "data_quality",
    "deceptive_practice",
    "external_action",
    "live_platform_access",
    "metric_fabrication",
    "missing_required_context",
    "misrepresentation",
    "privacy_or_consent",
    "protected_attribute",
    "prompt_injection",
    "unsupported_claim",
]
Confidence = Literal["high", "medium", "low"]
CostTier = Literal["cheap", "strong", "none"]


def clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def tuple_from_any(value: object) -> tuple[str, ...]:
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
        text = clean_text(item)
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
    cost_ceiling_inr: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _total_matches_ledger(self) -> "CostUsage":
        computed = round(sum(stage.cost_inr for stage in self.stage_costs), 6)
        if abs(computed - self.total_inr) > 0.01:
            raise ValueError("CostUsage.total_inr must equal sum(stage_costs.cost_inr)")
        if self.total_inr > self.cost_ceiling_inr + 0.01:
            raise ValueError("CostUsage.total_inr cannot exceed cost_ceiling_inr")
        return self


class MetricInput(CoreContractModel):
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source: str | None = None

    @field_validator("label", "value", "source", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str | None:
        cleaned = clean_text(value)
        return cleaned or None


class FunnelStageInput(CoreContractModel):
    stage: str = Field(min_length=1)
    count: int = Field(ge=0)

    @field_validator("stage", mode="before")
    @classmethod
    def _strip_stage(cls, value: object) -> str:
        return clean_text(value)


class DigitalMarketingRequest(CoreContractModel):
    business_context: str | None = None
    product_or_service: str | None = None
    campaign_goal: str | None = None
    conversion_goal: str | None = None
    target_audience: str | None = None
    icp_summary: str | None = None
    segment_summary: str | None = None
    offer: str | None = None
    brand_voice: str | None = None
    budget: str | None = None
    spend: str | None = None
    timeline: str | None = None
    reporting_period: str | None = None
    region: str | None = None
    language: str | None = None
    source_notes: str | None = None
    keyword_table: str | None = None
    ad_copy: str | None = None
    page_copy: str | None = None
    page_notes: str | None = None
    campaign_export: str | None = None
    metric_summary: str | None = None
    channel_summaries: str | None = None
    upstream_handoffs: str | None = None
    constraints: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    excluded_terms: tuple[str, ...] = ()
    competitors: tuple[str, ...] = ()
    page_sections: tuple[str, ...] = ()
    form_fields: tuple[str, ...] = ()
    content_inventory: tuple[str, ...] = ()
    owner_notes: tuple[str, ...] = ()
    compliance_notes: tuple[str, ...] = ()
    metrics: tuple[MetricInput, ...] = ()
    funnel_stages: tuple[FunnelStageInput, ...] = ()
    max_cost_rs: float | None = Field(default=None, ge=0.0)

    @field_validator(
        "business_context",
        "product_or_service",
        "campaign_goal",
        "conversion_goal",
        "target_audience",
        "icp_summary",
        "segment_summary",
        "offer",
        "brand_voice",
        "budget",
        "spend",
        "timeline",
        "reporting_period",
        "region",
        "language",
        "source_notes",
        "keyword_table",
        "ad_copy",
        "page_copy",
        "page_notes",
        "campaign_export",
        "metric_summary",
        "channel_summaries",
        "upstream_handoffs",
        mode="before",
    )
    @classmethod
    def _strip_optional_text(cls, value: object) -> str | None:
        cleaned = clean_text(value)
        return cleaned or None

    @field_validator(
        "constraints",
        "platforms",
        "channels",
        "keywords",
        "excluded_terms",
        "competitors",
        "page_sections",
        "form_fields",
        "content_inventory",
        "owner_notes",
        "compliance_notes",
        mode="before",
    )
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return tuple_from_any(value)

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
        raise ValueError("metrics must be a metric object or list of metric objects")

    @field_validator("funnel_stages", mode="before")
    @classmethod
    def _coerce_funnel_stages(cls, value: object) -> tuple[FunnelStageInput, ...]:
        if value is None or value == "":
            return ()
        if isinstance(value, FunnelStageInput):
            return (value,)
        if isinstance(value, dict):
            return (FunnelStageInput.model_validate(value),)
        if isinstance(value, (list, tuple)):
            return tuple(FunnelStageInput.model_validate(item) for item in value)
        raise ValueError("funnel_stages must be a stage object or list of stage objects")


class EvidenceItem(CoreContractModel):
    source_label: str = Field(min_length=1)
    claim_supported: str = Field(min_length=1)
    confidence: Confidence
    sensitivity: Literal["normal", "confidential", "pii_possible"] = "normal"


class RiskFlag(CoreContractModel):
    category: RiskCategory
    severity: RiskSeverity
    message: str = Field(min_length=1)
    evidence_needed: str | None = None


class DigitalMarketingHandoff(CoreContractModel):
    target_agent: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    fields: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


class MetricInsight(CoreContractModel):
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    confidence: Confidence


class OutputSection(CoreContractModel):
    name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    confidence: Confidence


class GeneratedRecommendation(CoreContractModel):
    item_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    actions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence: Confidence


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
    dimension_scores: tuple[QualityDimensionScore, ...] = Field(min_length=1)
    approval_reason: str = Field(min_length=1)
    revision_notes: tuple[str, ...] = ()
    passed: bool

    @model_validator(mode="after")
    def _score_contract(self) -> "QualityReport":
        total = sum(item.score for item in self.dimension_scores)
        if total != self.overall_score:
            raise ValueError("QualityReport.overall_score must equal dimension score sum")
        return self


class DigitalMarketingLLMOutput(CoreContractModel):
    summary: str = Field(min_length=20)
    recommendations: tuple[GeneratedRecommendation, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = ()


class DigitalMarketingPackage(CoreContractModel):
    request_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    status: TerminalStatus
    terminal_status: TerminalStatus
    quality_status: QualityStatus
    pass_status: PassStatus
    summary: str = Field(min_length=1)
    output_sections: tuple[OutputSection, ...] = ()
    primary_recommendations: tuple[GeneratedRecommendation, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    assumptions: tuple[str, ...] = ()
    metric_insights: tuple[MetricInsight, ...] = ()
    data_quality_warnings: tuple[RiskFlag, ...] = ()
    handoffs: tuple[DigitalMarketingHandoff, ...] = ()
    risk_flags: tuple[RiskFlag, ...] = ()
    quality_report: QualityReport
    cost_usage: CostUsage
    notes: str = Field(default="")
    generation_used_llm: bool = False

    @model_validator(mode="after")
    def _package_contract(self) -> "DigitalMarketingPackage":
        if self.status != self.terminal_status:
            raise ValueError("status and terminal_status must match")
        hard_fail = any(flag.severity == "hard_fail" for flag in self.risk_flags)
        expected_pass = "pass" if self.quality_report.passed and not hard_fail else "fail"
        if self.pass_status != expected_pass:
            raise ValueError("pass_status must mirror quality_report.passed and hard-fail risks")
        if hard_fail and self.status == "pass":
            raise ValueError("hard-fail risks cannot produce terminal status pass")
        if self.status == "pass" and self.quality_status != "approve":
            raise ValueError("terminal status pass requires quality_status approve")
        return self
