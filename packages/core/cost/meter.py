"""Cost metering helpers — the single place provider-native cost becomes INR (DESIGN §8).

ONE cost path for ALL billable providers: both ``LLMProvider`` and ``TranscriptionProvider``
return a ``Usage`` (provider-native amount + currency), and these helpers convert to INR and
enforce the Rs.50/blog ceiling uniformly — there are no separate per-provider cost paths.

``Usage`` already precludes negative cost/tokens/duration (``ge=0``); these helpers additionally
**fail closed** on currency problems (see ``to_inr``) and on non-finite/negative cost arguments
(see ``within_ceiling``).

Cloud-neutral by construction — imports only Pydantic (via ``Usage``) + the standard library.
"""

from __future__ import annotations

import json
import math

from ..interfaces.usage import Usage


def to_inr(amount: float, *, currency: str, fx_rates: dict[str, float]) -> float:
    """Convert a provider-native ``amount`` in ``currency`` to INR using config-supplied FX rates.

    ``fx_rates`` maps a currency code (uppercase) to its INR rate (e.g. ``{"USD": 83.0}``).
    **Fail closed:** if ``currency`` is missing/blank or absent from ``fx_rates``, raises
    ``ValueError`` — it must never default an unknown currency to ``0`` or silently skip it.
    An unconverted cost would understate the ledger and defeat the Rs.50/blog ceiling.
    """
    if not currency or not currency.strip():
        raise ValueError(
            "to_inr: currency must not be empty; a billable Usage must supply its currency "
            "(fail-closed — no implicit USD default)"
        )
    key = currency.strip().upper()
    if key not in fx_rates:
        raise ValueError(
            f"to_inr: unknown currency {key!r}; add it to cost.fx_rates in config "
            f"(fail-closed — available: {sorted(fx_rates)})"
        )
    rate = fx_rates[key]
    # Issue 2 Fix E: Reject zero, non-finite, or negative FX rates at conversion time.
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError(
            f"CostMeter: fx_rate={rate!r} must be finite and > 0 "
            f"(prevent silent ₹0 conversion) — "
            f"fx_rate for {key!r}={rate!r} in cost.fx_rates is invalid"
        )
    return amount * rate


def usage_cost_inr(usage: Usage, *, fx_rates: dict[str, float]) -> float:
    """INR cost of a single billable call — identical for LLM and transcription ``Usage``.

    If ``usage.cost_native == 0`` the cost is ``0.0`` INR and no currency is needed (``Usage``
    permits a ``None`` currency only when ``cost_native == 0``). Otherwise ``usage.currency`` is
    guaranteed present by the ``Usage`` invariant and is converted via ``to_inr`` — fail-closed
    on an unknown currency. Inputs are non-negative by the ``Usage`` contract, so the result is
    non-negative.
    """
    if usage.cost_native == 0.0:
        return 0.0
    # usage.currency is non-None here (guaranteed by Usage._currency_required_when_billable)
    return to_inr(usage.cost_native, currency=usage.currency or "", fx_rates=fx_rates)


def within_ceiling(spent_inr: float, next_call_inr: float, *, ceiling_inr: float = 50.0) -> bool:
    """Cost-gate check (DESIGN §1.3, §8): does the next billable step fit under the ceiling?

    Returns ``True`` iff ``spent_inr + next_call_inr <= ceiling_inr``.  Called before each
    strong-tier node and at the escalation decision.  Uses config-based fixed stage estimates
    (``estimated_stage_cost_inr``) for ``next_call_inr`` in v1.

    Validation (fail-closed):
    - ``spent_inr`` and ``next_call_inr`` must be non-negative finite floats.
    - ``ceiling_inr`` must be a non-negative finite float.
    Negative or non-finite values would bypass the ceiling silently; raising is the
    only safe behaviour.
    """
    if not (math.isfinite(spent_inr) and spent_inr >= 0):
        raise ValueError(
            f"within_ceiling: spent_inr={spent_inr!r} must be a non-negative finite float"
        )
    if not (math.isfinite(next_call_inr) and next_call_inr >= 0):
        raise ValueError(
            f"within_ceiling: next_call_inr={next_call_inr!r} must be a non-negative finite float"
        )
    if not (math.isfinite(ceiling_inr) and ceiling_inr >= 0):
        raise ValueError(
            f"within_ceiling: ceiling_inr={ceiling_inr!r} must be a non-negative finite float"
        )
    return spent_inr + next_call_inr <= ceiling_inr


