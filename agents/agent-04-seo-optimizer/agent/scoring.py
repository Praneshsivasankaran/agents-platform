"""Scoring and risk checks for Agent 04."""
from __future__ import annotations

from .schemas import (
    Agent04Request,
    DraftAnalysis,
    FAQBundle,
    HARD_FAIL_CODES,
    HeadingPlan,
    MetadataPackage,
    OptimizedDraftPackage,
    ReadabilityReport,
    RiskFlag,
    RiskReport,
    SEOScore,
)
from .tools import (
    count_words,
    detect_cta_presence,
    detect_prompt_injection_markers,
    detect_unsupported_claim_markers,
    excessive_repetition,
    keyword_density_check,
    simple_keyword_presence,
    top_terms,
)


def _risk(code: str, message: str) -> RiskFlag:
    severity = "hard_fail" if code in HARD_FAIL_CODES else "warning"
    return RiskFlag(code=code, severity=severity, message=message)  # type: ignore[arg-type]


def _dedupe_flags(flags: list[RiskFlag]) -> tuple[RiskFlag, ...]:
    seen: set[str] = set()
    out: list[RiskFlag] = []
    for flag in flags:
        if flag.code not in seen:
            out.append(flag)
            seen.add(flag.code)
    return tuple(out)


def build_risk_report(
    *,
    request: Agent04Request,
    analysis: DraftAnalysis,
    metadata: MetadataPackage | None,
    heading_plan: HeadingPlan | None,
    readability: ReadabilityReport | None,
    faq_bundle: FAQBundle | None,
    optimized: OptimizedDraftPackage | None,
) -> RiskReport:
    flags: list[RiskFlag] = []
    optimized_text = optimized.optimized_draft if optimized else ""

    if not optimized_text or count_words(optimized_text) < 40:
        flags.append(_risk("missing_optimized_draft", "Optimized draft is missing or too thin."))
    if metadata is None or not metadata.seo_title_options:
        flags.append(_risk("missing_title_options", "SEO title options are missing."))
    if metadata is None or not metadata.meta_description:
        flags.append(_risk("missing_meta_description", "Meta description is missing."))
    if metadata is None or not metadata.url_slug:
        flags.append(_risk("missing_slug", "URL slug is missing."))
    if metadata is None:
        flags.append(_risk("missing_metadata", "Metadata package is incomplete."))
    if not simple_keyword_presence(optimized_text or request.draft_content, request.primary_keyword):
        flags.append(_risk("missing_primary_keyword", "Primary keyword is missing from the optimized draft."))
    density = keyword_density_check(optimized_text or request.draft_content, request.primary_keyword)
    if density > 5.0:
        flags.append(_risk("keyword_stuffing", "Primary keyword density is too high."))
    if heading_plan is None or len(heading_plan.h2_h3_plan) < 2:
        flags.append(_risk("weak_heading_structure", "Heading plan needs at least two useful sections."))
    if readability is None or not readability.cta_suggestion or not detect_cta_presence(
        optimized_text, request.cta_direction
    ):
        flags.append(_risk("weak_cta", "CTA is missing or weak for the stated direction."))
    if detect_unsupported_claim_markers(request.draft_content) or detect_unsupported_claim_markers(
        optimized_text
    ):
        flags.append(_risk("unsupported_claims", "Draft includes claims that need evidence or removal."))
    if detect_prompt_injection_markers(request.draft_content):
        flags.append(_risk("prompt_injection_marker", "Draft contains prompt-injection style text."))
    if faq_bundle is None or not faq_bundle.faqs:
        flags.append(_risk("empty_faq_output", "FAQ suggestions are missing."))
    if "optimize your content" in optimized_text.lower() and count_words(optimized_text) < 120:
        flags.append(_risk("overly_generic_output", "Optimized draft appears generic or underdeveloped."))
    if excessive_repetition(optimized_text):
        flags.append(_risk("excessive_repetition", "Optimized draft repeats terms too often."))
    if _meaning_drift_detected(request.draft_content, optimized_text):
        flags.append(_risk("meaning_drift_warning", "Optimized draft may have drifted from the source meaning."))
    if analysis.word_count == 0:
        flags.append(_risk("empty_or_invalid_output", "Input draft could not be analyzed."))

    risk_flags = _dedupe_flags(flags)
    hard_fails = tuple(flag.code for flag in risk_flags if flag.severity == "hard_fail")
    return RiskReport(risk_flags=risk_flags, hard_fail_codes=hard_fails, passed=not hard_fails)


