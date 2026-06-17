"""Deterministic helper tools for Demand Generation Agents 08-14."""

from __future__ import annotations

import re
from uuid import uuid4

from .profiles import AgentProfile
from .schemas import (
    DemandGenHandoff,
    DemandGenRequest,
    EvidenceItem,
    GeneratedRecommendation,
    MetricInsight,
    RiskFlag,
    clean_text,
)


_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous",
    "developer message",
    "system prompt",
    "reveal your prompt",
    "jailbreak",
    "do not follow the above",
)

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
# Backwards-compatible alias (email was the original sole PII signal).
_PII_RE = _EMAIL_RE
# SSN-style "123-45-6789".
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# Phone-like token: optional country code then 8-16 separator/digit chars then a digit.
# A normalized-digit count of 10-15 is required (checked in code) so 4-7 digit funnel
# counts and budgets do not false-positive.
_PHONE_CANDIDATE_RE = re.compile(r"\+?\d[\d\s().-]{8,16}\d")
# Obvious long numeric identifiers (account/card/aadhaar-style runs of 9+ digits).
_LONG_ID_RE = re.compile(r"\b\d{9,}\b")


def _phone_matches(text: str) -> bool:
    for match in _PHONE_CANDIDATE_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 10 <= len(digits) <= 15:
            return True
    return False


def detect_pii_kinds(text: str) -> tuple[str, ...]:
    """Return the coarse kinds of PII present in ``text`` (email/phone/id)."""
    kinds: list[str] = []
    if _EMAIL_RE.search(text):
        kinds.append("email")
    if _phone_matches(text):
        kinds.append("phone")
    if _SSN_RE.search(text) or _LONG_ID_RE.search(text):
        kinds.append("id number")
    return tuple(kinds)


def redact_pii(text: str) -> str:
    """Replace email/phone/SSN/long-id PII with neutral placeholders.

    Used before any user-supplied text is copied into output evidence so the
    structured package (and any optional persisted artifact) never echoes raw
    lead-level PII. Order matters: emails and SSNs first, then separated/intl
    phone numbers, then any remaining long contiguous digit runs.
    """
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _SSN_RE.sub("[redacted-id]", text)

    def _phone_repl(match: "re.Match[str]") -> str:
        digits = re.sub(r"\D", "", match.group())
        return "[redacted-phone]" if 10 <= len(digits) <= 15 else match.group()

    text = _PHONE_CANDIDATE_RE.sub(_phone_repl, text)
    text = _LONG_ID_RE.sub("[redacted-id]", text)
    return text


def new_request_id(agent_id: str) -> str:
    return f"{agent_id}-{uuid4().hex[:12]}"


def request_text(request: DemandGenRequest | None) -> str:
    if request is None:
        return ""
    parts = [
        request.business_context or "",
        request.product_or_service or "",
        request.icp_summary or "",
        request.segment_summary or "",
        request.campaign_goal or "",
        request.offer or "",
        request.target_audience or "",
        request.budget or "",
        request.region or "",
        request.source_notes or "",
        " ".join(request.constraints),
        " ".join(request.audience_fields),
        " ".join(request.signals),
        " ".join(request.score_bands),
        " ".join(request.content_inventory),
        " ".join(f"{m.label} {m.value} {m.source or ''}" for m in request.metrics),
        " ".join(f"{s.stage} {s.count}" for s in request.funnel_stages),
    ]
    return clean_text(" ".join(parts))


def field_value(request: DemandGenRequest, field_name: str) -> object:
    return getattr(request, field_name)


def is_empty_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not clean_text(value)
    if isinstance(value, tuple):
        return len(value) == 0
    return False


def missing_required_fields(profile: AgentProfile, request: DemandGenRequest | None) -> tuple[str, ...]:
    if request is None:
        return profile.required_fields
    missing = [field for field in profile.required_fields if is_empty_value(field_value(request, field))]
    return tuple(missing)


