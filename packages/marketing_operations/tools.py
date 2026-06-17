"""Deterministic helper tools for Marketing Operations Agents 22-28."""

from __future__ import annotations

import re
from uuid import uuid4

from .profiles import AgentProfile
from .schemas import (
    EvidenceItem,
    GeneratedRecommendation,
    MarketingOperationsHandoff,
    MarketingOperationsRequest,
    MetricInsight,
    OutputSection,
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
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE_CANDIDATE_RE = re.compile(r"\+?\d[\d\s().-]{8,16}\d")
_LONG_ID_RE = re.compile(r"\b\d{9,}\b")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

# Common natural-language forms of protected attributes that the exact-token
# protected_terms list misses (e.g. "pregnant" vs "pregnancy", "minors" vs "age").
# Kept high-signal to avoid false positives in ops/B2B text. Each entry maps a
# regex to the canonical protected class it evidences.
_PROTECTED_SYNONYMS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("pregnancy", re.compile(r"\bpregnant\b")),
    ("age (minors)", re.compile(r"\bminors?\b|\bunderage\b|under[\s-]?18\b")),
)

# A request to certify/attest legal, regulatory, or compliance status — the core
# boundary Agent 27 must refuse. Matches "certify GDPR compliance",
# "certify our SOC2 compliance", "GDPR compliance certified", etc. (a regulation
# name inserted between "certify" and "compliance" otherwise evades the exact
# "certify compliance" forbidden term).
_CERTIFY_COMPLIANCE_RE = re.compile(
    r"certif\w*[^.]{0,40}(complian|legal|gdpr|ccpa|hipaa|can-?spam|casl|soc\s?2|regulat|privacy law|data protection)"
    r"|(complian\w*|gdpr|ccpa|hipaa|can-?spam|casl|soc\s?2|regulat\w*|data protection)[^.]{0,40}certif\w*",
    re.I,
)


def _phone_matches(text: str) -> bool:
    for match in _PHONE_CANDIDATE_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 10 <= len(digits) <= 15:
            return True
    return False


def detect_pii_kinds(text: str) -> tuple[str, ...]:
    kinds: list[str] = []
    if _EMAIL_RE.search(text):
        kinds.append("email")
    if _phone_matches(text):
        kinds.append("phone")
    if _SSN_RE.search(text) or _LONG_ID_RE.search(text):
        kinds.append("id number")
    return tuple(kinds)


def redact_pii(text: str) -> str:
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


_TEXT_FIELDS = (
    "business_context",
    "product_or_service",
    "campaign_objective",
    "campaign_type",
    "campaign_goal",
    "conversion_goal",
    "target_audience",
    "icp_summary",
    "segment_summary",
    "offer",
    "brand_voice",
    "budget",
    "spend",
    "timeline",
    "launch_window",
    "reporting_period",
    "region",
    "market_context",
    "language",
    "source_notes",
    "workflow_objective",
    "trigger_event",
    "workflow_context",
    "message_context",
    "message_sequence",
    "consent_context",
    "suppression_context",
    "privacy_notes",
    "compliance_context",
    "channel_context",
    "measurement_goal",
    "destination_context",
    "tracking_context",
    "system_context",
    "data_hygiene_objective",
    "field_list",
    "mapping_notes",
    "sample_summary",
    "issue_summary",
    "routing_objective",
    "segment_context",
    "score_context",
    "qualification_context",
    "territory_context",
    "owner_context",
    "queue_context",
    "capacity_context",
    "sla_expectations",
    "approval_context",
    "launch_checklist",
    "qa_results",
    "risk_register",
    "asset_inventory",
    "owner_action_list",
    "keyword_table",
    "ad_copy",
    "page_copy",
    "page_notes",
    "campaign_export",
    "metric_summary",
    "channel_summaries",
    "upstream_handoffs",
)

_TUPLE_FIELDS = (
    "constraints",
    "platforms",
    "channels",
    "keywords",
    "excluded_terms",
    "competitors",
    "page_sections",
    "form_fields",
    "content_inventory",
    "owner_notes",
    "compliance_notes",
    "approval_notes",
    "asset_list",
    "dependency_notes",
    "qa_requirements",
    "rollback_notes",
    "monitoring_goals",
    "field_names",
    "lifecycle_stages",
    "routing_rules",
    "tracking_requirements",
    "checklist_items",
)


