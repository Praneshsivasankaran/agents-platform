"""Deterministic local helper tools for Agent 06.

These helpers do not call networks, cloud SDKs, search engines, research APIs,
analytics tools, CRMs, CMSs, or email systems.
"""
from __future__ import annotations

import re
from collections import Counter

from .schemas import (
    Agent06Request,
    ClaimEvidence,
    EvidenceItem,
    EvidenceMap,
    EvidenceStatus,
    GenericContentFlag,
    GenericContentReport,
    RiskSeverity,
    WhitepaperDraft,
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


def important_terms(request: Agent06Request | None) -> tuple[str, ...]:
    if request is None:
        return ()
    raw_terms = [
        request.topic,
        request.target_audience,
        request.industry,
        request.problem,
        request.solution,
    ]
    raw_terms.extend(request.differentiators)
    terms: list[str] = []
    seen: set[str] = set()
    for value in raw_terms:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", value.lower()):
            if token not in seen and token not in {"with", "from", "that", "this", "into", "their", "your"}:
                terms.append(token)
                seen.add(token)
    return tuple(terms[:30])


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
        "send email",
        "write to cms",
        "update wordpress",
        "push to crm",
        "update crm",
        "send marketing email",
        "post to linkedin",
        "schedule campaign",
        "call analytics",
    )
    return tuple(marker for marker in markers if marker in lowered)


def detect_forbidden_claim_markers(text: str, supplied_context: str = "") -> tuple[str, ...]:
    lowered = str(text or "").lower()
    supplied = str(supplied_context or "").lower()
    markers: list[str] = []
    for pattern_name, pattern in (
        ("percentage_claim", r"\b\d+(?:\.\d+)?\s?%"),
        ("multiplier_claim", r"\b\d+(?:\.\d+)?x\b"),
        ("money_claim", r"(?:rs|inr|\$|usd)\s?\d"),
        ("year_or_date_claim", r"\b20\d{2}\b"),
    ):
        if re.search(pattern, lowered) and not re.search(pattern, supplied):
            markers.append(pattern_name)
    for phrase in (
        "according to gartner",
        "according to forrester",
        "according to idc",
        "according to mckinsey",
        "research shows",
        "studies show",
        "market leader",
        "industry-leading",
        "best-in-class",
        "guaranteed",
        "proven to",
        "case study shows",
        "fortune 500",
    ):
        if phrase in lowered and phrase not in supplied:
            markers.append(phrase)
    return tuple(dict.fromkeys(markers))


def detect_source_verification_claims(text: str, supplied_context: str = "") -> tuple[str, ...]:
    lowered = str(text or "").lower()
    supplied = str(supplied_context or "").lower()
    markers = (
        "verified source",
        "externally verified",
        "independent research confirms",
        "published data confirms",
        "cited source",
    )
    return tuple(marker for marker in markers if marker in lowered and marker not in supplied)


