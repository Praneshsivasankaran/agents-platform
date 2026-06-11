"""Unit tests — core.cost.meter helpers (DESIGN §8).

Verifies:
- to_inr: correct conversion, fail-closed on empty/unknown currency
- usage_cost_inr: zero-cost shortcut, billable conversion, synthetic usage
- within_ceiling: boundary cases (exactly at ceiling = True, over = False)
- total_cost_inr: sum of StageCost list
- can_afford_stage: integrates total + estimate + ceiling
"""

from __future__ import annotations

import pytest

from core.cost import can_afford_stage, compute_max_tokens, estimate_for_stage, to_inr, total_cost_inr, usage_cost_inr, within_ceiling
from core.interfaces.usage import Usage

from agent.schemas import StageCost


# ---------------------------------------------------------------------------
# 1. to_inr — conversion + fail-closed cases
# ---------------------------------------------------------------------------

_FX = {"USD": 83.0, "EUR": 90.0}


def test_to_inr_usd():
    assert to_inr(1.0, currency="USD", fx_rates=_FX) == pytest.approx(83.0)


def test_to_inr_eur():
    assert to_inr(0.5, currency="EUR", fx_rates=_FX) == pytest.approx(45.0)


def test_to_inr_lowercase_currency_normalised():
    # Currency keys are uppercased internally
    assert to_inr(1.0, currency="usd", fx_rates=_FX) == pytest.approx(83.0)


def test_to_inr_zero_amount():
    assert to_inr(0.0, currency="USD", fx_rates=_FX) == pytest.approx(0.0)


def test_to_inr_fails_closed_empty_currency():
    with pytest.raises(ValueError, match="must not be empty"):
        to_inr(1.0, currency="", fx_rates=_FX)


def test_to_inr_fails_closed_blank_currency():
    with pytest.raises(ValueError, match="must not be empty"):
        to_inr(1.0, currency="   ", fx_rates=_FX)


def test_to_inr_fails_closed_unknown_currency():
    with pytest.raises(ValueError, match="unknown currency"):
        to_inr(1.0, currency="GBP", fx_rates=_FX)


def test_to_inr_fails_closed_no_implicit_default():
    """Verify that an unknown currency is never silently defaulted to 0."""
    with pytest.raises(ValueError):
        to_inr(5.0, currency="JPY", fx_rates=_FX)
    # (if it had defaulted to 0, 5 JPY would become ₹0, understating the ledger)


def test_to_inr_rejects_negative_fx_rate():
    """Third repair: a negative FX rate would corrupt the cost ledger."""
    with pytest.raises(ValueError, match="finite and > 0"):
        to_inr(1.0, currency="USD", fx_rates={"USD": -83.0})


def test_to_inr_rejects_infinite_fx_rate():
    """Third repair: an infinite FX rate would corrupt the cost ledger."""
    import math
    with pytest.raises(ValueError, match="finite"):
        to_inr(1.0, currency="USD", fx_rates={"USD": math.inf})


def test_to_inr_rejects_nan_fx_rate():
    """Third repair: a NaN FX rate would corrupt the cost ledger."""
    import math
    with pytest.raises(ValueError):
        to_inr(1.0, currency="USD", fx_rates={"USD": math.nan})


# ---------------------------------------------------------------------------
# 2. usage_cost_inr
# ---------------------------------------------------------------------------

def test_usage_cost_inr_zero_cost_no_currency_needed():
    # cost_native=0 → no currency required; result is 0.0
    usage = Usage(prompt_tokens=100, completion_tokens=20, synthetic=True)
    assert usage_cost_inr(usage, fx_rates=_FX) == pytest.approx(0.0)


def test_usage_cost_inr_billable():
    usage = Usage(prompt_tokens=200, completion_tokens=50, cost_native=0.01, currency="USD")
    result = usage_cost_inr(usage, fx_rates=_FX)
    assert result == pytest.approx(0.01 * 83.0)


def test_usage_cost_inr_synthetic_is_zero():
    # Synthetic usage always has cost_native=0, so result is 0.0
    usage = Usage(prompt_tokens=500, completion_tokens=100, synthetic=True)
    assert usage_cost_inr(usage, fx_rates=_FX) == pytest.approx(0.0)