def request_text(request: MarketingOperationsRequest | None) -> str:
    if request is None:
        return ""
    parts: list[str] = []
    for field in _TEXT_FIELDS:
        value = getattr(request, field, None)
        if value:
            parts.append(str(value))
    for field in _TUPLE_FIELDS:
        value = getattr(request, field, ())
        if value:
            parts.append(" ".join(str(item) for item in value))
    parts.extend(f"{m.label} {m.value} {m.source or ''}" for m in request.metrics)
    parts.extend(f"{s.stage} {s.count}" for s in request.funnel_stages)
    return clean_text(" ".join(parts))


def field_value(request: MarketingOperationsRequest, field_name: str) -> object:
    return getattr(request, field_name, None)


def is_empty_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not clean_text(value)
    if isinstance(value, tuple):
        return len(value) == 0
    return False


def missing_required_fields(profile: AgentProfile, request: MarketingOperationsRequest | None) -> tuple[str, ...]:
    if request is None:
        missing = list(profile.required_fields)
        missing.extend("one of: " + ", ".join(group) for group in profile.required_any_fields)
        return tuple(missing)
    missing = [field for field in profile.required_fields if is_empty_value(field_value(request, field))]
    for group in profile.required_any_fields:
        if all(is_empty_value(field_value(request, field)) for field in group):
            missing.append("one of: " + ", ".join(group))
    return tuple(missing)


def _contains_any(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in text)


def detect_risks(profile: AgentProfile, request: MarketingOperationsRequest | None) -> tuple[RiskFlag, ...]:
    if request is None:
        return (
            RiskFlag(
                category="missing_required_context",
                severity="hard_fail",
                message="Request could not be validated.",
                evidence_needed="Provide the required structured request fields.",
            ),
        )
    text_raw = request_text(request)
    text = text_raw.lower()
    flags: list[RiskFlag] = []
    missing = missing_required_fields(profile, request)
    if missing:
        flags.append(
            RiskFlag(
                category="missing_required_context",
                severity="hard_fail",
                message="Required Marketing Operations context is missing: " + ", ".join(missing),
                evidence_needed="Provide: " + ", ".join(missing),
            )
        )
    injection = _contains_any(text, _INJECTION_MARKERS)
    if injection:
        flags.append(
            RiskFlag(
                category="prompt_injection",
                severity="high",
                message="Input contains prompt-injection style text and was treated only as data.",
                evidence_needed=", ".join(injection),
            )
        )
    forbidden = _contains_any(text, profile.forbidden_actions)
    if forbidden:
        category = "approval_or_certification" if any("approve" in item or "certify" in item for item in forbidden) else "external_action"
        flags.append(
            RiskFlag(
                category=category,
                severity="hard_fail",
                message="The request asks for live access, activation, approval, certification, or external writes outside v1.",
                evidence_needed=", ".join(forbidden[:8]),
            )
        )
    protected_list = [
        term for term in profile.protected_terms if re.search(rf"\b{re.escape(term)}\b", text)
    ]
    protected_list += [label for label, pattern in _PROTECTED_SYNONYMS if pattern.search(text)]
    protected = tuple(dict.fromkeys(protected_list))
    if protected:
        flags.append(
            RiskFlag(
                category="protected_attribute",
                severity="hard_fail",
                message="Protected or sensitive personal attributes cannot be used for targeting, routing, segmentation, or compliance decisions.",
                evidence_needed=", ".join(protected[:8]),
            )
        )
    unsupported = _contains_any(text, profile.unsupported_claim_terms)
    if unsupported:
        flags.append(
            RiskFlag(
                category="misrepresentation",
                severity="hard_fail",
                message="The request asks for unsupported approval, legal, launch, data-quality, or performance claims.",
                evidence_needed=", ".join(unsupported[:8]),
            )
        )
    pii_kinds = detect_pii_kinds(text_raw)
    if pii_kinds:
        flags.append(
            RiskFlag(
                category="privacy_or_consent",
                severity="hard_fail",
                message="Potential PII appears in supplied operational context and is redacted in evidence.",
                evidence_needed="Remove or summarize lead/customer-level PII: " + ", ".join(pii_kinds),
            )
        )
    flags.extend(_agent_specific_risks(profile, request, text))
    return dedupe_risks(tuple(flags))