def total_cost_inr(stage_costs: list) -> float:
    """Sum the ``cost_inr`` field across a list of ``StageCost``-duck-typed objects.

    The ``StageCost`` schema lives with the agent's typed contracts (DESIGN §7); this helper
    operates on any sequence of objects that expose a ``cost_inr: float`` attribute so it stays
    cloud-neutral and agent-agnostic.
    """
    return sum(getattr(sc, "cost_inr", 0.0) for sc in stage_costs)


def estimate_prompt_tokens(
    messages: list,
    response_schema=None,
    tools: list | None = None,
) -> int:
    """Conservative upper-bound estimate of provider-billed input tokens.

    Uses **one token per UTF-8 byte** as the pessimistic bound.  This over-estimates
    for typical English text (real tokenisers give ~1 token per 3–4 chars) but
    **guarantees the estimate never falls below the actual token count** for any
    input encoding — the fundamental requirement for a safe input-cost reserve.

    Methodology
    -----------
    - **1 token per UTF-8 byte** for all textual content (message bodies, role names,
      schema/tool JSON).  Guaranteed conservative: every known BPE tokeniser produces
      at most one token per byte (a multi-byte sequence is always a single token, never
      more than one per byte).  Dividing by 4 would under-count short strings, ASCII
      punctuation, and code-heavy content where each character may tokenise separately.
    - **Per-message framing** (``_OVERHEAD_BYTES_PER_MESSAGE``) covering chat-template
      start/end markers (e.g. ``<|im_start|>…<|im_end|>`` adds ~20 bytes per turn;
      16 is a conservative floor for most formats).
    - **Request framing** (``_REQUEST_FRAMING_BYTES``) for the overall JSON wrapper
      and request-start tokens billed as input.
    - **Response-schema overhead**: structured calls embed the Pydantic JSON schema as
      a system instruction or tool definition.  When ``response_schema`` is not ``None``
      the schema is serialised to compact JSON and counted as additional prompt bytes.
      **Serialisation failure raises ``ValueError``** — an unknown schema size cannot be
      bounded conservatively.
    - **Tools overhead**: ``tools`` (if supplied) are serialised to compact JSON.
      Serialisation failure raises ``ValueError``.
    - **Non-string content raises ``ValueError``** — an unknown type has an unknown byte
      size; treating it as 0 would under-count tokens and corrupt the cost reserve.
      ``None`` is the only acceptable non-string value (treated as 0 bytes, representing
      a missing/empty content field).

    Returns at least 1.

    Raises
    ------
    ValueError
        - ``messages`` contains a non-string, non-None ``content`` value.
        - ``response_schema.model_json_schema()`` raises (serialisation failure).
        - ``tools`` cannot be serialised to compact JSON.
    """
    _OVERHEAD_BYTES_PER_MESSAGE: int = 16   # chat-template framing bytes per turn
    _REQUEST_FRAMING_BYTES: int = 16        # overall request envelope bytes

    total: int = _REQUEST_FRAMING_BYTES

    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if content is None:
            content_bytes = 0
        elif isinstance(content, str):
            content_bytes = len(content.encode("utf-8"))
        else:
            raise ValueError(
                f"estimate_prompt_tokens: unsupported content type "
                f"{type(content).__name__!r} in message with role={role!r}; "
                "message content must be a str or None — other types have an "
                "unknown byte size and cannot be counted conservatively"
            )
        role_bytes: int = len(role.encode("utf-8")) if isinstance(role, str) else 0
        total += _OVERHEAD_BYTES_PER_MESSAGE + role_bytes + content_bytes

    if response_schema is not None:
        try:
            schema_str: str = json.dumps(
                response_schema.model_json_schema(),
                separators=(",", ":"),
                ensure_ascii=False,
            )
        except Exception as exc:
            raise ValueError(
                f"estimate_prompt_tokens: failed to serialise response_schema "
                f"{type(response_schema).__name__!r} to JSON — cannot produce a "
                f"conservative token estimate without knowing the schema byte size: "
                f"{type(exc).__name__}"
            ) from exc
        total += _OVERHEAD_BYTES_PER_MESSAGE + len(schema_str.encode("utf-8"))

    if tools is not None:
        try:
            tools_str: str = json.dumps(tools, separators=(",", ":"), ensure_ascii=False)
        except Exception as exc:
            raise ValueError(
                f"estimate_prompt_tokens: failed to serialise tools list to JSON: "
                f"{type(exc).__name__}"
            ) from exc
        total += _OVERHEAD_BYTES_PER_MESSAGE + len(tools_str.encode("utf-8"))

    return max(1, total)


