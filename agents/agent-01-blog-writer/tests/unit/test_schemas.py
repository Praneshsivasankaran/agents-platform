"""Unit tests — Agent 01 schema contracts (DESIGN §7).

Seventh repair pass:
- ExtractedIdeas: tests updated for new fields (main_idea, key_points, suggested_angle)
  replacing the old ideas tuple.  Validator: usable=True requires non-blank main_idea.
- BlogPlan: tests for new fields (title_candidates, audience, angle, target_keywords)
  with default values so existing tests still pass unchanged.

Sixth repair pass (intact):
- BlogEnrichment: item-level whitespace validation for alternative_titles/seo_keywords;
  suggested_tags is now required (was optional).
- QualityReport: retriable-only flags with needs_human=True are rejected (sixth repair) —
  prevents the LLM from bypassing the revision loop.
- BlogPackage._passed_package_invariants: suggested_tags check added.

Fifth repair pass (intact):
- BlogEnrichment: new schema with required-field validation.
- BlogPlan: whitespace-only title/tone rejected.
- QualityReport: unknown hard_fail_flags values rejected.
- BlogPackage._passed_package_invariants: requires non-empty enrichment for 'pass'.
- CoreContractModel: allow_inf_nan=False — StageCost(cost_inr=inf) raises ValidationError.

Previous repair notes (intact):
- BlogStatus: "passed" renamed to "pass".
- BlogPackage: enrichment fields restored; validator uses "pass" status.
- BlogPlan: blank title/tone rejected; sections max=6; blank section headings rejected.
- QualityReport: needs_human=True only required for TERMINAL hard-fail flags.
"""

from __future__ import annotations

import math
import pytest
from pydantic import ValidationError

from agent.nodes.finalize import _derive_short_summary
from agent.schemas import (
    BlogEnrichment,
    BlogPackage,
    BlogPlan,
    CostUsage,
    ExtractedIdeas,
    QualityReport,
    SourceNote,
    StageCost,
    SubScores,
    _HARD_FAIL_CODES,
    _RETRIABLE_HARD_FAIL_CODES,
    _TERMINAL_HARD_FAIL_CODES,
)
from core.interfaces.base import CoreContractModel


# ---------------------------------------------------------------------------
# 1. All schemas are CoreContractModel subclasses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", [
    SourceNote, ExtractedIdeas, BlogPlan, SubScores,
    QualityReport, StageCost, CostUsage, BlogEnrichment, BlogPackage,
])
def test_is_core_contract_model(cls):
    assert issubclass(cls, CoreContractModel)


# ---------------------------------------------------------------------------
# 2. Frozen — mutations are rejected
# ---------------------------------------------------------------------------

def test_source_note_frozen():
    note = SourceNote(title="test")
    with pytest.raises((TypeError, ValidationError)):
        note.title = "mutated"  # type: ignore[misc]


def test_blog_plan_frozen():
    plan = BlogPlan(
        title="T", sections=("A", "B", "C"), tone="informative", target_word_count=500,
        audience="developers", angle="practical guide",
        title_candidates=("Alt T",), target_keywords=("test",),
    )
    with pytest.raises((TypeError, ValidationError)):
        plan.title = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3. extra=forbid — unknown fields are rejected at construction
# ---------------------------------------------------------------------------

def test_source_note_rejects_unknown_field():
    with pytest.raises(ValidationError):
        SourceNote(title="t", unknown_field="oops")  # type: ignore[call-arg]