def _agent_specific_risks(profile: AgentProfile, request: MarketingOperationsRequest, text: str) -> tuple[RiskFlag, ...]:
    flags: list[RiskFlag] = []
    if profile.agent_id == "agent-22":
        if not (request.owner_context or request.owner_notes or request.owner_action_list):
            flags.append(_warning("data_quality", "Brief owner context is missing.", "Provide requester, DRIs, or approval owners."))
        if not (request.approval_context or request.approval_notes):
            flags.append(_warning("approval_or_certification", "Approval path is not supplied.", "Provide required reviewers or approval evidence."))
        if not (request.tracking_context or request.tracking_requirements or request.measurement_goal):
            flags.append(_warning("data_quality", "Tracking or measurement expectations are missing.", "Provide success metrics, reporting goal, or tracking requirements."))
        if not (request.asset_inventory or request.asset_list or request.content_inventory):
            flags.append(_warning("data_quality", "Asset inventory is missing.", "Provide required assets, landing pages, copy, or creative dependencies."))
    elif profile.agent_id == "agent-23":
        if not (request.suppression_context or request.consent_context or request.compliance_notes):
            flags.append(
                RiskFlag(
                    category="privacy_or_consent",
                    severity="high",
                    message="Workflow design is missing explicit consent or suppression context.",
                    evidence_needed="Provide consent basis, suppression rules, or Agent 27 handoff.",
                )
            )
        if not any(term in text for term in ("exit", "unsubscribe", "goal met", "suppress", "stop condition")):
            flags.append(_warning("data_quality", "Exit criteria are not clearly supplied.", "Define workflow exit, suppression, and stop conditions."))
    elif profile.agent_id == "agent-24":
        if request.sample_summary and not (request.field_list or request.mapping_notes):
            flags.append(_warning("data_quality", "Sample-only data context limits hygiene confidence.", "Provide field list, mapping notes, or data dictionary."))
        if any(term in text for term in ("duplicate", "dupe", "normalization", "conflicting mapping", "lifecycle conflict")):
            flags.append(_warning("data_quality", "Supplied notes indicate duplicate, normalization, mapping, or lifecycle risk.", "Confirm affected fields and stewardship owner."))
    elif profile.agent_id == "agent-25":
        matched = _contains_any(text, ("hide attribution", "manipulate attribution", "launder attribution", "mask source", "fake source"))
        if matched:
            flags.append(
                RiskFlag(
                    category="attribution_integrity",
                    severity="hard_fail",
                    message="Attribution manipulation or hiding source truth is not allowed.",
                    evidence_needed=", ".join(matched),
                )
            )
        if not (request.tracking_context or request.tracking_requirements or request.metric_summary):
            flags.append(_warning("data_quality", "Tracking QA details are not supplied.", "Provide event, pixel, conversion, or QA requirements."))
    elif profile.agent_id == "agent-26":
        if any(term in text for term in ("capacity conflict", "territory conflict", "round robin conflict", "owner conflict")):
            flags.append(
                RiskFlag(
                    category="routing_fairness",
                    severity="medium",
                    message="Supplied routing context indicates territory, capacity, owner, or queue conflicts.",
                    evidence_needed="Resolve conflicts before implementation.",
                )
            )
        if not (request.owner_context or request.queue_context or request.capacity_context):
            flags.append(_warning("data_quality", "Owner, queue, or capacity context is thin.", "Provide fallback owners, queues, or capacity rules."))
    elif profile.agent_id == "agent-27":
        if not (request.consent_context or request.suppression_context or request.privacy_notes):
            flags.append(
                RiskFlag(
                    category="privacy_or_consent",
                    severity="high",
                    message="Consent, suppression, or privacy context is missing or too thin.",
                    evidence_needed="Provide consent basis, suppression rules, privacy constraints, or legal-review notes.",
                )
            )
        if any(term in text for term in ("legal advice", "act as lawyer", "replace counsel", "final legal answer")):
            flags.append(
                RiskFlag(
                    category="legal_boundary",
                    severity="hard_fail",
                    message="Agent 27 cannot provide legal advice or replace counsel.",
                    evidence_needed="Reframe as operational risk triage with human legal review.",
                )
            )
        if _CERTIFY_COMPLIANCE_RE.search(text):
            flags.append(
                RiskFlag(
                    category="approval_or_certification",
                    severity="hard_fail",
                    message="Agent 27 cannot certify legal, regulatory, or compliance status; that requires qualified human/legal sign-off.",
                    evidence_needed="Reframe as operational risk triage; certification is out of scope for v1.",
                )
            )
    elif profile.agent_id == "agent-28":
        matched = _contains_any(text, ("hard_fail", "hard-fail", "unresolved blocker", "no-go", "blocker unresolved", "critical blocker"))
        if matched:
            flags.append(
                RiskFlag(
                    category="blocker_preservation",
                    severity="hard_fail",
                    message="Upstream hard-fail or unresolved launch blocker must be preserved and cannot pass readiness.",
                    evidence_needed=", ".join(matched),
                )
            )
        if not (request.owner_action_list or request.owner_notes):
            flags.append(_warning("data_quality", "Owner/action list is missing.", "Provide final owner actions or approval owners."))
    return tuple(flags)


