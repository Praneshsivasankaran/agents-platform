"""``core.cost`` — the single INR cost-metering namespace (DESIGN §8).

Re-exports the public surface so callers write ``from core.cost import within_ceiling`` etc.

Eighth repair pass:
- Added resolve_is_mock from budget.py.

Seventh repair pass:
- Added CostCeilingExceeded, CallAuthorization, authorize_call from budget.py.
"""

from .budget import CallAuthorization, CostCeilingExceeded, authorize_call, resolve_is_mock
from .meter import (
    can_afford_stage,
    compute_max_tokens,
    count_prompt_tokens,
    estimate_for_stage,
    estimate_prompt_tokens,
    to_inr,
    total_cost_inr,
    usage_cost_inr,
    within_ceiling,
)

__all__ = [
    "CallAuthorization",
    "CostCeilingExceeded",
    "authorize_call",
    "resolve_is_mock",
    "can_afford_stage",
    "compute_max_tokens",
    "count_prompt_tokens",
    "estimate_for_stage",
    "estimate_prompt_tokens",
    "to_inr",
    "total_cost_inr",
    "usage_cost_inr",
    "within_ceiling",
]
