"""Typed I/O contracts for Agent 01 (DESIGN §7).

Final repair pass (Increment 3):
- BillableNodeError: new exception carrying a StageCost for when post-response
  processing fails after a successful (and thus billable) LLM call.  Lets
  _node_with_error_guard preserve the incurred cost while still setting error_state.
- QualityReport._pass_flag_implies_not_needs_human: pass_flag=True requires
  needs_human=False — a passing blog must not be escalated to human review.
- BlogPackage._passed_package_invariants: added quality.pass_flag, quality.overall_score,
  and quality.needs_human cross-checks for defense-in-depth.
- BlogEnrichment: blank-item check added for suggested_tags; max_length=160 on
  meta_description (SEO standard).
- BlogPackage: max_length=160 on meta_description.

Eighth repair pass (intact):
- BlogPlan: audience and angle are now required to be non-blank (validator added).
  angle default changed from "" to "general overview" so the default is always valid.
  title_candidates, target_keywords, and key_points now reject blank items within
  the tuple (item-level validation).

Seventh repair pass (intact):
- ExtractedIdeas: replaced ideas:tuple with main_idea:str, key_points:tuple[str,...],
  suggested_angle:str|None per DESIGN.md.  Validator: usable=True requires non-blank
  main_idea (was: >= 2 non-blank entries in ideas).
- BlogPlan: added title_candidates:tuple, audience:str, angle:str,
  target_keywords:tuple per DESIGN.md.  All new fields have safe defaults so
  existing tests and plan nodes need only minimal updates.

Sixth repair pass (intact):
- BlogEnrichment: item-level whitespace validation added for alternative_titles and
  seo_keywords tuples; suggested_tags is now required (non-empty) per spec.
- QualityReport._validate_needs_human_against_flags: bidirectional enforcement —
  TERMINAL flags require needs_human=True (existing); RETRIABLE-ONLY flags now also
  require needs_human=False, preventing the LLM from bypassing the revision loop by
  setting needs_human=True on a retriable flag.
- BlogPackage._passed_package_invariants: added check for non-empty suggested_tags.

Fifth repair pass (intact):
- BlogEnrichment: new schema for the enrichment LLM response (AGENT_SPEC §6.4).
  Validators reject empty/blank fields so LLM failures trigger the fallback path.
- BlogPlan: whitespace-only title/tone rejected (min_length=1 allows a single space).
- QualityReport: unknown hard_fail_flags strings rejected immediately.
- BlogPackage._passed_package_invariants: 'pass' packages require non-empty enrichment.
- CoreContractModel now carries allow_inf_nan=False (in base.py).

Previous repair notes (intact):
- BlogStatus: "passed" renamed to "pass".
- Hard-fail codes split into TERMINAL and RETRIABLE sets.
- BlogPlan: sections 3–6; blank headings rejected.
"""
from __future__ import annotations
from typing import Any, Literal
from pydantic import Field, model_validator
from core.interfaces.base import CoreContractModel


class SourceNote(CoreContractModel):
    url: str | None = Field(default=None)
    title: str = Field(default="")
    snippet: str = Field(default="")


class ExtractedIdeas(CoreContractModel):
    """Typed extraction result aligned with DESIGN.md (seventh repair).

    Fields
    ------
    main_idea:       Primary topic or thesis of the source material.
    key_points:      Supporting points or sub-ideas from the source.
    suggested_angle: Optional angle or framing the blog could adopt.
    source_notes:    Cited sources (URLs / titles) from the input.
    usable:          True iff a substantive main idea was found.
    thin_reason:     When usable=False, explains why the input is thin.

    Invariant: usable=True requires a non-blank main_idea.
    """
    main_idea: str = Field(default="")
    key_points: tuple[str, ...] = Field(default=())
    suggested_angle: str | None = Field(default=None)
    source_notes: tuple[SourceNote, ...] = Field(default=())
    usable: bool = Field(description="True iff a substantive main idea was extractable")
    thin_reason: str | None = Field(default=None)

    @model_validator(mode="after")
    def _usable_requires_non_blank_main_idea(self):
        """usable=True requires a non-blank main_idea (seventh repair).

        An empty or whitespace-only main_idea means no substantive topic was
        found in the source — that is a thin-input condition (usable=False).
        """
        if self.usable and not self.main_idea.strip():
            raise ValueError(
                "usable=True requires a non-blank main_idea "
                "(an empty main_idea means no substantive topic was found — "
                "set usable=False and explain in thin_reason)"
            )
        return self


