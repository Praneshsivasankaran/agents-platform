"""Unit tests — centralized budget authorization (packages/core/cost/budget.py).

Eighth repair pass tests:
- remaining_inr is now the per-call budget (ceiling - current - downstream_reserve),
  NOT the total remaining headroom.  Tests updated to reflect this semantic change.

Seventh repair pass tests:
- authorize_call approves calls within the ceiling
- authorize_call raises CostCeilingExceeded when ceiling would be exceeded
- Non-mock + zero pricing fails closed (ValueError)
- Mock + zero pricing is usable (no fail-closed)
- Draft authorization reserves review cost
- Cheap call at ₹49.90 cannot push spending above ₹50
- Zero and exact-ceiling authorizations
- CostCeilingExceeded is distinct from ValueError/RuntimeError
"""
from __future__ import annotations

import pytest

from core.cost import (
    CallAuthorization,
    CostCeilingExceeded,
    authorize_call,
    estimate_prompt_tokens,
    resolve_is_mock,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stage_cost(stage: str, cost_inr: float):
    """Return a duck-typed stage-cost object (cost_inr attribute)."""
    class _SC:
        def __init__(self, s, c):
            self.stage = s
            self.cost_inr = c
    return _SC(stage, cost_inr)


def _estimated() -> dict[str, float]:
    return {
        "normalize": 0.3,
        "extract_ideas": 0.3,
        "plan": 0.5,
        "draft": 12.0,
        "review": 6.0,
    }


# ---------------------------------------------------------------------------
# 1. Approval within ceiling
# ---------------------------------------------------------------------------

def test_authorize_call_approves_within_ceiling():
    # normalize: current=0, reserve=0.3+0.5+12+6=18.8
    # call_budget = max(0, 50 - 0 - 18.8) = 31.2
    auth = authorize_call(
        stage_name="normalize",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=("extract_ideas", "plan", "draft", "review"),
        output_cost_per_token_inr=0.0,
        is_mock=True,
    )
    assert isinstance(auth, CallAuthorization)
    assert auth.max_tokens is None          # mock, cpt=0 → no token cap derivable
    # Eighth repair: remaining_inr is the per-call budget (ceiling - current - reserve),
    # not total remaining headroom.  31.2 = 50 - 0 - (0.3+0.5+12+6).
    assert auth.remaining_inr == pytest.approx(31.2)


def test_authorize_call_returns_correct_remaining():
    """remaining_inr is the per-call budget: ceiling - current_spend - downstream_reserve.

    Eighth repair: semantics changed from (ceiling - current) to (ceiling - current - reserve).
    With ₹5 spent and downstream_reserve=plan(0.5)+draft(12)+review(6)=18.5:
      call_budget = 50 - 5 - 18.5 = 26.5
    """
    spent = [_stage_cost("normalize", 5.0)]
    auth = authorize_call(
        stage_name="extract_ideas",
        stage_costs=spent,
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=("plan", "draft", "review"),
        output_cost_per_token_inr=0.0,
        is_mock=True,
    )
    assert auth.remaining_inr == pytest.approx(26.5)   # 50 - 5 - (0.5+12+6) = 26.5


# ---------------------------------------------------------------------------
# 2. CostCeilingExceeded when budget would be exceeded
# ---------------------------------------------------------------------------

def test_authorize_call_raises_cost_ceiling_exceeded_when_over():
    """40 spent + draft(12) + review(6) = 58 > 50 → CostCeilingExceeded."""
    with pytest.raises(CostCeilingExceeded):
        authorize_call(
            stage_name="draft",
            stage_costs=[_stage_cost("prior", 40.0)],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=("review",),
            output_cost_per_token_inr=0.0,
            is_mock=True,
        )


def test_authorize_call_raises_cost_ceiling_exceeded_zero_ceiling():
    """Zero ceiling → any positive estimate exceeds it immediately."""
    with pytest.raises(CostCeilingExceeded):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=0.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.0,
            is_mock=True,
        )


def test_authorize_call_allows_when_just_within_ceiling():
    """0 + normalize(0.3) + downstream(18.8) = 19.1 <= 19.1 → allowed (strict >)."""
    auth = authorize_call(
        stage_name="normalize",
        stage_costs=[],
        ceiling_inr=19.1,
        estimated_costs=_estimated(),
        downstream_stages=("extract_ideas", "plan", "draft", "review"),
        output_cost_per_token_inr=0.0,
        is_mock=True,
    )
    assert isinstance(auth, CallAuthorization)


