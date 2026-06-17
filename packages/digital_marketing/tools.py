"""Deterministic helper tools for Digital Marketing Agents 15-21."""

from __future__ import annotations

import re
from uuid import uuid4

from .profiles import AgentProfile
from .schemas import (
    DigitalMarketingHandoff,
    DigitalMarketingRequest,
    EvidenceItem,
    GeneratedRecommendation,
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
_URL_RE = re.compile(r"https?://\S+", re.I)
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


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


def request_text(request: DigitalMarketingRequest | None) -> str:
    if request is None:
        return ""
    parts = [
        request.business_context or "",
        request.product_or_service or "",
        request.campaign_goal or "",
        request.conversion_goal or "",
        request.target_audience or "",
        request.icp_summary or "",
        request.segment_summary or "",
        request.offer or "",
        request.brand_voice or "",
        request.budget or "",
        request.spend or "",
        request.timeline or "",
        request.reporting_period or "",
        request.region or "",
        request.language or "",
        request.source_notes or "",
        request.keyword_table or "",
        request.ad_copy or "",
        request.page_copy or "",
        request.page_notes or "",
        request.campaign_export or "",
        request.metric_summary or "",
        request.channel_summaries or "",
        request.upstream_handoffs or "",
        " ".join(request.constraints),
        " ".join(request.platforms),
        " ".join(request.channels),
        " ".join(request.keywords),
        " ".join(request.excluded_terms),
        " ".join(request.competitors),
        " ".join(request.page_sections),
        " ".join(request.form_fields),
        " ".join(request.content_inventory),
        " ".join(request.owner_notes),
        " ".join(request.compliance_notes),
        " ".join(f"{m.label} {m.value} {m.source or ''}" for m in request.metrics),
        " ".join(f"{s.stage} {s.count}" for s in request.funnel_stages),
    ]
    return clean_text(" ".join(parts))


def field_value(request: DigitalMarketingRequest, field_name: str) -> object:
    return getattr(request, field_name)


def is_empty_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not clean_text(value)
    if isinstance(value, tuple):
        return len(value) == 0
    return False


def _has_substantive_page_text(request: DigitalMarketingRequest) -> bool:
    """True only if supplied page material has real copy beyond bare URL(s).

    A URL pasted into ``page_copy`` / ``page_sections`` is NOT page content the
    agent can review — it does not crawl. Stripping URLs and requiring a few
    residual words prevents a URL-only request from slipping past the no-crawl
    guard simply because it was placed in ``page_copy`` instead of ``page_notes``.
    """
    blob = (request.page_copy or "") + " " + " ".join(request.page_sections)
    residue = clean_text(_URL_RE.sub(" ", blob))
    return len(residue.split()) >= 3


def missing_required_fields(profile: AgentProfile, request: DigitalMarketingRequest | None) -> tuple[str, ...]:
    if request is None:
        missing = list(profile.required_fields)
        missing.extend("one of: " + ", ".join(group) for group in profile.required_any_fields)
        return tuple(missing)
    missing = [field for field in profile.required_fields if is_empty_value(field_value(request, field))]
    for group in profile.required_any_fields:
        if all(is_empty_value(field_value(request, field)) for field in group):
            missing.append("one of: " + ", ".join(group))
    return tuple(missing)


def detect_risks(profile: AgentProfile, request: DigitalMarketingRequest | None) -> tuple[RiskFlag, ...]:
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
                message="Required Digital Marketing context is missing: " + ", ".join(missing),
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
                message="The request asks for live access, activation, or external writes outside v1.",
                evidence_needed=", ".join(forbidden[:8]),
            )
        )
    protected = [term for term in profile.protected_terms if re.search(rf"\b{re.escape(term)}\b", text)]
    if protected:
        flags.append(
            RiskFlag(
                category="protected_attribute",
                severity="hard_fail",
                message="Protected or sensitive personal attributes cannot be used for targeting, copy, or reporting decisions.",
                evidence_needed=", ".join(protected[:8]),
            )
        )
    unsupported = [term for term in profile.unsupported_claim_terms if term in text]
    if unsupported:
        category = "misrepresentation" if profile.agent_id == "agent-21" else "unsupported_claim"
        flags.append(
            RiskFlag(
                category=category,
                severity="hard_fail",
                message="The request asks for unsupported or fabricated claims, metrics, or performance statements.",
                evidence_needed=", ".join(unsupported[:8]),
            )
        )
    pii_kinds = detect_pii_kinds(request_text(request))
    if pii_kinds:
        flags.append(
            RiskFlag(
                category="privacy_or_consent",
                severity="hard_fail",
                message="Potential PII appears in supplied marketing context and must be removed or summarized before model use.",
                evidence_needed="Remove or summarize lead/customer-level PII: " + ", ".join(pii_kinds),
            )
        )
    flags.extend(_agent_specific_risks(profile, request, text))
    return dedupe_risks(tuple(flags))