def test_blog_plan_rejects_unknown_field():
    with pytest.raises(ValidationError):
        BlogPlan(
            title="T", sections=("A", "B", "C"), tone="casual",
            target_word_count=400,
            audience="developers", angle="practical", title_candidates=("A",), target_keywords=("kw",),
            unknown="x",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# 4. SubScores — 9-dimension design with per-dimension bounds
# ---------------------------------------------------------------------------

def _make_sub_scores(**overrides) -> SubScores:
    defaults = dict(
        structure_flow=10, clarity_readability=10, idea_coverage=10, originality=10,
        tone_audience_fit=7, seo_usefulness=7, factual_safety_sources=7,
        grammar_polish=3, engagement_value=3,
    )
    defaults.update(overrides)
    return SubScores(**defaults)


def _sub_scores_sum(ss: SubScores) -> int:
    return (
        ss.structure_flow + ss.clarity_readability + ss.idea_coverage + ss.originality
        + ss.tone_audience_fit + ss.seo_usefulness + ss.factual_safety_sources
        + ss.grammar_polish + ss.engagement_value
    )


def test_sub_scores_all_9_fields_present():
    ss = _make_sub_scores()
    for field in (
        "structure_flow", "clarity_readability", "idea_coverage", "originality",
        "tone_audience_fit", "seo_usefulness", "factual_safety_sources",
        "grammar_polish", "engagement_value",
    ):
        assert hasattr(ss, field)


def test_sub_scores_valid_maxima():
    ss = SubScores(
        structure_flow=15, clarity_readability=15, idea_coverage=15, originality=15,
        tone_audience_fit=10, seo_usefulness=10, factual_safety_sources=10,
        grammar_polish=5, engagement_value=5,
    )
    assert _sub_scores_sum(ss) == 100


def test_sub_scores_rejects_structure_flow_over_max():
    with pytest.raises(ValidationError):
        SubScores(
            structure_flow=16,
            clarity_readability=15, idea_coverage=15, originality=15,
            tone_audience_fit=10, seo_usefulness=10, factual_safety_sources=10,
            grammar_polish=5, engagement_value=5,
        )


def test_sub_scores_rejects_negative_dimension():
    with pytest.raises(ValidationError):
        _make_sub_scores(structure_flow=-1)


def test_sub_scores_rejects_engagement_value_over_max():
    with pytest.raises(ValidationError):
        _make_sub_scores(engagement_value=6)


def test_sub_scores_rejects_grammar_polish_over_max():
    with pytest.raises(ValidationError):
        _make_sub_scores(grammar_polish=6)


# ---------------------------------------------------------------------------
# 5. QualityReport — validators
# ---------------------------------------------------------------------------

def _make_quality_pass(**overrides) -> QualityReport:
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    base = dict(
        sub_scores=ss, overall_score=total, pass_flag=False,
        needs_human=False, revision_notes="Needs improvement.",
    )
    base.update(overrides)
    return QualityReport(**base)


def _make_quality_passing() -> QualityReport:
    ss = SubScores(
        structure_flow=14, clarity_readability=13, idea_coverage=14, originality=13,
        tone_audience_fit=9, seo_usefulness=8, factual_safety_sources=9,
        grammar_polish=4, engagement_value=4,
    )
    return QualityReport(
        sub_scores=ss, overall_score=_sub_scores_sum(ss),
        pass_flag=True, needs_human=False,
    )


def test_quality_report_pass():
    report = _make_quality_passing()
    assert report.pass_flag is True
    assert report.hard_fail_flags == ()
    assert report.overall_score >= 80


def test_quality_report_revise():
    report = _make_quality_pass()
    assert not report.pass_flag
    assert not report.needs_human


def test_quality_report_terminal_hard_fail_requires_needs_human():
    """Terminal hard-fail flags require needs_human=True."""
    ss = _make_sub_scores(structure_flow=3, clarity_readability=3)
    total = _sub_scores_sum(ss)
    report = QualityReport(
        sub_scores=ss, overall_score=total, pass_flag=False,
        needs_human=True, hard_fail_flags=("injection_followed",),
    )
    assert report.needs_human is True
    assert "injection_followed" in report.hard_fail_flags


def test_quality_report_retriable_hard_fail_does_not_require_needs_human():
    """Retriable hard-fail flags do NOT require needs_human=True (fifth repair)."""
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    for flag in ("poor_structure", "main_idea_ignored", "not_review_ready"):
        report = QualityReport(
            sub_scores=ss, overall_score=total, pass_flag=False,
            needs_human=False, hard_fail_flags=(flag,),
        )
        assert report.needs_human is False
        assert flag in report.hard_fail_flags


def test_quality_report_rejects_unknown_hard_fail_code():
    """Unknown hard_fail_flags are rejected immediately (fifth repair)."""
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    with pytest.raises(ValidationError, match="Unknown hard_fail_flags"):
        QualityReport(
            sub_scores=ss, overall_score=total, pass_flag=False,
            needs_human=True,
            hard_fail_flags=("invented_flag_xyz",),
        )


def test_quality_report_rejects_mixed_known_and_unknown_codes():
    """Even one unknown code in the tuple must be rejected."""
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    with pytest.raises(ValidationError, match="Unknown hard_fail_flags"):
        QualityReport(
            sub_scores=ss, overall_score=total, pass_flag=False,
            needs_human=True,
            hard_fail_flags=("injection_followed", "totally_made_up"),
        )


def test_quality_report_overall_score_must_match_sub_scores():
    ss = _make_sub_scores()
    real_sum = _sub_scores_sum(ss)
    with pytest.raises(ValidationError, match="overall_score"):
        QualityReport(
            sub_scores=ss, overall_score=real_sum + 5,
            pass_flag=False, needs_human=False,
        )


def test_quality_report_pass_flag_must_match_invariant():
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)  # 67 < 80
    with pytest.raises(ValidationError, match="pass_flag"):
        QualityReport(
            sub_scores=ss, overall_score=total,
            pass_flag=True,  # WRONG
            needs_human=False,
        )


def test_quality_report_terminal_hard_fail_without_needs_human_rejected():
    """Terminal hard-fail without needs_human=True is rejected."""
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    with pytest.raises(ValidationError, match="needs_human"):
        QualityReport(
            sub_scores=ss, overall_score=total, pass_flag=False,
            needs_human=False,                       # WRONG for terminal flag
            hard_fail_flags=("injection_followed",),
        )


def test_quality_report_retriable_only_flags_with_needs_human_rejected():
    """Retriable-only hard-fail flags with needs_human=True are rejected (sixth repair).

    Setting needs_human=True on a retriable-only result would bypass the revision loop
    and escalate directly to human review, defeating the graph's revision contract.
    """
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    for retriable_flag in ("poor_structure", "main_idea_ignored", "not_review_ready"):
        with pytest.raises(ValidationError, match="needs_human"):
            QualityReport(
                sub_scores=ss, overall_score=total, pass_flag=False,
                needs_human=True,           # WRONG: only retriable flags present
                hard_fail_flags=(retriable_flag,),
            )


def test_quality_report_retriable_only_flags_accept_needs_human_false():
    """Retriable-only flags with needs_human=False remain valid (revision loop contract)."""
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    for retriable_flag in ("poor_structure", "main_idea_ignored", "not_review_ready"):
        report = QualityReport(
            sub_scores=ss, overall_score=total, pass_flag=False,
            needs_human=False,              # CORRECT: revision loop will handle this
            hard_fail_flags=(retriable_flag,),
        )
        assert report.needs_human is False


def test_quality_report_mixed_terminal_and_retriable_flags_needs_human_true():
    """Mixed flags (terminal + retriable): terminal rule dominates → needs_human=True required."""
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    # This should succeed (needs_human=True is correct when terminal flag is present)
    report = QualityReport(
        sub_scores=ss, overall_score=total, pass_flag=False,
        needs_human=True,
        hard_fail_flags=("injection_followed", "poor_structure"),
    )
    assert report.needs_human is True


def test_quality_report_dimension_out_of_range():
    with pytest.raises(ValidationError):
        SubScores(
            structure_flow=16,
            clarity_readability=15, idea_coverage=15, originality=15,
            tone_audience_fit=10, seo_usefulness=10, factual_safety_sources=10,
            grammar_polish=5, engagement_value=5,
        )


# ---------------------------------------------------------------------------
# 6. Hard-fail code sets
# ---------------------------------------------------------------------------

def test_terminal_and_retriable_codes_are_disjoint():
    assert _TERMINAL_HARD_FAIL_CODES.isdisjoint(_RETRIABLE_HARD_FAIL_CODES)


def test_hard_fail_codes_is_union():
    assert _HARD_FAIL_CODES == _TERMINAL_HARD_FAIL_CODES | _RETRIABLE_HARD_FAIL_CODES


def test_terminal_codes_contain_security_critical_flags():
    for code in ("injection_followed", "copyright_violation", "harmful_content"):
        assert code in _TERMINAL_HARD_FAIL_CODES


def test_retriable_codes_contain_structural_flags():
    for code in ("poor_structure", "main_idea_ignored", "not_review_ready"):
        assert code in _RETRIABLE_HARD_FAIL_CODES