def test_authorize_call_blocks_one_rupee_over():
    """19.1 > 19.0 → CostCeilingExceeded."""
    with pytest.raises(CostCeilingExceeded):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=19.0,
            estimated_costs=_estimated(),
            downstream_stages=("extract_ideas", "plan", "draft", "review"),
            output_cost_per_token_inr=0.0,
            is_mock=True,
        )


# ---------------------------------------------------------------------------
# 3. Fail-closed: non-mock + zero pricing raises ValueError
# ---------------------------------------------------------------------------

def test_authorize_call_fail_closed_non_mock_zero_pricing():
    """Non-mock provider with zero output pricing must fail closed."""
    with pytest.raises(ValueError, match="fail-closed"):
        authorize_call(
            stage_name="draft",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=("review",),
            output_cost_per_token_inr=0.0,
            is_mock=False,  # non-mock: zero pricing → ValueError
        )


def test_authorize_call_fail_closed_non_mock_non_zero_pricing_allowed():
    """Non-mock with real per-token pricing is allowed."""
    auth = authorize_call(
        stage_name="draft",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=("review",),
        output_cost_per_token_inr=0.00058,   # real pricing (e.g. Gemini Pro)
        is_mock=False,
    )
    assert isinstance(auth, CallAuthorization)
    assert auth.max_tokens is not None     # token cap derived from remaining headroom


# ---------------------------------------------------------------------------
# 4. Mock + zero pricing remains usable
# ---------------------------------------------------------------------------

def test_authorize_call_mock_zero_pricing_usable():
    """is_mock=True + zero pricing → no fail-closed → None max_tokens (no cap)."""
    auth = authorize_call(
        stage_name="review",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=(),
        output_cost_per_token_inr=0.0,
        is_mock=True,
    )
    assert auth.max_tokens is None


# ---------------------------------------------------------------------------
# 5. Draft reserves review cost
# ---------------------------------------------------------------------------

def test_draft_reserves_review_cost():
    """Spent ₹32: draft(12) + review(6) = 18 → 32+18=50 <= 50 → allowed."""
    auth = authorize_call(
        stage_name="draft",
        stage_costs=[_stage_cost("prior", 32.0)],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=("review",),
        output_cost_per_token_inr=0.0,
        is_mock=True,
    )
    assert isinstance(auth, CallAuthorization)


def test_draft_blocked_when_review_reserve_would_exceed_ceiling():
    """Spent ₹33: draft(12) + review(6) = 18 → 33+18=51 > 50 → CostCeilingExceeded."""
    with pytest.raises(CostCeilingExceeded):
        authorize_call(
            stage_name="draft",
            stage_costs=[_stage_cost("prior", 33.0)],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=("review",),
            output_cost_per_token_inr=0.0,
            is_mock=True,
        )


# ---------------------------------------------------------------------------
# 6. Cheap call at ₹49.90 cannot push total above ₹50
# ---------------------------------------------------------------------------

def test_cheap_call_at_49_90_cannot_push_above_50():
    """₹49.90 spent + normalize(0.3) > 50 → blocked even without downstream reserve."""
    with pytest.raises(CostCeilingExceeded):
        authorize_call(
            stage_name="normalize",
            stage_costs=[_stage_cost("draft", 49.90)],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),   # even with no reserve, 49.90+0.3=50.2 > 50
            output_cost_per_token_inr=0.0,
            is_mock=True,
        )


# ---------------------------------------------------------------------------
# 7. CostCeilingExceeded is its own type (not ValueError / RuntimeError)
# ---------------------------------------------------------------------------

def test_cost_ceiling_exceeded_is_distinct_exception():
    assert issubclass(CostCeilingExceeded, Exception)
    assert not issubclass(CostCeilingExceeded, ValueError)
    assert not issubclass(CostCeilingExceeded, RuntimeError)


def test_cost_ceiling_exceeded_is_catchable_separately():
    caught = False
    try:
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=0.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.0,
            is_mock=True,
        )
    except CostCeilingExceeded:
        caught = True
    assert caught


# ---------------------------------------------------------------------------
# 8. Missing pricing config for stage raises ValueError (fail-closed)
# ---------------------------------------------------------------------------

def test_authorize_call_missing_stage_raises_value_error():
    """Stage not in estimated_costs raises ValueError (fail-closed)."""
    with pytest.raises(ValueError, match="No cost estimate configured"):
        authorize_call(
            stage_name="unknown_stage",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.0,
            is_mock=True,
        )


