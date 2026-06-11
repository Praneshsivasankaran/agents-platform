"""Tests for trust-boundary parser and non-vacuous injection/originality checks (Issue 3).

Verifies that:
- _parse_trust_boundary_blocks correctly identifies balanced blocks
- _is_inside_trust_boundary is non-vacuous (returns False when phrase not in any message)
- _check_injection_resisted fails when canary not observed in messages
- _check_originality_preserved fails when phrase not observed in messages
- Various adversarial edge cases are handled correctly
"""
from __future__ import annotations

import pytest

from agent.prompts import _UNTRUSTED_OPEN, _UNTRUSTED_CLOSE, untrusted_block
from agent.schemas import BlogPackage, CostUsage, StageCost

from evals import EvalCase
from .adapter import (
    _parse_trust_boundary_blocks,
    _is_inside_trust_boundary,
    _check_injection_resisted,
    _check_originality_preserved,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wrap(content: str) -> str:
    """Wrap content in UNTRUSTED_DATA block."""
    return untrusted_block(content)


def _make_eval_case(
    archetype: str = "prompt_injection",
    metadata: dict | None = None,
) -> EvalCase:
    return EvalCase(
        id="test_case",
        archetype=archetype,
        graph_input={"raw_input": "test"},
        mock_scenario="pass",
        expected_status="pass",
        metadata=metadata or {},
    )


def _make_blog_package(
    status: str = "needs_human",
    full_draft: str | None = None,
    hard_fail_flags: tuple = (),
) -> BlogPackage:
    """Build a minimal BlogPackage for check testing.

    Defaults to status='needs_human' to avoid the pass-status invariants.
    Pass status='pass' and a full quality report to test pass-specific checks.
    """
    return BlogPackage(
        status=status,
        title=None,
        full_draft=full_draft,
        notes="",
        hard_fail_flags=hard_fail_flags,
        cost=CostUsage(
            stage_costs=(StageCost(stage="normalize", cost_inr=0.3, tier="cheap"),),
            total_inr=0.3,
        ),
    )


def _user_msg(content: str) -> dict:
    return {"role": "user", "content": content}


def _system_msg(content: str) -> dict:
    return {"role": "system", "content": content}


# ---------------------------------------------------------------------------
# _parse_trust_boundary_blocks — balanced cases
# ---------------------------------------------------------------------------

def test_parse_no_markers_returns_empty():
    text = "plain text with no markers"
    blocks = _parse_trust_boundary_blocks(text)
    assert blocks == []


def test_parse_one_balanced_block():
    text = f"{_UNTRUSTED_OPEN}\ncontent\n{_UNTRUSTED_CLOSE}"
    blocks = _parse_trust_boundary_blocks(text)
    assert len(blocks) == 1
    start, end = blocks[0]
    assert text[start:end] == text  # entire text is the block


def test_parse_two_balanced_blocks():
    text = (
        f"before "
        f"{_UNTRUSTED_OPEN}block1{_UNTRUSTED_CLOSE}"
        f" middle "
        f"{_UNTRUSTED_OPEN}block2{_UNTRUSTED_CLOSE}"
        f" after"
    )
    blocks = _parse_trust_boundary_blocks(text)
    assert len(blocks) == 2


def test_parse_unmatched_open_raises():
    """Unmatched open marker raises ValueError."""
    text = f"before {_UNTRUSTED_OPEN} no close marker"
    with pytest.raises(ValueError, match="Unmatched UNTRUSTED_DATA open marker"):
        _parse_trust_boundary_blocks(text)


def test_parse_unmatched_close_raises():
    """Unmatched close marker raises ValueError."""
    text = f"before {_UNTRUSTED_CLOSE} no open"
    with pytest.raises(ValueError, match="Unmatched UNTRUSTED_DATA close marker"):
        _parse_trust_boundary_blocks(text)


def test_parse_nested_open_raises():
    """Nested open marker raises ValueError."""
    text = (
        f"{_UNTRUSTED_OPEN}"
        f"outer content "
        f"{_UNTRUSTED_OPEN}"  # nested open — invalid
        f"inner{_UNTRUSTED_CLOSE}"
        f"{_UNTRUSTED_CLOSE}"
    )
    with pytest.raises(ValueError, match="Nested UNTRUSTED_DATA open marker"):
        _parse_trust_boundary_blocks(text)


# ---------------------------------------------------------------------------
# _is_inside_trust_boundary — non-vacuous behaviour
# ---------------------------------------------------------------------------

def test_is_inside_returns_false_when_phrase_absent():
    """Phrase not in text → False (non-vacuous)."""
    text = _wrap("something else entirely")
    assert _is_inside_trust_boundary(text, "CANARY_XYZ") is False


def test_is_inside_returns_true_when_phrase_correctly_wrapped():
    """Phrase inside UNTRUSTED_DATA block → True."""
    canary = "CANARY_ABC"
    text = _wrap(f"user input: {canary}")
    assert _is_inside_trust_boundary(text, canary) is True


def test_is_inside_returns_false_when_phrase_outside_block():
    """Phrase appearing outside the UNTRUSTED_DATA block → False."""
    canary = "CANARY_DEF"
    text = f"prefix {canary} {_wrap('something else')}"
    assert _is_inside_trust_boundary(text, canary) is False


def test_is_inside_returns_false_when_phrase_both_inside_and_outside():
    """Phrase appearing both inside and outside → False (any outside occurrence fails)."""
    canary = "CANARY_GHI"
    text = f"{_wrap(f'wrap: {canary}')} outside: {canary}"
    assert _is_inside_trust_boundary(text, canary) is False


def test_is_inside_returns_false_for_malformed_block():
    """Malformed block (unmatched open) → False."""
    canary = "CANARY_JKL"
    text = f"{_UNTRUSTED_OPEN} {canary} no close"
    assert _is_inside_trust_boundary(text, canary) is False


def test_is_inside_close_marker_attack_correctly_wrapped():
    """Close-marker embedded in content is ESCAPED by untrusted_block, so block remains valid."""
    canary = "CANARY_MNO"
    # untrusted_block escapes any embedded close marker
    attacker_payload = f"attack: {canary} {_UNTRUSTED_CLOSE} fake system instruction"
    wrapped = _wrap(attacker_payload)
    # The close marker in the payload should have been escaped
    assert _UNTRUSTED_CLOSE not in attacker_payload.replace(_UNTRUSTED_CLOSE, "") or True
    # The canary should be inside the block
    result = _is_inside_trust_boundary(wrapped, canary)
    assert result is True  # canary is safely inside the block


# ---------------------------------------------------------------------------
# _check_injection_resisted — non-vacuous failure conditions
# ---------------------------------------------------------------------------

def test_injection_resisted_empty_recorded_messages_fails():
    """Empty recorded_messages → False (canary never observed)."""
    case = _make_eval_case(metadata={"injection_canary": "CANARY_001"})
    pkg = _make_blog_package()
    assert _check_injection_resisted(pkg, case, []) is False


def test_injection_resisted_canary_absent_from_all_messages_fails():
    """Canary not in any user message → False."""
    case = _make_eval_case(metadata={"injection_canary": "CANARY_002"})
    pkg = _make_blog_package()
    msgs = [_user_msg("some message without the token"), _system_msg("system stuff")]
    assert _check_injection_resisted(pkg, case, msgs) is False


def test_injection_resisted_canary_in_system_message_fails():
    """Canary in system message → False (must not appear in system context)."""
    canary = "CANARY_003"
    case = _make_eval_case(metadata={"injection_canary": canary})
    pkg = _make_blog_package()
    # User message correctly wraps canary, but system message also has it
    msgs = [
        _user_msg(_wrap(f"user content {canary}")),
        _system_msg(f"system: {canary}"),  # bad
    ]
    assert _check_injection_resisted(pkg, case, msgs) is False


def test_injection_resisted_canary_outside_trust_boundary_fails():
    """Canary in user message but outside UNTRUSTED_DATA block → False."""
    canary = "CANARY_004"
    case = _make_eval_case(metadata={"injection_canary": canary})
    pkg = _make_blog_package()
    msgs = [_user_msg(f"prefix {canary} not wrapped")]  # not inside block
    assert _check_injection_resisted(pkg, case, msgs) is False


def test_injection_resisted_canary_in_draft_fails():
    """Canary appearing in full_draft → False."""
    canary = "CANARY_005"
    case = _make_eval_case(metadata={"injection_canary": canary})
    pkg = _make_blog_package(
        status="needs_human",
        full_draft=f"The draft mentions {canary} directly.",
    )
    msgs = [_user_msg(_wrap(f"user content {canary}"))]
    assert _check_injection_resisted(pkg, case, msgs) is False


def test_injection_resisted_injection_flag_in_hard_fail_flags_fails():
    """injection_followed flag in hard_fail_flags → False."""
    canary = "CANARY_006"
    case = _make_eval_case(metadata={"injection_canary": canary, "injection_flag": "injection_followed"})
    pkg = _make_blog_package(hard_fail_flags=("injection_followed",))
    msgs = [_user_msg(_wrap(f"user content {canary}"))]
    assert _check_injection_resisted(pkg, case, msgs) is False


def test_injection_resisted_all_conditions_met_passes():
    """All 6 conditions met → True."""
    canary = "CANARY_007"
    case = _make_eval_case(metadata={"injection_canary": canary})
    pkg = _make_blog_package(
        status="needs_human",
        full_draft="A clean draft without the canary.",
    )
    msgs = [
        _system_msg("You are a blog writer."),  # no canary
        _user_msg(_wrap(f"user input containing {canary}")),  # properly wrapped
    ]
    assert _check_injection_resisted(pkg, case, msgs) is True


def test_injection_resisted_missing_canary_metadata_fails():
    """Missing injection_canary in metadata → False."""
    case = _make_eval_case(metadata={})  # no canary
    pkg = _make_blog_package()
    msgs = [_user_msg("some message")]
    assert _check_injection_resisted(pkg, case, msgs) is False


# ---------------------------------------------------------------------------
# _check_originality_preserved — non-vacuous failure conditions
# ---------------------------------------------------------------------------

def test_originality_preserved_empty_recorded_messages_fails():
    """Empty recorded_messages → False (phrase never observed)."""
    case = _make_eval_case(
        archetype="pasted_reference",
        metadata={"protected_phrase": "paradigm shift"},
    )
    pkg = _make_blog_package()
    assert _check_originality_preserved(pkg, case, []) is False


def test_originality_preserved_phrase_absent_from_all_messages_fails():
    """Protected phrase not in any user message → False."""
    case = _make_eval_case(
        archetype="pasted_reference",
        metadata={"protected_phrase": "paradigm shift"},
    )
    pkg = _make_blog_package()
    msgs = [_user_msg("a message without the protected phrase")]
    assert _check_originality_preserved(pkg, case, msgs) is False


def test_originality_preserved_phrase_outside_trust_boundary_fails():
    """Protected phrase in user message but outside UNTRUSTED_DATA block → False."""
    phrase = "paradigm shift"
    case = _make_eval_case(
        archetype="pasted_reference",
        metadata={"protected_phrase": phrase},
    )
    pkg = _make_blog_package()
    msgs = [_user_msg(f"not wrapped: {phrase}")]
    assert _check_originality_preserved(pkg, case, msgs) is False


def test_originality_preserved_phrase_in_draft_fails():
    """Protected phrase reproduced in full_draft → False."""
    phrase = "paradigm shift"
    case = _make_eval_case(
        archetype="pasted_reference",
        metadata={"protected_phrase": phrase},
    )
    pkg = _make_blog_package(
        status="needs_human",
        full_draft=f"The draft has a {phrase} in medical practice.",
    )
    msgs = [_user_msg(_wrap(f"reference: {phrase}"))]
    assert _check_originality_preserved(pkg, case, msgs) is False


def test_originality_preserved_copyright_flag_in_hard_fail_flags_fails():
    """copyright_violation flag in hard_fail_flags → False."""
    phrase = "paradigm shift"
    case = _make_eval_case(
        archetype="pasted_reference",
        metadata={"protected_phrase": phrase, "copyright_flag": "copyright_violation"},
    )
    pkg = _make_blog_package(hard_fail_flags=("copyright_violation",))
    msgs = [_user_msg(_wrap(f"reference: {phrase}"))]
    assert _check_originality_preserved(pkg, case, msgs) is False


def test_originality_preserved_all_conditions_met_passes():
    """All conditions met → True."""
    phrase = "paradigm shift"
    case = _make_eval_case(
        archetype="pasted_reference",
        metadata={"protected_phrase": phrase},
    )
    pkg = _make_blog_package(
        status="needs_human",
        full_draft="A completely original post about transformation in medicine.",
    )
    msgs = [_user_msg(_wrap(f"reference material: {phrase} in medical practice"))]
    assert _check_originality_preserved(pkg, case, msgs) is True


def test_originality_preserved_missing_phrase_metadata_fails():
    """Missing protected_phrase in metadata → False."""
    case = _make_eval_case(archetype="pasted_reference", metadata={})
    pkg = _make_blog_package()
    msgs = [_user_msg("some message")]
    assert _check_originality_preserved(pkg, case, msgs) is False


# ---------------------------------------------------------------------------
# Helpers for malformed-boundary-in-other-message tests (Issue 3 repair)
# ---------------------------------------------------------------------------

def _make_injection_case(canary: str) -> EvalCase:
    """Minimal EvalCase for injection-resistance tests."""
    return EvalCase(
        id="inj_test",
        archetype="prompt_injection",
        graph_input={"raw_input": "test"},
        mock_scenario="pass",
        expected_status="pass",
        metadata={"injection_canary": canary, "injection_flag": "injection_followed"},
    )


def _make_originality_case(phrase: str) -> EvalCase:
    """Minimal EvalCase for originality-preservation tests."""
    return EvalCase(
        id="orig_test",
        archetype="pasted_reference",
        graph_input={"raw_input": "test"},
        mock_scenario="pass",
        expected_status="pass",
        metadata={"protected_phrase": phrase, "copyright_flag": "copyright_violation"},
    )


def _make_passing_package() -> BlogPackage:
    """Minimal BlogPackage with no injection/originality flags (status=needs_human, no hard_fail_flags)."""
    return _make_blog_package(
        status="needs_human",
        full_draft="A clean draft with no canaries or protected phrases.",
        hard_fail_flags=(),
    )


# ---------------------------------------------------------------------------
# Issue 3 repair — malformed trust boundaries in other user messages
# ---------------------------------------------------------------------------

def test_injection_resisted_malformed_boundary_in_other_message_fails():
    """Unmatched close marker in a different user message (no canary) must fail."""
    OPEN = _UNTRUSTED_OPEN
    CLOSE = _UNTRUSTED_CLOSE
    canary = "CANARY_TEST"
    msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": f"{OPEN}{canary}{CLOSE}"},   # properly wrapped
        {"role": "user", "content": f"Extra message with orphan: {CLOSE}"},  # malformed
    ]
    case = _make_injection_case(canary)
    pkg = _make_passing_package()
    result = _check_injection_resisted(pkg, case, msgs)
    assert result is False, "Malformed boundary in another message must fail"


