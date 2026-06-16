"""Scoring and approval logic for Agent 07."""
from __future__ import annotations

from .schemas import (
    APPROVE_THRESHOLD,
    CaseStudyDraft,
    CaseStudyRequest,
    EvidenceMap,
    MissingInfoWarning,
    QualityDimensionScore,
    QualityReport,
    REVISE_MIN_THRESHOLD,
    RiskFlag,
)
from .tools import clean_text, draft_text, important_terms, word_count


def _dimension(name: str, score: int, max_score: int) -> QualityDimensionScore:
    return QualityDimensionScore(name=name, score=max(0, min(score, max_score)), max_score=max_score)


def _has_hard_fail(risks: tuple[RiskFlag, ...]) -> bool:
    return any(flag.severity == "hard_fail" for flag in risks)


def _has_high_risk(risks: tuple[RiskFlag, ...]) -> bool:
    return any(flag.severity in {"high", "hard_fail"} for flag in risks)


def _has_high_warning(warnings: tuple[MissingInfoWarning, ...]) -> bool:
    return any(warning.severity == "high" for warning in warnings)


def _has_medium_or_high_warning(warnings: tuple[MissingInfoWarning, ...]) -> bool:
    return any(warning.severity in {"medium", "high"} for warning in warnings)


def _challenge_score(request: CaseStudyRequest | None, draft: CaseStudyDraft | None) -> int:
    if request is None or draft is None:
        return 0
    base = 4 if word_count(request.challenge) >= 5 else 0
    section_words = word_count(draft.challenge_section)
    if section_words >= 55:
        base += 8
    elif section_words >= 30:
        base += 6
    elif section_words >= 15:
        base += 3
    challenge_tokens = [token for token in request.challenge.lower().split() if len(token) > 4]
    hits = sum(1 for token in challenge_tokens if token in draft.challenge_section.lower())
    return min(15, base + min(3, hits))


def _solution_score(request: CaseStudyRequest | None, draft: CaseStudyDraft | None) -> int:
    if request is None or draft is None:
        return 0
    base = 4 if word_count(request.solution_summary) >= 5 else 0
    section_words = word_count(draft.solution_section)
    if section_words >= 55:
        base += 8
    elif section_words >= 30:
        base += 6
    elif section_words >= 15:
        base += 3
    terms = important_terms(request)
    text = draft.solution_section.lower()
    hits = sum(1 for term in terms if term in text)
    return min(15, base + min(3, hits))


def _evidence_score(evidence: EvidenceMap | None, warnings: tuple[MissingInfoWarning, ...]) -> int:
    if evidence is None:
        return 0
    score = 8 if evidence.metric_highlights else 4
    score += min(8, len(evidence.metric_highlights) * 4)
    if any(metric.confidence == "high" for metric in evidence.metric_highlights):
        score += 4
    if any(warning.field == "metrics" for warning in warnings):
        score -= 4
    if any("source" in item.lower() for item in evidence.missing_evidence):
        score -= 2
    return max(0, min(20, score))


def _credibility_score(risks: tuple[RiskFlag, ...]) -> int:
    score = 15
    for flag in risks:
        if flag.severity == "hard_fail":
            score -= 12
        elif flag.severity == "high":
            score -= 6
        elif flag.severity == "medium":
            score -= 3
        elif flag.severity == "low":
            score -= 1
    return max(0, min(15, score))


def _structure_score(draft: CaseStudyDraft | None) -> int:
    if draft is None:
        return 0
    sections = (
        draft.executive_summary,
        draft.customer_background,
        draft.challenge_section,
        draft.solution_section,
        draft.implementation_section,
        draft.results_section,
        draft.cta_section,
    )
    filled = sum(1 for section in sections if word_count(section) >= 20)
    return min(10, int((filled / len(sections)) * 10))


def _tone_score(request: CaseStudyRequest | None, draft: CaseStudyDraft | None) -> int:
    if request is None or draft is None:
        return 0
    text = draft_text(draft)
    if not text:
        return 0
    score = 7 if word_count(text) >= 260 else 5
    if request.brand_voice and any(token in text.lower() for token in request.brand_voice.lower().split() if len(token) > 4):
        score += 2
    if request.tone in {"executive", "professional"} and any(
        phrase in text.lower() for phrase in ("executive", "business", "review", "outcome")
    ):
        score += 1
    return min(10, score)