# ---------------------------------------------------------------------------
# 9. max_tokens derivation with real pricing
# ---------------------------------------------------------------------------

def test_authorize_call_derives_max_tokens_with_real_pricing():
    """review has no downstream: call_budget = 50 - 0 - 0 = 50 → max_tokens = 50000."""
    auth = authorize_call(
        stage_name="review",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=(),
        output_cost_per_token_inr=0.001,   # ₹0.001 per output token
        is_mock=False,
    )
    # call_budget = 50.0 - 0 - 0 = 50.0; max_tokens = int(50.0 / 0.001) = 50000
    assert auth.max_tokens == 50000


def test_authorize_call_max_tokens_preserves_downstream_reserve():
    """max_tokens must not allow draft output to consume review's budget share.

    Eighth repair: draft with ₹32 spent and review(₹6) downstream.
    call_budget = 50 - 32 - 6 = 12 → max_tokens = int(12 / 0.001) = 12000.
    Previously would have been int(18 / 0.001) = 18000 — over-allocating ₹6 to draft.
    """
    auth = authorize_call(
        stage_name="draft",
        stage_costs=[_stage_cost("prior", 32.0)],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=("review",),
        output_cost_per_token_inr=0.001,
        is_mock=False,
    )
    # call_budget = 50 - 32 - 6(review) = 12 → max_tokens = 12000
    assert auth.max_tokens == 12000
    assert auth.remaining_inr == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# 10. resolve_is_mock validation
# ---------------------------------------------------------------------------

def test_resolve_is_mock_returns_true_for_mock_provider():
    """provider='mock' → is_mock=True regardless of cost.is_mock."""
    assert resolve_is_mock({"provider": "mock"}) is True
    assert resolve_is_mock({"provider": "mock", "cost": {"is_mock": False}}) is True
    assert resolve_is_mock({"provider": "mock", "cost": {"is_mock": True}}) is True


def test_resolve_is_mock_returns_true_for_cost_is_mock_without_provider():
    """No provider key + cost.is_mock=True → True (offline test config)."""
    assert resolve_is_mock({"cost": {"is_mock": True}}) is True
    assert resolve_is_mock({"cost": {}}) is False


def test_resolve_is_mock_raises_for_cloud_provider_with_is_mock_true():
    """provider='gcp' + cost.is_mock=True → ValueError (misconfiguration guard)."""
    with pytest.raises(ValueError, match="cost.is_mock=True"):
        resolve_is_mock({"provider": "gcp", "cost": {"is_mock": True}})


def test_resolve_is_mock_false_for_cloud_provider_without_is_mock():
    """provider='gcp' without cost.is_mock → False (safe default)."""
    assert resolve_is_mock({"provider": "gcp"}) is False
    assert resolve_is_mock({"provider": "gcp", "cost": {"is_mock": False}}) is False


def test_resolve_is_mock_false_for_empty_config():
    """No provider, no is_mock → False."""
    assert resolve_is_mock({}) is False


def test_resolve_is_mock_reads_llm_provider_over_top_level():
    """llm.provider takes precedence over top-level provider key.

    Ninth repair: resolve_is_mock reads llm.provider first (the key used by
    get_llm_provider factory), then falls back to top-level provider.
    {llm.provider: mock} → True even if top-level provider is absent.
    """
    assert resolve_is_mock({"llm": {"provider": "mock"}}) is True
    # llm.provider beats top-level provider
    assert resolve_is_mock({"llm": {"provider": "mock"}, "provider": "gcp"}) is True


def test_resolve_is_mock_llm_provider_cloud_raises_with_is_mock_true():
    """llm.provider='gcp' + cost.is_mock=True → ValueError (misconfiguration guard).

    Both {provider:mock, llm.provider:gcp} and {llm.provider:gcp} with cost.is_mock=True
    must raise — the factory uses llm.provider, not the top-level key.
    """
    with pytest.raises(ValueError, match="cost.is_mock=True"):
        resolve_is_mock({"llm": {"provider": "gcp"}, "cost": {"is_mock": True}})
    # llm.provider wins over top-level mock
    with pytest.raises(ValueError, match="cost.is_mock=True"):
        resolve_is_mock({
            "provider": "mock",
            "llm": {"provider": "gcp"},
            "cost": {"is_mock": True},
        })


