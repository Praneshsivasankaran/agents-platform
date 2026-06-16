"""Typed contracts for Agent 06 - Whitepaper Development Agent."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from core import CoreContractModel


Agent06Status = Literal[
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
EvidenceStatus = Literal[
    "supported_by_user_evidence",
    "user_provided_unverified",
    "needs_evidence",
    "general_reasoning",
    "unsupported",
]

QUALITY_PASS_THRESHOLD = 80

RiskCode = Literal[
    "missing_required_inputs",
    "missing_required_section",
    "missing_claim_evidence_status",
    "missing_evidence_section",
    "fabricated_claim",
    "unsupported_verified_claim",
    "generic_content",
    "thin_sections",
    "target_audience_ignored",
    "problem_solution_ignored",
    "external_action_claimed",
    "prompt_injection_marker",
    "unsafe_regulated_claim",
    "excluded_claim_used",
    "source_verification_claimed",
    "empty_or_invalid_output",
]

HARD_FAIL_CODES: frozenset[str] = frozenset(
    {
        "missing_required_inputs",
        "missing_required_section",
        "missing_claim_evidence_status",
        "missing_evidence_section",
        "fabricated_claim",
        "unsupported_verified_claim",
        "generic_content",
        "external_action_claimed",
        "source_verification_claimed",
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


class Agent06Request(CoreContractModel):
    topic: str = Field(min_length=1)
    company_context: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    solution: str = Field(min_length=1)
    tone: str = Field(min_length=1)
    target_depth: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    proof_points: tuple[str, ...] = ()
    source_notes: tuple[str, ...] = ()
    differentiators: tuple[str, ...] = ()
    objections: tuple[str, ...] = ()
    compliance_constraints: tuple[str, ...] = ()
    excluded_claims: tuple[str, ...] = ()

    @field_validator(
        "topic",
        "company_context",
        "target_audience",
        "industry",
        "problem",
        "solution",
        "tone",
        "target_depth",
        "cta",
        mode="before",
    )
    @classmethod
    def _strip_required(cls, value: object) -> str:
        return _clean_text(value)

    @field_validator(
        "proof_points",
        "source_notes",
        "differentiators",
        "objections",
        "compliance_constraints",
        "excluded_claims",
        mode="before",
    )
    @classmethod
    def _coerce_tuple(cls, value: object) -> tuple[str, ...]:
        return _tuple_from_any(value)


class NormalizedContext(CoreContractModel):
    request_summary: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    company_context_summary: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    industry_context: str = Field(min_length=1)
    problem_summary: str = Field(min_length=1)
    solution_summary: str = Field(min_length=1)
    tone: str = Field(min_length=1)
    target_depth: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    constraints: tuple[str, ...] = ()


class AnglePlan(CoreContractModel):
    recommended_angle: str = Field(min_length=1)
    audience_promise: str = Field(min_length=1)
    narrative_thesis: str = Field(min_length=1)
    title_options: tuple[str, ...] = Field(min_length=3)


class EvidenceItem(CoreContractModel):
    evidence_id: str = Field(min_length=1)
    claim_area: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)
    status: EvidenceStatus
    source_note: str = Field(default="")


class EvidenceMap(CoreContractModel):
    evidence_items: tuple[EvidenceItem, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()


class OutlineSection(CoreContractModel):
    section_id: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    key_points: tuple[str, ...] = Field(min_length=1)
    evidence_needed: tuple[str, ...] = ()


class WhitepaperOutline(CoreContractModel):
    sections: tuple[OutlineSection, ...] = Field(min_length=8)


class WhitepaperSectionDraft(CoreContractModel):
    section_id: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    body: str = Field(min_length=1)


class WhitepaperDraft(CoreContractModel):
    executive_summary: str = Field(min_length=1)
    target_audience_and_pain_points: str = Field(min_length=1)
    problem_statement: str = Field(min_length=1)
    industry_context: str = Field(min_length=1)
    proposed_solution: str = Field(min_length=1)
    benefits: str = Field(min_length=1)
    use_cases: str = Field(min_length=1)
    implementation_approach: str = Field(min_length=1)
    risks_and_challenges: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    sections: tuple[WhitepaperSectionDraft, ...] = ()


class ClaimEvidence(CoreContractModel):
    claim: str = Field(min_length=1)
    evidence_status: EvidenceStatus
    evidence_reference: str = Field(default="")
    review_note: str = Field(default="")


class ClaimReviewReport(CoreContractModel):
    key_claims: tuple[ClaimEvidence, ...] = ()
    unsupported_claims: tuple[str, ...] = ()
    fabricated_or_forbidden_claims: tuple[str, ...] = ()


class GenericContentFlag(CoreContractModel):
    location: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: RiskSeverity
    recommended_fix: str = Field(default="")


class GenericContentReport(CoreContractModel):
    flags: tuple[GenericContentFlag, ...] = ()
    hard_fail: bool

    @model_validator(mode="after")
    def _hard_fail_matches_flags(self) -> "GenericContentReport":
        expected = any(flag.severity == "hard_fail" for flag in self.flags)
        if self.hard_fail != expected:
            raise ValueError("GenericContentReport.hard_fail must mirror hard-fail flags")
        return self


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


class WhitepaperQualityScore(CoreContractModel):
    input_completeness: int = Field(ge=0, le=10)
    specificity: int = Field(ge=0, le=15)
    audience_fit: int = Field(ge=0, le=10)
    structure_completeness: int = Field(ge=0, le=15)
    problem_solution_logic: int = Field(ge=0, le=15)
    evidence_discipline: int = Field(ge=0, le=15)
    depth_actionability: int = Field(ge=0, le=10)
    tone_clarity: int = Field(ge=0, le=5)
    risk_review_readiness: int = Field(ge=0, le=5)
    total_score: int = Field(ge=0, le=100)
    passed: bool
    hard_fail_codes: tuple[RiskCode, ...] = ()

    @model_validator(mode="after")
    def _score_contract(self) -> "WhitepaperQualityScore":
        expected = (
            self.input_completeness
            + self.specificity
            + self.audience_fit
            + self.structure_completeness
            + self.problem_solution_logic
            + self.evidence_discipline
            + self.depth_actionability
            + self.tone_clarity
            + self.risk_review_readiness
        )
        if self.total_score != expected:
            raise ValueError("WhitepaperQualityScore.total_score must equal subscore sum")
        expected_pass = self.total_score >= QUALITY_PASS_THRESHOLD and not self.hard_fail_codes
        if self.passed != expected_pass:
            raise ValueError("WhitepaperQualityScore.passed contradicts threshold/hard-fail contract")
        return self


class WhitepaperDevelopmentPackage(CoreContractModel):
    status: Agent06Status
    package_id: str = Field(default="")
    request_summary: str = Field(default="")
    title_options: tuple[str, ...] = ()
    recommended_angle: str = Field(default="")
    executive_summary: str = Field(default="")
    target_audience_and_pain_points: str = Field(default="")
    problem_statement: str = Field(default="")
    industry_context: str = Field(default="")
    proposed_solution: str = Field(default="")
    benefits: str = Field(default="")
    use_cases: str = Field(default="")
    implementation_approach: str = Field(default="")
    risks_and_challenges: str = Field(default="")
    conclusion: str = Field(default="")
    cta: str = Field(default="")
    key_claims: tuple[ClaimEvidence, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    risk_flags: tuple[RiskFlag, ...] = ()
    generic_content_flags: tuple[GenericContentFlag, ...] = ()
    quality_score: WhitepaperQualityScore | None = None
    pass_status: PassStatus = "fail"
    improvement_suggestions: tuple[str, ...] = ()
    cost: CostUsage
    notes: str = Field(default="")
    generation_used_llm: bool = False

    @model_validator(mode="after")
    def _package_contract(self) -> "WhitepaperDevelopmentPackage":
        if self.quality_score is not None:
            expected_status = "pass" if self.quality_score.passed else "fail"
            if self.pass_status != expected_status:
                raise ValueError("pass_status must mirror quality_score.passed")
        if self.status == "pass":
            if self.quality_score is None or not self.quality_score.passed:
                raise ValueError("Passed package requires a passing WhitepaperQualityScore")
            required = (
                self.title_options,
                self.recommended_angle,
                self.executive_summary,
                self.problem_statement,
                self.proposed_solution,
                self.key_claims,
            )
            if not all(required):
                raise ValueError("Passed package is missing required whitepaper output fields")
            if any(claim.evidence_status == "unsupported" for claim in self.key_claims):
                raise ValueError("Passed package cannot contain unsupported key claims")
        return self


class BillableNodeError(Exception):
    """A node failed after a billable provider call and must preserve cost."""

    def __init__(self, stage_cost: StageCost, cause: Exception) -> None:
        self.stage_cost = stage_cost
        self.cause = cause
        super().__init__(f"BillableNodeError wrapping {type(cause).__name__}")


WhitepaperPackage = WhitepaperDevelopmentPackage
