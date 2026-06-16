"""Scoring and risk checks for Agent 06."""
from __future__ import annotations

from .schemas import (
    Agent06Request,
    ClaimReviewReport,
    EvidenceMap,
    GenericContentReport,
    HARD_FAIL_CODES,
    RiskFlag,
    RiskReport,
    WhitepaperDraft,
    WhitepaperOutline,
    WhitepaperQualityScore,
)
from .tools import (
    clean_text,
    detect_external_action_requests,
    detect_forbidden_claim_markers,
    detect_prompt_injection_markers,
    detect_source_verification_claims,
    draft_text,
    evidence_status_counts,
    important_terms,
    supplied_context_text,
    word_count,
)


def _risk(code: str, message: str, *, affected: tuple[str, ...] = (), fix: str = "") -> RiskFlag:
    severity = "hard_fail" if code in HARD_FAIL_CODES else "warning"
    return RiskFlag(
        code=code,  # type: ignore[arg-type]
        severity=severity,
        message=message,
        affected_items=affected,
        recommended_fix=fix,
    )


def _dedupe_flags(flags: list[RiskFlag]) -> tuple[RiskFlag, ...]:
    seen: set[str] = set()
    out: list[RiskFlag] = []
    for flag in flags:
        key = f"{flag.code}:{','.join(flag.affected_items)}"
        if key not in seen:
            out.append(flag)
            seen.add(key)
    return tuple(out)


def build_risk_report(
    *,
    request: Agent06Request | None,
    validation_errors: tuple[str, ...] = (),
    draft: WhitepaperDraft | None,
    outline: WhitepaperOutline | None,
    evidence_map: EvidenceMap | None,
    claim_review: ClaimReviewReport | None,
    generic_report: GenericContentReport | None,
) -> RiskReport:
    flags: list[RiskFlag] = []

    if validation_errors:
        flags.append(
            _risk(
                "missing_required_inputs",
                "Request validation failed before a review-ready whitepaper package could be generated.",
                affected=validation_errors,
                fix="Provide all required Agent 06 whitepaper fields.",
            )
        )

    if request is None:
        risk_flags = _dedupe_flags(flags)
        hard_fails = tuple(flag.code for flag in risk_flags if flag.severity == "hard_fail")
        return RiskReport(risk_flags=risk_flags, hard_fail_codes=hard_fails, passed=not hard_fails)

    combined_user_context = supplied_context_text(request)
    if detect_prompt_injection_markers(combined_user_context):
        flags.append(
            _risk(
                "prompt_injection_marker",
                "Input contains prompt-injection style text; it must be treated only as data.",
                fix="Review or remove the affected source note before publication.",
            )
        )
    if detect_external_action_requests(combined_user_context):
        flags.append(
            _risk(
                "external_action_claimed",
                "Input requests publishing, CRM/CMS, analytics, email, or other external actions.",
                fix="Keep Agent 06 v1 draft-only and remove external action instructions.",
            )
        )

    if outline is None or len(outline.sections) < 8:
        flags.append(_risk("missing_required_section", "Whitepaper outline is missing required sections."))
    if draft is None:
        flags.append(_risk("empty_or_invalid_output", "Whitepaper draft sections are missing."))
    else:
        required_sections = (
            draft.executive_summary,
            draft.target_audience_and_pain_points,
            draft.problem_statement,
            draft.industry_context,
            draft.proposed_solution,
            draft.benefits,
            draft.use_cases,
            draft.implementation_approach,
            draft.risks_and_challenges,
            draft.conclusion,
            draft.cta,
        )
        if any(not clean_text(section) for section in required_sections):
            flags.append(_risk("missing_required_section", "One or more required whitepaper sections are empty."))
        thin = tuple(
            label
            for label, section in (
                ("executive_summary", draft.executive_summary),
                ("problem_statement", draft.problem_statement),
                ("proposed_solution", draft.proposed_solution),
                ("benefits", draft.benefits),
                ("implementation_approach", draft.implementation_approach),
            )
            if word_count(section) < 30
        )
        if thin:
            flags.append(
                _risk(
                    "thin_sections",
                    "Some sections are too thin to guide content review.",
                    affected=thin,
                    fix="Expand thin sections with specific company/product context and useful detail.",
                )
            )
        forbidden = detect_forbidden_claim_markers(draft_text(draft), combined_user_context)
        if forbidden:
            flags.append(
                _risk(
                    "fabricated_claim",
                    "Draft contains verified-sounding or quantified claims not found in supplied context.",
                    affected=forbidden,
                    fix="Remove invented claims or add user-provided evidence.",
                )
            )
        source_claims = detect_source_verification_claims(draft_text(draft), combined_user_context)
        if source_claims:
            flags.append(
                _risk(
                    "source_verification_claimed",
                    "Draft claims external/source verification that Agent 06 did not perform.",
                    affected=source_claims,
                    fix="Reword as user-provided/unverified or add human-verified citations.",
                )
            )

    if claim_review is None or not claim_review.key_claims:
        flags.append(_risk("missing_claim_evidence_status", "Key claims and evidence status are missing."))
    elif claim_review.fabricated_or_forbidden_claims:
        flags.append(
            _risk(
                "fabricated_claim",
                "Claim review found fabricated or forbidden claims.",
                affected=claim_review.fabricated_or_forbidden_claims,
                fix="Remove the claims or add supplied evidence.",
            )
        )
    elif claim_review.unsupported_claims:
        flags.append(
            _risk(
                "unsupported_verified_claim",
                "Claim review found unsupported claims that need evidence.",
                affected=claim_review.unsupported_claims,
                fix="Mark claims as needing evidence or add supplied proof points.",
            )
        )

    if evidence_map is None:
        flags.append(_risk("missing_evidence_section", "Evidence map is missing."))

    if generic_report and generic_report.flags:
        for flag in generic_report.flags:
            flags.append(
                _risk(
                    "generic_content",
                    flag.message,
                    affected=(flag.location,),
                    fix=flag.recommended_fix,
                )
            )

    if request.excluded_claims and draft is not None:
        lowered = draft_text(draft).lower()
        used = tuple(claim for claim in request.excluded_claims if clean_text(claim).lower() in lowered)
        if used:
            flags.append(
                _risk(
                    "excluded_claim_used",
                    "Draft uses one or more excluded claims.",
                    affected=used,
                    fix="Remove excluded claims from the package.",
                )
            )

    risk_flags = _dedupe_flags(flags)
    hard_fails = tuple(flag.code for flag in risk_flags if flag.severity == "hard_fail")
    return RiskReport(risk_flags=risk_flags, hard_fail_codes=hard_fails, passed=not hard_fails)