def test_resolve_is_mock_fallback_to_top_level_provider():
    """When llm.provider is absent, top-level provider is used (backwards compat)."""
    assert resolve_is_mock({"provider": "mock"}) is True
    assert resolve_is_mock({"provider": "gcp"}) is False
    with pytest.raises(ValueError, match="cost.is_mock=True"):
        resolve_is_mock({"provider": "gcp", "cost": {"is_mock": True}})


# ---------------------------------------------------------------------------
# 11. input_cost_per_token_inr parameter in authorize_call
# ---------------------------------------------------------------------------

def test_authorize_call_input_cost_reduces_output_budget():
    """input_cost reserve is subtracted from the per-call output budget.

    With ceiling=50, current=0, downstream=18.5 (plan+draft+review):
      call_budget = 50 - 0 - 18.5 = 31.5
      input_reserve = 0.001 * 1000 = 1.0
      output_budget = 31.5 - 1.0 = 30.5
      max_tokens = int(30.5 / 0.001) = 30500
    """
    auth = authorize_call(
        stage_name="extract_ideas",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=("plan", "draft", "review"),
        output_cost_per_token_inr=0.001,
        input_cost_per_token_inr=0.001,
        prompt_tokens_estimate=1000,
        is_mock=False,
    )
    # call_budget = 50 - 0 - (0.5+12+6) = 31.5
    # output_budget = 31.5 - (0.001 * 1000) = 30.5
    assert auth.max_tokens == 30500
    # remaining_inr reflects the full per-call budget (before input_reserve subtraction)
    assert auth.remaining_inr == pytest.approx(31.5)


def test_authorize_call_input_cost_zero_no_effect():
    """input_cost_per_token_inr=0.0 (default) has no effect on max_tokens."""
    auth_with = authorize_call(
        stage_name="review",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=(),
        output_cost_per_token_inr=0.001,
        input_cost_per_token_inr=0.0,
        prompt_tokens_estimate=10000,
        is_mock=False,
    )
    auth_without = authorize_call(
        stage_name="review",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=(),
        output_cost_per_token_inr=0.001,
        is_mock=False,
    )
    assert auth_with.max_tokens == auth_without.max_tokens


def test_authorize_call_max_tokens_zero_raises_cost_ceiling_exceeded():
    """When output_budget ≤ 0 (input reserve >= call_budget), max_tokens=0.

    Tenth repair: authorize_call now raises CostCeilingExceeded when max_tokens=0
    so the provider is NEVER called — incurring input charges with no output budget
    is rejected pre-emptively rather than caught post-hoc.

    Scenario: normalize with no downstream, ceiling=0.6, input_cpt=0.001, prompt=1000t:
      call_budget = 0.6, input_reserve = 1.0 > 0.6 → output_budget=0 → max_tokens=0
      → CostCeilingExceeded (not CostCeilingExceeded from estimate check:
        0 + 0.3 + 0 = 0.3 <= 0.6 passes estimate check first)
    """
    with pytest.raises(CostCeilingExceeded, match="output-token headroom"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=0.6,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            input_cost_per_token_inr=0.001,
            prompt_tokens_estimate=1000,
            is_mock=False,
        )


# ---------------------------------------------------------------------------
# 12. Input parameter validation — finite and non-negative (tenth repair)
# ---------------------------------------------------------------------------

def test_authorize_call_raises_on_negative_output_pricing():
    """Negative output_cost_per_token_inr must be rejected immediately."""
    with pytest.raises(ValueError, match="output_cost_per_token_inr"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=-0.001,  # negative — must fail
            is_mock=False,
        )


def test_authorize_call_raises_on_nan_output_pricing():
    """NaN output_cost_per_token_inr must be rejected (would corrupt max_tokens)."""
    import math as _math
    with pytest.raises(ValueError, match="output_cost_per_token_inr"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=_math.nan,
            is_mock=True,
        )


def test_authorize_call_raises_on_infinite_output_pricing():
    """Infinite output_cost_per_token_inr must be rejected."""
    import math as _math
    with pytest.raises(ValueError, match="output_cost_per_token_inr"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=_math.inf,
            is_mock=True,
        )


def test_authorize_call_raises_on_negative_input_pricing():
    """Negative input_cost_per_token_inr must be rejected (would inflate output budget)."""
    with pytest.raises(ValueError, match="input_cost_per_token_inr"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            input_cost_per_token_inr=-0.001,  # negative — must fail
            is_mock=False,
        )