def detect_generic_phrases(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    phrases = (
        "unlock value",
        "drive innovation",
        "transform your business",
        "seamless solution",
        "cutting-edge solution",
        "game changer",
        "leverage synergies",
        "future-proof",
        "robust solution",
        "empower organizations",
        "in today's fast-paced world",
        "ever-evolving landscape",
    )
    return tuple(phrase for phrase in phrases if phrase in lowered)


def supplied_context_text(request: Agent06Request | None) -> str:
    if request is None:
        return ""
    parts = [
        request.topic,
        request.company_context,
        request.target_audience,
        request.industry,
        request.problem,
        request.solution,
        request.tone,
        request.target_depth,
        request.cta,
        " ".join(request.proof_points),
        " ".join(request.source_notes),
        " ".join(request.differentiators),
        " ".join(request.objections),
        " ".join(request.compliance_constraints),
        " ".join(request.excluded_claims),
    ]
    return clean_text(" ".join(parts))


def build_evidence_map(request: Agent06Request) -> EvidenceMap:
    items: list[EvidenceItem] = []
    for index, proof in enumerate(request.proof_points, start=1):
        items.append(
            EvidenceItem(
                evidence_id=f"proof-{index:03d}",
                claim_area="supplied proof point",
                evidence_text=proof,
                status="supported_by_user_evidence",
                source_note="User-provided proof point; human should verify before publication.",
            )
        )
    for index, note in enumerate(request.source_notes, start=1):
        items.append(
            EvidenceItem(
                evidence_id=f"source-{index:03d}",
                claim_area="source note",
                evidence_text=note,
                status="user_provided_unverified",
                source_note="User-provided source note; not independently verified by Agent 06.",
            )
        )
    missing: list[str] = []
    if not request.proof_points:
        missing.append("Quantified proof points or metrics for the solution's impact.")
    if not request.source_notes:
        missing.append("Approved source notes or internal references for factual claims.")
    if not request.differentiators:
        missing.append("Specific differentiators that separate the solution from alternatives.")
    if not request.objections:
        missing.append("Known buyer objections or adoption blockers to address.")
    return EvidenceMap(
        evidence_items=tuple(items),
        missing_evidence=tuple(missing),
        missing_inputs=tuple(missing),
    )


def _claim_status_for(text: str, evidence_map: EvidenceMap) -> tuple[EvidenceStatus, str]:
    lowered = text.lower()
    for item in evidence_map.evidence_items:
        evidence_words = {
            token
            for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{4,}", item.evidence_text.lower())
            if token not in {"about", "their", "there", "which", "would", "could", "should"}
        }
        if evidence_words and sum(1 for token in evidence_words if token in lowered) >= 2:
            return item.status, item.evidence_id
    if re.search(r"\b\d+(?:\.\d+)?\s?%|\b\d+(?:\.\d+)?x\b", lowered):
        return "needs_evidence", ""
    return "general_reasoning", ""


def extract_claims_from_draft(
    draft: WhitepaperDraft | None,
    evidence_map: EvidenceMap | None,
    supplied_context: str = "",
) -> tuple[tuple[ClaimEvidence, ...], tuple[str, ...], tuple[str, ...]]:
    if draft is None:
        return (), (), ()
    evidence_map = evidence_map or EvidenceMap()
    source_texts = (
        draft.executive_summary,
        draft.problem_statement,
        draft.proposed_solution,
        draft.benefits,
        draft.use_cases,
        draft.implementation_approach,
        draft.risks_and_challenges,
    )
    sentences: list[str] = []
    for text in source_texts:
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            cleaned = clean_text(sentence)
            if word_count(cleaned) >= 6:
                sentences.append(cleaned)
    selected = tuple(dict.fromkeys(sentences[:10]))
    claims: list[ClaimEvidence] = []
    unsupported: list[str] = []
    forbidden: list[str] = []
    for sentence in selected:
        markers = detect_forbidden_claim_markers(sentence, supplied_context)
        status, reference = _claim_status_for(sentence, evidence_map)
        if markers and not reference:
            status = "unsupported"
            forbidden.append(sentence)
        if status in {"unsupported", "needs_evidence"}:
            unsupported.append(sentence)
        claims.append(
            ClaimEvidence(
                claim=sentence,
                evidence_status=status,
                evidence_reference=reference,
                review_note=(
                    "Human verification required before publication."
                    if status in {"needs_evidence", "unsupported", "user_provided_unverified"}
                    else ""
                ),
            )
        )
    if not claims:
        claims.append(
            ClaimEvidence(
                claim="No substantive key claims could be extracted from the draft.",
                evidence_status="unsupported",
                review_note="Add concrete, evidence-aware claims before review.",
            )
        )
        unsupported.append(claims[0].claim)
    return tuple(claims), tuple(dict.fromkeys(unsupported)), tuple(dict.fromkeys(forbidden))


def draft_text(draft: WhitepaperDraft | None) -> str:
    if draft is None:
        return ""
    return "\n".join(
        (
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
            "\n".join(section.body for section in draft.sections),
        )
    )


def detect_generic_content(
    *,
    request: Agent06Request | None,
    draft: WhitepaperDraft | None,
) -> GenericContentReport:
    flags: list[GenericContentFlag] = []
    text = draft_text(draft)
    if not draft or word_count(text) < 220:
        flags.append(
            GenericContentFlag(
                location="draft",
                message="Draft is too thin to be a useful whitepaper development package.",
                severity="hard_fail",
                recommended_fix="Add deeper section content, examples, objections, implementation detail, and evidence notes.",
            )
        )
    phrases = detect_generic_phrases(text)
    if phrases:
        flags.append(
            GenericContentFlag(
                location="draft",
                message="Generic whitepaper phrasing detected: " + ", ".join(phrases[:6]),
                severity="hard_fail",
                recommended_fix="Replace broad filler with company/product-specific mechanisms and buyer-relevant details.",
            )
        )
    terms = important_terms(request)
    if request is not None and terms:
        lowered = text.lower()
        hit_count = sum(1 for term in terms if term in lowered)
        if hit_count < min(5, max(2, len(terms) // 5)):
            flags.append(
                GenericContentFlag(
                    location="draft",
                    message="Draft does not use enough supplied company/product/topic-specific language.",
                    severity="hard_fail",
                    recommended_fix="Tie every section back to the supplied topic, product context, problem, solution, and audience.",
                )
            )
    section_texts = [
        draft.executive_summary if draft else "",
        draft.problem_statement if draft else "",
        draft.proposed_solution if draft else "",
        draft.benefits if draft else "",
        draft.implementation_approach if draft else "",
    ]
    too_short = sum(1 for item in section_texts if word_count(item) < 30)
    if too_short >= 2:
        flags.append(
            GenericContentFlag(
                location="sections",
                message="Multiple required sections are too short to be review-ready.",
                severity="hard_fail",
                recommended_fix="Expand weak sections with specific context, useful explanation, and evidence needs.",
            )
        )
    normalized_sections = [
        re.sub(r"[^a-z0-9]+", " ", item.lower()).strip()
        for item in section_texts
        if item
    ]
    repeated = [text for text, count in Counter(normalized_sections).items() if count > 1]
    if repeated:
        flags.append(
            GenericContentFlag(
                location="sections",
                message="Repeated section wording suggests placeholder content.",
                severity="hard_fail",
                recommended_fix="Rewrite repeated sections with distinct purpose and detail.",
            )
        )
    return GenericContentReport(flags=tuple(flags), hard_fail=any(flag.severity == "hard_fail" for flag in flags))


def evidence_status_counts(claims: tuple[ClaimEvidence, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in claims:
        counts[claim.evidence_status] = counts.get(claim.evidence_status, 0) + 1
    return counts
