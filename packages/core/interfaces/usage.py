"""Usage — the SINGLE billing + token-accounting contract for one billable call.

Returned by every billable provider (``LLMProvider`` AND ``TranscriptionProvider``) so one
cost meter (``core.cost.meter``) can convert provider-native currency to INR and enforce the
₹50/blog ceiling uniformly (DESIGN §8). There is deliberately ONE cost path, not separate
per-provider paths.

Typed I/O per the platform rule: Pydantic. Cloud-neutral by construction — imports only
Pydantic + the standard library; never a cloud SDK.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from .base import CoreContractModel


class Usage(CoreContractModel):
    """Provider-native cost + usage for a single billable call.

    **Immutable + copy-safe** (via ``CoreContractModel``): cannot be mutated, and
    ``model_copy(update=...)`` revalidates — so it can never be coerced into an invalid state that
    would undermine the running ledger or the ₹50/blog ceiling.

    All quantities are **non-negative and finite** (``ge=0``, ``allow_inf_nan=False`` — rejects
    ``inf`` / ``-inf`` / ``nan``). ``currency`` has **no default** and is normalized (stripped +
    upper-cased); it **must be supplied whenever ``cost_native > 0``** — a missing or blank currency
    on a billable call is rejected (fail-closed; never implicitly USD, never silently zero).
    Conversion to INR happens centrally in ``core.cost`` (fail-closed on an unknown currency).
    ``synthetic=True`` marks mock/offline usage so it is never mistaken for a real billed call.
    """

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    audio_seconds: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    cost_native: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    # No default: a billable call MUST name its currency (see validator below). None is allowed
    # only for non-billable usage (cost_native == 0, e.g. free/synthetic).
    currency: str | None = None
    synthetic: bool = False

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if not v:
            raise ValueError("currency must not be blank/whitespace-only")
        return v

    @model_validator(mode="after")
    def _currency_required_when_billable(self) -> "Usage":
        if self.cost_native > 0 and not self.currency:
            raise ValueError(
                "currency is required when cost_native > 0 "
                "(fail-closed; no implicit USD default, never treated as zero)"
            )
        return self
