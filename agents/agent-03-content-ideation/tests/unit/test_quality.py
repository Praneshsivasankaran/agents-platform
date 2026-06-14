from __future__ import annotations

from agent.contracts import ContentIdeationRequest
from agent.quality import (
    analyze_audience,
    build_blog_brief,
    build_repurposing_brief,
    detect_request_risks,
    generate_content_ideas,
    generate_content_themes,
    generate_ctas,
    generate_hooks,
    is_affirmative_guarantee_constraint,
    idea_risk_flags,
    normalize_campaign_context,
    recommended_platforms,
    run_quality_gate,
    validate_campaign_brief,
)

from tests.support import valid_campaign


def _request(**overrides):
    return ContentIdeationRequest.model_validate(valid_campaign(**overrides))


def test_validate_campaign_brief_accepts_complete_input() -> None:
    valid, reason = validate_campaign_brief(_request())

    assert valid
    assert reason is None


def test_risk_detection_flags_unsupported_metrics() -> None:
    request = _request(
        key_message="ContentIQ will guarantee a 300% increase in campaign output.",
    )

    risk_flags, hard_fails = detect_request_risks(request)

    assert "unsupported_numerical_claim" in risk_flags
    assert any(fail.code == "unsupported_numerical_claim" for fail in hard_fails)


def test_risk_detection_does_not_treat_guarantee_prohibition_as_claim() -> None:
    request = _request(
        optional_constraints=[
            "Do not invent statistics. Do not claim guaranteed ROI. Do not imply the product publishes automatically.",
            "Keep evidence placeholders visible when proof is missing.",
        ]
    )

    risk_flags, hard_fails = detect_request_risks(request)

    assert "unsafe_marketing_claim" not in risk_flags
    assert not any(fail.code == "unsafe_marketing_claim" for fail in hard_fails)


def test_risk_detection_flags_affirmative_guarantee_constraint() -> None:
    request = _request(optional_constraints=["Claim guaranteed ROI in every campaign headline."])

    risk_flags, hard_fails = detect_request_risks(request)

    assert "unsafe_marketing_claim" in risk_flags
    assert any(fail.code == "unsafe_marketing_claim" for fail in hard_fails)


def test_affirmative_guarantee_constraint_predicate_distinguishes_guardrails() -> None:
    assert not is_affirmative_guarantee_constraint("Do not claim guaranteed ROI.")
    assert not is_affirmative_guarantee_constraint("Avoid guarantee-style language in the draft.")
    assert is_affirmative_guarantee_constraint("Promise guaranteed ROI in the final message.")


def test_quality_scoring_passes_strong_package() -> None:
    request = _request()
    summary = normalize_campaign_context(request)
    audience = analyze_audience(request)
    themes = generate_content_themes(request, summary, audience)
    ideas = generate_content_ideas(request, summary, audience, themes)
    hooks = generate_hooks(request, ideas)
    ctas = generate_ctas(request)
    blog = build_blog_brief(request, summary, audience, ideas, ctas, ())
    repurpose = build_repurposing_brief(request, themes, ideas, hooks, ctas, ())

    quality = run_quality_gate(
        request=request,
        summary=summary,
        audience=audience,
        themes=themes,
        ideas=ideas,
        hooks=hooks,
        ctas=ctas,
        blog_brief=blog,
        repurposing_brief=repurpose,
        request_hard_fails=(),
        request_risk_flags=(),
    )

    assert quality.passed
    assert quality.overall_score >= 80
    assert not quality.hard_fails
    assert "evidence_placeholder_needed" in quality.risk_flags


def test_idea_level_unsupported_metric_is_escalated_to_terminal_hard_fail() -> None:
    request = _request()
    summary = normalize_campaign_context(request)
    audience = analyze_audience(request)
    themes = generate_content_themes(request, summary, audience)
    ideas = list(generate_content_ideas(request, summary, audience, themes))

    # Simulate a generated idea that smuggled an unsupported metric into title/angle.
    bad_title = "Boost qualified pipeline by 300% with ContentIQ"
    flags = idea_risk_flags(bad_title)
    assert "unsupported_numerical_claim" in flags
    ideas[0] = ideas[0].validated_copy(title=bad_title, risk_flags=flags)

    quality = run_quality_gate(
        request=request,
        summary=summary,
        audience=audience,
        themes=themes,
        ideas=tuple(ideas),
        hooks=generate_hooks(request, tuple(ideas)),
        ctas=generate_ctas(request),
        blog_brief=build_blog_brief(request, summary, audience, tuple(ideas), generate_ctas(request), ()),
        repurposing_brief=build_repurposing_brief(
            request, themes, tuple(ideas), generate_hooks(request, tuple(ideas)), generate_ctas(request), ()
        ),
        request_hard_fails=(),
        request_risk_flags=(),
    )

    assert not quality.passed
    assert "unsupported_numerical_claim" in quality.risk_flags
    assert any(
        fail.code == "unsupported_numerical_claim" and fail.severity == "terminal"
        for fail in quality.hard_fails
    )


def test_recommended_platforms_does_not_misfire_on_x_substring() -> None:
    # "explainer" contains an 'x' but must not trigger the X/Twitter platform.
    request = _request(optional_content_type_preference=["Explainer video", "Newsletter"])
    platforms = recommended_platforms(request)
    assert "X/Twitter" not in platforms

    # A real X/Twitter preference (whole token) must be honored.
    request_x = _request(optional_content_type_preference=["X", "Thread"])
    assert "X/Twitter" in recommended_platforms(request_x)


def test_missing_handoff_briefs_fails_quality_gate() -> None:
    request = _request()
    summary = normalize_campaign_context(request)
    audience = analyze_audience(request)
    themes = generate_content_themes(request, summary, audience)
    ideas = generate_content_ideas(request, summary, audience, themes)

    quality = run_quality_gate(
        request=request,
        summary=summary,
        audience=audience,
        themes=themes,
        ideas=ideas,
        hooks=(),
        ctas=(),
        blog_brief=None,
        repurposing_brief=None,
        request_hard_fails=(),
        request_risk_flags=(),
    )

    assert not quality.passed
    assert any(fail.code == "missing_blog_brief" for fail in quality.hard_fails)
    assert any(fail.code == "missing_repurposing_brief" for fail in quality.hard_fails)