def test_authorize_call_raises_on_nan_input_pricing():
    """NaN input_cost_per_token_inr must be rejected (would corrupt output budget)."""
    import math as _math
    with pytest.raises(ValueError, match="input_cost_per_token_inr"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            input_cost_per_token_inr=_math.nan,
            is_mock=False,
        )


def test_authorize_call_raises_on_negative_prompt_tokens():
    """Negative prompt_tokens_estimate must be rejected (would inflate output budget)."""
    with pytest.raises(ValueError, match="prompt_tokens_estimate"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            input_cost_per_token_inr=0.001,
            prompt_tokens_estimate=-1,  # negative — must fail
            is_mock=False,
        )


def test_authorize_call_input_cost_clamps_output_budget_raises_ceiling_exceeded():
    """When input_reserve >= call_budget, output_budget=0 → max_tokens=0 → CostCeilingExceeded.

    Tenth repair: max_tokens=0 now raises CostCeilingExceeded (pre-call) instead of
    returning a zero-cap authorization.  Calling the provider with max_tokens=0 would
    still incur input charges; the guard fires before that can happen.

    Use 'normalize' (estimate=0.3) with no downstream stages and ceiling=0.6:
    - pre-call estimate check: 0 + 0.3 + 0 = 0.3 <= 0.6 → passes
    - call_budget = 0.6 - 0 - 0 = 0.6
    - input_reserve = 0.001 * 1000 = 1.0 > 0.6 → output_budget = 0 → max_tokens=0
    - → CostCeilingExceeded raised before provider is called
    """
    with pytest.raises(CostCeilingExceeded, match="output-token headroom"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=0.6,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            input_cost_per_token_inr=0.001,
            prompt_tokens_estimate=1000,
            is_mock=False,
        )


# ---------------------------------------------------------------------------
# 13. fixed_cost_inr parameter — eleventh repair
# ---------------------------------------------------------------------------

def test_authorize_call_fixed_cost_reduces_output_budget():
    """fixed_cost_inr is subtracted from per-call budget alongside input reserve.

    review with no downstream, ceiling=50, output_cpt=0.001, fixed_cost=5.0:
      call_budget = 50 - 0 - 0 = 50.0
      total_reserve = input_reserve(0) + fixed_cost(5.0) = 5.0
      output_budget = 50 - 5 = 45 → max_tokens = int(45 / 0.001) = 45000
    """
    auth = authorize_call(
        stage_name="review",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=(),
        output_cost_per_token_inr=0.001,
        fixed_cost_inr=5.0,
        is_mock=False,
    )
    assert auth.max_tokens == 45000


def test_authorize_call_fixed_cost_and_input_reserve_combined():
    """fixed_cost_inr and input_reserve both reduce output budget.

    review, ceiling=50, output_cpt=0.001, input_cpt=0.001, prompt=1000, fixed=2.0:
      call_budget = 50.0
      total_reserve = (0.001 * 1000) + 2.0 = 3.0
      output_budget = 47.0 → max_tokens = 47000
    """
    auth = authorize_call(
        stage_name="review",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=(),
        output_cost_per_token_inr=0.001,
        input_cost_per_token_inr=0.001,
        prompt_tokens_estimate=1000,
        fixed_cost_inr=2.0,
        is_mock=False,
    )
    assert auth.max_tokens == 47000


def test_authorize_call_fixed_cost_zero_no_effect():
    """fixed_cost_inr=0.0 (default) has no effect on max_tokens."""
    auth_with = authorize_call(
        stage_name="review",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=(),
        output_cost_per_token_inr=0.001,
        fixed_cost_inr=0.0,
        is_mock=False,
    )
    auth_without = authorize_call(
        stage_name="review",
        stage_costs=[],
        ceiling_inr=50.0,
        estimated_costs=_estimated(),
        downstream_stages=(),
        output_cost_per_token_inr=0.001,
        is_mock=False,
    )
    assert auth_with.max_tokens == auth_without.max_tokens


def test_authorize_call_raises_on_negative_fixed_cost():
    """Negative fixed_cost_inr must be rejected (would inflate output budget)."""
    with pytest.raises(ValueError, match="fixed_cost_inr"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            fixed_cost_inr=-1.0,  # negative — must fail
            is_mock=False,
        )