class BlogPlan(CoreContractModel):
    """Invariants:
    - title, tone, audience, angle must be non-blank (not whitespace-only).
    - sections: 3–6 non-blank headings.
    - title_candidates (min 1 item), target_keywords (min 1 item), key_points: items must be non-blank.

    Ninth repair: audience and angle are now truly required (no default).
    title_candidates and target_keywords now require at least 1 item (min_length=1, no default).
    This ensures the LLM cannot produce a valid BlogPlan without filling all planning output.

    Eighth repair: audience and angle had non-blank validators and non-empty defaults.
    Seventh repair: added title_candidates, audience, angle, target_keywords per DESIGN.md.
    """
    title: str = Field(description="Proposed blog title", min_length=1)
    title_candidates: tuple[str, ...] = Field(
        min_length=1, description="2-3 alternative headline options the LLM considered"
    )
    audience: str = Field(
        min_length=1,
        description="Intended audience (e.g. 'technology enthusiasts', 'beginners')",
    )
    sections: tuple[str, ...] = Field(min_length=3, max_length=6)
    tone: str = Field(description="Writing tone", min_length=1)
    angle: str = Field(
        min_length=1,
        description="Blog angle or framing chosen for this draft",
    )
    target_keywords: tuple[str, ...] = Field(
        min_length=1, description="Primary SEO keywords the post should target"
    )
    target_word_count: int = Field(ge=100, le=5000)
    key_points: tuple[str, ...] = Field(default=())

    @model_validator(mode="after")
    def _non_blank_strings(self):
        """min_length=1 prevents empty strings but allows a single space — reject whitespace-only.

        Eighth repair: extended to cover audience and angle (previously only title/tone).
        """
        if not self.title.strip():
            raise ValueError(
                "BlogPlan.title must not be whitespace-only "
                "(a single space satisfies min_length=1 but is semantically blank)"
            )
        if not self.tone.strip():
            raise ValueError(
                "BlogPlan.tone must not be whitespace-only "
                "(a single space satisfies min_length=1 but is semantically blank)"
            )
        if not self.audience.strip():
            raise ValueError(
                "BlogPlan.audience must not be whitespace-only "
                "(provide a meaningful audience description, e.g. 'general readers')"
            )
        if not self.angle.strip():
            raise ValueError(
                "BlogPlan.angle must not be whitespace-only "
                "(provide a framing angle, e.g. 'practical applications')"
            )
        return self

    @model_validator(mode="after")
    def _validate_tuple_items(self):
        """Reject blank items within title_candidates, target_keywords, and key_points.

        Eighth repair: item-level whitespace validation for all plan tuple fields,
        consistent with how BlogEnrichment.alternative_titles / seo_keywords are validated.
        """
        blank_tc = [t for t in self.title_candidates if not t.strip()]
        if blank_tc:
            raise ValueError(
                f"BlogPlan.title_candidates contains {len(blank_tc)} blank item(s); "
                "every headline candidate must be non-blank"
            )
        blank_kw = [k for k in self.target_keywords if not k.strip()]
        if blank_kw:
            raise ValueError(
                f"BlogPlan.target_keywords contains {len(blank_kw)} blank item(s); "
                "every SEO keyword must be non-blank"
            )
        blank_kp = [k for k in self.key_points if not k.strip()]
        if blank_kp:
            raise ValueError(
                f"BlogPlan.key_points contains {len(blank_kp)} blank item(s); "
                "every key point must be non-blank"
            )
        return self

    @model_validator(mode="after")
    def _validate_sections(self):
        if len(self.sections) < 3:
            raise ValueError(
                "BlogPlan.sections must contain at least 3 headings "
                "(matching the 3-6 sections in the prompt)"
            )
        if len(self.sections) > 6:
            raise ValueError(
                "BlogPlan.sections must not exceed 6 headings "
                "(prompt specifies 3-6 sections)"
            )
        blank = [s for s in self.sections if not s.strip()]
        if blank:
            raise ValueError(
                f"BlogPlan.sections contains {len(blank)} blank heading(s); "
                "each section heading must be non-blank"
            )
        return self