# ---------------------------------------------------------------------------
# 7. ExtractedIdeas — seventh repair: main_idea + key_points replace ideas tuple
# ---------------------------------------------------------------------------

def test_extracted_ideas_usable_with_main_idea():
    """usable=True with a non-blank main_idea is accepted."""
    ideas = ExtractedIdeas(
        main_idea="Machine learning is transforming healthcare.",
        key_points=("ML improves accuracy.", "AI speeds up triage."),
        usable=True,
    )
    assert ideas.usable is True
    assert ideas.thin_reason is None
    assert ideas.main_idea == "Machine learning is transforming healthcare."
    assert len(ideas.key_points) == 2


def test_extracted_ideas_usable_requires_non_blank_main_idea():
    """usable=True with empty main_idea is rejected (seventh repair)."""
    with pytest.raises(ValidationError, match="non-blank main_idea"):
        ExtractedIdeas(usable=True, main_idea="", key_points=("A point.",))


def test_extracted_ideas_usable_requires_main_idea_not_whitespace_only():
    """usable=True with whitespace-only main_idea is rejected."""
    with pytest.raises(ValidationError, match="non-blank main_idea"):
        ExtractedIdeas(usable=True, main_idea="   ", key_points=("A point.",))


def test_extracted_ideas_usable_no_key_points_allowed():
    """usable=True with non-blank main_idea but empty key_points is valid.

    The validator only requires main_idea; key_points is not required for usable=True.
    """
    ideas = ExtractedIdeas(
        main_idea="ML in healthcare.", key_points=(), usable=True,
    )
    assert ideas.usable is True
    assert ideas.key_points == ()


def test_extracted_ideas_with_suggested_angle():
    """suggested_angle is an optional string field."""
    ideas = ExtractedIdeas(
        main_idea="ML in healthcare.",
        suggested_angle="focus on diagnostic improvements",
        usable=True,
    )
    assert ideas.suggested_angle == "focus on diagnostic improvements"


def test_extracted_ideas_suggested_angle_defaults_none():
    ideas = ExtractedIdeas(main_idea="ML in healthcare.", usable=True)
    assert ideas.suggested_angle is None


def test_extracted_ideas_thin():
    ideas = ExtractedIdeas(
        main_idea="", key_points=(), usable=False, thin_reason="Too short to draft a blog."
    )
    assert not ideas.usable
    assert ideas.thin_reason == "Too short to draft a blog."


def test_extracted_ideas_usable_false_allows_empty_main_idea():
    """usable=False does not require main_idea (thin-input path)."""
    ideas = ExtractedIdeas(usable=False, main_idea="", key_points=(), thin_reason="Not enough ideas.")
    assert ideas.usable is False
    assert ideas.main_idea == ""
    assert ideas.key_points == ()


def test_extracted_ideas_source_notes_default_empty():
    ideas = ExtractedIdeas(usable=False, thin_reason="Too short.")
    assert ideas.source_notes == ()


# ---------------------------------------------------------------------------
# 8. BlogPlan — section / word-count / blank / whitespace constraints
# ---------------------------------------------------------------------------
#
# Ninth repair: audience and angle are now required (no default); title_candidates
# and target_keywords require at least 1 item (min_length=1, no default).
# Use _make_bp() helper to avoid repeating the required fields in every test.

def _make_bp(**kwargs) -> BlogPlan:
    """Build a minimal valid BlogPlan; override fields via kwargs.

    Ninth repair: all four newly-required fields (audience, angle,
    title_candidates, target_keywords) are provided as defaults here so
    individual tests only need to specify the field under test.
    """
    defaults: dict = dict(
        title="Test Blog Title",
        sections=("Introduction", "Main Body", "Conclusion"),
        tone="informative",
        target_word_count=500,
        # Ninth repair — required, no defaults in schema:
        audience="technology enthusiasts",
        angle="practical applications",
        title_candidates=("Alt Title A",),
        target_keywords=("technology",),
    )
    defaults.update(kwargs)
    return BlogPlan(**defaults)


def test_blog_plan_valid():
    plan = _make_bp(sections=("Intro", "Body", "Outro"), tone="casual", target_word_count=600)
    assert len(plan.sections) == 3
    assert plan.target_word_count == 600
    # Ninth repair: required fields are present
    assert plan.audience == "technology enthusiasts"
    assert plan.angle == "practical applications"
    assert len(plan.title_candidates) >= 1
    assert len(plan.target_keywords) >= 1


def test_blog_plan_word_count_too_low():
    with pytest.raises(ValidationError):
        _make_bp(target_word_count=99)


def test_blog_plan_word_count_too_high():
    with pytest.raises(ValidationError):
        _make_bp(target_word_count=5001)


def test_blog_plan_requires_at_least_three_sections():
    """sections tuple must have at least 3 entries."""
    with pytest.raises(ValidationError):
        _make_bp(sections=("A", "B"))

    with pytest.raises(ValidationError):
        _make_bp(sections=("A",))

    with pytest.raises(ValidationError):
        _make_bp(sections=())


def test_blog_plan_rejects_more_than_six_sections():
    """sections tuple must not exceed 6 entries."""
    with pytest.raises(ValidationError):
        _make_bp(sections=("A", "B", "C", "D", "E", "F", "G"))  # 7 sections


def test_blog_plan_accepts_exactly_six_sections():
    plan = _make_bp(sections=("A", "B", "C", "D", "E", "F"))
    assert len(plan.sections) == 6


def test_blog_plan_rejects_blank_title():
    """title must be non-blank."""
    with pytest.raises(ValidationError):
        _make_bp(title="")


def test_blog_plan_rejects_whitespace_only_title():
    """title=' ' satisfies min_length=1 but must be rejected as whitespace-only (fifth repair)."""
    with pytest.raises(ValidationError):
        _make_bp(title=" ")


def test_blog_plan_rejects_blank_tone():
    """tone must be non-blank."""
    with pytest.raises(ValidationError):
        _make_bp(tone="")


def test_blog_plan_rejects_whitespace_only_tone():
    """tone='  ' satisfies min_length=1 but must be rejected as whitespace-only (fifth repair)."""
    with pytest.raises(ValidationError):
        _make_bp(tone="  ")