def _meaning_drift_detected(original: str, optimized: str) -> bool:
    if not original or not optimized:
        return True
    source_terms = set(top_terms(original, limit=8))
    if not source_terms:
        return False
    optimized_lower = optimized.lower()
    retained = sum(1 for term in source_terms if term in optimized_lower)
    return retained < max(2, len(source_terms) // 3)


def score_output(
    *,
    request: Agent04Request,
    analysis: DraftAnalysis,
    metadata: MetadataPackage | None,
    keyword_plan,
    heading_plan: HeadingPlan | None,
    readability: ReadabilityReport | None,
    faq_bundle: FAQBundle | None,
    risk_report: RiskReport,
    optimized: OptimizedDraftPackage | None,
) -> SEOScore:
    optimized_text = optimized.optimized_draft if optimized else ""

    metadata_quality = 0
    if metadata is not None:
        metadata_quality += 6 if metadata.seo_title_options else 0
        metadata_quality += 6 if 120 <= len(metadata.meta_description) <= 160 else 3 if metadata.meta_description else 0
        metadata_quality += 4 if metadata.url_slug else 0
        metadata_quality += 4 if metadata.recommended_h1 else 0
    metadata_quality = min(20, metadata_quality)

    keyword_usage = 0
    if simple_keyword_presence(optimized_text, request.primary_keyword):
        keyword_usage += 10
    density = keyword_density_check(optimized_text, request.primary_keyword)
    if 0.2 <= density <= 3.5:
        keyword_usage += 5
    present_secondaries = sum(
        1 for keyword in request.secondary_keywords if simple_keyword_presence(optimized_text, keyword)
    )
    if request.secondary_keywords:
        keyword_usage += min(5, int((present_secondaries / len(request.secondary_keywords)) * 5))
    else:
        keyword_usage += 5

    heading_structure = 0
    if heading_plan is not None:
        heading_structure += 5 if heading_plan.recommended_h1 else 0
        heading_structure += min(10, len(heading_plan.h2_h3_plan) * 3)

    readability_score = 0
    if readability is not None:
        readability_score += 8 if readability.readability_score >= 50 else 4
        readability_score += 4 if readability.fixes else 0
        readability_score += 3 if readability.intro_improvement and readability.conclusion_improvement else 0

    content_goal_alignment = 5
    combined_context = " ".join(
        (
            request.topic,
            request.target_audience,
            request.content_goal,
            request.brand_tone,
            request.cta_direction,
        )
    ).lower()
    optimized_lower = optimized_text.lower()
    if request.topic.lower() in optimized_lower:
        content_goal_alignment += 2
    if request.primary_keyword.lower() in optimized_lower:
        content_goal_alignment += 2
    if request.cta_direction and detect_cta_presence(optimized_text, request.cta_direction):
        content_goal_alignment += 1
    if request.content_goal and any(term in optimized_lower for term in top_terms(combined_context, limit=4)):
        content_goal_alignment = min(10, content_goal_alignment + 1)

    faq_usefulness = min(10, (len(faq_bundle.faqs) if faq_bundle else 0) * 4)
    risk_safety = 10
    if any(flag.severity == "hard_fail" for flag in risk_report.risk_flags):
        risk_safety = 0
    elif risk_report.risk_flags:
        risk_safety = max(4, 10 - len(risk_report.risk_flags) * 2)

    total_score = (
        metadata_quality
        + min(20, keyword_usage)
        + min(15, heading_structure)
        + min(15, readability_score)
        + min(10, content_goal_alignment)
        + min(10, faq_usefulness)
        + risk_safety
    )
    return SEOScore(
        metadata_quality=metadata_quality,
        keyword_usage=min(20, keyword_usage),
        heading_structure=min(15, heading_structure),
        readability=min(15, readability_score),
        content_goal_alignment=min(10, content_goal_alignment),
        faq_usefulness=min(10, faq_usefulness),
        risk_safety=risk_safety,
        total_score=total_score,
        passed=total_score >= 80 and not risk_report.hard_fail_codes,
        hard_fail_codes=risk_report.hard_fail_codes,
    )
