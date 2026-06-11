"""intake node — validate input before any billable work (generated skeleton)."""
from __future__ import annotations

from typing import Any

from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider

from ..state import ReportWriterState


def make_intake_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = llm  # signature consistency; intake does not call the model

    def intake(state: ReportWriterState) -> dict[str, Any]:
        with tel.span("intake") as span_id:
            raw = state.get("raw_input", "")
            if not isinstance(raw, str) or not raw.strip():
                tel.log("intake.invalid_input", span_id=span_id)
                return {
                    "error_state": {
                        "node": "intake",
                        "kind": "invalid_input",
                        "message": "raw_input must be a non-empty string",
                    }
                }
            tel.log("intake.accepted", span_id=span_id)
            return {}

    return intake