def detect_risks(profile: AgentProfile, request: DemandGenRequest | None) -> tuple[RiskFlag, ...]:
    if request is None:
        return (
            RiskFlag(
                category="missing_required_context",
                severity="hard_fail",
                message="Request could not be validated.",
                evidence_needed="Provide the required structured request fields.",
            ),
        )
    text = request_text(request).lower()
    flags: list[RiskFlag] = []
    missing = missing_required_fields(profile, request)
    if missing:
        flags.append(
            RiskFlag(
                category="missing_required_context",
                severity="hard_fail",
                message="Required planning context is missing: " + ", ".join(missing),
                evidence_needed="Provide: " + ", ".join(missing),
            )
        )
    injection = [marker for marker in _INJECTION_MARKERS if marker in text]
    if injection:
        flags.append(
            RiskFlag(
                category="prompt_injection",
                severity="high",
                message="Input contains prompt-injection style text and was treated only as data.",
                evidence_needed=", ".join(injection),
            )
        )
    forbidden = [term for term in profile.forbidden_actions if term in text]
    if forbidden:
        flags.append(
            RiskFlag(
                category="external_action",
                severity="hard_fail",
                message=(
                    "The request asks for an external action that is outside v1. "
                    "Human approval and a future integration are required."
                ),
                evidence_needed=", ".join(forbidden[:8]),
            )
        )
    protected = [term for term in profile.protected_terms if re.search(rf"\b{re.escape(term)}\b", text)]
    if protected:
        flags.append(
            RiskFlag(
                category="protected_attribute",
                severity="hard_fail",
                message="Protected or sensitive personal attributes cannot be used for targeting or scoring.",
                evidence_needed=", ".join(protected[:8]),
            )
        )
    leaky = [term for term in profile.leaky_terms if term in text]
    if leaky:
        flags.append(
            RiskFlag(
                category="bias_or_leakage",
                severity="hard_fail",
                message="Leaky outcome fields cannot be used as lead scoring inputs.",
                evidence_needed=", ".join(leaky[:8]),
            )
        )
    pii_kinds = detect_pii_kinds(request_text(request))
    if pii_kinds:
        flags.append(
            RiskFlag(
                category="data_quality",
                severity="hard_fail",
                message=(
                    "Potential lead-level PII (" + ", ".join(pii_kinds) + ") appears in the "
                    "supplied notes and must be removed or summarized before model use."
                ),
                evidence_needed=(
                    "Remove or summarize lead-level PII (email, phone, or ID numbers) "
                    "before rerunning the agent."
                ),
            )
        )
    if profile.agent_id == "agent-09" and not request.metrics:
        size_terms = ("audience size", "segment size", "estimate size", "size estimate")
        if any(term in text for term in size_terms):
            flags.append(
                RiskFlag(
                    category="data_quality",
                    severity="hard_fail",
                    message="Audience size estimates require user-supplied count or size data in v1.",
                    evidence_needed="Provide audience count metrics or remove the size-estimation request.",
                )
            )
    if profile.metric_mode == "conversion":
        flags.extend(conversion_data_quality_risks(request))
    return dedupe_risks(tuple(flags))


def conversion_data_quality_risks(request: DemandGenRequest) -> tuple[RiskFlag, ...]:
    stages = request.funnel_stages
    flags: list[RiskFlag] = []
    if len(stages) < 2:
        flags.append(
            RiskFlag(
                category="data_quality",
                severity="hard_fail",
                message="Conversion analysis needs at least two funnel stages with counts.",
                evidence_needed="Provide stage names and non-negative counts.",
            )
        )
        return tuple(flags)
    previous = stages[0].count
    for stage in stages[1:]:
        if stage.count > previous:
            flags.append(
                RiskFlag(
                    category="data_quality",
                    severity="hard_fail",
                    message="Funnel stage counts increase downstream, suggesting inconsistent denominators.",
                    evidence_needed=f"Check denominator for stage {stage.stage}.",
                )
            )
            break
        previous = stage.count
    if stages[0].count < 30:
        flags.append(
            RiskFlag(
                category="data_quality",
                severity="medium",
                message="Small sample size may make conversion rates unreliable.",
                evidence_needed="Provide a larger sample or mark findings as directional.",
            )
        )
    return tuple(flags)


def build_evidence(request: DemandGenRequest | None) -> tuple[EvidenceItem, ...]:
    if request is None:
        return ()
    evidence: list[EvidenceItem] = []
    for label, value in (
        ("business_context", request.business_context),
        ("icp_summary", request.icp_summary),
        ("segment_summary", request.segment_summary),
        ("campaign_goal", request.campaign_goal),
        ("offer", request.offer),
        ("source_notes", request.source_notes),
    ):
        if value:
            evidence.append(
                EvidenceItem(
                    source_label=label,
                    claim_supported=redact_pii(clean_text(value))[:180],
                    confidence="medium" if label == "source_notes" else "high",
                    sensitivity="confidential" if label == "source_notes" else "normal",
                )
            )
    for metric in request.metrics:
        evidence.append(
            EvidenceItem(
                source_label=f"metric:{metric.label}",
                claim_supported=redact_pii(f"{metric.label}: {metric.value}"),
                confidence="high" if metric.source else "medium",
            )
        )
    for stage in request.funnel_stages:
        evidence.append(
            EvidenceItem(
                source_label=f"funnel:{stage.stage}",
                claim_supported=redact_pii(f"{stage.stage}: {stage.count}"),
                confidence="high",
            )
        )
    return tuple(evidence[:12])


