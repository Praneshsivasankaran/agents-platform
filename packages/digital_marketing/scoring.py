"""Shared scoring helpers for Digital Marketing Agents 15-21."""

from __future__ import annotations

from .profiles import AgentProfile
from .schemas import (
    DigitalMarketingRequest,
    GeneratedRecommendation,
    MetricInsight,
    OutputSection,
    QualityDimensionScore,
    QualityReport,
    RiskFlag,
)
from .tools import missing_required_fields


def _has_hard_fail(risks: tuple[RiskFlag, ...]) -> bool:
    return any(flag.severity == "hard_fail" for flag in risks)


def _risk_penalty(risks: tuple[RiskFlag, ...]) -> int:
    penalty = 0
    for risk in risks:
        if risk.severity == "hard_fail":
            penalty += 30
        elif risk.severity == "high":
            penalty += 12
        elif risk.severity == "medium":
            penalty += 6
        else:
            penalty += 2
    return penalty


def _dimension_score(
    *,
    dimension_name: str,
    max_score: int,
    profile: AgentProfile,
    request: DigitalMarketingRequest | None,
    recommendations: tuple[GeneratedRecommendation, ...],
    output_sections: tuple[OutputSection, ...],
    risks: tuple[RiskFlag, ...],
    metric_insights: tuple[MetricInsight, ...],
) -> int:
    if request is None:
        return 0
    score = max_score
    missing = missing_required_fields(profile, request)
    if missing:
        score -= min(max_score, len(missing) * 5)
    if not recommendations and not _has_hard_fail(risks):
        score -= max(4, max_score // 2)
    if not output_sections and not _has_hard_fail(risks):
        score -= max(3, max_score // 4)

    name = dimension_name.lower()
    if any(token in name for token in ("risk", "policy", "safety", "privacy", "consent", "truthfulness")):
        score -= _risk_penalty(risks)
    elif any(token in name for token in ("metric", "data", "denominator", "sample", "calculation", "kpi")):
        if profile.metric_mode in {"paid", "cro", "reporting"}:
            score = score if metric_insights else max(0, score - max(6, max_score // 2))
        elif profile.metric_mode == "keyword" and not request.metrics:
            score -= max(3, max_score // 4)
    elif any(token in name for token in ("handoff", "readiness")):
        if not profile.handoff_targets:
            score -= 2
    elif any(token in name for token in ("platform", "channel")):
        if not (request.platforms or request.channels):
            score -= max(4, max_score // 3)
    elif any(token in name for token in ("keyword", "cluster", "intent")):
        if not (request.keywords or request.keyword_table):
            score -= max(5, max_score // 2)
    elif any(token in name for token in ("page", "form", "cta", "friction", "proof")):
        if not (request.page_copy or request.page_notes or request.page_sections or request.form_fields):
            score -= max(4, max_score // 3)
    elif any(token in name for token in ("calendar", "asset", "dependency")):
        if not (request.timeline and (request.content_inventory or request.owner_notes)):
            score -= max(3, max_score // 4)
    elif any(token in name for token in ("claim", "compliance")):
        if not (request.source_notes or request.compliance_notes):
            score -= max(3, max_score // 4)
    else:
        score -= min(6, _risk_penalty(risks) // 2)

    if _has_hard_fail(risks):
        score = min(score, max_score // 3)
    return max(0, min(score, max_score))


def score_quality(
    *,
    profile: AgentProfile,
    request: DigitalMarketingRequest | None,
    recommendations: tuple[GeneratedRecommendation, ...],
    output_sections: tuple[OutputSection, ...] = (),
    risks: tuple[RiskFlag, ...],
    metric_insights: tuple[MetricInsight, ...] = (),
    validation_errors: tuple[str, ...] = (),
) -> QualityReport:
    if validation_errors or request is None:
        dimensions = tuple(
            QualityDimensionScore(name=name, score=0, max_score=max_score)
            for name, max_score in profile.quality_dimensions
        )
        return QualityReport(
            overall_score=0,
            dimension_scores=dimensions,
            approval_reason="Required request fields are missing or invalid.",
            revision_notes=validation_errors,
            passed=False,
        )

    dimensions = tuple(
        QualityDimensionScore(
            name=name,
            score=_dimension_score(
                dimension_name=name,
                max_score=max_score,
                profile=profile,
                request=request,
                recommendations=recommendations,
                output_sections=output_sections,
                risks=risks,
                metric_insights=metric_insights,
            ),
            max_score=max_score,
        )
        for name, max_score in profile.quality_dimensions
    )
    total = sum(item.score for item in dimensions)
    notes = []
    for risk in risks:
        notes.append(risk.evidence_needed or risk.message)
    if total < profile.approve_threshold:
        notes.append("Review and strengthen supplied evidence, caveats, and handoffs before approval.")
    if _has_hard_fail(risks):
        reason = "Reject: hard-fail safety, scope, data, or truthfulness issue requires human correction."
    elif total >= profile.approve_threshold:
        reason = "Approve: package is review-ready for advisory Digital Marketing use."
    elif total >= profile.revise_min_threshold:
        reason = "Revise: package is useful but requires human review before use."
    else:
        reason = "Reject: package is too incomplete or risky for use."
    return QualityReport(
        overall_score=min(100, total),
        dimension_scores=dimensions,
        approval_reason=reason,
        revision_notes=tuple(dict.fromkeys(note for note in notes if note)),
        passed=(total >= profile.pass_threshold and not _has_hard_fail(risks)),
    )


def determine_quality_status(profile: AgentProfile, quality: QualityReport, risks: tuple[RiskFlag, ...]) -> str:
    if _has_hard_fail(risks) or quality.overall_score < profile.revise_min_threshold:
        return "reject"
    if quality.overall_score >= profile.approve_threshold:
        return "approve"
    return "revise"


def determine_terminal_status(
    *,
    quality_status: str,
    quality: QualityReport,
    risks: tuple[RiskFlag, ...],
    budget_limited: bool,
    error: bool,
) -> str:
    if budget_limited:
        return "stopped_cost_ceiling"
    if error:
        return "error"
    if _has_hard_fail(risks):
        return "needs_human"
    if quality_status == "approve" and quality.passed:
        return "pass"
    return "needs_human"