def test_blog_plan_rejects_blank_section_headings():
    """Blank section headings are rejected."""
    with pytest.raises(ValidationError):
        _make_bp(sections=("A", "", "C"))

    with pytest.raises(ValidationError):
        _make_bp(sections=("A", "   ", "C"))


# ---------------------------------------------------------------------------
# 8b. BlogPlan — ninth repair: required fields, min_length=1 tuple enforcement
# ---------------------------------------------------------------------------

def test_blog_plan_requires_audience():
    """Ninth repair: audience has no default — omitting it raises ValidationError."""
    with pytest.raises(ValidationError):
        BlogPlan(
            title="T", sections=("A", "B", "C"), tone="informative", target_word_count=300,
            angle="practical", title_candidates=("Alt",), target_keywords=("kw",),
            # audience omitted
        )


def test_blog_plan_requires_angle():
    """Ninth repair: angle has no default — omitting it raises ValidationError."""
    with pytest.raises(ValidationError):
        BlogPlan(
            title="T", sections=("A", "B", "C"), tone="informative", target_word_count=300,
            audience="developers", title_candidates=("Alt",), target_keywords=("kw",),
            # angle omitted
        )


def test_blog_plan_requires_nonempty_title_candidates():
    """Ninth repair: title_candidates has min_length=1 — empty tuple raises ValidationError."""
    with pytest.raises(ValidationError):
        BlogPlan(
            title="T", sections=("A", "B", "C"), tone="informative", target_word_count=300,
            audience="developers", angle="practical",
            title_candidates=(),  # empty — violates min_length=1
            target_keywords=("kw",),
        )


def test_blog_plan_requires_nonempty_target_keywords():
    """Ninth repair: target_keywords has min_length=1 — empty tuple raises ValidationError."""
    with pytest.raises(ValidationError):
        BlogPlan(
            title="T", sections=("A", "B", "C"), tone="informative", target_word_count=300,
            audience="developers", angle="practical",
            title_candidates=("Alt",),
            target_keywords=(),  # empty — violates min_length=1
        )


def test_blog_plan_rejects_whitespace_only_audience():
    """audience='  ' must be rejected (non-blank required, eighth repair)."""
    with pytest.raises(ValidationError, match="audience"):
        _make_bp(audience="   ")


def test_blog_plan_rejects_whitespace_only_angle():
    """angle='  ' must be rejected (non-blank required, eighth repair)."""
    with pytest.raises(ValidationError, match="angle"):
        _make_bp(angle="   ")


def test_blog_plan_rejects_empty_angle():
    """angle='' must be rejected — the empty string fails min_length=1."""
    with pytest.raises(ValidationError):
        _make_bp(angle="")


def test_blog_plan_rejects_empty_audience():
    """audience='' must be rejected — the empty string fails min_length=1."""
    with pytest.raises(ValidationError):
        _make_bp(audience="")


def test_blog_plan_rejects_blank_title_candidate():
    """title_candidates containing a blank string must be rejected (eighth repair)."""
    with pytest.raises(ValidationError, match="title_candidates"):
        _make_bp(title_candidates=("Good Title", ""))


def test_blog_plan_rejects_blank_target_keyword():
    """target_keywords containing a blank string must be rejected (eighth repair)."""
    with pytest.raises(ValidationError, match="target_keywords"):
        _make_bp(target_keywords=("machine learning", "  "))


def test_blog_plan_rejects_blank_key_point():
    """key_points containing a blank string must be rejected (eighth repair)."""
    with pytest.raises(ValidationError, match="key_points"):
        _make_bp(key_points=("Good point", ""))


def test_blog_plan_accepts_valid_tuple_items():
    """Non-blank tuples for title_candidates, target_keywords, key_points are accepted."""
    plan = _make_bp(
        title_candidates=("Title A", "Title B"),
        target_keywords=("ai", "healthcare"),
        key_points=("Point 1", "Point 2"),
    )
    assert len(plan.title_candidates) == 2
    assert len(plan.target_keywords) == 2
    assert len(plan.key_points) == 2


def test_blog_plan_key_points_can_be_empty():
    """key_points remains optional (no min_length constraint) — empty tuple is valid."""
    plan = _make_bp(key_points=())
    assert plan.key_points == ()


def test_blog_plan_accepts_single_title_candidate():
    """title_candidates with exactly 1 item (min_length=1) is the minimum valid value."""
    plan = _make_bp(title_candidates=("Only Option",))
    assert plan.title_candidates == ("Only Option",)


def test_blog_plan_accepts_single_target_keyword():
    """target_keywords with exactly 1 item (min_length=1) is the minimum valid value."""
    plan = _make_bp(target_keywords=("ai",))
    assert plan.target_keywords == ("ai",)


# ---------------------------------------------------------------------------
# 9. StageCost — cost/token bounds + non-finite rejection (fifth repair)
# ---------------------------------------------------------------------------

def test_stage_cost_valid():
    sc = StageCost(stage="draft", cost_inr=10.5, tier="strong")
    assert sc.cost_inr == 10.5
    assert sc.tier == "strong"


def test_stage_cost_negative_cost_rejected():
    with pytest.raises(ValidationError):
        StageCost(stage="draft", cost_inr=-1.0, tier="strong")


def test_stage_cost_invalid_tier():
    with pytest.raises(ValidationError):
        StageCost(stage="draft", cost_inr=5.0, tier="ultra")  # type: ignore[arg-type]


def test_stage_cost_rejects_infinite_cost():
    """allow_inf_nan=False on CoreContractModel prevents inf cost (fifth repair)."""
    with pytest.raises(ValidationError):
        StageCost(stage="draft", cost_inr=math.inf, tier="strong")


def test_stage_cost_rejects_nan_cost():
    """allow_inf_nan=False on CoreContractModel prevents NaN cost (fifth repair)."""
    with pytest.raises(ValidationError):
        StageCost(stage="draft", cost_inr=math.nan, tier="strong")


def test_cost_usage_rejects_infinite_total():
    """CostUsage.total_inr=inf is rejected by allow_inf_nan=False (fifth repair)."""
    with pytest.raises(ValidationError):
        CostUsage(stage_costs=(), total_inr=math.inf)


# ---------------------------------------------------------------------------
# 10. CostUsage — total_inr + stage_costs shape + ledger validator
# ---------------------------------------------------------------------------