def calculate_conversion_insights(request: DemandGenRequest | None) -> tuple[MetricInsight, ...]:
    if request is None or len(request.funnel_stages) < 2:
        return ()
    insights: list[MetricInsight] = []
    stages = request.funnel_stages
    for prior, current in zip(stages, stages[1:]):
        if prior.count == 0:
            insights.append(
                MetricInsight(
                    label=f"{prior.stage} to {current.stage}",
                    value="undefined",
                    explanation="Prior stage count is zero, so the conversion rate cannot be calculated.",
                    confidence="low",
                )
            )
            continue
        rate = current.count / prior.count
        drop = prior.count - current.count
        insights.append(
            MetricInsight(
                label=f"{prior.stage} to {current.stage}",
                value=f"{rate:.1%}",
                explanation=f"Deterministic calculation: {current.count} / {prior.count}; drop-off {drop}.",
                confidence="high",
            )
        )
    return tuple(insights)


def build_metric_insights(profile: AgentProfile, request: DemandGenRequest | None) -> tuple[MetricInsight, ...]:
    if profile.metric_mode == "conversion":
        return calculate_conversion_insights(request)
    if request is None:
        return ()
    insights = [
        MetricInsight(
            label=metric.label,
            value=metric.value,
            explanation=metric.source or "User-supplied metric; verify before operational use.",
            confidence="high" if metric.source else "medium",
        )
        for metric in request.metrics
    ]
    return tuple(insights[:8])


def build_handoffs(profile: AgentProfile, request: DemandGenRequest | None) -> tuple[DemandGenHandoff, ...]:
    assumptions = build_assumptions(profile, request)
    return tuple(
        DemandGenHandoff(
            target_agent=target,
            purpose=f"Use this {profile.primary_object} output as structured planning context.",
            fields=profile.recommended_outputs[:5],
            assumptions=assumptions[:3],
        )
        for target in profile.handoff_targets
    )


def build_assumptions(profile: AgentProfile, request: DemandGenRequest | None) -> tuple[str, ...]:
    assumptions: list[str] = [
        "Output is advisory and requires human approval before activation.",
        "All source material was treated as direct context, not as autonomous research.",
    ]
    if request is None:
        return tuple(assumptions)
    if not request.source_notes:
        assumptions.append("Source notes were not supplied, so evidence confidence is limited.")
    if profile.metric_mode == "conversion" and request.funnel_stages:
        assumptions.append("Conversion math uses the supplied stage counts and does not query live systems.")
    if request.budget:
        assumptions.append("Budget guidance is planning-only and not authorization to spend.")
    return tuple(assumptions)


def build_recommendations(
    profile: AgentProfile,
    request: DemandGenRequest | None,
    evidence: tuple[EvidenceItem, ...],
    risks: tuple[RiskFlag, ...],
    metric_insights: tuple[MetricInsight, ...],
) -> tuple[GeneratedRecommendation, ...]:
    if any(flag.severity == "hard_fail" for flag in risks):
        return ()
    context = request_text(request)
    anchor = (
        request.campaign_goal
        or request.segment_summary
        or request.icp_summary
        or request.business_context
        or profile.purpose
        if request
        else profile.purpose
    )
    evidence_refs = tuple(item.source_label for item in evidence[:4])
    recs: list[GeneratedRecommendation] = []
    for index, item_type in enumerate(profile.recommended_outputs, start=1):
        title = f"{item_type} for {profile.primary_object}"
        description = (
            f"Plan {index}: define {item_type.lower()} using the supplied context around "
            f"{redact_pii(clean_text(anchor))[:160]}. Keep this advisory until a human approves execution."
        )
        rationale = (
            f"This supports {profile.title} by turning direct context into an operational "
            f"{profile.primary_object} artifact without external writes."
        )
        actions = (
            f"Review the {item_type.lower()} with the responsible GTM owner.",
            "Verify evidence, consent, and operational constraints before use.",
            "Pass the structured handoff to the next approved MarketingIQ agent.",
        )
        if profile.metric_mode == "conversion" and metric_insights:
            rationale = (
                "Deterministic funnel calculations indicate where conversion drop-off should be reviewed. "
                f"{metric_insights[0].label}: {metric_insights[0].value}."
            )
        recs.append(
            GeneratedRecommendation(
                item_type=item_type,
                title=title,
                description=description,
                rationale=rationale,
                actions=actions,
                evidence_refs=evidence_refs,
                confidence="high" if evidence_refs else "medium",
            )
        )
    return tuple(recs)


def dedupe_risks(flags: tuple[RiskFlag, ...]) -> tuple[RiskFlag, ...]:
    seen: set[tuple[str, str, str, str | None]] = set()
    out: list[RiskFlag] = []
    for flag in flags:
        key = (flag.category, flag.severity, flag.message, flag.evidence_needed)
        if key not in seen:
            out.append(flag)
            seen.add(key)
    return tuple(out)
