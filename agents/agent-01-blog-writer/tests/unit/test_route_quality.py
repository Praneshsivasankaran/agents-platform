"""Unit tests — route_quality_decision pure routing function (DESIGN §1.3).

Tests the isolated routing logic that controls the draft→review→finalize loop.
Uses the exported ``route_quality_decision`` from ``agent.graph`` — a pure function
that can be tested without building the full LangGraph StateGraph.

Verifies:
- pass_flag=True → "finalize" regardless of cycle count
- needs_human=True → "finalize" regardless of cycle count
- any hard_fail_flag → "finalize" regardless of cycle count
- revision_cycle >= max_cycles → "finalize" (cycles exhausted)
- low score, no hard fail, cycles remaining → "cost_gate" (loop back)
- priority order: pass_flag > needs_human > hard_fail > exhausted > revise
"""

from __future__ import annotations

import pytest

from agent.graph import route_quality_decision


# ---------------------------------------------------------------------------
# 1. Pass path — always terminal
# ---------------------------------------------------------------------------

def test_pass_routes_to_finalize():
    result = route_quality_decision(
        pass_flag=True,
        needs_human=False,
        hard_fail_flags=(),
        revision_cycle=1,
        max_cycles=2,
    )
    assert result == "finalize"


def test_pass_at_cycle_0_routes_to_finalize():
    result = route_quality_decision(
        pass_flag=True,
        needs_human=False,
        hard_fail_flags=(),
        revision_cycle=0,
        max_cycles=2,
    )
    assert result == "finalize"


def test_pass_overrides_revision_cycle():
    # Even if cycles are not exhausted, pass_flag wins
    result = route_quality_decision(
        pass_flag=True,
        needs_human=False,
        hard_fail_flags=(),
        revision_cycle=0,
        max_cycles=2,
    )
    assert result == "finalize"


# ---------------------------------------------------------------------------
# 2. needs_human path — always terminal
# ---------------------------------------------------------------------------

def test_needs_human_routes_to_finalize():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=True,
        hard_fail_flags=(),
        revision_cycle=0,
        max_cycles=2,
    )
    assert result == "finalize"


def test_needs_human_at_max_cycles_routes_to_finalize():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=True,
        hard_fail_flags=(),
        revision_cycle=2,
        max_cycles=2,
    )
    assert result == "finalize"


# ---------------------------------------------------------------------------
# 3. Hard-fail path — always terminal
# ---------------------------------------------------------------------------

def test_injection_followed_routes_to_finalize():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=False,
        hard_fail_flags=("injection_followed",),
        revision_cycle=0,
        max_cycles=2,
    )
    assert result == "finalize"


def test_multiple_hard_fails_routes_to_finalize():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=False,
        hard_fail_flags=("injection_followed", "factual_error"),
        revision_cycle=0,
        max_cycles=2,
    )
    assert result == "finalize"


def test_hard_fail_even_with_cycles_remaining():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=False,
        hard_fail_flags=("harmful_content",),
        revision_cycle=0,
        max_cycles=2,
    )
    assert result == "finalize"


# ---------------------------------------------------------------------------
# 4. Cycle-exhausted path — terminal when revision_cycle >= max_cycles
# ---------------------------------------------------------------------------

def test_cycles_exhausted_exact_boundary():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=False,
        hard_fail_flags=(),
        revision_cycle=2,
        max_cycles=2,
    )
    assert result == "finalize"


def test_cycles_exhausted_over_max():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=False,
        hard_fail_flags=(),
        revision_cycle=3,
        max_cycles=2,
    )
    assert result == "finalize"


def test_cycles_not_yet_exhausted():
    # revision_cycle=1 with max_cycles=2 → one more revision allowed
    result = route_quality_decision(
        pass_flag=False,
        needs_human=False,
        hard_fail_flags=(),
        revision_cycle=1,
        max_cycles=2,
    )
    assert result == "cost_gate"


# ---------------------------------------------------------------------------
# 5. Revision path — cost_gate when cycles remain and no terminal condition
# ---------------------------------------------------------------------------

def test_low_score_no_hard_fail_first_cycle():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=False,
        hard_fail_flags=(),
        revision_cycle=1,
        max_cycles=2,
    )
    assert result == "cost_gate"


def test_fresh_run_cycle_0_routes_to_cost_gate():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=False,
        hard_fail_flags=(),
        revision_cycle=0,
        max_cycles=2,
    )
    assert result == "cost_gate"


def test_max_cycles_1_exhausts_after_one_review():
    # With max_cycles=1, the first review cycle (revision_cycle=1) should exhaust
    result = route_quality_decision(
        pass_flag=False,
        needs_human=False,
        hard_fail_flags=(),
        revision_cycle=1,
        max_cycles=1,
    )
    assert result == "finalize"


# ---------------------------------------------------------------------------
# 6. Priority ordering — when multiple conditions are true simultaneously
# ---------------------------------------------------------------------------

def test_pass_takes_priority_over_needs_human():
    # Contradictory state (shouldn't occur normally), but pass_flag wins
    result = route_quality_decision(
        pass_flag=True,
        needs_human=True,
        hard_fail_flags=(),
        revision_cycle=0,
        max_cycles=2,
    )
    assert result == "finalize"


def test_pass_takes_priority_over_hard_fail():
    result = route_quality_decision(
        pass_flag=True,
        needs_human=False,
        hard_fail_flags=("injection_followed",),
        revision_cycle=0,
        max_cycles=2,
    )
    assert result == "finalize"


def test_needs_human_takes_priority_over_exhausted():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=True,
        hard_fail_flags=(),
        revision_cycle=5,
        max_cycles=2,
    )
    assert result == "finalize"


# ---------------------------------------------------------------------------
# 7. Empty tuple hard_fail_flags is treated as no hard fails
# ---------------------------------------------------------------------------

def test_empty_hard_fail_flags_not_terminal():
    result = route_quality_decision(
        pass_flag=False,
        needs_human=False,
        hard_fail_flags=(),
        revision_cycle=0,
        max_cycles=2,
    )
    assert result == "cost_gate"
