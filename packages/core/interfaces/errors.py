"""
Provider-neutral exceptions for cost-accountable provider failures.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.interfaces.usage import Usage


# Allowlisted, content-free failure categories. Never derived from exception class
# names (dynamically-named classes can embed data), never from raw messages.
BILLABLE_FAILURE_CATEGORIES = frozenset({
    "provider_call_failed",      # litellm.completion() raised (timeout/network/etc.)
    "usage_extraction_failed",   # usage object missing/malformed
    "cost_computation_failed",   # cost could not be computed
    "response_shape_invalid",    # choices/message/content missing or wrong type
    "response_empty",            # content empty/whitespace
    "json_parse_failed",         # structured output not valid JSON
    "schema_validation_failed",  # JSON did not match schema
    "unknown",                   # fallback — must still be content-free
})


class BillableProviderError(Exception):
    """
    Raised when a provider call incurred (or may have incurred) cost but
    subsequent processing failed.

    Carries ONLY content-free information:
    - ``usage``: the incurred/estimated Usage (tokens + cost)
    - ``category``: an allowlisted failure category string (never an exception
      object, never a dynamic class name, never a raw message)

    The original exception is never stored. Callers MUST NOT use
    ``raise BillableProviderError(...) from exc`` (that re-attaches ``__cause__``).
    Construct inside the except block, then raise after leaving it so that
    ``__cause__`` and ``__context__`` are both ``None`` (no implicit chaining).
    """

    def __init__(self, usage: "Usage", category: str) -> None:
        if category not in BILLABLE_FAILURE_CATEGORIES:
            category = "unknown"
        self.usage = usage
        self.category: str = category
        super().__init__(
            f"billable-provider-failure:{category} "
            f"prompt_tokens={usage.prompt_tokens} "
            f"completion_tokens={usage.completion_tokens} "
            f"cost_native={usage.cost_native:.6f}{usage.currency}"
        )

    def __reduce__(self):
        # Reconstruct from content-free state only (usage + allowlisted category).
        return (self.__class__, (self.usage, self.category))