def test_authorize_call_raises_on_nan_fixed_cost():
    """NaN fixed_cost_inr must be rejected."""
    import math as _math
    with pytest.raises(ValueError, match="fixed_cost_inr"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            fixed_cost_inr=_math.nan,
            is_mock=True,
        )


def test_authorize_call_raises_on_infinite_fixed_cost():
    """Infinite fixed_cost_inr must be rejected."""
    import math as _math
    with pytest.raises(ValueError, match="fixed_cost_inr"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            fixed_cost_inr=_math.inf,
            is_mock=True,
        )


def test_authorize_call_fixed_cost_raises_ceiling_exceeded_when_exhausts_budget():
    """fixed_cost_inr alone exhausting budget → output_budget=0 → CostCeilingExceeded.

    normalize, no downstream, ceiling=0.4, output_cpt=0.001, fixed_cost=0.5:
      call_budget = 0.4 (since 0 + 0.3 + 0 = 0.3 <= 0.4 → passes estimate check)
      total_reserve = 0 + 0.5 = 0.5 > 0.4 → output_budget=0 → max_tokens=0
      → CostCeilingExceeded (output-token headroom)
    """
    with pytest.raises(CostCeilingExceeded, match="output-token headroom"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=0.4,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            fixed_cost_inr=0.5,
            is_mock=False,
        )


# ---------------------------------------------------------------------------
# 14. prompt_tokens_estimate type validation — eleventh repair
# ---------------------------------------------------------------------------

def test_authorize_call_raises_on_boolean_prompt_tokens_estimate():
    """Boolean values for prompt_tokens_estimate must be rejected (True == 1, False == 0 in Python).

    Eleventh repair: isinstance check explicitly rejects bool before int check
    so True/False are not silently treated as 1/0.
    """
    with pytest.raises(ValueError, match="prompt_tokens_estimate"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            prompt_tokens_estimate=True,  # bool — must be rejected
            is_mock=False,
        )

    with pytest.raises(ValueError, match="prompt_tokens_estimate"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            prompt_tokens_estimate=False,  # bool — must be rejected
            is_mock=False,
        )


def test_authorize_call_raises_on_float_prompt_tokens_estimate():
    """Float (non-int) prompt_tokens_estimate must be rejected.

    Eleventh repair: fractional token counts are nonsensical — the estimator
    returns an int; a float here likely indicates a miscalculation.
    """
    with pytest.raises(ValueError, match="prompt_tokens_estimate"):
        authorize_call(
            stage_name="normalize",
            stage_costs=[],
            ceiling_inr=50.0,
            estimated_costs=_estimated(),
            downstream_stages=(),
            output_cost_per_token_inr=0.001,
            prompt_tokens_estimate=100.5,  # float — must be rejected
            is_mock=False,
        )


# ---------------------------------------------------------------------------
# 15. estimate_prompt_tokens — adversarial / edge-case coverage (final repair)
#
# Implementation constants (byte-per-token, fail-closed):
#   _REQUEST_FRAMING_BYTES    = 16   (overall request envelope)
#   _OVERHEAD_BYTES_PER_MESSAGE = 16 (per-message chat-template framing)
#   role "user" = 4 UTF-8 bytes
#   role "system" = 6 UTF-8 bytes
#
# Formula:
#   total = 16 (framing)
#         + Σ messages: 16 (overhead) + len(role.utf8) + len(content.utf8)
#         + if schema: 16 (overhead) + len(schema_json.utf8)
#         + if tools:  16 (overhead) + len(tools_json.utf8)
# ---------------------------------------------------------------------------

def _msgs(*contents: str) -> list:
    """Build minimal messages list for estimate_prompt_tokens tests (role='user')."""
    return [{"role": "user", "content": c} for c in contents]


def test_estimate_prompt_tokens_empty_messages():
    """Zero messages → only request framing; still returns ≥ 1."""
    result = estimate_prompt_tokens([])
    assert result >= 1


def test_estimate_prompt_tokens_short_non_multiple_of_four():
    """5-byte string counts as 5 tokens (1 byte = 1 token, not ceil(5/4)=2).

    Final repair: 1 token per byte is the guaranteed conservative bound.
    Minimum for _msgs("hello") = REQUEST_FRAMING(16) + MSG_OVERHEAD(16)
                                 + role("user"=4) + content("hello"=5) = 41.
    """
    result = estimate_prompt_tokens(_msgs("hello"))   # 5 ASCII chars = 5 bytes
    assert result >= 41, f"Expected ≥ 41 for 5-byte 'user' message, got {result}"


