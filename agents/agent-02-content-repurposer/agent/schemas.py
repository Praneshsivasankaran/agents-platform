"""Typed contracts for Agent 02 - Content Repurposing Agent.

All LLM-facing and terminal payload models subclass CoreContractModel so the
shared structured-output validator can enforce strict, frozen, deeply immutable
schemas before provider calls. Use tuples and nested models, never loose lists
or dicts, for any schema that can cross a provider or output boundary.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from core import CoreContractModel


SourceType = Literal["agent01_blog_package", "raw_article_text"]
Platform = Literal["linkedin", "instagram", "x_twitter", "short_video", "newsletter"]
ContentType = Literal["post", "thread", "caption", "script", "email"]
Agent02Status = Literal["pass", "needs_more_input", "needs_human", "stopped_cost_ceiling", "error"]
FailureSeverity = Literal["terminal", "retriable"]

TerminalHardFailCode = Literal[
    "prompt_injection_followed",
    "fake_facts",
    "fake_statistics",
    "unsupported_claims",
    "changed_source_meaning",
    "fake_publishing_claim",
    "attempted_external_action",
    "confidential_content_exposed",
    "cost_ceiling_exceeded",
    "direct_cloud_sdk_import",
]
RetriableFailureCode = Literal[
    "generic_content",
    "weak_hook",
    "weak_cta",
    "platform_mismatch",
    "too_repetitive",
    "low_usefulness_score",
    "same_content_reused",
    "poor_formatting",
    "weak_audience_relevance",
    "weak_claim_grounding",
]
HardFailCode = TerminalHardFailCode | RetriableFailureCode


DEFAULT_PLATFORMS: tuple[Platform, ...] = ("linkedin", "instagram", "x_twitter", "short_video")
OPTIONAL_NEWSLETTER: Platform = "newsletter"
QUALITY_PASS_THRESHOLD = 85
PLATFORM_MINIMUM_SCORE = 75

TERMINAL_HARD_FAIL_CODES: frozenset[str] = frozenset(
    {
        "prompt_injection_followed",
        "fake_facts",
        "fake_statistics",
        "unsupported_claims",
        "changed_source_meaning",
        "fake_publishing_claim",
        "attempted_external_action",
        "confidential_content_exposed",
        "cost_ceiling_exceeded",
        "direct_cloud_sdk_import",
    }
)
RETRIABLE_FAILURE_CODES: frozenset[str] = frozenset(
    {
        "generic_content",
        "weak_hook",
        "weak_cta",
        "platform_mismatch",
        "too_repetitive",
        "low_usefulness_score",
        "same_content_reused",
        "poor_formatting",
        "weak_audience_relevance",
        "weak_claim_grounding",
    }
)


class MetadataItem(CoreContractModel):
    key: str = Field(min_length=1)
    value: str = Field(default="")


class SourceContent(CoreContractModel):
    """Stable serialized source contract accepted by Agent 02.

    Agent 02 deliberately does not import Agent 01 internals. Agent 01 output
    can be serialized into this shape when status="pass".
    """

    source_type: SourceType
    title: str = Field(default="")
    summary: str = Field(default="")
    full_text: str | None = None
    blog_body: str | None = None
    seo_keywords: tuple[str, ...] = ()
    suggested_tags: tuple[str, ...] = ()
    meta_description: str | None = None
    source_status: str | None = None
    human_approved: bool | None = None
    source_metadata: tuple[MetadataItem, ...] = ()

    @model_validator(mode="after")
    def _has_text(self) -> "SourceContent":
        body = self.full_text or self.blog_body or ""
        if self.source_type == "agent01_blog_package" and self.source_status not in (None, "pass"):
            raise ValueError("Agent 01 source packages must have source_status='pass' when provided")
        if not (self.title.strip() or self.summary.strip() or body.strip()):
            raise ValueError("SourceContent requires title, summary, full_text, or blog_body")
        return self


def _clean_text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raw_items = value.replace("\n", ",").replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]
    cleaned: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return tuple(cleaned)


class Agent03PlatformDirection(CoreContractModel):
    platform: str = Field(default="")
    direction: str = Field(min_length=1)


class Agent03RepurposingBrief(CoreContractModel):
    """Optional strategy handoff contract accepted from Agent 03.

    Agent 02 keeps source content as the factual base. This brief only guides
    platform choice, tone, hooks, CTA, and campaign-message consistency.
    """

    core_message: str = Field(default="")
    target_audience: str = Field(default="")
    recommended_platforms: tuple[str, ...] = ()
    platform_direction: tuple[Agent03PlatformDirection, ...] = ()
    hooks: tuple[str, ...] = ()
    cta: str = Field(default="")
    content_pillars: tuple[str, ...] = ()
    tone_rules: tuple[str, ...] = ()
    message_guardrails: tuple[str, ...] = ()
    repurposing_focus: str = Field(default="")
    consistent_message: str = Field(default="")
    risk_flags: tuple[str, ...] = ()
    quality_notes: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _normalize_aliases_and_lists(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        aliases = {
            "core_campaign_message": "core_message",
            "platform_recommendations": "recommended_platforms",
            "platform_specific_direction": "platform_direction",
            "cta_direction": "cta",
            "what_should_stay_consistent": "consistent_message",
            "what_should_stay_consistent_across_all_platforms": "consistent_message",
        }
        for alias, canonical in aliases.items():
            if alias in normalized:
                if canonical not in normalized:
                    normalized[canonical] = normalized[alias]
                normalized.pop(alias, None)

        tuple_fields = (
            "recommended_platforms",
            "hooks",
            "content_pillars",
            "tone_rules",
            "message_guardrails",
            "risk_flags",
            "quality_notes",
        )
        for field_name in tuple_fields:
            value = normalized.get(field_name)
            if field_name == "hooks" and isinstance(value, dict):
                normalized[field_name] = tuple(
                    f"{platform}: {hook}".strip()
                    for platform, hook in value.items()
                    if str(hook).strip()
                )
            else:
                normalized[field_name] = _clean_text_tuple(value)

        direction = normalized.get("platform_direction")
        if isinstance(direction, dict):
            normalized["platform_direction"] = tuple(
                {"platform": str(platform), "direction": str(value)}
                for platform, value in direction.items()
                if str(value).strip()
            )
        elif isinstance(direction, str):
            normalized["platform_direction"] = (
                {"platform": "", "direction": direction},
            ) if direction.strip() else ()
        elif isinstance(direction, (list, tuple)):
            items: list[object] = []
            for item in direction:
                if isinstance(item, dict):
                    items.append(item)
                elif str(item).strip():
                    items.append({"platform": "", "direction": str(item)})
            normalized["platform_direction"] = tuple(items)
        else:
            normalized["platform_direction"] = ()

        for field_name, value in list(normalized.items()):
            if field_name not in tuple_fields and field_name != "platform_direction" and isinstance(value, str):
                normalized[field_name] = " ".join(value.split())
        return normalized

    @model_validator(mode="after")
    def _requires_strategy_signal(self) -> "Agent03RepurposingBrief":
        if not any(
            (
                self.core_message,
                self.target_audience,
                self.recommended_platforms,
                self.platform_direction,
                self.hooks,
                self.cta,
                self.content_pillars,
                self.tone_rules,
                self.message_guardrails,
                self.repurposing_focus,
                self.consistent_message,
            )
        ):
            raise ValueError("repurposing_brief_from_agent_03 requires strategy guidance")
        return self


class Agent02Request(CoreContractModel):
    source: SourceContent
    target_platforms: tuple[Platform, ...] = ()
    include_newsletter: bool = False
    audience: str = Field(default="")
    brand_tone: str = Field(default="")
    campaign_goal: str = Field(default="")
    cta: str = Field(default="")
    repurposing_brief_from_agent_03: Agent03RepurposingBrief | None = None


class SourceClaim(CoreContractModel):
    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    claim_type: Literal["fact", "statistic", "recommendation", "positioning"] = "fact"
    supported: bool = True


class ParsedSource(CoreContractModel):
    title: str = Field(default="")
    summary: str = Field(default="")
    body: str = Field(default="")
    source_claims: tuple[SourceClaim, ...] = ()
    tone: str = Field(default="")
    audience_hint: str = Field(default="")
    cta_hint: str = Field(default="")
    seo_keywords: tuple[str, ...] = ()
    suggested_tags: tuple[str, ...] = ()
    usable: bool
    thin_reason: str | None = None
    confidential_flags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _usable_has_body_and_claims(self) -> "ParsedSource":
        if self.usable and (not self.body.strip() or not self.source_claims):
            raise ValueError("usable ParsedSource requires body and at least one source claim")
        return self


class CoreMessage(CoreContractModel):
    main_message: str = Field(min_length=1)
    supporting_points: tuple[str, ...] = ()


class AudienceValue(CoreContractModel):
    audience: str = Field(min_length=1)
    pain_points: tuple[str, ...] = ()
    practical_takeaways: tuple[str, ...] = ()
    why_it_matters: str = Field(min_length=1)


class ContentAngle(CoreContractModel):
    angle_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    platform_fit: tuple[Platform, ...] = ()
    rationale: str = Field(default="")


class PlatformStrategy(CoreContractModel):
    platform: Platform
    content_type: ContentType
    angle_id: str = Field(min_length=1)
    format_notes: str = Field(default="")
    cta: str = Field(default="")


class PlatformRules(CoreContractModel):
    platform: Platform
    content_type: ContentType
    min_chars: int = Field(ge=0)
    max_chars: int = Field(ge=0)
    min_hashtags: int = Field(ge=0)
    max_hashtags: int = Field(ge=0)
    requires_hook: bool = True
    requires_cta: bool = True
    requires_visual_angle: bool = False
    min_thread_posts: int = Field(default=0, ge=0)
    max_thread_posts: int = Field(default=0, ge=0)
    min_duration_s: int = Field(default=0, ge=0)
    max_duration_s: int = Field(default=0, ge=0)
    notes: str = Field(default="")


class PlatformDraft(CoreContractModel):
    platform: Platform
    content_type: ContentType
    hook: str = Field(default="")
    body: str = Field(default="")
    cta: str = Field(default="")
    hashtags: tuple[str, ...] = ()
    thread_posts: tuple[str, ...] = ()
    scene_directions: tuple[str, ...] = ()
    voiceover: str = Field(default="")
    on_screen_text: tuple[str, ...] = ()
    visual_angle: str = Field(default="")
    subject_line: str = Field(default="")
    preview_text: str = Field(default="")
    why_this_works: str = Field(default="")
    audience_value: str = Field(default="")
    usage_notes: str = Field(default="")
    risk_flags: tuple[str, ...] = ()
    quality_score: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def _has_platform_content(self) -> "PlatformDraft":
        parts = (
            self.hook,
            self.body,
            self.voiceover,
            " ".join(self.thread_posts),
            self.subject_line,
        )
        if not any(part.strip() for part in parts):
            raise ValueError("PlatformDraft requires at least one content field")
        return self


class LLMPlatformDraft(CoreContractModel):
    """One platform draft as authored by the LLM (structured-output contract).

    This is the *creative* payload the model returns. Agent 02 parses it into a
    validated ``PlatformDraft`` and then runs the deterministic platform/quality/
    factual validators over it as guardrails. Structural fields the model omits are
    completed deterministically; an unusable draft falls back to a deterministic
    template for that platform (see ``coerce_llm_drafts``).
    """

    platform: Platform
    hook: str = Field(default="")
    body: str = Field(default="")
    cta: str = Field(default="")
    hashtags: tuple[str, ...] = ()
    thread_posts: tuple[str, ...] = ()
    scene_directions: tuple[str, ...] = ()
    voiceover: str = Field(default="")
    on_screen_text: tuple[str, ...] = ()
    visual_angle: str = Field(default="")
    subject_line: str = Field(default="")
    preview_text: str = Field(default="")
    why_this_works: str = Field(default="")
    audience_value: str = Field(default="")


class LLMDraftBundle(CoreContractModel):
    """Structured LLM response for the draft-generation stage: one draft per platform."""

    drafts: tuple[LLMPlatformDraft, ...] = Field(default=())


class PlatformValidationResult(CoreContractModel):
    platform: Platform
    passed: bool
    score: int = Field(ge=0, le=100)
    issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    character_count: int = Field(default=0, ge=0)
    hashtag_count: int = Field(default=0, ge=0)


class UnsupportedClaim(CoreContractModel):
    platform: Platform
    claim_text: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    severity: FailureSeverity
    # Specific hard-fail category so a human reviewer sees WHY a claim failed
    # (a publishing claim is not the same risk as an ungrounded statistic).
    code: HardFailCode = "unsupported_claims"

    @model_validator(mode="after")
    def _code_matches_severity(self) -> "UnsupportedClaim":
        if self.code in TERMINAL_HARD_FAIL_CODES and self.severity != "terminal":
            raise ValueError(f"{self.code} must be severity='terminal'")
        if self.code in RETRIABLE_FAILURE_CODES and self.severity != "retriable":
            raise ValueError(f"{self.code} must be severity='retriable'")
        return self


class FactualConsistencyReport(CoreContractModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    unsupported_claims: tuple[UnsupportedClaim, ...] = ()
    changed_meaning: bool = False


class UsefulnessReport(CoreContractModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    generic_content_detected: bool = False
    repeated_across_platforms: bool = False
    issues: tuple[str, ...] = ()


class QualitySubScores(CoreContractModel):
    audience_relevance: int = Field(ge=0, le=15)
    usefulness: int = Field(ge=0, le=15)
    factual_consistency: int = Field(ge=0, le=15)
    platform_fit: int = Field(ge=0, le=15)
    hook_strength: int = Field(ge=0, le=10)
    message_clarity: int = Field(ge=0, le=10)
    cta_quality: int = Field(ge=0, le=10)
    brand_tone_alignment: int = Field(ge=0, le=5)
    readability_polish: int = Field(ge=0, le=5)


class PlatformScore(CoreContractModel):
    platform: Platform
    score: int = Field(ge=0, le=100)


def sum_quality_subscores(sub_scores: QualitySubScores) -> int:
    return (
        sub_scores.audience_relevance
        + sub_scores.usefulness
        + sub_scores.factual_consistency
        + sub_scores.platform_fit
        + sub_scores.hook_strength
        + sub_scores.message_clarity
        + sub_scores.cta_quality
        + sub_scores.brand_tone_alignment
        + sub_scores.readability_polish
    )


class HardFail(CoreContractModel):
    code: HardFailCode
    severity: FailureSeverity
    reason: str = Field(min_length=1)
    platform: Platform | None = None

    @model_validator(mode="after")
    def _severity_matches_code(self) -> "HardFail":
        if self.code in TERMINAL_HARD_FAIL_CODES and self.severity != "terminal":
            raise ValueError(f"{self.code} must be severity='terminal'")
        if self.code in RETRIABLE_FAILURE_CODES and self.severity != "retriable":
            raise ValueError(f"{self.code} must be severity='retriable'")
        return self


class QualityReport(CoreContractModel):
    overall_score: int = Field(ge=0, le=100)
    sub_scores: QualitySubScores
    platform_scores: tuple[PlatformScore, ...] = ()
    hard_fails: tuple[HardFail, ...] = ()
    pass_flag: bool
    needs_revision: bool
    improvement_suggestions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _overall_matches_subscores(self) -> "QualityReport":
        expected = sum_quality_subscores(self.sub_scores)
        if self.overall_score != expected:
            raise ValueError("QualityReport.overall_score must equal sub_scores sum")
        return self

    @model_validator(mode="after")
    def _pass_flag_matches_contract(self) -> "QualityReport":
        terminal = any(h.severity == "terminal" for h in self.hard_fails)
        no_hard_fails = not self.hard_fails
        platform_ok = all(p.score >= PLATFORM_MINIMUM_SCORE for p in self.platform_scores)
        expected = self.overall_score >= QUALITY_PASS_THRESHOLD and no_hard_fails and platform_ok
        if self.pass_flag != expected:
            raise ValueError("QualityReport.pass_flag contradicts threshold/hard-fail/platform contract")
        if terminal and self.needs_revision:
            raise ValueError("Terminal hard-fails must not request revision")
        # A passing report must not also request revision — the graph would otherwise route a
        # finished package back into the revision loop. Mirrors Agent 01's pass_flag/needs_human guard.
        if self.pass_flag and self.needs_revision:
            raise ValueError("A passing QualityReport (pass_flag=True) must have needs_revision=False")
        # `all(... for [])` is vacuously True, so the platform check above cannot vouch for an
        # empty platform_scores. A passing package must score at least one platform draft
        # (spec: no individual platform draft below 75) — reject a vacuous pass.
        if self.pass_flag and not self.platform_scores:
            raise ValueError("A passing QualityReport must include at least one platform score")
        return self


class HashtagSet(CoreContractModel):
    platform: Platform
    hashtags: tuple[str, ...] = ()


class StageCost(CoreContractModel):
    stage: str
    cost_inr: float = Field(ge=0.0)
    tier: Literal["cheap", "strong", "stt", "none"]
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


class RepurposedContentPackage(CoreContractModel):
    status: Agent02Status
    package_id: str = Field(default="")
    source_summary: str = Field(default="")
    content_brief: str = Field(default="")
    platform_outputs: tuple[PlatformDraft, ...] = ()
    markdown_review_package: str = Field(default="")
    output_package_uri: str | None = None
    validation_report: tuple[PlatformValidationResult, ...] = ()
    factual_consistency_report: FactualConsistencyReport | None = None
    usefulness_report: UsefulnessReport | None = None
    quality_report: QualityReport | None = None
    cta_options: tuple[str, ...] = ()
    hashtag_sets: tuple[HashtagSet, ...] = ()
    cost: CostUsage
    hard_fails: tuple[HardFail, ...] = ()
    improvement_suggestions: tuple[str, ...] = ()
    notes: str = Field(default="")
    revision_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _passed_package_contract(self) -> "RepurposedContentPackage":
        if self.status == "pass":
            if not self.platform_outputs:
                raise ValueError("Passed package requires platform_outputs")
            if self.quality_report is None or not self.quality_report.pass_flag:
                raise ValueError("Passed package requires passing quality_report")
            if self.hard_fails:
                raise ValueError("Passed package cannot include hard_fails")
            if not self.markdown_review_package.strip():
                raise ValueError("Passed package requires markdown_review_package")
        return self


class BillableNodeError(Exception):
    """A node failed after a billable provider call and must preserve cost."""

    def __init__(self, stage_cost: StageCost, cause: Exception) -> None:
        self.stage_cost = stage_cost
        self.cause = cause
        super().__init__(f"BillableNodeError wrapping {type(cause).__name__}")


# Backward-compatible alias for the generated scaffold tests and any early imports.
ContentRepurposerPackage = RepurposedContentPackage