# Sum of maxima = 15+15+15+15+10+10+10+5+5 = 100
_SUBSCORE_FIELDS: tuple[str, ...] = (
    "structure_flow", "clarity_readability", "idea_coverage", "originality",
    "tone_audience_fit", "seo_usefulness", "factual_safety_sources",
    "grammar_polish", "engagement_value",
)

# Hard-fail codes split by recoverability (DESIGN §9.2)
_TERMINAL_HARD_FAIL_CODES: frozenset[str] = frozenset({
    "injection_followed",    # LLM followed injected instructions — security breach
    "copyright_violation",   # near-verbatim copy of copyrighted text
    "harmful_content",       # hate speech, dangerous instructions, etc.
    "factual_error",         # verifiable factual claim is wrong
    "unsupported_claim",     # verifiable claim unsupported by any source material
})

_RETRIABLE_HARD_FAIL_CODES: frozenset[str] = frozenset({
    "poor_structure",        # severe structural problems — a revision can fix these
    "main_idea_ignored",     # draft ignores primary topic — revision should address
    "not_review_ready",      # placeholder/stub draft — re-draft may succeed
})

_HARD_FAIL_CODES: frozenset[str] = _TERMINAL_HARD_FAIL_CODES | _RETRIABLE_HARD_FAIL_CODES


class SubScores(CoreContractModel):
    """Nine independent quality dimension scores. Maxima sum to 100.
    structure_flow:15, clarity_readability:15, idea_coverage:15, originality:15,
    tone_audience_fit:10, seo_usefulness:10, factual_safety_sources:10,
    grammar_polish:5, engagement_value:5."""
    structure_flow: int = Field(ge=0, le=15)
    clarity_readability: int = Field(ge=0, le=15)
    idea_coverage: int = Field(ge=0, le=15)
    originality: int = Field(ge=0, le=15)
    tone_audience_fit: int = Field(ge=0, le=10)
    seo_usefulness: int = Field(ge=0, le=10)
    factual_safety_sources: int = Field(ge=0, le=10)
    grammar_polish: int = Field(ge=0, le=5)
    engagement_value: int = Field(ge=0, le=5)


def _sum_sub_scores(sub: Any) -> int:
    if isinstance(sub, dict):
        return sum(sub.get(f, 0) for f in _SUBSCORE_FIELDS)
    return sum(getattr(sub, f, 0) for f in _SUBSCORE_FIELDS)