def test_cost_usage_empty():
    cu = CostUsage(stage_costs=(), total_inr=0.0)
    assert cu.total_inr == 0.0
    assert cu.stage_costs == ()


def test_cost_usage_with_entries():
    sc1 = StageCost(stage="normalize", cost_inr=0.5, tier="cheap")
    sc2 = StageCost(stage="draft", cost_inr=10.0, tier="strong")
    cu = CostUsage(stage_costs=(sc1, sc2), total_inr=10.5)
    assert len(cu.stage_costs) == 2
    assert cu.total_inr == 10.5


def test_cost_usage_negative_total_rejected():
    with pytest.raises(ValidationError):
        CostUsage(stage_costs=(), total_inr=-0.01)


def test_cost_usage_total_mismatch_rejected():
    sc = StageCost(stage="draft", cost_inr=10.0, tier="strong")
    with pytest.raises(ValidationError):
        CostUsage(stage_costs=(sc,), total_inr=99.0)


# ---------------------------------------------------------------------------
# 11. BlogEnrichment — new schema (fifth repair)
# ---------------------------------------------------------------------------

def _make_enrichment(**overrides) -> BlogEnrichment:
    """Create a valid BlogEnrichment with all required fields."""
    defaults = dict(
        alternative_titles=("Alt Title A", "Alt Title B"),
        short_summary="A concise summary of the blog post.",
        seo_keywords=("keyword1", "keyword2"),
        suggested_tags=("tag1", "tag2"),
        meta_description="A one-sentence meta description for search engines.",
    )
    defaults.update(overrides)
    return BlogEnrichment(**defaults)


def test_blog_enrichment_valid():
    enrich = _make_enrichment()
    assert len(enrich.alternative_titles) == 2
    assert enrich.short_summary != ""
    assert len(enrich.seo_keywords) == 2
    assert enrich.meta_description != ""


def test_blog_enrichment_rejects_empty_alternative_titles():
    """alternative_titles must be non-empty (fifth repair)."""
    with pytest.raises(ValidationError, match="alternative_titles"):
        _make_enrichment(alternative_titles=())


def test_blog_enrichment_rejects_empty_short_summary():
    """short_summary must not be empty or whitespace-only (fifth repair)."""
    with pytest.raises(ValidationError, match="short_summary"):
        _make_enrichment(short_summary="")


def test_blog_enrichment_rejects_whitespace_only_short_summary():
    with pytest.raises(ValidationError, match="short_summary"):
        _make_enrichment(short_summary="   ")


def test_derive_short_summary_skips_markdown_title_and_ends_sentence():
    draft = """# AI Agents for Small Business

In the world of small business, time is the most precious commodity. Every day, teams lose hours to repeated support tickets and routine knowledge-work tasks.

## A later section
More text here.
"""

    summary = _derive_short_summary(title="AI Agents for Small Business", draft=draft)

    assert not summary.startswith("#")
    assert "AI Agents for Small Business" not in summary
    assert summary == "In the world of small business, time is the most precious commodity."


def test_derive_short_summary_falls_back_when_draft_has_only_heading():
    summary = _derive_short_summary(title="Fallback Title", draft="# Fallback Title")

    assert summary == "A blog post about Fallback Title."


def test_blog_enrichment_rejects_empty_seo_keywords():
    """seo_keywords must be non-empty (fifth repair)."""
    with pytest.raises(ValidationError, match="seo_keywords"):
        _make_enrichment(seo_keywords=())


def test_blog_enrichment_rejects_empty_meta_description():
    """meta_description must not be empty or whitespace-only (fifth repair)."""
    with pytest.raises(ValidationError, match="meta_description"):
        _make_enrichment(meta_description="")


def test_blog_enrichment_rejects_whitespace_only_meta_description():
    with pytest.raises(ValidationError, match="meta_description"):
        _make_enrichment(meta_description="\t")


def test_blog_enrichment_rejects_empty_suggested_tags():
    """suggested_tags is required and must be non-empty (sixth repair: was optional)."""
    with pytest.raises(ValidationError, match="suggested_tags"):
        _make_enrichment(suggested_tags=())


def test_blog_enrichment_rejects_whitespace_only_alternative_title_item():
    """Each item in alternative_titles must be non-whitespace-only (sixth repair)."""
    with pytest.raises(ValidationError, match="alternative_titles"):
        _make_enrichment(alternative_titles=("Valid Title", "   "))


def test_blog_enrichment_rejects_whitespace_only_alternative_title_single():
    """A single whitespace-only alternative title is rejected (sixth repair)."""
    with pytest.raises(ValidationError, match="alternative_titles"):
        _make_enrichment(alternative_titles=("\t",))


def test_blog_enrichment_rejects_whitespace_only_seo_keyword_item():
    """Each item in seo_keywords must be non-whitespace-only (sixth repair)."""
    with pytest.raises(ValidationError, match="seo_keywords"):
        _make_enrichment(seo_keywords=("valid-keyword", "  "))


def test_blog_enrichment_rejects_whitespace_only_seo_keyword_single():
    """A single whitespace-only SEO keyword is rejected (sixth repair)."""
    with pytest.raises(ValidationError, match="seo_keywords"):
        _make_enrichment(seo_keywords=("\n",))


def test_blog_enrichment_accepts_non_empty_suggested_tags():
    """suggested_tags with at least one item is valid."""
    enrich = _make_enrichment(suggested_tags=("ai",))
    assert enrich.suggested_tags == ("ai",)


def test_blog_enrichment_frozen():
    enrich = _make_enrichment()
    with pytest.raises((TypeError, ValidationError)):
        enrich.short_summary = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 12. BlogPackage — fifth repair: 'pass' packages require enrichment
# ---------------------------------------------------------------------------

def _make_cost() -> CostUsage:
    return CostUsage(stage_costs=(), total_inr=0.0)


def _make_passing_quality() -> QualityReport:
    return _make_quality_passing()


_ENRICH = dict(
    alternative_titles=("Alt Title A", "Alt Title B"),
    short_summary="A concise summary of the blog post.",
    seo_keywords=("keyword1", "keyword2"),
    suggested_tags=("tag1",),
    meta_description="A one-sentence meta description.",
)