def test_estimate_prompt_tokens_counts_every_byte():
    """n-byte ASCII content adds exactly n to the estimate over an empty message."""
    r_empty = estimate_prompt_tokens(_msgs(""))
    for n in range(1, 33):
        content = "a" * n          # ASCII: n chars = n bytes
        result = estimate_prompt_tokens(_msgs(content))
        assert result == r_empty + n, (
            f"n={n}: expected empty({r_empty}) + {n} = {r_empty + n}, got {result}"
        )


def test_estimate_prompt_tokens_empty_string_has_overhead():
    """Empty-content message contributes request framing + message overhead + role bytes."""
    result = estimate_prompt_tokens(_msgs(""))
    # REQUEST_FRAMING(16) + MSG_OVERHEAD(16) + role("user"=4) + content(0) = 36
    assert result == 36, f"Expected 36 for empty-content user message, got {result}"


def test_estimate_prompt_tokens_emoji_uses_byte_length():
    """Emoji (4 UTF-8 bytes per code point) count 4 tokens each, not 1.

    Final repair: 1 token per UTF-8 byte means a 4-byte emoji contributes 4 tokens,
    not 1.  This is deliberately pessimistic — it is always a safe upper bound.
    """
    single_emoji = "👋"      # 1 code point = 4 UTF-8 bytes → 4 tokens
    triple_emoji = "👋🎉🚀"   # 3 code points = 12 UTF-8 bytes → 12 tokens

    r_empty = estimate_prompt_tokens(_msgs(""))
    r_single = estimate_prompt_tokens(_msgs(single_emoji))
    r_triple = estimate_prompt_tokens(_msgs(triple_emoji))

    assert r_single == r_empty + 4, (
        f"Single emoji (4 bytes) must add exactly 4 over empty: "
        f"empty={r_empty}, single={r_single}"
    )
    assert r_triple == r_empty + 12, (
        f"Three emoji (12 bytes) must add exactly 12 over empty: "
        f"empty={r_empty}, triple={r_triple}"
    )


def test_estimate_prompt_tokens_cjk_uses_byte_length():
    """CJK characters (3 UTF-8 bytes each) count 3 tokens each, not 1.

    '日本語' = 3 CJK chars × 3 bytes = 9 bytes → 9 tokens.
    Old ceil(chars/4) approach: ceil(3/4) = 1 token — undercounts by 9×.
    """
    cjk = "日本語"   # 3 CJK chars × 3 bytes = 9 bytes
    r_cjk = estimate_prompt_tokens(_msgs(cjk))
    r_empty = estimate_prompt_tokens(_msgs(""))

    byte_count = len(cjk.encode("utf-8"))  # 9
    assert byte_count == 9, "Test precondition: 3 CJK chars = 9 UTF-8 bytes"
    assert r_cjk == r_empty + byte_count, (
        f"CJK estimate must be empty({r_empty}) + {byte_count} bytes = {r_empty + byte_count}, "
        f"got {r_cjk}"
    )


def test_estimate_prompt_tokens_code_heavy_prompt():
    """Code content with ASCII punctuation counts 1 token per char (all ASCII = 1 byte)."""
    code = 'def f(x): return {"k": [x+1, x-1], "ok": x>0}'   # 49 ASCII chars = 49 bytes
    r = estimate_prompt_tokens(_msgs(code))
    r_empty = estimate_prompt_tokens(_msgs(""))
    byte_count = len(code.encode("utf-8"))  # 49 for ASCII
    assert r == r_empty + byte_count, (
        f"Code estimate must be empty({r_empty}) + {byte_count} = {r_empty + byte_count}, "
        f"got {r}"
    )


def test_estimate_prompt_tokens_schema_overhead_added():
    """response_schema adds its JSON byte-count to the estimate."""
    from pydantic import BaseModel, Field

    class _Schema(BaseModel):
        title: str = Field(description="Title")
        tags: list[str] = Field(default=[])

    msgs = _msgs("Write a blog post about Python.")
    without_schema = estimate_prompt_tokens(msgs)
    with_schema = estimate_prompt_tokens(msgs, response_schema=_Schema)

    assert with_schema > without_schema, (
        f"Schema overhead must increase the estimate: "
        f"without={without_schema}, with={with_schema}"
    )