def test_usage_cost_inr_fails_on_unknown_currency():
    usage = Usage(cost_native=1.0, currency="GBP")
    with pytest.raises(ValueError, match="unknown currency"):
        usage_cost_inr(usage, fx_rates=_FX)


# ---------------------------------------------------------------------------
# 3. within_ceiling — boundary cases
# ---------------------------------------------------------------------------

def test_within_ceiling_exactly_at_limit():
    # spent + next == ceiling → True (inclusive)
    assert within_ceiling(40.0, 10.0, ceiling_inr=50.0) is True


def test_within_ceiling_under():
    assert within_ceiling(30.0, 5.0, ceiling_inr=50.0) is True


def test_within_ceiling_over_by_one_rupee():
    assert within_ceiling(40.0, 10.1, ceiling_inr=50.0) is False


def test_within_ceiling_default_50():
    assert within_ceiling(49.0, 1.0) is True
    assert within_ceiling(49.0, 1.1) is False


def test_within_ceiling_zero_spent():
    assert within_ceiling(0.0, 12.0, ceiling_inr=50.0) is True


def test_within_ceiling_zero_estimate():
    # A free stage (0 estimate) always fits
    assert within_ceiling(49.9, 0.0, ceiling_inr=50.0) is True


def test_within_ceiling_rejects_negative_spent():
    """Second repair: negative spent_inr is rejected (fail-closed)."""
    with pytest.raises(ValueError, match="non-negative"):
        within_ceiling(-1.0, 10.0, ceiling_inr=50.0)


def test_within_ceiling_rejects_negative_next_call():
    with pytest.raises(ValueError, match="non-negative"):
        within_ceiling(10.0, -0.01, ceiling_inr=50.0)


def test_within_ceiling_rejects_infinite_spent():
    import math
    with pytest.raises(ValueError, match="finite"):
        within_ceiling(math.inf, 0.0, ceiling_inr=50.0)


def test_within_ceiling_rejects_nan_value():
    import math
    with pytest.raises(ValueError):
        within_ceiling(math.nan, 0.0, ceiling_inr=50.0)


def test_within_ceiling_zero_ceiling_blocks_any_spend():
    """ceiling_inr=0 is valid; any positive spend fails the gate."""
    assert within_ceiling(0.0, 0.0, ceiling_inr=0.0) is True
    assert within_ceiling(0.0, 0.01, ceiling_inr=0.0) is False


# ---------------------------------------------------------------------------
# 4. total_cost_inr
# ---------------------------------------------------------------------------

def test_total_cost_inr_empty():
    assert total_cost_inr([]) == pytest.approx(0.0)


def test_total_cost_inr_single():
    sc = StageCost(stage="draft", cost_inr=12.0, tier="strong")
    assert total_cost_inr([sc]) == pytest.approx(12.0)


def test_total_cost_inr_multiple():
    scs = [
        StageCost(stage="normalize", cost_inr=0.5, tier="cheap"),
        StageCost(stage="extract_ideas", cost_inr=0.3, tier="cheap"),
        StageCost(stage="plan", cost_inr=0.4, tier="cheap"),
        StageCost(stage="draft", cost_inr=12.0, tier="strong"),
        StageCost(stage="review", cost_inr=6.0, tier="strong"),
    ]
    assert total_cost_inr(scs) == pytest.approx(19.2)


def test_total_cost_inr_with_duck_typed_objects():
    """total_cost_inr uses getattr so it works on any object with cost_inr."""
    class DuckCost:
        def __init__(self, cost_inr):
            self.cost_inr = cost_inr

    assert total_cost_inr([DuckCost(5.0), DuckCost(3.0)]) == pytest.approx(8.0)


# ---------------------------------------------------------------------------
# 5. can_afford_stage
# ---------------------------------------------------------------------------

_ESTIMATED = {"draft": 12.0, "review": 6.0}
_CEILING = 50.0


def test_can_afford_stage_fresh_run():
    # No prior spend → easily affordable
    assert can_afford_stage([], "draft", _ESTIMATED, _CEILING) is True


def test_can_afford_stage_just_fits():
    # Spent 38 + draft estimate 12 == 50 == ceiling → True
    scs = [StageCost(stage="misc", cost_inr=38.0, tier="strong")]
    assert can_afford_stage(scs, "draft", _ESTIMATED, _CEILING) is True