def _make_passed_pkg(**overrides) -> BlogPackage:
    """Create a valid 'pass' BlogPackage with all required enrichment fields."""
    defaults = dict(
        status="pass",
        cost=_make_cost(),
        hard_fail_flags=(),
        title="Machine Learning in Healthcare",
        full_draft="# ML in Healthcare\n\nContent here.",
        quality=_make_passing_quality(),
        **_ENRICH,
    )
    defaults.update(overrides)
    return BlogPackage(**defaults)


def test_blog_package_passed():
    """status='pass' (not 'passed') is the correct value."""
    pkg = _make_passed_pkg()
    assert pkg.status == "pass"
    assert pkg.title == "Machine Learning in Healthcare"
    assert pkg.full_draft is not None


def test_blog_package_passed_status_string_is_pass():
    """Confirm the literal value is 'pass', not 'passed'."""
    pkg = _make_passed_pkg()
    assert pkg.status == "pass"
    # 'passed' is NOT a valid status
    with pytest.raises(ValidationError):
        _make_passed_pkg(status="passed")  # type: ignore[arg-type]


def test_blog_package_passed_without_title_rejected():
    """title is required for passed packages."""
    with pytest.raises(ValidationError):
        _make_passed_pkg(title=None)


def test_blog_package_passed_without_full_draft_rejected():
    with pytest.raises(ValidationError):
        _make_passed_pkg(full_draft=None)


def test_blog_package_passed_without_enrichment_rejected():
    """A 'pass' package without alternative_titles is rejected (fifth repair)."""
    with pytest.raises(ValidationError, match="alternative_title"):
        _make_passed_pkg(alternative_titles=())


def test_blog_package_passed_without_short_summary_rejected():
    """A 'pass' package without short_summary is rejected (fifth repair)."""
    with pytest.raises(ValidationError, match="short_summary"):
        _make_passed_pkg(short_summary=None)


def test_blog_package_passed_without_seo_keywords_rejected():
    """A 'pass' package without seo_keywords is rejected (fifth repair)."""
    with pytest.raises(ValidationError, match="seo_keyword"):
        _make_passed_pkg(seo_keywords=())


def test_blog_package_passed_without_meta_description_rejected():
    """A 'pass' package without meta_description is rejected (fifth repair)."""
    with pytest.raises(ValidationError, match="meta_description"):
        _make_passed_pkg(meta_description=None)


def test_blog_package_passed_without_suggested_tags_rejected():
    """A 'pass' package without suggested_tags is rejected (sixth repair)."""
    with pytest.raises(ValidationError, match="suggested_tag"):
        _make_passed_pkg(suggested_tags=())


def test_blog_package_enrichment_fields_present():
    """Enrichment fields are present with empty defaults on non-'pass' packages."""
    pkg = BlogPackage(
        status="error",
        cost=_make_cost(),
        hard_fail_flags=(),
        notes="error",
    )
    assert hasattr(pkg, "alternative_titles")
    assert hasattr(pkg, "short_summary")
    assert hasattr(pkg, "seo_keywords")
    assert hasattr(pkg, "suggested_tags")
    assert hasattr(pkg, "meta_description")
    # Non-'pass' packages can have empty enrichment (no requirement)
    assert pkg.alternative_titles == ()
    assert pkg.short_summary is None
    assert pkg.seo_keywords == ()
    assert pkg.suggested_tags == ()
    assert pkg.meta_description is None


def test_blog_package_enrichment_fields_can_be_set():
    pkg = _make_passed_pkg(
        alternative_titles=("Alt 1", "Alt 2"),
        short_summary="A brief summary.",
        seo_keywords=("ml", "healthcare"),
        suggested_tags=("ai", "health"),
        meta_description="SEO meta description.",
    )
    assert pkg.alternative_titles == ("Alt 1", "Alt 2")
    assert pkg.short_summary == "A brief summary."


def test_blog_package_needs_human():
    pkg = BlogPackage(
        status="needs_human", cost=_make_cost(),
        hard_fail_flags=("injection_followed",), notes="Escalated.",
    )
    assert pkg.status == "needs_human"
    assert pkg.notes == "Escalated."


def test_blog_package_stopped_cost_ceiling():
    pkg = BlogPackage(
        status="stopped_cost_ceiling", cost=_make_cost(),
        hard_fail_flags=(), notes="Cost ceiling reached.",
    )
    assert pkg.status == "stopped_cost_ceiling"


def test_blog_package_error():
    pkg = BlogPackage(
        status="error", cost=_make_cost(),
        hard_fail_flags=(), notes="raw_input is missing or blank; cannot proceed.",
    )
    assert pkg.status == "error"


def test_blog_package_invalid_status():
    with pytest.raises(ValidationError):
        BlogPackage(status="unknown_status", cost=_make_cost(), hard_fail_flags=())  # type: ignore[arg-type]


def test_blog_package_hard_fail_flags_is_tuple():
    pkg = BlogPackage(
        status="needs_human", cost=_make_cost(),
        hard_fail_flags=("injection_followed", "factual_error"),
    )
    assert isinstance(pkg.hard_fail_flags, tuple)
    assert len(pkg.hard_fail_flags) == 2


def test_blog_package_source_notes_immutable():
    pkg = _make_passed_pkg(source_notes=(SourceNote(title="My Blog"),))
    assert isinstance(pkg.source_notes, tuple)
    assert pkg.source_notes[0].title == "My Blog"


def test_blog_package_passed_with_hard_fail_rejected():
    with pytest.raises(ValidationError):
        _make_passed_pkg(hard_fail_flags=("injection_followed",))


# ---------------------------------------------------------------------------
# 13. revalidating copy via validated_copy
# ---------------------------------------------------------------------------

def test_validated_copy_updates_full_draft():
    pkg = _make_passed_pkg(full_draft="# Draft v1")
    pkg2 = pkg.validated_copy(full_draft="# Hello\n\nContent.")
    assert pkg2.full_draft == "# Hello\n\nContent."
    assert pkg2.status == "pass"
    assert pkg.full_draft == "# Draft v1"  # original unchanged


def test_validated_copy_rejects_invalid_update():
    pkg = _make_passed_pkg()
    with pytest.raises(ValidationError):
        pkg.validated_copy(status="not_a_real_status")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 14. Final repair: new contract invariants (Item 2)
# ---------------------------------------------------------------------------

# 14a. QualityReport.pass_flag=True requires needs_human=False

