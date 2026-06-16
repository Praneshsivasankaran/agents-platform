from __future__ import annotations

from agent.schemas import CaseStudyRequest
from agent.scoring import determine_status, score_case_study_quality
from agent.tools import build_evidence_map, build_missing_information_warnings, build_risk_flags
from agent.workflow import _draft_fallback, _normalize_fallback, _plan_fallback, _quote_cta_fallback


def sample_request(**overrides):
    data = {
        "customer_name": "Acme Bank",
        "industry": "Financial services",
        "target_audience": "CIOs and operations leaders",
        "challenge": "Manual onboarding reviews delayed enterprise account launches and scattered approval evidence.",
        "solution_summary": "A workflow automation program centralized onboarding tasks, approval routing, and evidence capture.",
        "product_or_service": "LaunchFlow onboarding automation",
        "implementation_notes": "The rollout started with one business unit, mapped approval steps, and trained operations managers.",
        "results": "Enterprise account launch time decreased and operations teams gained a clearer audit trail.",
        "metrics": [
            {
                "label": "Launch cycle reduction",
                "value": "32%",
                "baseline": "Average launch cycle before rollout",
                "after": "Average launch cycle after rollout",
                "source": "Internal implementation report",
            }
        ],
        "customer_quotes": ["The workflow gave our operations leads one place to manage launch evidence."],
        "source_notes": "Internal implementation report and customer interview notes.",
        "brand_voice": "clear executive practical",
        "tone": "executive",
        "cta_goal": "Book an onboarding workflow assessment",
    }
    data.update(overrides)
    return CaseStudyRequest.model_validate(data)


def _fallback_package_parts(request: CaseStudyRequest):
    normalized = _normalize_fallback(request)
    evidence = build_evidence_map(request)
    plan = _plan_fallback(request, normalized, evidence)
    draft = _draft_fallback(request, normalized, evidence, plan)
    warnings = build_missing_information_warnings(request, evidence)
    risks = build_risk_flags(request=request, draft=draft)
    return evidence, draft, warnings, risks


def test_metric_extraction_uses_supplied_metrics_without_invention() -> None:
    request = sample_request()
    evidence = build_evidence_map(request)

    assert evidence.metric_highlights
    assert evidence.metric_highlights[0].value == "32%"
    assert evidence.metric_highlights[0].confidence == "high"


def test_missing_metrics_warns_but_still_scores_usable_draft() -> None:
    request = sample_request(metrics=(), results="Teams reported better launch consistency and clearer ownership.")
    evidence, draft, warnings, risks = _fallback_package_parts(request)
    quality = score_case_study_quality(
        request=request,
        draft=draft,
        evidence_map=evidence,
        missing_warnings=warnings,
        risk_flags=risks,
    )
    status = determine_status(quality=quality, risk_flags=risks, missing_warnings=warnings)

    assert any(warning.field == "metrics" for warning in warnings)
    assert draft.final_markdown_draft
    assert quality.overall_score >= 65
    assert status == "revise"


def test_unsupported_claim_input_becomes_hard_fail_risk() -> None:
    request = sample_request(
        metrics=(),
        source_notes="",
        results="The solution guaranteed 10x ROI with no evidence and was legally approved.",
    )
    _, draft, _, risks = _fallback_package_parts(request)

    assert draft.final_markdown_draft
    assert any(flag.category == "unsupported_claim" and flag.severity == "hard_fail" for flag in risks)


def test_no_supplied_quote_creates_placeholder_not_fake_quote() -> None:
    request = sample_request(customer_quotes=())
    normalized = _normalize_fallback(request)
    evidence = build_evidence_map(request)
    quote_package = _quote_cta_fallback(request, normalized, evidence)

    assert quote_package.customer_quote_placeholders
    assert not any("Acme Bank said" in quote for quote in quote_package.pull_quotes)


def test_confidential_customer_adds_high_risk_flag() -> None:
    request = sample_request(anonymize_customer=True, source_notes="Customer is confidential under NDA.")
    _, _, _, risks = _fallback_package_parts(request)

    assert any(flag.category == "confidentiality" and flag.severity == "high" for flag in risks)