def test_can_afford_stage_does_not_fit():
    # Spent 39 + draft estimate 12 == 51 > 50 → False
    scs = [StageCost(stage="misc", cost_inr=39.0, tier="strong")]
    assert can_afford_stage(scs, "draft", _ESTIMATED, _CEILING) is False


def test_can_afford_stage_unknown_stage_raises():
    """Repair (Issue #5): unknown stage must raise ValueError, never default to 0.

    Defaulting an unknown stage to 0 would silently allow unlimited budget consumption
    for unregistered stages, defeating the ₹50/blog ceiling (fail-closed design).
    """
    scs = [StageCost(stage="misc", cost_inr=49.9, tier="strong")]
    with pytest.raises(ValueError, match="No cost estimate configured for stage"):
        can_afford_stage(scs, "unknown_stage", _ESTIMATED, _CEILING)


def test_can_afford_stage_after_two_revision_cycles():
    # Simulate: normalize(0.5) + extract_ideas(0.3) + plan(0.4) + draft(12) + review(6)
    #         + draft(12) + review(6) = 37.2 → still fits for another draft(12)? 37.2+12=49.2<=50 ✓
    scs = [
        StageCost(stage="normalize", cost_inr=0.5, tier="cheap"),
        StageCost(stage="extract_ideas", cost_inr=0.3, tier="cheap"),
        StageCost(stage="plan", cost_inr=0.4, tier="cheap"),
        StageCost(stage="draft", cost_inr=12.0, tier="strong"),
        StageCost(stage="review", cost_inr=6.0, tier="strong"),
        StageCost(stage="draft", cost_inr=12.0, tier="strong"),
        StageCost(stage="review", cost_inr=6.0, tier="strong"),
    ]
    total = total_cost_inr(scs)  # 37.2
    assert total == pytest.approx(37.2)
    assert can_afford_stage(scs, "draft", _ESTIMATED, _CEILING) is True


def test_can_afford_ceiling_is_configurable():
    scs = [StageCost(stage="draft", cost_inr=3.0, tier="strong")]
    assert can_afford_stage(scs, "draft", {"draft": 2.0}, ceiling_inr=5.0) is True   # 3+2=5 ✓
    assert can_afford_stage(scs, "draft", {"draft": 2.1}, ceiling_inr=5.0) is False  # 3+2.1=5.1 ✗


# ---------------------------------------------------------------------------
# 6. estimate_for_stage — fail-closed lookup (Repair Issue #5)
# ---------------------------------------------------------------------------

def test_estimate_for_stage_known():
    assert estimate_for_stage("draft", _ESTIMATED) == pytest.approx(12.0)
    assert estimate_for_stage("review", _ESTIMATED) == pytest.approx(6.0)


def test_estimate_for_stage_unknown_raises():
    """Fail-closed: unknown stage name must raise ValueError, never return 0."""
    with pytest.raises(ValueError, match="No cost estimate configured for stage"):
        estimate_for_stage("nonexistent_stage", _ESTIMATED)


def test_estimate_for_stage_error_mentions_known_stages():
    """The error message must list known stages so the operator can fix config."""
    with pytest.raises(ValueError, match="draft"):
        estimate_for_stage("typo_stage", _ESTIMATED)


def test_estimate_for_stage_empty_config_raises():
    """An empty estimated_costs dict raises for any stage name."""
    with pytest.raises(ValueError):
        estimate_for_stage("draft", {})


def test_estimate_for_stage_rejects_negative_estimate():
    """Third repair: a negative estimate would corrupt the cost gate."""
    with pytest.raises(ValueError, match="non-negative"):
        estimate_for_stage("draft", {"draft": -1.0})


def test_estimate_for_stage_rejects_infinite_estimate():
    """Third repair: an infinite estimate would corrupt the cost gate."""
    import math
    with pytest.raises(ValueError, match="finite"):
        estimate_for_stage("draft", {"draft": math.inf})


def test_estimate_for_stage_rejects_nan_estimate():
    """Third repair: a NaN estimate is rejected."""
    import math
    with pytest.raises(ValueError):
        estimate_for_stage("draft", {"draft": math.nan})