class QualityReport(CoreContractModel):
    """Invariants: overall_score == sum(sub_scores); pass_flag invariant;
    needs_human when TERMINAL hard-fail flags present; no unknown flag codes accepted."""
    overall_score: int = Field(ge=0, le=100)
    sub_scores: SubScores
    pass_flag: bool
    hard_fail_flags: tuple[str, ...] = Field(default=())
    revision_notes: str = Field(default="")
    needs_human: bool
    improvement_suggestions: tuple[str, ...] = Field(default=())

    @model_validator(mode="after")
    def _valid_hard_fail_codes(self):
        """Reject unknown hard_fail_flags values immediately (fail-closed).

        Only the 8 registered codes are accepted; an unknown code indicates either
        a prompt-injection attempt (the LLM invented an unrecognised string) or a
        configuration bug.  Either way, rejecting it at the schema layer forces
        a fallback rather than silently propagating garbage.
        """
        unknown = [f for f in self.hard_fail_flags if f not in _HARD_FAIL_CODES]
        if unknown:
            raise ValueError(
                f"Unknown hard_fail_flags {unknown!r}; "
                f"allowed codes: {sorted(_HARD_FAIL_CODES)}"
            )
        return self

    @model_validator(mode="after")
    def _overall_score_must_match_sub_scores(self):
        expected = _sum_sub_scores(self.sub_scores)
        if self.overall_score != expected:
            raise ValueError(
                f"overall_score={self.overall_score} does not equal sub_scores sum={expected}. "
                "overall_score must be structure_flow+clarity_readability+idea_coverage+"
                "originality+tone_audience_fit+seo_usefulness+factual_safety_sources+"
                "grammar_polish+engagement_value"
            )
        return self

    @model_validator(mode="after")
    def _pass_flag_must_match_invariant(self):
        expected = self.overall_score >= 80 and not self.hard_fail_flags
        if self.pass_flag != expected:
            raise ValueError(
                f"pass_flag={self.pass_flag} contradicts the invariant "
                f"(overall_score >= 80 AND hard_fail_flags empty). "
                f"Computed: score={self.overall_score} >= 80 is {self.overall_score >= 80}, "
                f"flags empty is {not self.hard_fail_flags}"
            )
        return self

    @model_validator(mode="after")
    def _validate_needs_human_against_flags(self):
        """Bidirectional needs_human ↔ flag-type contract (sixth + final repair).

        Rule: needs_human=True is ONLY permitted when at least one TERMINAL hard-fail
        flag is present.  This closes two bypass paths:

        1. No flags + needs_human=True — rejected (final repair).
           A low-score report with no hard-fail flags must enter the revision loop,
           not bypass it by setting needs_human=True.

        2. RETRIABLE-ONLY flags + needs_human=True — rejected (sixth repair).
           Retriable flags (poor_structure, main_idea_ignored, not_review_ready) route
           through the revision loop.  Setting needs_human=True skips the loop entirely.

        3. TERMINAL flags + needs_human=False — rejected (fifth repair).
           Terminal flags (injection_followed, factual_error, harmful_content, etc.)
           require immediate human review — the graph must not silently pass them.

        4. TERMINAL flags + needs_human=True — accepted (correct contract).

        Mixed (both terminal + retriable): terminal rule dominates → needs_human=True.
        """
        terminal_flags = [f for f in self.hard_fail_flags if f in _TERMINAL_HARD_FAIL_CODES]
        if self.needs_human and not terminal_flags:
            raise ValueError(
                "needs_human=True requires at least one terminal hard-fail flag — "
                "the graph escalates to human review only when a terminal hard fail is present; "
                "a low score or retriable-only flags must enter the revision loop instead. "
                f"Got needs_human=True with flags={list(self.hard_fail_flags)}"
            )
        if terminal_flags and not self.needs_human:
            raise ValueError(
                f"needs_human must be True when terminal hard_fail_flags are present; "
                f"got terminal flags={terminal_flags} but needs_human=False"
            )
        return self

    @model_validator(mode="after")
    def _pass_flag_implies_not_needs_human(self):
        """pass_flag=True requires needs_human=False (final repair).

        pass_flag=True means the blog passed automated quality review: score >= 80 AND
        no hard-fail flags.  A passing blog must NOT be escalated to manual review.
        Setting needs_human=True on a passing report would route the finished product
        to the human queue instead of finalizing — defeating the automation entirely.
        """
        if self.pass_flag and self.needs_human:
            raise ValueError(
                "pass_flag=True requires needs_human=False — a passing blog must not "
                "be escalated to human review. "
                f"Got pass_flag={self.pass_flag}, needs_human={self.needs_human}"
            )
        return self


class StageCost(CoreContractModel):
    stage: str
    cost_inr: float = Field(ge=0.0)
    tier: Literal["cheap", "strong", "stt", "none"]
    tokens_prompt: int = Field(default=0, ge=0)
    tokens_completion: int = Field(default=0, ge=0)


class CostUsage(CoreContractModel):
    """Invariant: total_inr must equal sum(sc.cost_inr) within 1-paisa tolerance."""
    stage_costs: tuple[StageCost, ...] = Field(default=())
    total_inr: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _total_must_match_ledger(self):
        computed = sum(sc.cost_inr for sc in self.stage_costs)
        if abs(self.total_inr - computed) > 0.01:
            raise ValueError(
                f"CostUsage.total_inr={self.total_inr:.4f} does not match "
                f"sum of stage_costs={computed:.4f}"
            )
        return self