def _readability_score(draft: CaseStudyDraft | None) -> int:
    if draft is None:
        return 0
    text = draft_text(draft)
    words = word_count(text)
    if words >= 420:
        return 10
    if words >= 300:
        return 8
    if words >= 220:
        return 6
    return 3 if words >= 140 else 0


def _cta_score(request: CaseStudyRequest | None, draft: CaseStudyDraft | None) -> int:
    if request is None or draft is None:
        return 0
    if not clean_text(draft.cta_section):
        return 0
    if request.cta_goal:
        tokens = [token for token in request.cta_goal.lower().split() if len(token) > 3]
        if any(token in draft.cta_section.lower() for token in tokens):
            return 5
        return 3
    return 2


def score_case_study_quality(
    *,
    request: CaseStudyRequest | None,
    draft: CaseStudyDraft | None,
    evidence_map: EvidenceMap | None,
    missing_warnings: tuple[MissingInfoWarning, ...],
    risk_flags: tuple[RiskFlag, ...],
    validation_errors: tuple[str, ...] = (),
) -> QualityReport:
    if validation_errors or request is None:
        dimensions = (
            _dimension("challenge_clarity", 0, 15),
            _dimension("solution_specificity", 0, 15),
            _dimension("evidence_backed_results", 0, 20),
            _dimension("credibility_claim_safety", 0, 15),
            _dimension("structure_completeness", 0, 10),
            _dimension("brand_tone_fit", 0, 10),
            _dimension("readability", 0, 10),
            _dimension("cta_usefulness", 0, 5),
        )
        return QualityReport(
            overall_score=0,
            dimension_scores=dimensions,
            approval_reason="Required case study fields are missing or invalid.",
            revision_notes=validation_errors,
            passed=False,
        )

    dimensions = (
        _dimension("challenge_clarity", _challenge_score(request, draft), 15),
        _dimension("solution_specificity", _solution_score(request, draft), 15),
        _dimension("evidence_backed_results", _evidence_score(evidence_map, missing_warnings), 20),
        _dimension("credibility_claim_safety", _credibility_score(risk_flags), 15),
        _dimension("structure_completeness", _structure_score(draft), 10),
        _dimension("brand_tone_fit", _tone_score(request, draft), 10),
        _dimension("readability", _readability_score(draft), 10),
        _dimension("cta_usefulness", _cta_score(request, draft), 5),
    )
    total = sum(item.score for item in dimensions)
    notes: list[str] = []
    if missing_warnings:
        notes.extend(warning.message for warning in missing_warnings if warning.severity in {"medium", "high"})
    if risk_flags:
        notes.extend(flag.message for flag in risk_flags)
    if total < APPROVE_THRESHOLD:
        notes.append("Strengthen evidence, metrics, quote approval, or section depth before approval.")
    if _has_hard_fail(risk_flags):
        reason = "Reject: hard-fail claim, scope, or safety risk requires human correction."
    elif total >= APPROVE_THRESHOLD and not risk_flags and not _has_medium_or_high_warning(missing_warnings):
        reason = "Approve: complete case study package with credible evidence handling."
    elif total >= REVISE_MIN_THRESHOLD:
        reason = "Revise: usable case study package, but missing context or risks need review."
    else:
        reason = "Reject: case study package is too thin or risky to use."
    return QualityReport(
        overall_score=min(100, total),
        dimension_scores=dimensions,
        approval_reason=reason,
        revision_notes=tuple(dict.fromkeys(note for note in notes if note)),
        passed=total >= 80,
    )


def determine_status(
    *,
    quality: QualityReport,
    risk_flags: tuple[RiskFlag, ...],
    missing_warnings: tuple[MissingInfoWarning, ...],
    budget_limited: bool = False,
) -> str:
    if _has_hard_fail(risk_flags):
        return "reject"
    if quality.overall_score < REVISE_MIN_THRESHOLD:
        return "reject"
    if budget_limited:
        return "revise"
    if quality.overall_score >= APPROVE_THRESHOLD and not risk_flags and not _has_medium_or_high_warning(missing_warnings):
        return "approve"
    return "revise"
