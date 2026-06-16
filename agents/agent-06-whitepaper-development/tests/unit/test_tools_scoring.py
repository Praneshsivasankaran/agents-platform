from __future__ import annotations

from agent.schemas import Agent06Request
from agent.tools import (
    build_evidence_map,
    detect_forbidden_claim_markers,
    detect_generic_content,
    extract_claims_from_draft,
)
from agent.workflow import _draft_fallback, _angle_fallback, _normalize_fallback, _outline_fallback


def sample_request(**overrides):
    data = {
        "topic": "AI governance operating model",
        "company_context": "Acme PolicyOS helps compliance teams manage AI policy reviews.",
        "target_audience": "CIOs and compliance leaders",
        "industry": "Financial services",
        "problem": "AI initiatives are slowed by manual policy review and unclear ownership.",
        "solution": "A workflow platform for AI policy intake, review routing, evidence capture, and approval tracking.",
        "tone": "executive, precise, and practical",
        "target_depth": "detailed B2B whitepaper",
        "cta": "Book a governance readiness workshop",
        "proof_points": ["Internal pilot centralized review evidence across three policy teams"],
        "differentiators": ["role-based review routing", "evidence capture"],
    }
    data.update(overrides)
    return Agent06Request.model_validate(data)


def test_forbidden_claim_detection_flags_unsupplied_statistics() -> None:
    markers = detect_forbidden_claim_markers("This improves review speed by 42%.", "No numbers here.")

    assert "percentage_claim" in markers


def test_evidence_map_marks_missing_evidence() -> None:
    evidence = build_evidence_map(sample_request(proof_points=[]))

    assert evidence.missing_evidence
    assert not evidence.evidence_items


def test_fallback_draft_is_specific_enough_to_avoid_generic_hard_fail() -> None:
    request = sample_request()
    normalized = _normalize_fallback(request)
    angle = _angle_fallback(request, normalized)
    evidence = build_evidence_map(request)
    outline = _outline_fallback(request, angle, evidence)
    draft = _draft_fallback(request, normalized, angle, evidence, outline)

    report = detect_generic_content(request=request, draft=draft)

    assert report.hard_fail is False
    assert request.solution.split()[0].lower() in draft.proposed_solution.lower()


def test_claim_extraction_assigns_evidence_status() -> None:
    request = sample_request()
    normalized = _normalize_fallback(request)
    angle = _angle_fallback(request, normalized)
    evidence = build_evidence_map(request)
    outline = _outline_fallback(request, angle, evidence)
    draft = _draft_fallback(request, normalized, angle, evidence, outline)

    claims, unsupported, forbidden = extract_claims_from_draft(draft, evidence, request.model_dump_json())

    assert claims
    assert all(claim.evidence_status for claim in claims)
    assert not forbidden
    assert isinstance(unsupported, tuple)