# ---------------------------------------------------------------------------
# 7. Combined-headroom check — cost gate checks draft + review together
# ---------------------------------------------------------------------------

def test_combined_headroom_draft_and_review_fit():
    """Headroom is checked for draft+review combined, not just draft.

    spent=30, draft=12, review=6 → combined=18 → 30+18=48 ≤ 50 → ok
    """
    scs = [StageCost(stage="normalize", cost_inr=30.0, tier="cheap")]
    draft_est = estimate_for_stage("draft", _ESTIMATED)   # 12
    review_est = estimate_for_stage("review", _ESTIMATED)  # 6
    combined = draft_est + review_est                       # 18
    assert within_ceiling(total_cost_inr(scs), combined, ceiling_inr=50.0) is True


# ---------------------------------------------------------------------------
# 8. compute_max_tokens — derive token cap from remaining budget (fifth repair)
# ---------------------------------------------------------------------------

def test_compute_max_tokens_zero_cost_per_token_returns_none():
    """When cost-per-token is 0 (unpriced/mock tier), no cap is derivable → None."""
    assert compute_max_tokens(10.0, output_cost_per_token_inr=0.0) is None


def test_compute_max_tokens_basic():
    """remaining=10.0, cpt=0.01 → 10/0.01=1000 tokens."""
    result = compute_max_tokens(10.0, output_cost_per_token_inr=0.01)
    assert result == 1000


def test_compute_max_tokens_fractional():
    """remaining=5.0, cpt=0.003 → int(5/0.003)=1666."""
    result = compute_max_tokens(5.0, output_cost_per_token_inr=0.003)
    assert result == 1666


def test_compute_max_tokens_zero_remaining():
    """No remaining budget → 0 tokens (block the call)."""
    result = compute_max_tokens(0.0, output_cost_per_token_inr=0.01)
    assert result == 0


def test_compute_max_tokens_very_small_remaining():
    """Less than one token's worth → 0."""
    result = compute_max_tokens(0.005, output_cost_per_token_inr=0.01)
    assert result == 0


def test_compute_max_tokens_rejects_negative_cpt():
    """Negative cost-per-token is fail-closed."""
    with pytest.raises(ValueError, match="non-negative"):
        compute_max_tokens(10.0, output_cost_per_token_inr=-0.01)


def test_compute_max_tokens_rejects_infinite_cpt():
    """Infinite cost-per-token is fail-closed."""
    import math
    with pytest.raises(ValueError, match="finite"):
        compute_max_tokens(10.0, output_cost_per_token_inr=math.inf)


def test_compute_max_tokens_rejects_nan_cpt():
    """NaN cost-per-token is fail-closed."""
    import math
    with pytest.raises(ValueError):
        compute_max_tokens(10.0, output_cost_per_token_inr=math.nan)


def test_compute_max_tokens_rejects_negative_remaining():
    """Negative remaining_inr is fail-closed (should never happen; nodes pass max(0, ...))."""
    with pytest.raises(ValueError, match="non-negative"):
        compute_max_tokens(-1.0, output_cost_per_token_inr=0.01)


def test_compute_max_tokens_rejects_infinite_remaining():
    """Infinite remaining_inr is fail-closed."""
    import math
    with pytest.raises(ValueError, match="finite"):
        compute_max_tokens(math.inf, output_cost_per_token_inr=0.01)


def test_compute_max_tokens_large_budget():
    """Large remaining budget yields a large but finite token count."""
    result = compute_max_tokens(50.0, output_cost_per_token_inr=0.001)
    assert result == 50000


def test_combined_headroom_fails_when_review_would_exceed():
    """If draft alone fits but draft+review would exceed, combined check must fail.

    spent=33, draft=12 → 45 ≤ 50 (draft alone fits)
    spent=33, draft+review=18 → 51 > 50 (combined fails)
    """
    spent = 33.0
    draft_est = estimate_for_stage("draft", _ESTIMATED)   # 12
    review_est = estimate_for_stage("review", _ESTIMATED)  # 6
    combined = draft_est + review_est                       # 18

    assert within_ceiling(spent, draft_est, ceiling_inr=50.0) is True   # draft alone fits
    assert within_ceiling(spent, combined, ceiling_inr=50.0) is False   # combined does NOT
