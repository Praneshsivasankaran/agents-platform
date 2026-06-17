"""Shared scoring helpers for Demand Generation Agents 08-14."""

from __future__ import annotations

from .profiles import AgentProfile
from .schemas import (
    DemandGenRequest,
    GeneratedRecommendation,
    MetricInsight,
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
    request: DemandGenRequest | None,
    recommendations: tuple[GeneratedRecommendation, ...],
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
    if any(token in dimension_name for token in ("compliance", "safety", "bias", "protected", "suppression")):
        score -= _risk_penalty(risks)
    elif any(token in dimension_name for token in ("evidence", "data_quality", "metric_math")):
        if profile.metric_mode == "conversion":
            score = max_score if len(metric_insights) >= 1 else max_score // 3
        elif not (request.source_notes or request.metrics):
            score -= max(4, max_score // 3)
    elif any(token in dimension_name for token in ("handoff", "routing", "sales")):
        if not profile.handoff_targets:
            score -= 2
    elif any(token in dimension_name for token in ("budget", "timeline")):
        if not request.budget:
            score -= max(3, max_score // 4)
    elif any(token in dimension_name for token in ("content", "asset")):
        if profile.agent_id == "agent-13" and not request.content_inventory:
            score -= max(5, max_score // 2)
    elif any(token in dimension_name for token in ("segment", "icp", "audience")):
        if not (request.icp_summary or request.segment_summary or request.target_audience):
            score -= max(5, max_score // 2)
    else:
        score -= min(6, _risk_penalty(risks) // 2)
    if _has_hard_fail(risks):
        score = min(score, max_score // 3)
    return max(0, min(score, max_score))


def score_quality(
    *,
    profile: AgentProfile,
    request: DemandGenRequest | None,
    recommendations: tuple[GeneratedRecommendation, ...],
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
        notes.append("Review and strengthen evidence, constraints, and downstream handoff before approval.")
    if _has_hard_fail(risks):
        reason = "Reject: hard-fail safety, scope, or compliance issue requires human correction."
    elif total >= profile.approve_threshold:
        reason = "Approve: package is review-ready for advisory planning use."
    elif total >= profile.revise_min_threshold:
        reason = "Revise: package is usable but requires human review before use."
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