def _warning(category: str, message: str, evidence_needed: str) -> RiskFlag:
    return RiskFlag(
        category=category,  # type: ignore[arg-type]
        severity="medium",
        message=message,
        evidence_needed=evidence_needed,
    )


def build_evidence(request: MarketingOperationsRequest | None) -> tuple[EvidenceItem, ...]:
    if request is None:
        return ()
    evidence: list[EvidenceItem] = []
    for label in _TEXT_FIELDS:
        value = getattr(request, label, None)
        if value:
            redacted = redact_pii(clean_text(value))
            sensitivity = "pii_possible" if redacted != clean_text(value) else "confidential"
            if label in {"business_context", "product_or_service", "campaign_objective", "campaign_goal"}:
                sensitivity = "normal"
            evidence.append(
                EvidenceItem(
                    source_label=label,
                    claim_supported=redacted[:180],
                    confidence="medium" if label in {"source_notes", "upstream_handoffs", "sample_summary"} else "high",
                    sensitivity=sensitivity,
                )
            )
    for label in _TUPLE_FIELDS:
        values = getattr(request, label, ())
        for value in values[:4]:
            redacted = redact_pii(clean_text(value))
            evidence.append(
                EvidenceItem(
                    source_label=label,
                    claim_supported=redacted[:180],
                    confidence="medium",
                    sensitivity="pii_possible" if redacted != clean_text(value) else "confidential",
                )
            )
    for metric in request.metrics:
        evidence.append(
            EvidenceItem(
                source_label=f"metric:{metric.label}",
                claim_supported=redact_pii(f"{metric.label}: {metric.value}")[:180],
                confidence="high" if metric.source else "medium",
            )
        )
    for stage in request.funnel_stages:
        evidence.append(
            EvidenceItem(
                source_label=f"funnel:{stage.stage}",
                claim_supported=redact_pii(f"{stage.stage}: {stage.count}")[:180],
                confidence="high",
            )
        )
    return tuple(evidence[:18])


def _metric_number(value: str) -> float | None:
    match = _NUMBER_RE.search(value.replace(",", ""))
    return float(match.group()) if match else None


def build_metric_insights(profile: AgentProfile, request: MarketingOperationsRequest | None) -> tuple[MetricInsight, ...]:
    if request is None:
        return ()
    insights: list[MetricInsight] = []
    for metric in request.metrics:
        number = _metric_number(metric.value)
        explanation = metric.source or "User-supplied metric; verify definition and denominator before use."
        confidence = "high" if metric.source else "medium"
        if number is not None:
            explanation = f"Supplied numeric value retained without live-system lookup. {explanation}"
        insights.append(MetricInsight(label=metric.label, value=metric.value, explanation=explanation, confidence=confidence))
    if request.funnel_stages:
        previous = None
        for stage in request.funnel_stages:
            if previous and previous.count > 0:
                rate = stage.count / previous.count
                insights.append(
                    MetricInsight(
                        label=f"{previous.stage} to {stage.stage}",
                        value=f"{rate:.1%}",
                        explanation=f"Deterministic calculation from supplied counts: {stage.count} / {previous.count}.",
                        confidence="high",
                    )
                )
            previous = stage
    checklist_count = len(request.checklist_items) + len(request.qa_requirements) + len(request.tracking_requirements)
    if checklist_count:
        insights.append(
            MetricInsight(
                label="Supplied checklist item count",
                value=str(checklist_count),
                explanation="Counted from supplied checklist, QA, and tracking requirement fields.",
                confidence="high",
            )
        )
    if profile.metric_mode in {"tracking", "launch"} and not (request.metrics or request.measurement_goal or request.tracking_context):
        insights.append(
            MetricInsight(
                label="Measurement context",
                value="missing",
                explanation="No live tracking was verified and no measurement context was supplied.",
                confidence="high",
            )
        )
    return tuple(insights[:12])