def test_estimate_prompt_tokens_schema_overhead_proportional_to_schema_size():
    """Larger schema JSON → larger estimate (byte-proportional)."""
    from pydantic import BaseModel, Field

    class _Small(BaseModel):
        x: int

    class _Large(BaseModel):
        title: str = Field(description="A very descriptive title for the blog post")
        tags: list[str] = Field(description="A list of SEO-relevant tags")
        audience: str = Field(description="Target audience description")
        sections: list[str] = Field(description="List of section headings")
        word_count: int = Field(ge=100, le=5000, description="Target word count")
        tone: str = Field(description="Writing tone for the post")
        angle: str = Field(description="Unique angle or perspective")

    msgs = _msgs("Test")
    r_small = estimate_prompt_tokens(msgs, response_schema=_Small)
    r_large = estimate_prompt_tokens(msgs, response_schema=_Large)

    assert r_large > r_small, (
        f"Larger schema must produce a larger estimate: small={r_small}, large={r_large}"
    )


def test_estimate_prompt_tokens_multiple_messages_each_add_overhead():
    """Each additional message adds exactly MSG_OVERHEAD(16) + role(4) + content bytes."""
    single = estimate_prompt_tokens(_msgs("hello"))   # 5 ASCII bytes
    double = estimate_prompt_tokens(_msgs("hello", "hello"))

    assert double > single, "Two messages must cost more than one"
    # Second identical message: MSG_OVERHEAD(16) + role("user"=4) + content(5) = 25
    assert double == single + 25, (
        f"Second message must add exactly 25 bytes: single={single}, double={double}"
    )


def test_estimate_prompt_tokens_returns_at_least_one():
    """Minimal and empty inputs still return at least 1."""
    assert estimate_prompt_tokens([]) >= 1
    assert estimate_prompt_tokens([{"role": "user"}]) >= 1          # missing content key
    assert estimate_prompt_tokens([{"role": "user", "content": ""}]) >= 1
    assert estimate_prompt_tokens([{"role": "user", "content": None}]) >= 1  # None → 0 bytes


def test_estimate_prompt_tokens_none_content_ok_zero_bytes():
    """None content is explicitly allowed and treated as 0 content bytes."""
    r_none = estimate_prompt_tokens([{"role": "user", "content": None}])
    r_empty = estimate_prompt_tokens([{"role": "user", "content": ""}])
    assert r_none == r_empty, (
        "None content must produce the same estimate as empty string"
    )


def test_estimate_prompt_tokens_non_str_content_raises():
    """Non-string, non-None content raises ValueError (fail-closed)."""
    with pytest.raises(ValueError, match="unsupported content type"):
        estimate_prompt_tokens([{"role": "user", "content": 42}])

    with pytest.raises(ValueError, match="unsupported content type"):
        estimate_prompt_tokens([{"role": "user", "content": ["a", "b"]}])

    with pytest.raises(ValueError, match="unsupported content type"):
        estimate_prompt_tokens([{"role": "user", "content": {"text": "hello"}}])


def test_estimate_prompt_tokens_schema_failure_raises_value_error():
    """If response_schema.model_json_schema() raises, ValueError is raised (not swallowed)."""
    class _BrokenSchema:
        def model_json_schema(self):
            raise RuntimeError("intentional serialisation failure")

    with pytest.raises(ValueError, match="failed to serialise response_schema"):
        estimate_prompt_tokens(_msgs("hi"), response_schema=_BrokenSchema())


def test_estimate_prompt_tokens_ascii_punctuation_one_byte_per_char():
    """ASCII punctuation is 1 byte per character → 1 token per char (same as letters)."""
    punctuation = "{}[]():,!@#$%^&*"  # 16 ASCII chars = 16 bytes
    assert len(punctuation) == 16   # self-documenting guard; edit string if count ever changes
    r = estimate_prompt_tokens(_msgs(punctuation))
    r_empty = estimate_prompt_tokens(_msgs(""))
    assert r == r_empty + 16, (
        f"16 ASCII punctuation chars (16 bytes) must add 16 to empty estimate: "
        f"empty={r_empty}, result={r}"
    )


def test_estimate_prompt_tokens_tools_overhead_added():
    """tools list adds its JSON byte-count to the estimate."""
    msgs = _msgs("hi")
    without_tools = estimate_prompt_tokens(msgs)
    with_tools = estimate_prompt_tokens(msgs, tools=[{"name": "search", "description": "search the web"}])
    assert with_tools > without_tools, (
        f"tools overhead must increase estimate: without={without_tools}, with={with_tools}"
    )