def _agent_specific_risks(profile: AgentProfile, request: DigitalMarketingRequest, text: str) -> tuple[RiskFlag, ...]:
    flags: list[RiskFlag] = []
    if profile.agent_id == "agent-15":
        if not request.metrics and not any(term in text for term in ("volume", "cpc", "difficulty", "rank")):
            flags.append(
                RiskFlag(
                    category="data_quality",
                    severity="medium",
                    message="Keyword volume, CPC, difficulty, and ranking data were not supplied.",
                    evidence_needed="Provide keyword metrics or treat priority as heuristic.",
                )
            )
    if profile.agent_id == "agent-16":
        claim_terms = ("best", "leading", "guaranteed", "certified", "clinical", "financial return", "risk-free")
        if any(term in text for term in claim_terms) and not (request.source_notes or request.compliance_notes):
            flags.append(
                RiskFlag(
                    category="unsupported_claim",
                    severity="high",
                    message="Strong ad claims need supplied proof or compliance notes before use.",
                    evidence_needed="Provide approved proof points or soften the claim.",
                )
            )
    if profile.agent_id == "agent-17":
        has_url = bool(_URL_RE.search(text))
        has_page_material = _has_substantive_page_text(request)
        if has_url and not has_page_material:
            flags.append(
                RiskFlag(
                    category="live_platform_access",
                    severity="hard_fail",
                    message="URL-only landing page requests are unsupported in v1 because the agent does not crawl pages.",
                    evidence_needed="Paste page copy, outline, wireframe notes, or screenshot text notes.",
                )
            )
        if len(request.form_fields) >= 8:
            flags.append(
                RiskFlag(
                    category="data_quality",
                    severity="medium",
                    message="The supplied form appears long enough to create conversion friction.",
                    evidence_needed="Review field necessity and consent language.",
                )
            )
    if profile.agent_id in {"agent-18", "agent-20", "agent-21"}:
        flags.extend(metric_data_quality_risks(profile, request))
    if profile.agent_id in {"agent-19", "agent-20"}:
        consent_terms = ("ignore consent", "bypass consent", "bypass suppression", "no unsubscribe", "dark pattern")
        matched = [term for term in consent_terms if term in text]
        if matched:
            flags.append(
                RiskFlag(
                    category="privacy_or_consent",
                    severity="hard_fail",
                    message="Consent, suppression, privacy, or manipulation bypass is outside v1 and unsafe.",
                    evidence_needed=", ".join(matched),
                )
            )
    if profile.agent_id == "agent-21":
        if any(term in text for term in ("hide bad", "hide negative", "make it look better", "fake improvement")):
            flags.append(
                RiskFlag(
                    category="misrepresentation",
                    severity="hard_fail",
                    message="Performance reports must include negative results and must not misrepresent performance.",
                    evidence_needed="Remove the misrepresentation request and provide truthful caveats.",
                )
            )
    return tuple(flags)


def metric_data_quality_risks(profile: AgentProfile, request: DigitalMarketingRequest) -> tuple[RiskFlag, ...]:
    flags: list[RiskFlag] = []
    if request.funnel_stages:
        stages = request.funnel_stages
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
                    message="Small sample size may make rates and experiment priorities unreliable.",
                    evidence_needed="Provide a larger sample or mark findings as directional.",
                )
            )
    if profile.agent_id in {"agent-18", "agent-21"}:
        text = request_text(request).lower()
        asks_rate = any(term in text for term in ("ctr", "cvr", "cpa", "roas", "conversion rate"))
        has_metric_context = bool(request.metrics or request.metric_summary or request.campaign_export or request.channel_summaries)
        if asks_rate and not has_metric_context:
            flags.append(
                RiskFlag(
                    category="data_quality",
                    severity="hard_fail",
                    message="Rate, CPA, ROAS, or performance claims require supplied metrics and denominators.",
                    evidence_needed="Provide impressions/clicks/conversions/spend/revenue as applicable.",
                )
            )
    return tuple(flags)