class BillableNodeError(Exception):
    """Raised by an LLM node when post-response processing fails after a billable call.

    When a node successfully calls the LLM provider but subsequent work fails
    (telemetry, currency conversion, schema validation, metric emission, etc.),
    the incurred cost must still be recorded in the ledger so the ``total_inr``
    in the final ``BlogPackage`` is truthful.

    This exception carries the ``stage_cost`` so ``_node_with_error_guard`` can
    append it to ``cost_usage`` while setting ``error_state``.  Without this, a
    telemetry or currency error following a successful LLM call would silently drop
    the incurred cost and produce a falsely-compliant ``total_inr``.

    Usage pattern in nodes::

        response = llm.respond(...)
        # Create StageCost IMMEDIATELY after usage is available.
        # usage_cost_inr may raise ValueError for unknown currencies — let it
        # propagate; _node_with_error_guard handles it as a generic Exception.
        cost_inr = usage_cost_inr(response.usage, fx_rates=fx_rates)
        stage_cost = StageCost(stage="draft", cost_inr=cost_inr, ...)

        # All post-response processing — any failure here raises BillableNodeError.
        try:
            tel.record_usage(response.usage, ...)
            # ... parse structured output, emit metrics, build return dict ...
            return {..., "cost_usage": [stage_cost]}
        except Exception as exc:
            raise BillableNodeError(stage_cost, exc) from exc

    The ``cause`` attribute holds the original exception.  Only its type name
    surfaces in ``error_state`` — the raw message is suppressed to avoid leaking
    file paths, stack frames, or LLM-generated content through telemetry.
    """

    def __init__(self, stage_cost: "StageCost", cause: Exception) -> None:
        self.stage_cost = stage_cost
        self.cause = cause
        # Expose only the exception type — raw message may contain sensitive content.
        super().__init__(f"BillableNodeError wrapping {type(cause).__name__}")


# Source of truth: "pass" (not "passed") per AGENT_SPEC §6 and DESIGN §7
BlogStatus = Literal["pass", "needs_human", "stopped_cost_ceiling", "error"]


class BlogEnrichment(CoreContractModel):
    """SEO and discoverability metadata for a passed blog post (AGENT_SPEC §6.4).

    In v1 this is derived from existing plan/draft data by _fallback_enrichment in
    finalize.py (a non-billable assembly node).  All fields are validated for
    non-empty, non-whitespace-only content so that a broken derivation is caught
    immediately rather than producing a silently blank package.

    sixth repair: suggested_tags is now required (non-empty); item-level whitespace
    validation added for alternative_titles and seo_keywords tuples.
    """
    alternative_titles: tuple[str, ...] = Field(default=())
    short_summary: str = Field(default="")
    seo_keywords: tuple[str, ...] = Field(default=())
    suggested_tags: tuple[str, ...] = Field(default=())
    meta_description: str = Field(default="", max_length=160)

    @model_validator(mode="after")
    def _required_fields_non_empty(self):
        """Enforce that all enrichment fields are filled, non-blank, and item-level valid.

        Checks applied (sixth repair):
        - alternative_titles: non-empty tuple; each item must be non-whitespace-only.
        - short_summary: non-empty, non-whitespace-only string.
        - seo_keywords: non-empty tuple; each item must be non-whitespace-only.
        - suggested_tags: non-empty tuple (spec requires at least one tag).
        - meta_description: non-empty, non-whitespace-only string.
        """
        if not self.alternative_titles:
            raise ValueError(
                "BlogEnrichment.alternative_titles must be non-empty "
                "(at least one alternative headline is required)"
            )
        blank_titles = [t for t in self.alternative_titles if not t.strip()]
        if blank_titles:
            raise ValueError(
                f"BlogEnrichment.alternative_titles contains {len(blank_titles)} blank item(s); "
                "every alternative title must be non-whitespace-only"
            )
        if not self.short_summary.strip():
            raise ValueError(
                "BlogEnrichment.short_summary must not be empty or whitespace-only"
            )
        if not self.seo_keywords:
            raise ValueError(
                "BlogEnrichment.seo_keywords must be non-empty "
                "(at least one SEO keyword is required)"
            )
        blank_kw = [k for k in self.seo_keywords if not k.strip()]
        if blank_kw:
            raise ValueError(
                f"BlogEnrichment.seo_keywords contains {len(blank_kw)} blank item(s); "
                "every SEO keyword must be non-whitespace-only"
            )
        if not self.suggested_tags:
            raise ValueError(
                "BlogEnrichment.suggested_tags must be non-empty "
                "(at least one tag is required per AGENT_SPEC §6.4)"
            )
        blank_tags = [t for t in self.suggested_tags if not t.strip()]
        if blank_tags:
            raise ValueError(
                f"BlogEnrichment.suggested_tags contains {len(blank_tags)} blank item(s); "
                "every tag must be non-whitespace-only"
            )
        if not self.meta_description.strip():
            raise ValueError(
                "BlogEnrichment.meta_description must not be empty or whitespace-only"
            )
        return self