def _specificity_score(request: Agent06Request | None, draft: WhitepaperDraft | None) -> int:
    if request is None or draft is None:
        return 0
    terms = important_terms(request)
    if not terms:
        return 0
    text = draft_text(draft).lower()
    hits = sum(1 for term in terms if term in text)
    return min(15, 4 + hits)


def _audience_score(request: Agent06Request | None, draft: WhitepaperDraft | None) -> int:
    if request is None or draft is None:
        return 0
    text = (draft.target_audience_and_pain_points + " " + draft.executive_summary).lower()
    tokens = [t for t in request.target_audience.lower().split() if len(t) > 3]
    hits = sum(1 for token in tokens if token in text)
    return min(10, 5 + hits * 2) if hits else 4


def _structure_score(outline: WhitepaperOutline | None, draft: WhitepaperDraft | None) -> int:
    if outline is None or draft is None:
        return 0
    required = (
        draft.executive_summary,
        draft.target_audience_and_pain_points,
        draft.problem_statement,
        draft.industry_context,
        draft.proposed_solution,
        draft.benefits,
        draft.use_cases,
        draft.implementation_approach,
        draft.risks_and_challenges,
        draft.conclusion,
        draft.cta,
    )
    filled = sum(1 for section in required if word_count(section) >= 20)
    return min(15, int((filled / len(required)) * 15))


def _logic_score(request: Agent06Request | None, draft: WhitepaperDraft | None) -> int:
    if request is None or draft is None:
        return 0
    text = draft_text(draft).lower()
    problem_hits = sum(1 for token in request.problem.lower().split() if len(token) > 4 and token in text)
    solution_hits = sum(1 for token in request.solution.lower().split() if len(token) > 4 and token in text)
    return min(15, 5 + problem_hits + solution_hits)


def _evidence_score(claim_review: ClaimReviewReport | None, evidence_map: EvidenceMap | None) -> int:
    if claim_review is None or not claim_review.key_claims:
        return 0
    counts = evidence_status_counts(claim_review.key_claims)
    score = 15
    score -= counts.get("unsupported", 0) * 6
    score -= counts.get("needs_evidence", 0) * 3
    score -= len(claim_review.fabricated_or_forbidden_claims) * 8
    if evidence_map and not evidence_map.evidence_items:
        score -= 2
    return max(0, min(15, score))


def _depth_score(draft: WhitepaperDraft | None) -> int:
    if draft is None:
        return 0
    count = word_count(draft_text(draft))
    if count >= 700:
        return 10
    if count >= 450:
        return 8
    if count >= 300:
        return 6
    return 3 if count >= 180 else 0


def _tone_score(draft: WhitepaperDraft | None) -> int:
    if draft is None:
        return 0
    text = draft_text(draft)
    if not text:
        return 0
    if "xxx" in text.lower():
        return 1
    return 5 if word_count(text) >= 220 else 3


def score_output(
    *,
    request: Agent06Request | None,
    outline: WhitepaperOutline | None,
    draft: WhitepaperDraft | None,
    evidence_map: EvidenceMap | None,
    claim_review: ClaimReviewReport | None,
    generic_report: GenericContentReport | None,
    risk_report: RiskReport,
    validation_errors: tuple[str, ...] = (),
) -> WhitepaperQualityScore:
    input_completeness = 0 if validation_errors or request is None else 10
    specificity = _specificity_score(request, draft)
    audience_fit = _audience_score(request, draft)
    structure_completeness = _structure_score(outline, draft)
    problem_solution_logic = _logic_score(request, draft)
    evidence_discipline = _evidence_score(claim_review, evidence_map)
    depth_actionability = _depth_score(draft)
    tone_clarity = _tone_score(draft)
    risk_review_readiness = 5
    if risk_report.hard_fail_codes:
        risk_review_readiness = 0
    elif risk_report.risk_flags:
        risk_review_readiness = max(2, 5 - len(risk_report.risk_flags))
    if generic_report and generic_report.hard_fail:
        risk_review_readiness = 0

    total_score = (
        input_completeness
        + specificity
        + audience_fit
        + structure_completeness
        + problem_solution_logic
        + evidence_discipline
        + depth_actionability
        + tone_clarity
        + risk_review_readiness
    )
    return WhitepaperQualityScore(
        input_completeness=input_completeness,
        specificity=specificity,
        audience_fit=audience_fit,
        structure_completeness=structure_completeness,
        problem_solution_logic=problem_solution_logic,
        evidence_discipline=evidence_discipline,
        depth_actionability=depth_actionability,
        tone_clarity=tone_clarity,
        risk_review_readiness=risk_review_readiness,
        total_score=min(100, total_score),
        passed=total_score >= 80 and not risk_report.hard_fail_codes,
        hard_fail_codes=risk_report.hard_fail_codes,
    )
