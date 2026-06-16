"""Deterministic local helper tools for Agent 07.

These helpers do not call networks, cloud SDKs, search engines, analytics APIs,
CRMs, CMSs, social APIs, or customer databases.
"""
from __future__ import annotations

import re
from collections import Counter

from .schemas import (
    CaseStudyDraft,
    CaseStudyRequest,
    EvidenceMap,
    MetricHighlight,
    MissingInfoWarning,
    RiskFlag,
)


def clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def split_text_items(value: object) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        raw = value.replace("\n", ",").replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set, frozenset)):
        raw = tuple(value)
    else:
        raw = (value,)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = clean_text(item)
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return tuple(out)


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def important_terms(request: CaseStudyRequest | None) -> tuple[str, ...]:
    if request is None:
        return ()
    raw_terms = [
        request.customer_name or "",
        request.industry,
        request.target_audience,
        request.challenge,
        request.solution_summary,
        request.product_or_service or "",
        request.results,
    ]
    terms: list[str] = []
    seen: set[str] = set()
    for value in raw_terms:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", value.lower()):
            if token not in seen and token not in {"with", "from", "that", "this", "into", "their", "your"}:
                terms.append(token)
                seen.add(token)
    return tuple(terms[:30])


def supplied_context_text(request: CaseStudyRequest | None) -> str:
    if request is None:
        return ""
    metric_text = " ".join(
        " ".join(
            clean_text(item)
            for item in (metric.label, metric.value, metric.baseline, metric.after, metric.source)
            if item
        )
        for metric in request.metrics
    )
    parts = [
        request.customer_name or "",
        request.industry,
        request.target_audience,
        request.challenge,
        request.solution_summary,
        request.product_or_service or "",
        request.implementation_notes or "",
        request.results,
        metric_text,
        " ".join(request.customer_quotes),
        request.source_notes or "",
        request.brand_voice or "",
        request.cta_goal or "",
    ]
    return clean_text(" ".join(parts))