def test_quality_report_pass_flag_true_with_needs_human_true_rejected():
    """pass_flag=True + needs_human=True is rejected (two independent validators).

    The _validate_needs_human_against_flags validator now fires first (final repair):
    needs_human=True with no terminal hard-fail flags is always invalid — a passing
    blog has no flags, so this validator rejects the combination before
    _pass_flag_implies_not_needs_human even runs.
    """
    ss = SubScores(
        structure_flow=14, clarity_readability=13, idea_coverage=14, originality=13,
        tone_audience_fit=9, seo_usefulness=8, factual_safety_sources=9,
        grammar_polish=4, engagement_value=4,
    )
    total = (14 + 13 + 14 + 13 + 9 + 8 + 9 + 4 + 4)   # = 88, ≥ 80
    with pytest.raises(ValidationError, match="needs_human"):
        QualityReport(
            sub_scores=ss, overall_score=total,
            pass_flag=True, needs_human=True,   # contradictory: rejected by needs_human validator
        )


def test_quality_report_pass_flag_true_with_needs_human_false_accepted():
    """pass_flag=True + needs_human=False is valid (control case for 14a)."""
    ss = SubScores(
        structure_flow=14, clarity_readability=13, idea_coverage=14, originality=13,
        tone_audience_fit=9, seo_usefulness=8, factual_safety_sources=9,
        grammar_polish=4, engagement_value=4,
    )
    total = 14 + 13 + 14 + 13 + 9 + 8 + 9 + 4 + 4   # 88
    report = QualityReport(
        sub_scores=ss, overall_score=total,
        pass_flag=True, needs_human=False,
    )
    assert report.pass_flag is True
    assert report.needs_human is False


# 14b. BlogEnrichment.suggested_tags: blank tag rejected

def test_blog_enrichment_rejects_blank_tag_item():
    """suggested_tags containing a blank string is rejected (final repair Item 2)."""
    with pytest.raises(ValidationError, match="blank"):
        _make_enrichment(suggested_tags=("valid-tag", "  "))


def test_blog_enrichment_rejects_single_blank_tag():
    """A single whitespace-only tag in suggested_tags is rejected."""
    with pytest.raises(ValidationError, match="blank"):
        _make_enrichment(suggested_tags=("\t",))


def test_blog_enrichment_rejects_empty_string_tag():
    """An empty-string tag in suggested_tags is rejected."""
    with pytest.raises(ValidationError, match="blank"):
        _make_enrichment(suggested_tags=("good-tag", ""))


def test_blog_enrichment_accepts_all_non_blank_tags():
    """All non-blank tags pass the blank-tag check (control case)."""
    enrich = _make_enrichment(suggested_tags=("ai", "machine-learning", "healthcare"))
    assert enrich.suggested_tags == ("ai", "machine-learning", "healthcare")


# 14c. BlogEnrichment.meta_description max_length=160

def test_blog_enrichment_rejects_meta_description_over_160_chars():
    """meta_description > 160 chars is rejected (final repair Item 2: max_length=160)."""
    too_long = "A" * 161
    with pytest.raises(ValidationError, match="meta_description"):
        _make_enrichment(meta_description=too_long)


def test_blog_enrichment_accepts_meta_description_exactly_160_chars():
    """meta_description of exactly 160 chars is accepted (boundary case)."""
    exactly_160 = "A" * 160
    enrich = _make_enrichment(meta_description=exactly_160)
    assert len(enrich.meta_description) == 160


def test_blog_enrichment_accepts_meta_description_under_160_chars():
    """meta_description shorter than 160 chars is accepted (normal case)."""
    short = "A concise meta description for SEO purposes."
    enrich = _make_enrichment(meta_description=short)
    assert enrich.meta_description == short


# 14d. BlogPackage.meta_description max_length=160

def test_blog_package_rejects_meta_description_over_160_chars():
    """BlogPackage.meta_description > 160 chars is rejected (final repair Item 2: max_length=160)."""
    too_long = "B" * 161
    with pytest.raises(ValidationError):
        _make_passed_pkg(meta_description=too_long)


def test_blog_package_accepts_meta_description_exactly_160_chars():
    """BlogPackage.meta_description of exactly 160 chars is accepted."""
    exactly_160 = "B" * 160
    pkg = _make_passed_pkg(meta_description=exactly_160)
    assert len(pkg.meta_description) == 160


def test_blog_package_accepts_meta_description_none():
    """BlogPackage.meta_description=None is accepted on non-'pass' packages."""
    pkg = BlogPackage(
        status="error", cost=_make_cost(), hard_fail_flags=(), notes="error",
    )
    assert pkg.meta_description is None


# 14e. BlogPackage._passed_package_invariants: quality cross-checks

def test_blog_package_passed_requires_quality_pass_flag_true():
    """A 'pass' BlogPackage with quality.pass_flag=False is rejected (final repair Item 2)."""
    # _make_quality_pass() has pass_flag=False (review-worthy but not passing)
    failing_quality = _make_quality_pass()   # pass_flag=False, needs_human=False
    assert not failing_quality.pass_flag
    with pytest.raises(ValidationError, match="pass_flag"):
        _make_passed_pkg(quality=failing_quality)


def test_blog_package_passed_requires_quality_overall_score_at_least_80():
    """A 'pass' BlogPackage with quality.overall_score < 80 is rejected (final repair Item 2).

    Note: QualityReport's own validator already rejects pass_flag=True when score < 80,
    so this test constructs a QualityReport with pass_flag=False (score < 80) and
    confirms the BlogPackage invariant catches it too.
    """
    # Build a low-scoring but valid QualityReport (pass_flag=False since score < 80)
    low_ss = _make_sub_scores()   # sum = 67 < 80
    total = _sub_scores_sum(low_ss)
    assert total < 80
    low_quality = QualityReport(
        sub_scores=low_ss, overall_score=total,
        pass_flag=False, needs_human=False,
    )
    with pytest.raises(ValidationError):
        _make_passed_pkg(quality=low_quality)