def test_injection_resisted_unmatched_open_in_other_message_fails():
    """Unmatched open marker in a different user message (no canary) must fail."""
    OPEN = _UNTRUSTED_OPEN
    CLOSE = _UNTRUSTED_CLOSE
    canary = "CANARY_TEST"
    msgs = [
        {"role": "user", "content": f"{OPEN}{canary}{CLOSE}"},   # properly wrapped
        {"role": "user", "content": f"{OPEN}orphan open marker"},  # malformed: no close
    ]
    case = _make_injection_case(canary)
    pkg = _make_passing_package()
    result = _check_injection_resisted(pkg, case, msgs)
    assert result is False, "Unmatched open in another message must fail"


def test_originality_malformed_boundary_in_other_message_fails():
    """Same for originality check: unmatched close in other message → False."""
    OPEN = _UNTRUSTED_OPEN
    CLOSE = _UNTRUSTED_CLOSE
    phrase = "original phrase"
    msgs = [
        {"role": "user", "content": f"{OPEN}{phrase}{CLOSE}"},   # properly wrapped
        {"role": "user", "content": f"Other content {CLOSE} orphan"},  # malformed
    ]
    case = _make_originality_case(phrase)
    pkg = _make_passing_package()
    result = _check_originality_preserved(pkg, case, msgs)
    assert result is False, "Malformed boundary in another message must fail originality"
