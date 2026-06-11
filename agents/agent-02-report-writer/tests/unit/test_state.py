"""Unit test: graph state shape (generated skeleton)."""
from __future__ import annotations

from agent.state import ReportWriterState


def test_state_has_core_fields():
    ann = ReportWriterState.__annotations__
    for field in ("raw_input", "cost_usage", "cost_gate_ok", "error_state", "status", "final_output"):
        assert field in ann