def test_blog_package_passed_requires_quality_needs_human_false():
    """A 'pass' BlogPackage with quality.needs_human=True is rejected (final repair Item 2).

    We construct the contradictory QualityReport using model_construct (bypassing
    QualityReport's own _pass_flag_implies_not_needs_human validator) to test
    BlogPackage's independent invariant check.
    """
    ss = SubScores(
        structure_flow=14, clarity_readability=13, idea_coverage=14, originality=13,
        tone_audience_fit=9, seo_usefulness=8, factual_safety_sources=9,
        grammar_polish=4, engagement_value=4,
    )
    # Use model_construct to bypass QualityReport's validators
    # (simulating a hypothetical bypass scenario that BlogPackage must independently guard against)
    bad_quality = QualityReport.model_construct(
        sub_scores=ss, overall_score=88,
        pass_flag=True, needs_human=True,   # contradictory — bypassed via model_construct
        hard_fail_flags=(), revision_notes=None, improvement_suggestions=(),
    )
    with pytest.raises(ValidationError, match="needs_human"):
        _make_passed_pkg(quality=bad_quality)


def test_blog_package_passed_accepts_valid_passing_quality():
    """A 'pass' BlogPackage with valid passing quality is accepted (control case for 14e)."""
    good_quality = _make_quality_passing()
    pkg = _make_passed_pkg(quality=good_quality)
    assert pkg.status == "pass"
    assert pkg.quality.pass_flag is True
    assert pkg.quality.overall_score >= 80
    assert pkg.quality.needs_human is False


# ---------------------------------------------------------------------------
# 15. Final repair: needs_human bypass closed (Issue 1)
# ---------------------------------------------------------------------------

def test_quality_report_no_flags_needs_human_true_rejected():
    """needs_human=True with no hard-fail flags is rejected (final repair Issue 1).

    A low-score report with no flags must enter the revision loop, not bypass it.
    Setting needs_human=True without any terminal flag is now explicitly invalid.
    """
    ss = _make_sub_scores()   # score = 67 < 80
    total = _sub_scores_sum(ss)
    with pytest.raises(ValidationError, match="needs_human"):
        QualityReport(
            sub_scores=ss, overall_score=total,
            pass_flag=False, needs_human=True,   # no flags → rejected
        )


def test_quality_report_no_flags_needs_human_false_accepted():
    """needs_human=False with no flags is accepted — routes through the revision loop."""
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    report = QualityReport(
        sub_scores=ss, overall_score=total,
        pass_flag=False, needs_human=False,
    )
    assert report.needs_human is False
    assert report.hard_fail_flags == ()


def test_quality_report_needs_human_requires_terminal_flag_not_retriable():
    """needs_human=True requires a TERMINAL flag; retriable-only flags still route to revision."""
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    for retriable_flag in _RETRIABLE_HARD_FAIL_CODES:
        with pytest.raises(ValidationError, match="needs_human"):
            QualityReport(
                sub_scores=ss, overall_score=total,
                pass_flag=False, needs_human=True,
                hard_fail_flags=(retriable_flag,),   # retriable only → needs_human=True blocked
            )


def test_quality_report_terminal_flag_still_requires_needs_human_true():
    """Terminal hard-fail flag without needs_human=True is still rejected (invariant intact)."""
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    for terminal_flag in _TERMINAL_HARD_FAIL_CODES:
        with pytest.raises(ValidationError, match="needs_human"):
            QualityReport(
                sub_scores=ss, overall_score=total,
                pass_flag=False, needs_human=False,   # wrong: terminal flag requires True
                hard_fail_flags=(terminal_flag,),
            )


def test_quality_report_terminal_flag_with_needs_human_true_accepted():
    """Terminal flag + needs_human=True is accepted (the only valid needs_human=True case)."""
    ss = _make_sub_scores()
    total = _sub_scores_sum(ss)
    for terminal_flag in _TERMINAL_HARD_FAIL_CODES:
        report = QualityReport(
            sub_scores=ss, overall_score=total,
            pass_flag=False, needs_human=True,
            hard_fail_flags=(terminal_flag,),
        )
        assert report.needs_human is True
        assert terminal_flag in report.hard_fail_flags


# ---------------------------------------------------------------------------
# 16. Final repair: BlogPackage whitespace enrichment items (Issue 2)
# ---------------------------------------------------------------------------

def test_blog_package_passed_rejects_blank_alternative_title():
    """Whitespace-only alternative_title in a passed package is rejected (Issue 2)."""
    with pytest.raises(ValidationError, match="blank"):
        _make_passed_pkg(alternative_titles=("   ",))


def test_blog_package_passed_rejects_blank_seo_keyword():
    """Whitespace-only seo_keyword in a passed package is rejected (Issue 2)."""
    with pytest.raises(ValidationError, match="blank"):
        _make_passed_pkg(seo_keywords=("\t",))


def test_blog_package_passed_rejects_blank_suggested_tag():
    """Whitespace-only suggested_tag in a passed package is rejected (Issue 2)."""
    with pytest.raises(ValidationError, match="blank"):
        _make_passed_pkg(suggested_tags=("",))


def test_blog_package_passed_rejects_mixed_valid_and_blank_alternative_title():
    """A mix of valid and blank alternative_titles is rejected (Issue 2)."""
    with pytest.raises(ValidationError, match="blank"):
        _make_passed_pkg(alternative_titles=("Valid Title", "  "))


def test_blog_package_passed_rejects_mixed_valid_and_blank_seo_keyword():
    """A mix of valid and blank seo_keywords is rejected (Issue 2)."""
    with pytest.raises(ValidationError, match="blank"):
        _make_passed_pkg(seo_keywords=("ai", ""))


def test_blog_package_passed_accepts_all_non_blank_enrichment_items():
    """All non-blank enrichment items are accepted (control case for Issue 2)."""
    pkg = _make_passed_pkg(
        alternative_titles=("Alt Title A", "Alt Title B"),
        seo_keywords=("machine learning", "healthcare"),
        suggested_tags=("ai", "health"),
    )
    assert len(pkg.alternative_titles) == 2
    assert len(pkg.seo_keywords) == 2
    assert len(pkg.suggested_tags) == 2


def test_blog_package_error_status_accepts_blank_items():
    """Non-'pass' packages do not have the blank-item constraint (invariant only for 'pass')."""
    # error status has empty tuples — blank item check should not fire
    pkg = BlogPackage(
        status="error", cost=_make_cost(), hard_fail_flags=(), notes="error",
    )
    assert pkg.alternative_titles == ()
    assert pkg.seo_keywords == ()
    assert pkg.suggested_tags == ()