def detect_prompt_injection_markers(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    markers = (
        "ignore previous instructions",
        "ignore all previous",
        "system prompt",
        "developer message",
        "reveal your prompt",
        "jailbreak",
        "act as system",
        "do not follow the above",
    )
    return tuple(marker for marker in markers if marker in lowered)


def detect_external_action_requests(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    markers = (
        "publish this",
        "upload this",
        "post this",
        "post to linkedin",
        "send email",
        "write to cms",
        "update wordpress",
        "push to crm",
        "update crm",
        "call analytics",
        "send campaign",
    )
    return tuple(marker for marker in markers if marker in lowered)


def detect_confidentiality_markers(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    markers = (
        "confidential",
        "under nda",
        "do not name",
        "anonymize",
        "anonymous",
        "private customer",
        "internal only",
    )
    return tuple(marker for marker in markers if marker in lowered)


def detect_pii_markers(text: str) -> tuple[str, ...]:
    markers: list[str] = []
    if re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text or "", flags=re.I):
        markers.append("email_address")
    if re.search(r"(?:\+?\d[\d\s().-]{8,}\d)", text or ""):
        markers.append("phone_number")
    return tuple(markers)


def detect_unsupported_claim_markers(text: str, supplied_context: str = "") -> tuple[str, ...]:
    lowered = str(text or "").lower()
    supplied = str(supplied_context or "").lower()
    markers: list[str] = []
    for phrase in (
        "guaranteed",
        "guarantee",
        "market leader",
        "industry-leading",
        "best-in-class",
        "proven to",
        "fully compliant",
        "legally approved",
        "customer-approved",
        "without evidence",
        "no evidence",
    ):
        if phrase in lowered and phrase not in supplied:
            markers.append(phrase)
    for pattern_name, pattern in (
        ("percentage_claim", r"\b\d+(?:\.\d+)?\s?%"),
        ("multiplier_claim", r"\b\d+(?:\.\d+)?x\b"),
        ("money_claim", r"(?:rs|inr|\$|usd)\s?\d"),
    ):
        if re.search(pattern, lowered) and not re.search(pattern, supplied):
            markers.append(pattern_name)
    return tuple(dict.fromkeys(markers))


def detect_high_risk_input_claims(request: CaseStudyRequest) -> tuple[str, ...]:
    text = supplied_context_text(request).lower()
    markers: list[str] = []
    for phrase in (
        "guaranteed",
        "guarantee",
        "without evidence",
        "no evidence",
        "legally approved",
        "fully compliant",
        "customer-approved",
    ):
        if phrase in text:
            markers.append(phrase)
    if re.search(r"\b\d+(?:\.\d+)?x\b", text) and not request.metrics:
        markers.append("unsourced_multiplier")
    if re.search(r"\b\d+(?:\.\d+)?\s?%", text) and not request.metrics and not request.source_notes:
        markers.append("unsourced_percentage")
    return tuple(dict.fromkeys(markers))


_METRIC_RE = re.compile(
    r"(?P<value>(?:\b\d+(?:\.\d+)?\s?%|\b\d+(?:\.\d+)?x\b|(?:Rs|INR|\$|USD)\s?\d[\d,]*(?:\.\d+)?|\b\d+\s?(?:hours?|days?|weeks?|months?)\b))",
    flags=re.I,
)


def extract_metric_highlights(request: CaseStudyRequest) -> tuple[MetricHighlight, ...]:
    highlights: list[MetricHighlight] = []
    seen: set[str] = set()
    for metric in request.metrics:
        evidence_parts = [part for part in (metric.baseline, metric.after, metric.source) if part]
        evidence = "; ".join(evidence_parts) or "User-provided metric; human should verify before publication."
        key = f"{metric.label}:{metric.value}".lower()
        if key not in seen:
            highlights.append(
                MetricHighlight(
                    label=metric.label,
                    value=metric.value,
                    evidence=evidence,
                    confidence="high" if metric.source else "medium",
                )
            )
            seen.add(key)

    source_blob = clean_text(" ".join([request.results, request.source_notes or ""]))
    for match in _METRIC_RE.finditer(source_blob):
        value = clean_text(match.group("value"))
        key = value.lower()
        if key in seen:
            continue
        start = max(0, match.start() - 70)
        end = min(len(source_blob), match.end() + 90)
        highlights.append(
            MetricHighlight(
                label="Result metric from supplied notes",
                value=value,
                evidence=clean_text(source_blob[start:end]),
                confidence="medium" if request.source_notes else "low",
            )
        )
        seen.add(key)
    return tuple(highlights)


def build_evidence_map(request: CaseStudyRequest) -> EvidenceMap:
    metrics = extract_metric_highlights(request)
    missing: list[str] = []
    if not metrics:
        missing.append("Quantified metrics, baselines, or before/after values.")
    elif any(metric.confidence != "high" for metric in metrics):
        missing.append("Named source or approval trail for one or more metric claims.")
    if not request.source_notes:
        missing.append("Source notes or interview notes for claim verification.")
    if not request.customer_quotes:
        missing.append("Approved customer quote or testimonial.")
    if not request.implementation_notes:
        missing.append("Implementation/process detail.")
    notes = tuple(split_text_items(request.source_notes or ""))
    return EvidenceMap(
        metric_highlights=metrics,
        supplied_quotes=request.customer_quotes,
        evidence_notes=notes,
        missing_evidence=tuple(dict.fromkeys(missing)),
    )


def build_missing_information_warnings(request: CaseStudyRequest, evidence: EvidenceMap) -> tuple[MissingInfoWarning, ...]:
    warnings: list[MissingInfoWarning] = []
    for field_name, value, label in (
        ("challenge", request.challenge, "A clear customer challenge is required."),
        ("solution_summary", request.solution_summary, "A concrete solution summary is required."),
        ("results", request.results, "Outcome notes are required."),
    ):
        if word_count(value) < 5:
            warnings.append(MissingInfoWarning(field=field_name, severity="high", message=label))
    if not request.customer_name and not request.anonymize_customer:
        warnings.append(
            MissingInfoWarning(
                field="customer_name",
                severity="medium",
                message="Customer name is missing; draft will use an anonymized customer label.",
            )
        )
    if not evidence.metric_highlights:
        warnings.append(
            MissingInfoWarning(
                field="metrics",
                severity="medium",
                message="No measurable metrics were supplied; the draft must keep results qualitative.",
            )
        )
    if not request.implementation_notes:
        warnings.append(
            MissingInfoWarning(
                field="implementation_notes",
                severity="medium",
                message="Implementation/process detail is missing or thin.",
            )
        )
    if not request.customer_quotes:
        warnings.append(
            MissingInfoWarning(
                field="customer_quotes",
                severity="low",
                message="No approved customer quote supplied; quote outputs must stay as placeholders.",
            )
        )
    if not request.cta_goal:
        warnings.append(
            MissingInfoWarning(
                field="cta_goal",
                severity="low",
                message="CTA goal missing; default CTA suggestions will be generic review prompts.",
            )
        )
    return tuple(warnings)


def draft_text(draft: CaseStudyDraft | None) -> str:
    if draft is None:
        return ""
    return "\n".join(
        (
            draft.executive_summary,
            draft.customer_background,
            draft.challenge_section,
            draft.solution_section,
            draft.implementation_section,
            draft.results_section,
            draft.cta_section,
            draft.final_markdown_draft,
        )
    )


def build_risk_flags(
    *,
    request: CaseStudyRequest | None,
    draft: CaseStudyDraft | None,
    validation_errors: tuple[str, ...] = (),
) -> tuple[RiskFlag, ...]:
    flags: list[RiskFlag] = []
    if validation_errors or request is None:
        return (
            RiskFlag(
                category="missing_required_context",
                severity="hard_fail",
                message="Request validation failed before a review-ready case study could be generated.",
                evidence_needed="Provide required case study fields.",
            ),
        )

    context = supplied_context_text(request)
    injection = detect_prompt_injection_markers(context)
    if injection:
        flags.append(
            RiskFlag(
                category="prompt_injection",
                severity="high",
                message="Input contains prompt-injection style text and was treated only as data.",
                evidence_needed=", ".join(injection),
            )
        )
    external = detect_external_action_requests(context)
    if external:
        flags.append(
            RiskFlag(
                category="external_action",
                severity="hard_fail",
                message="Input requests publishing, CRM/CMS, analytics, email, or social actions outside v1 scope.",
                evidence_needed=", ".join(external),
            )
        )
    confidentiality = detect_confidentiality_markers(context)
    if request.anonymize_customer or confidentiality:
        flags.append(
            RiskFlag(
                category="confidentiality",
                severity="high",
                message="Customer usage needs anonymization or explicit approval before public use.",
                evidence_needed=", ".join(confidentiality) or "Confirm customer public-use approval.",
            )
        )
    pii = detect_pii_markers(context)
    if pii:
        flags.append(
            RiskFlag(
                category="pii",
                severity="high",
                message="Potential PII found in supplied notes; remove or approve before public use.",
                evidence_needed=", ".join(pii),
            )
        )
    risky_input = detect_high_risk_input_claims(request)
    if risky_input:
        flags.append(
            RiskFlag(
                category="unsupported_claim",
                severity="hard_fail",
                message="Supplied story contains major unsupported or exaggerated claims that require evidence.",
                evidence_needed=", ".join(risky_input),
            )
        )

    text = draft_text(draft)
    invented = detect_unsupported_claim_markers(text, context)
    if invented:
        flags.append(
            RiskFlag(
                category="invented_metric",
                severity="hard_fail",
                message="Draft contains metrics or verified-sounding claims not found in supplied evidence.",
                evidence_needed=", ".join(invented),
            )
        )
    if draft and not request.customer_quotes:
        quote_like = re.findall(r'"[^"]{12,}"', text)
        attributed = [item for item in quote_like if "placeholder" not in item.lower()]
        if attributed:
            flags.append(
                RiskFlag(
                    category="quote_risk",
                    severity="hard_fail",
                    message="Draft appears to contain attributed quote text without a supplied customer quote.",
                    evidence_needed="Provide approved customer quote text or keep placeholders only.",
                )
            )
    if draft and request.customer_quotes:
        supplied_quotes = {quote.lower() for quote in request.customer_quotes}
        for quote in request.customer_quotes:
            if quote.lower() not in text.lower():
                flags.append(
                    RiskFlag(
                        category="quote_risk",
                        severity="medium",
                        message="A supplied customer quote was not included in the draft package.",
                        evidence_needed=quote,
                    )
                )
                break
        if not supplied_quotes:
            pass

    return _dedupe_flags(flags)


def detect_generic_phrases(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    phrases = (
        "unlock value",
        "drive innovation",
        "transform your business",
        "seamless solution",
        "cutting-edge solution",
        "game changer",
        "future-proof",
        "robust solution",
        "in today's fast-paced world",
    )
    return tuple(phrase for phrase in phrases if phrase in lowered)


def detect_generic_content(
    *,
    request: CaseStudyRequest | None,
    draft: CaseStudyDraft | None,
) -> tuple[RiskFlag, ...]:
    flags: list[RiskFlag] = []
    text = draft_text(draft)
    if draft is None or word_count(text) < 220:
        flags.append(
            RiskFlag(
                category="brand_risk",
                severity="hard_fail",
                message="Draft is too thin to be a useful review-ready case study.",
                evidence_needed="Expand core sections with customer context, challenge, solution, implementation, and results.",
            )
        )
    generic = detect_generic_phrases(text)
    if generic:
        flags.append(
            RiskFlag(
                category="brand_risk",
                severity="high",
                message="Generic case study phrasing detected.",
                evidence_needed=", ".join(generic[:6]),
            )
        )
    terms = important_terms(request)
    if request is not None and terms:
        lowered = text.lower()
        hits = sum(1 for term in terms if term in lowered)
        if hits < min(5, max(2, len(terms) // 5)):
            flags.append(
                RiskFlag(
                    category="brand_risk",
                    severity="hard_fail",
                    message="Draft does not use enough supplied customer/problem/solution language.",
                    evidence_needed="Tie sections back to the supplied case study context.",
                )
            )
    if draft is not None:
        sections = [
            draft.executive_summary,
            draft.customer_background,
            draft.challenge_section,
            draft.solution_section,
            draft.implementation_section,
            draft.results_section,
        ]
        normalized = [re.sub(r"[^a-z0-9]+", " ", section.lower()).strip() for section in sections]
        repeated = [section for section, count in Counter(normalized).items() if section and count > 1]
        if repeated:
            flags.append(
                RiskFlag(
                    category="brand_risk",
                    severity="hard_fail",
                    message="Repeated section wording suggests placeholder content.",
                    evidence_needed="Rewrite repeated sections with distinct purpose and detail.",
                )
            )
    return _dedupe_flags(flags)


def _dedupe_flags(flags: list[RiskFlag]) -> tuple[RiskFlag, ...]:
    seen: set[str] = set()
    out: list[RiskFlag] = []
    for flag in flags:
        key = f"{flag.category}:{flag.severity}:{flag.message}:{flag.evidence_needed or ''}"
        if key not in seen:
            out.append(flag)
            seen.add(key)
    return tuple(out)
