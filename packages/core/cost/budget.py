"""Centralized budget authorization for LLM calls (DESIGN §8).

Eighth repair pass:
- resolve_is_mock: validate provider/mock consistency at config-load time.
  If provider!='mock' but cost.is_mock=True, raise ValueError so a cloud overlay
  that accidentally inherits the mock bypass fails loudly at build time.
- authorize_call: fixed max_tokens derivation.  Token cap is now derived from
  the budget reserved for THIS call only:
    call_budget = ceiling - current_spend - downstream_reserve
  Previously it used (ceiling - current_spend) which included downstream budget
  and could allow the draft + all downstream stages to together exceed the ceiling.

Seventh repair pass:
- CostCeilingExceeded: typed exception for budget rejection, distinct from unexpected
  exceptions.  The graph error guard routes this to status='stopped_cost_ceiling', not
  'error'.
- CallAuthorization: frozen dataclass returned by authorize_call on approval.
- authorize_call: single shared pre-call gate.  Checks:
    current_spend + this_call_estimate + downstream_reserve <= ceiling_inr
  and derives a safe max_tokens cap from remaining headroom.
- Fail-closed: non-mock providers with output_cost_per_token_inr=0.0 raise ValueError
  before any LLM call is made (zero pricing would bypass the max_tokens safety cap).

Cloud-neutral: imports only from packages/core — no cloud SDK imports.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .meter import compute_max_tokens, estimate_for_stage, total_cost_inr


class CostCeilingExceeded(Exception):
    """Raised when a planned LLM call cannot fit within the remaining budget ceiling.

    This is a budget-rejection signal, NOT an unexpected error.  The graph error guard
    distinguishes it from generic exceptions:
      CostCeilingExceeded  → cost_gate_ok=False → stopped_cost_ceiling
      other exceptions     → error_state         → error

    Nodes do NOT catch this exception — they let it propagate so
    ``_node_with_error_guard`` handles routing.
    """


@dataclass(frozen=True)
class CallAuthorization:
    """Returned by authorize_call when the call is approved.

    Attributes
    ----------
    max_tokens:
        ``None`` — unpriced/mock tier (output_cost_per_token_inr=0.0 with is_mock=True);
                   no per-token cap can be derived from cost alone.
        ``int``  — output-token ceiling (>= 0) derived from the per-call budget
                   (ceiling - current_spend - downstream_reserve).
                   Pass as ``params={"max_tokens": v}`` to LLMProvider.respond().
    remaining_inr:
        Budget available exclusively for THIS call's output tokens after subtracting
        both current spend AND the downstream reserve from the ceiling.
        Downstream stages are NOT available to this call — using the full
        (ceiling - current_spend) window would allow total spend to exceed the ceiling.
    """
    max_tokens: int | None
    remaining_inr: float


def authorize_call(
    *,
    stage_name: str,
    stage_costs: list,
    ceiling_inr: float,
    estimated_costs: dict[str, float],
    downstream_stages: tuple[str, ...] | list[str] = (),
    output_cost_per_token_inr: float,
    input_cost_per_token_inr: float = 0.0,
    prompt_tokens_estimate: int = 0,
    fixed_cost_inr: float = 0.0,
    is_mock: bool = False,
) -> CallAuthorization:
    """Authorize or block a planned LLM call based on full pipeline budget.

    The authorization check is::

        current_spend + this_call_estimate + downstream_reserve <= ceiling_inr

    where ``downstream_reserve`` is the sum of estimates for all mandatory
    pipeline stages that follow this call.

    Per-call budget breakdown::

        call_budget   = ceiling_inr - current_spend - downstream_reserve
        total_reserve = input_reserve + fixed_cost_inr
        output_budget = max(0, call_budget - total_reserve)
        max_tokens    = int(output_budget / output_cost_per_token_inr)

    If ``output_budget <= 0`` (reserves consume the full call budget) →
    ``CostCeilingExceeded`` is raised BEFORE the provider is called, preventing
    input-token and fixed charges from being incurred with no output headroom.

    Parameters
    ----------
    stage_name:
        Name of the stage being authorized.  Must be a key in ``estimated_costs``.
    stage_costs:
        Current accumulated ``StageCost``-duck-typed objects (duck-typed: only
        ``cost_inr`` attribute is accessed).
    ceiling_inr:
        Hard budget ceiling in INR (must be a non-negative finite float).
    estimated_costs:
        Dict mapping stage names to conservative INR cost estimates.  Missing
        stage names raise ``ValueError`` (fail-closed — add to config).
    downstream_stages:
        Ordered list/tuple of mandatory pipeline stage names that follow this
        call.  Their estimates are summed to compute the downstream reserve.
    output_cost_per_token_inr:
        Per-output-token cost in INR.  Used to derive ``max_tokens``.
        For mock/free tiers: set to 0.0 AND pass ``is_mock=True``.
    input_cost_per_token_inr:
        Per-input-token cost in INR (default 0.0).  Multiplied by
        ``prompt_tokens_estimate`` to size the input reserve.  Nodes pass the
        ACTUAL prompt token count (counted after building messages) so the reserve
        precisely reflects the real prompt, not an arbitrary config ceiling.
    prompt_tokens_estimate:
        Conservative prompt-token estimate for this call (default 0).  Must be
        a non-boolean, non-negative int.  Nodes call ``estimate_prompt_tokens``
        (1 token per UTF-8 byte — guaranteed conservative) on the constructed
        messages and enforce the result is within the ``max_prompt_tokens``
        config limit before calling ``authorize_call``.
    fixed_cost_inr:
        Flat per-call cost in INR charged regardless of token counts (default 0.0).
        Use for providers that charge a per-request fee.  Subtracted from
        ``call_budget`` alongside the input reserve to prevent fixed charges from
        pushing the total above the ceiling.
    is_mock:
        ``True`` → skip the fail-closed non-zero pricing check (offline/mock runs).
        ``False`` → if output_cost_per_token_inr == 0.0, raise ``ValueError``
                   (fail-closed: real providers must supply pricing).

    Returns
    -------
    CallAuthorization
        Approved budget: max_tokens cap and remaining call-level headroom.

    Raises
    ------
    CostCeilingExceeded
        Budget rejection (not an unexpected error — routed to stopped_cost_ceiling):
        - Estimated total (current + stage + downstream) exceeds the ceiling.
        - Output budget exhausted by reserves (input + fixed costs); max_tokens=0.
    ValueError
        - Any pricing / token-count parameter is non-finite, negative, or invalid type.
        - ``is_mock=False`` and ``output_cost_per_token_inr=0.0`` (fail-closed).
        - ``stage_name`` or a downstream stage absent from ``estimated_costs``.
        - ``ceiling_inr`` is not a non-negative finite float.
    """
    # ── Validate ALL numeric inputs before any arithmetic ─────────────────────
    # Tenth repair: NaN/negative pricing silently corrupts output-budget/max_tokens.
    # Eleventh repair: prompt_tokens_estimate must be a real non-boolean integer.
    if not (math.isfinite(output_cost_per_token_inr) and output_cost_per_token_inr >= 0):
        raise ValueError(
            f"authorize_call: output_cost_per_token_inr={output_cost_per_token_inr!r} "
            f"must be a finite, non-negative float for stage '{stage_name}' "
            f"(a NaN/negative value would corrupt the max_tokens calculation)"
        )
    if not (math.isfinite(input_cost_per_token_inr) and input_cost_per_token_inr >= 0):
        raise ValueError(
            f"authorize_call: input_cost_per_token_inr={input_cost_per_token_inr!r} "
            f"must be a finite, non-negative float for stage '{stage_name}' "
            f"(a negative value would inflate the output budget above the call ceiling)"
        )
    if not (math.isfinite(fixed_cost_inr) and fixed_cost_inr >= 0):
        raise ValueError(
            f"authorize_call: fixed_cost_inr={fixed_cost_inr!r} "
            f"must be a finite, non-negative float for stage '{stage_name}'"
        )
    # Eleventh repair: bool is a subclass of int in Python; True/False must be rejected
    # because they are semantically wrong (True=1 token, False=0 tokens) and mask
    # misconfiguration.  Fractional floats are also rejected — token counts are integers.
    if isinstance(prompt_tokens_estimate, bool):
        raise ValueError(
            f"authorize_call: prompt_tokens_estimate must be a non-boolean int, "
            f"got bool ({prompt_tokens_estimate!r}) for stage '{stage_name}'"
        )
    if not isinstance(prompt_tokens_estimate, int):
        raise ValueError(
            f"authorize_call: prompt_tokens_estimate must be an int, "
            f"got {type(prompt_tokens_estimate).__name__} ({prompt_tokens_estimate!r}) "
            f"for stage '{stage_name}'"
        )
    if prompt_tokens_estimate < 0:
        raise ValueError(
            f"authorize_call: prompt_tokens_estimate={prompt_tokens_estimate!r} "
            f"must be >= 0 for stage '{stage_name}' "
            f"(a negative estimate would inflate the output budget)"
        )

    # ── Fail-closed: non-mock providers must supply real pricing ─────────────
    if not is_mock and output_cost_per_token_inr == 0.0:
        raise ValueError(
            f"authorize_call: output_cost_per_token_inr=0.0 for stage '{stage_name}' "
            f"with is_mock=False — set a real per-token price in "
            f"cost.output_cost_per_token_inr in config, or set cost.is_mock=true for "
            f"offline/free runs "
            f"(fail-closed: zero pricing would bypass the max_tokens safety cap)"
        )

    if not (math.isfinite(ceiling_inr) and ceiling_inr >= 0):
        raise ValueError(
            f"authorize_call: ceiling_inr={ceiling_inr!r} must be a non-negative finite float"
        )

    current = total_cost_inr(stage_costs)

    # This call's own worst-case budget impact
    this_call = estimate_for_stage(stage_name, estimated_costs)   # raises on unknown stage

    # Sum of mandatory downstream stage reserves
    reserve = sum(
        estimate_for_stage(s, estimated_costs) for s in downstream_stages
    )  # estimate_for_stage raises if any stage is absent

    total_needed = current + this_call + reserve
    if total_needed > ceiling_inr:
        raise CostCeilingExceeded(
            f"Budget ceiling ₹{ceiling_inr:.2f}: "
            f"current_spend(₹{current:.4f}) + stage_estimate(₹{this_call:.4f}) "
            f"+ downstream_reserve(₹{reserve:.4f}) = ₹{total_needed:.4f} "
            f"exceeds ceiling — stage '{stage_name}' cannot be authorized"
        )

    # Budget available for THIS call's output tokens only (eighth repair).
    # Downstream reserves must NOT be counted toward this call's token budget —
    # using (ceiling - current) would give the draft the full remaining window,
    # allowing current + draft_output + review to together exceed the ceiling.
    call_budget = max(0.0, ceiling_inr - current - reserve)

    # Eleventh repair: input reserve uses ACTUAL prompt-token count (passed by nodes
    # after constructing messages and enforcing the max_prompt_tokens limit).
    # fixed_cost_inr covers flat per-request provider fees (e.g. context-window charges).
    input_reserve = input_cost_per_token_inr * prompt_tokens_estimate
    total_reserve = input_reserve + fixed_cost_inr
    output_budget = max(0.0, call_budget - total_reserve)

    max_tokens = compute_max_tokens(
        output_budget, output_cost_per_token_inr=output_cost_per_token_inr
    )

    # max_tokens=0 means reserves have consumed all call budget — no room for output.
    # Calling the provider would still incur input + fixed charges with zero output.
    # Raise CostCeilingExceeded here (pre-call) rather than incurring those charges.
    # max_tokens=None is the mock/free tier (output_cost_per_token_inr=0.0); valid.
    if max_tokens is not None and max_tokens == 0:
        raise CostCeilingExceeded(
            f"Budget ceiling ₹{ceiling_inr:.2f}: "
            f"no output-token headroom for stage '{stage_name}' "
            f"(call_budget=₹{call_budget:.4f}, "
            f"input_reserve=₹{input_reserve:.4f} [{prompt_tokens_estimate} tokens "
            f"× ₹{input_cost_per_token_inr}/token], "
            f"fixed_cost=₹{fixed_cost_inr:.4f}, "
            f"output_budget=₹{output_budget:.4f}) — "
            f"provider call blocked before incurring input/fixed charges"
        )

    return CallAuthorization(max_tokens=max_tokens, remaining_inr=call_budget)


def resolve_is_mock(cfg: dict) -> bool:
    """Validate and resolve whether this config represents a mock/free-tier run.

    Ninth repair: checks ``llm.provider`` (the key read by ``get_llm_provider()``)
    as the authoritative source, falling back to the top-level ``provider`` for
    backwards-compat with test configs that set only the top-level key.

    Eighth repair: validates consistency — a non-mock LLM provider that inherits
    ``cost.is_mock=True`` from base.yaml fails loudly at build time.

    Rules (in priority order)
    -------------------------
    - ``llm.provider='mock'`` OR ``provider='mock'``
        → True (mock declared)
    - llm/top-level provider is a non-mock cloud string + ``cost.is_mock=True``
        → **ValueError** — cloud overlay forgot to clear the mock bypass
    - provider absent (offline test config) + ``cost.is_mock=True``
        → True (legacy test signal, no cloud provider to validate against)
    - otherwise
        → False

    Parameters
    ----------
    cfg:
        Full agent config dict (the same dict passed to ``build_graph``).

    Raises
    ------
    ValueError
        Provider/mock consistency mismatch: the resolved LLM provider is a
        non-mock cloud string while ``cost.is_mock=True``.
    """
    cost_cfg = cfg.get("cost", {})
    # llm.provider is what get_llm_provider() reads — authoritative for LLM mock status.
    # Fall back to top-level provider for backwards-compat with test configs.
    llm_provider: str = cfg.get("llm", {}).get("provider", "")
    top_provider: str = cfg.get("provider", "")
    provider: str = llm_provider or top_provider   # llm.provider takes precedence
    cost_is_mock: bool = bool(cost_cfg.get("is_mock", False))

    if provider == "mock":
        return True
    # Only raise if provider is explicitly a non-mock cloud name AND is_mock=True.
    # An empty/absent provider key (offline test configs without an explicit provider)
    # is allowed through — those rely solely on cost.is_mock.
    if provider and cost_is_mock:
        raise ValueError(
            f"Configuration error: cost.is_mock=True with LLM provider='{provider}'. "
            f"A cloud overlay must set cost.is_mock=false (or omit it — false is "
            f"the safe default) to prevent the mock bypass from being inherited."
        )
    return cost_is_mock
