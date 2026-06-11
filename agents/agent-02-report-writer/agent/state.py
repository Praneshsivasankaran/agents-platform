"""ReportWriterState — the LangGraph graph state for Report Writing Agent (generated skeleton).

Specialize this: add intermediate-artifact fields produced between intake and finalize.
Accumulators MUST use ``operator.add`` (never last-write-wins) so concurrent/looping nodes
append rather than clobber.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from .schemas import StageCost, ReportWriterPackage


class ReportWriterState(TypedDict, total=False):
    # ---- input ----
    raw_input: str
    input_type: str  # "text" in the skeleton; add "voice"/"video" when the agent needs media

    # ---- intermediate artifacts (add your stages here) ----
    result: str

    # ---- accumulators (operator.add — never last-write-wins) ----
    cost_usage: Annotated[list[StageCost], operator.add]

    # ---- cost-gate routing (set False by the graph guard on a ceiling breach) ----
    cost_gate_ok: bool

    # ---- error routing (routes to finalize when set) ----
    error_state: dict[str, Any]

    # ---- terminal ----
    status: str
    final_output: ReportWriterPackage