def build_evidence(request: DigitalMarketingRequest | None) -> tuple[EvidenceItem, ...]:
    if request is None:
        return ()
    evidence: list[EvidenceItem] = []
    fields = (
        ("business_context", request.business_context),
        ("product_or_service", request.product_or_service),
        ("campaign_goal", request.campaign_goal),
        ("conversion_goal", request.conversion_goal),
        ("target_audience", request.target_audience),
        ("offer", request.offer),
        ("source_notes", request.source_notes),
        ("keyword_table", request.keyword_table),
        ("ad_copy", request.ad_copy),
        ("page_copy", request.page_copy),
        ("page_notes", request.page_notes),
        ("campaign_export", request.campaign_export),
        ("metric_summary", request.metric_summary),
        ("channel_summaries", request.channel_summaries),
        ("upstream_handoffs", request.upstream_handoffs),
    )
    for label, value in fields:
        if value:
            evidence.append(
                EvidenceItem(
                    source_label=label,
                    claim_supported=redact_pii(clean_text(value))[:180],
                    confidence="medium" if label in {"source_notes", "upstream_handoffs"} else "high",
                    sensitivity="confidential" if label not in {"business_context", "product_or_service"} else "normal",
                )
            )
    for keyword in request.keywords[:8]:
        evidence.append(EvidenceItem(source_label="keyword", claim_supported=redact_pii(keyword), confidence="medium"))
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
    return tuple(evidence[:16])


def _metric_number(value: str) -> float | None:
    match = _NUMBER_RE.search(value.replace(",", ""))
    return float(match.group()) if match else None


def calculate_funnel_insights(request: DigitalMarketingRequest | None) -> tuple[MetricInsight, ...]:
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
                    explanation="Prior stage count is zero, so the rate cannot be calculated.",
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


_RATE_LABEL_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("impressions", ("impression",)),
    ("clicks", ("click",)),
    ("conversions", ("conversion", "submission", "signup", "lead")),
    ("spend", ("spend", "cost")),
    ("revenue", ("revenue", "sales")),
)


def _metric_lookup(request: DigitalMarketingRequest) -> dict[str, float]:
    """Map supplied metrics to canonical numeric values for deterministic rate math."""
    found: dict[str, float] = {}
    for metric in request.metrics:
        number = _metric_number(metric.value)
        if number is None:
            continue
        label = metric.label.lower()
        for canonical, aliases in _RATE_LABEL_ALIASES:
            if canonical in found:
                continue
            if canonical in label or any(alias in label for alias in aliases):
                found[canonical] = number
    return found


def derive_rate_metrics(request: DigitalMarketingRequest | None) -> tuple[MetricInsight, ...]:
    """Deterministically derive standard rate KPIs from supplied count metrics.

    Only uses values the user supplied — never invents data. Each derived KPI is
    clearly labelled ``(derived)`` and shows the exact division used. Zero or
    missing denominators yield an explicit ``undefined`` insight rather than a
    fabricated number.
    """
    if request is None or not request.metrics:
        return ()
    values = _metric_lookup(request)
    insights: list[MetricInsight] = []

    def _ratio(num_key: str, den_key: str, label: str, *, percent: bool) -> None:
        if num_key not in values or den_key not in values:
            return
        num, den = values[num_key], values[den_key]
        if den <= 0:
            insights.append(
                MetricInsight(
                    label=f"{label} (derived)",
                    value="undefined",
                    explanation=f"Deterministic calculation: {num_key} / {den_key} has a zero or missing denominator.",
                    confidence="low",
                )
            )
            return
        ratio = num / den
        value = f"{ratio:.1%}" if percent else f"{ratio:.2f}"
        insights.append(
            MetricInsight(
                label=f"{label} (derived)",
                value=value,
                explanation=f"Deterministic calculation: {num_key} / {den_key} = {num:g} / {den:g}.",
                confidence="high",
            )
        )

    _ratio("clicks", "impressions", "CTR", percent=True)
    _ratio("conversions", "clicks", "CVR", percent=True)
    _ratio("spend", "clicks", "CPC", percent=False)
    _ratio("spend", "conversions", "CPA", percent=False)
    _ratio("revenue", "spend", "ROAS", percent=False)
    return tuple(insights)


