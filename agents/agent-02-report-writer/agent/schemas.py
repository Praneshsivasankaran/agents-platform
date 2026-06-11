"""Typed I/O contracts for Report Writing Agent (generated skeleton).

All models subclass ``CoreContractModel`` (frozen + extra=forbid + deeply immutable) per the
platform's typed-I/O rule. Specialize ``ReportWriterPackage`` with the fields your agent emits.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from core import CoreContractModel


class StageCost(CoreContractModel):
    """One billable (or synthetic) stage's cost, feeding the central ledger (core.cost)."""

    stage: str
    cost_inr: float = Field(ge=0.0)
    tier: Literal["cheap", "strong", "stt", "none"]
    tokens_prompt: int = Field(default=0, ge=0)
    tokens_completion: int = Field(default=0, ge=0)


class CostUsage(CoreContractModel):
    """Invariant: ``total_inr`` equals ``sum(stage_costs.cost_inr)`` within 1-paisa tolerance."""

    stage_costs: tuple[StageCost, ...] = Field(default=())
    total_inr: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _total_matches_ledger(self) -> "CostUsage":
        computed = sum(sc.cost_inr for sc in self.stage_costs)
        if abs(computed - self.total_inr) > 0.01:
            raise ValueError("CostUsage.total_inr must equal sum(stage_costs.cost_inr)")
        return self


class ReportWriterPackage(CoreContractModel):
    """Terminal output of Report Writing Agent (draft-only in v1 — no publishing/CMS/social)."""

    status: Literal["pass", "needs_human", "stopped_cost_ceiling", "error"]
    cost: CostUsage
    result: str = ""
    notes: str = ""


class BillableNodeError(Exception):
    """Raised when post-response processing fails AFTER a billable LLM call.

    Carries the incurred ``StageCost`` so the graph guard can preserve it in the ledger — without
    this, a telemetry/parse error following a successful (billed) call would silently drop the
    cost and produce a falsely-compliant ``total_inr``. Exposes only the exception TYPE name
    (raw messages may contain sensitive content).
    """

    def __init__(self, stage_cost: "StageCost", cause: Exception) -> None:
        self.stage_cost = stage_cost
        self.cause = cause
        super().__init__(f"BillableNodeError wrapping {type(cause).__name__}")