class BlogPackage(CoreContractModel):
    """Terminal output record for one Agent 01 blog run (DESIGN §7, AGENT_SPEC §6.4).

    For status='pass': the enrichment fields (alternative_titles, short_summary,
    seo_keywords, meta_description) must be non-empty — finalize.py generates them
    via an LLM call and guarantees non-empty via a fallback.  For all other statuses
    these fields default to empty/None.

    Invariant: status='pass' requires non-empty full_draft, non-blank title, quality
    object, no hard_fail_flags, and non-empty enrichment fields.
    """
    status: BlogStatus
    title: str | None = Field(default=None)
    full_draft: str | None = Field(default=None)
    source_notes: tuple[SourceNote, ...] = Field(default=())
    quality: QualityReport | None = Field(default=None)
    hard_fail_flags: tuple[str, ...] = Field(default=())
    improvement_suggestions: tuple[str, ...] = Field(default=())
    cost: CostUsage
    notes: str | None = Field(default=None)
    revision_count: int = Field(default=0, ge=0)
    # ── Enrichment fields (AGENT_SPEC §6.4) — required for status='pass' ───
    alternative_titles: tuple[str, ...] = Field(default=())
    short_summary: str | None = Field(default=None)
    seo_keywords: tuple[str, ...] = Field(default=())
    suggested_tags: tuple[str, ...] = Field(default=())
    meta_description: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def _passed_package_invariants(self):
        if self.status == "pass":
            # Core content
            if not (self.full_draft and self.full_draft.strip()):
                raise ValueError(
                    "A passed BlogPackage must have a non-empty, non-blank full_draft"
                )
            if not (self.title and self.title.strip()):
                raise ValueError(
                    "A passed BlogPackage must have a non-empty, non-blank title"
                )
            if self.quality is None:
                raise ValueError("A passed BlogPackage must have a QualityReport")
            # Accumulated flags must NEVER appear in a passed package.
            # finalize.py uses quality.hard_fail_flags (always empty for pass_flag=True)
            # not the accumulated state["hard_fail_flags"], so historical retriable flags
            # from prior revision cycles are excluded.
            if self.hard_fail_flags:
                raise ValueError(
                    f"A passed BlogPackage must not have hard_fail_flags; "
                    f"got {self.hard_fail_flags}"
                )
            # Quality-report cross-checks — defense-in-depth on top of QualityReport's
            # own validators (final repair: verify the report itself says "pass").
            if not self.quality.pass_flag:
                raise ValueError(
                    "A passed BlogPackage must have quality.pass_flag=True "
                    "(the QualityReport must independently confirm a passing evaluation)"
                )
            if self.quality.overall_score < 80:
                raise ValueError(
                    f"A passed BlogPackage must have quality.overall_score >= 80; "
                    f"got {self.quality.overall_score}"
                )
            if self.quality.needs_human:
                raise ValueError(
                    "A passed BlogPackage must have quality.needs_human=False "
                    "(a blog pending human review cannot be marked as passed)"
                )
            # Enrichment fields — generated by finalize.py for passed packages
            if not self.alternative_titles:
                raise ValueError(
                    "A passed BlogPackage must have at least one alternative_title"
                )
            if not (self.short_summary and self.short_summary.strip()):
                raise ValueError(
                    "A passed BlogPackage must have a non-empty, non-blank short_summary"
                )
            if not self.seo_keywords:
                raise ValueError(
                    "A passed BlogPackage must have at least one seo_keyword"
                )
            if not self.suggested_tags:
                raise ValueError(
                    "A passed BlogPackage must have at least one suggested_tag "
                    "(sixth repair: suggested_tags required per AGENT_SPEC §6.4)"
                )
            if not (self.meta_description and self.meta_description.strip()):
                raise ValueError(
                    "A passed BlogPackage must have a non-empty, non-blank meta_description"
                )
            # Enrichment tuple item validation — each item must be non-whitespace-only.
            # BlogEnrichment enforces this on its own fields, but BlogPackage stores these
            # values directly so callers constructing BlogPackage must pass the same rule.
            for _field_name, _items in [
                ("alternative_titles", self.alternative_titles),
                ("seo_keywords", self.seo_keywords),
                ("suggested_tags", self.suggested_tags),
            ]:
                _blank = [t for t in _items if not (isinstance(t, str) and t.strip())]
                if _blank:
                    raise ValueError(
                        f"A passed BlogPackage.{_field_name} contains {len(_blank)} blank "
                        "item(s) — every item must be non-whitespace-only"
                    )
        return self