# Backward-compatible alias.  ``count_prompt_tokens`` implied an exact count
# (it was not); prefer ``estimate_prompt_tokens`` for new call-sites.
count_prompt_tokens = estimate_prompt_tokens


def estimate_for_stage(stage_name: str, estimated_costs: dict[str, float]) -> float:
    """Look up the cost estimate for ``stage_name``; raise ``ValueError`` if missing (fail-closed).

    **Fail-closed by design:** defaulting an unknown stage to 0 would allow unlimited budget
    consumption for unregistered stages, defeating the Rs.50/blog ceiling.  Callers must add
    every billable stage to ``cost.estimated_stage_cost_inr`` in config before using it.
    """
    if stage_name not in estimated_costs:
        raise ValueError(
            f"No cost estimate configured for stage '{stage_name}'; "
            f"add it to cost.estimated_stage_cost_inr in config "
            f"(fail-closed — known stages: {sorted(estimated_costs)})"
        )
    estimate = float(estimated_costs[stage_name])
    if not (math.isfinite(estimate) and estimate >= 0):
        raise ValueError(
            f"estimate_for_stage: estimate for '{stage_name}'={estimate!r} must be a "
            f"non-negative finite float (a negative or infinite estimate would corrupt "
            f"the cost gate)"
        )
    return estimate


def compute_max_tokens(remaining_inr: float, *, output_cost_per_token_inr: float) -> int | None:
    """Derive a per-call ``max_tokens`` limit from remaining budget headroom (DESIGN §8).

    Converts remaining INR headroom to a worst-case token count ceiling using the
    configured output cost per token.  Pass the result as ``params={"max_tokens": v}``
    to ``LLMProvider.respond()`` — LiteLLM, Vertex, and Bedrock all honour ``max_tokens``
    in request params so the provider enforces it at the API level.

    Returns
    -------
    None  — ``output_cost_per_token_inr`` is 0.0 (unpriced / mock tier); no cap derivable.
    0     — remaining_inr is 0; budget exhausted, the caller should block the API call.
    int   — token ceiling (>= 1) that fits within remaining budget.

    Validation (fail-closed): both arguments must be non-negative finite floats; raises
    ``ValueError`` otherwise.  A corrupt value must never silently skip the per-call cap.
    """
    if not (math.isfinite(output_cost_per_token_inr) and output_cost_per_token_inr >= 0):
        raise ValueError(
            f"compute_max_tokens: output_cost_per_token_inr={output_cost_per_token_inr!r} "
            "must be a non-negative finite float"
        )
    if not (math.isfinite(remaining_inr) and remaining_inr >= 0):
        raise ValueError(
            f"compute_max_tokens: remaining_inr={remaining_inr!r} "
            "must be a non-negative finite float"
        )
    if output_cost_per_token_inr == 0.0:
        return None  # unpriced tier — no per-token cap can be derived from cost alone
    return max(0, int(remaining_inr / output_cost_per_token_inr))


def can_afford_stage(
    stage_costs: list,
    stage_name: str,
    estimated_costs: dict[str, float],
    ceiling_inr: float,
) -> bool:
    """Return True iff the budget permits running ``stage_name`` next.

    ``estimated_costs`` maps stage names to fixed INR estimates (from
    ``cost.estimated_stage_cost_inr`` in config).  **Raises ``ValueError``** if
    ``stage_name`` is absent — defaulting unknown stages to 0 would silently defeat the
    Rs.50/blog ceiling (fail-closed, DESIGN §8).
    """
    current_total = total_cost_inr(stage_costs)
    estimate = estimate_for_stage(stage_name, estimated_costs)  # raises on unknown stage
    return within_ceiling(current_total, estimate, ceiling_inr=ceiling_inr)