def build_metric_insights(profile: AgentProfile, request: DigitalMarketingRequest | None) -> tuple[MetricInsight, ...]:
    if request is None:
        return ()
    insights: list[MetricInsight] = list(calculate_funnel_insights(request))
    for metric in request.metrics:
        number = _metric_number(metric.value)
        explanation = metric.source or "User-supplied metric; verify definition and denominator before use."
        confidence = "high" if metric.source else "medium"
        if number is not None and metric.label.lower() in {"clicks", "impressions", "conversions", "spend", "revenue"}:
            explanation = f"Supplied numeric metric retained without live-system lookup. {explanation}"
        insights.append(MetricInsight(label=metric.label, value=metric.value, explanation=explanation, confidence=confidence))
    insights.extend(derive_rate_metrics(request))
    if profile.metric_mode == "keyword" and not request.metrics:
        insights.append(
            MetricInsight(
                label="Keyword metric availability",
                value="missing",
                explanation="No live search volume, CPC, difficulty, or ranking data was supplied.",
                confidence="high",
            )
        )
    return tuple(insights[:12])


def build_output_sections(
    profile: AgentProfile,
    request: DigitalMarketingRequest | None,
    evidence: tuple[EvidenceItem, ...],
    risks: tuple[RiskFlag, ...],
) -> tuple[OutputSection, ...]:
    if any(flag.severity == "hard_fail" for flag in risks):
        return ()
    refs = tuple(item.source_label for item in evidence[:4])
    anchor = _anchor(profile, request)
    sections: list[OutputSection] = []
    assumptions = build_assumptions(profile, request)[:3]
    for section in profile.output_sections:
        sections.append(
            OutputSection(
                name=section,
                summary=(
                    f"{section.replace('_', ' ').title()} for {profile.primary_object}, grounded in "
                    f"supplied context around {redact_pii(anchor)[:160]}."
                ),
                evidence_refs=refs,
                assumptions=assumptions,
                confidence="high" if refs else "medium",
            )
        )
    return tuple(sections)


def build_handoffs(profile: AgentProfile, request: DigitalMarketingRequest | None) -> tuple[DigitalMarketingHandoff, ...]:
    assumptions = build_assumptions(profile, request)
    return tuple(
        DigitalMarketingHandoff(
            target_agent=target,
            purpose=f"Use this {profile.primary_object} as structured MarketingIQ context.",
            fields=profile.recommended_outputs[:5],
            assumptions=assumptions[:4],
        )
        for target in profile.handoff_targets
    )


def build_assumptions(profile: AgentProfile, request: DigitalMarketingRequest | None) -> tuple[str, ...]:
    assumptions: list[str] = [
        "Output is advisory and requires human approval before activation.",
        "All source material was treated as supplied direct context, not autonomous research.",
        "No live platform, SEO, ad, analytics, CRM, MAP, CMS, browser, warehouse, or dashboard data was queried.",
    ]
    if request is None:
        return tuple(assumptions)
    if not request.source_notes and not request.upstream_handoffs:
        assumptions.append("Source notes or upstream handoffs were not supplied, so evidence confidence is limited.")
    if profile.metric_mode in {"paid", "cro", "reporting"}:
        assumptions.append("Metric math uses only supplied values and does not verify live source-system state.")
    if request.budget or request.spend:
        assumptions.append("Budget and spend guidance is planning-only and not authorization to spend or change budgets.")
    return tuple(dict.fromkeys(assumptions))


def _anchor(profile: AgentProfile, request: DigitalMarketingRequest | None) -> str:
    if request is None:
        return profile.purpose
    return clean_text(
        request.campaign_goal
        or request.conversion_goal
        or request.offer
        or request.product_or_service
        or request.target_audience
        or request.source_notes
        or profile.purpose
    )


def build_recommendations(
    profile: AgentProfile,
    request: DigitalMarketingRequest | None,
    evidence: tuple[EvidenceItem, ...],
    risks: tuple[RiskFlag, ...],
    metric_insights: tuple[MetricInsight, ...],
) -> tuple[GeneratedRecommendation, ...]:
    if any(flag.severity == "hard_fail" for flag in risks):
        return ()
    anchor = _anchor(profile, request)
    evidence_refs = tuple(item.source_label for item in evidence[:5])
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
        if profile.metric_mode in {"paid", "cro", "reporting"} and metric_insights:
            rationale = (
                "Supplied metrics and deterministic calculations should guide the recommendation. "
                f"First metric insight: {metric_insights[0].label} = {metric_insights[0].value}."
            )
        if profile.metric_mode == "keyword" and item_type == "Missing metric warnings":
            rationale = "Search volume, CPC, keyword difficulty, and ranking data must be user-supplied or marked missing."
        actions = (
            f"Review the {item_type.lower()} with the responsible marketing owner.",
            "Verify evidence, policy, consent, and operational constraints before use.",
            "Pass the structured handoff to the next approved MarketingIQ agent.",
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