def build_output_sections(
    profile: AgentProfile,
    request: MarketingOperationsRequest | None,
    evidence: tuple[EvidenceItem, ...],
    risks: tuple[RiskFlag, ...],
) -> tuple[OutputSection, ...]:
    if any(flag.severity == "hard_fail" for flag in risks):
        return ()
    refs = tuple(item.source_label for item in evidence[:5])
    anchor = _anchor(profile, request)
    assumptions = build_assumptions(profile, request)[:4]
    sections: list[OutputSection] = []
    for section in profile.output_sections:
        summary = (
            f"{section.replace('_', ' ').title()} for {profile.primary_object}, grounded in "
            f"supplied context around {redact_pii(anchor)[:160]}."
        )
        if section == "not_legal_advice_boundary":
            summary = "This review is operational risk triage only; it is not legal advice and not legal or compliance certification."
        elif section == "human_go_no_go_recommendation":
            summary = "Provide a human-review go/no-go recommendation only; do not approve, launch, schedule, send, publish, or activate."
        sections.append(
            OutputSection(
                name=section,
                summary=summary,
                evidence_refs=refs,
                assumptions=assumptions,
                confidence="high" if refs else "medium",
            )
        )
    return tuple(sections)


def build_handoffs(profile: AgentProfile, request: MarketingOperationsRequest | None) -> tuple[MarketingOperationsHandoff, ...]:
    assumptions = build_assumptions(profile, request)
    return tuple(
        MarketingOperationsHandoff(
            target_agent=target,
            purpose=f"Use this {profile.primary_object} as structured MarketingIQ context.",
            fields=profile.recommended_outputs[:6],
            assumptions=assumptions[:5],
        )
        for target in profile.handoff_targets
    )


def build_assumptions(profile: AgentProfile, request: MarketingOperationsRequest | None) -> tuple[str, ...]:
    assumptions: list[str] = [
        "Output is advisory and requires human approval before any operational use.",
        "All source material was treated as supplied direct context, not autonomous research.",
        "No live CRM, MAP, CMS, analytics, tag manager, consent database, data warehouse, scheduler, or campaign platform was queried or changed.",
    ]
    if profile.agent_id == "agent-27":
        assumptions.append("This review is not legal advice and not legal or compliance certification.")
    if profile.agent_id == "agent-28":
        assumptions.append("Readiness output is not launch approval and cannot schedule, publish, send, spend, activate, or certify launch.")
    if request is None:
        return tuple(assumptions)
    if not request.source_notes and not request.upstream_handoffs:
        assumptions.append("Source notes or upstream handoffs were not supplied, so evidence confidence is limited.")
    if request.budget or request.spend:
        assumptions.append("Budget and spend references are planning context, not authorization to spend or change budgets.")
    return tuple(dict.fromkeys(assumptions))


def _anchor(profile: AgentProfile, request: MarketingOperationsRequest | None) -> str:
    if request is None:
        return profile.purpose
    return clean_text(
        request.campaign_objective
        or request.campaign_goal
        or request.workflow_objective
        or request.routing_objective
        or request.data_hygiene_objective
        or request.measurement_goal
        or request.compliance_context
        or request.offer
        or request.target_audience
        or request.source_notes
        or profile.purpose
    )


def build_recommendations(
    profile: AgentProfile,
    request: MarketingOperationsRequest | None,
    evidence: tuple[EvidenceItem, ...],
    risks: tuple[RiskFlag, ...],
    metric_insights: tuple[MetricInsight, ...],
) -> tuple[GeneratedRecommendation, ...]:
    if any(flag.severity == "hard_fail" for flag in risks):
        return ()
    anchor = _anchor(profile, request)
    evidence_refs = tuple(item.source_label for item in evidence[:6])
    recs: list[GeneratedRecommendation] = []
    for index, item_type in enumerate(profile.recommended_outputs, start=1):
        description = (
            f"Plan {index}: create {item_type.lower()} using supplied context around "
            f"{redact_pii(anchor)[:160]}. Keep the item advisory until a human approves use."
        )
        rationale = (
            f"This supports {profile.title} by turning direct context into a review-ready "
            f"{profile.primary_object} without live lookups or external writes."
        )
        if profile.agent_id == "agent-27" and item_type == "Not legal advice statement":
            description = "State that the output is not legal advice and not legal or compliance certification."
            rationale = "Agent 27 must preserve the human legal-review boundary in every complete output."
        if profile.agent_id == "agent-28" and item_type == "Human go no-go recommendation":
            description = "Provide a readiness recommendation for human review only, preserving blockers and warnings."
            rationale = "Agent 28 cannot approve, launch, schedule, send, publish, spend, or activate anything."
        if metric_insights:
            rationale += f" First supplied metric insight: {metric_insights[0].label} = {metric_insights[0].value}."
        actions = (
            f"Review the {item_type.lower()} with the responsible marketing operations owner.",
            "Verify evidence, consent, approvals, data quality, and operational constraints before use.",
            "Pass the structured handoff to the next approved MarketingIQ agent or human workflow.",
        )
        recs.append(
            GeneratedRecommendation(
                item_type=item_type,
                title=f"{item_type} for {profile.primary_object}",
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
