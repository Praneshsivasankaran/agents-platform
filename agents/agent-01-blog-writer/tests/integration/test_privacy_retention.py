"""Retention & privacy contract — end-to-end (Cycle 4, item 7).

These complement (do not duplicate) the unit-level guarantees already in place:
  - StdoutTelemetry redaction is unit-tested exhaustively in packages/core/tests/test_mock_providers.py
  - Transient GCS object deletion (success / provider-failure / cleanup-failure) is covered in
    packages/core/tests/test_gcp_transcription.py
  - transcribe-node temp-audio deletion on span entry/exit failure is in tests/unit/test_transcribe_node.py

What is NEW here is the END-TO-END contract: when the real graph runs on actual user content,
(1) that content never reaches the telemetry stream, and (2) extracted temporary audio is removed
after the run — i.e. the nodes actually route everything through the redacting sink and the
cleanup `finally` actually fires in a full graph invocation, not just in isolation.
"""
from __future__ import annotations

import copy
import io
import os
import tempfile
from typing import Any
from unittest.mock import patch

from core.media.extract_audio import _OWNED_TEMP_PREFIX
from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry
from core.providers.mock.transcription import MockTranscriptionProvider

from agent.graph import build_graph
from agent.schemas import BlogPackage

_SENTINEL = "ZZ_SECRET_USER_CONTENT_PII_4242_ZZ"

_CFG: dict[str, Any] = {
    "provider": "mock",
    "service": "privacy-test",
    "llm": {"provider": "mock", "tier_models": {"cheap": "mock/cheap", "strong": "mock/strong"}},
    "cost": {
        "ceiling_inr": 50.0,
        "is_mock": True,
        "fx_rates": {"USD": 83.0},
        "estimated_stage_cost_inr": {
            "normalize": 0.3, "extract_ideas": 0.3, "plan": 0.5,
            "draft": 12.0, "review": 6.0, "transcribe": 5.0,
        },
        "output_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
        "input_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
        "fixed_cost_inr": {"cheap": 0.0, "strong": 0.0},
        "max_prompt_tokens": {"cheap": 16384, "strong": 32768},
    },
    "graph": {"max_revision_cycles": 2},
    "object_storage": {"provider": "mock"},
    "secret_store": {"provider": "env"},
    "transcription": {"provider": "mock"},
}


def _cfg(**overrides) -> dict[str, Any]:
    cfg = copy.deepcopy(_CFG)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    return cfg


# ---------------------------------------------------------------------------
# Privacy: raw user content never reaches the telemetry stream
# ---------------------------------------------------------------------------

def test_text_raw_input_never_appears_in_telemetry():
    buf = io.StringIO()
    tel = StdoutTelemetry(service="privacy-test", stream=buf)
    graph = build_graph(_cfg(), MockLLMProvider(default_scenario="pass"), tel)
    pkg: BlogPackage = graph.invoke(
        {"raw_input": f"AI in healthcare. {_SENTINEL} more text.", "input_type": "text"}
    )["final_output"]

    telemetry_output = buf.getvalue()
    assert telemetry_output, "telemetry should have emitted records"
    assert _SENTINEL not in telemetry_output, (
        "raw user input leaked into the telemetry stream — content must never be logged"
    )
    # And the generated draft body must not be logged verbatim either.
    if pkg.full_draft and len(pkg.full_draft) > 20:
        assert pkg.full_draft not in telemetry_output, "draft body leaked into telemetry"


def test_voice_transcript_never_appears_in_telemetry():
    buf = io.StringIO()
    tel = StdoutTelemetry(service="privacy-test", stream=buf)
    graph = build_graph(_cfg(), MockLLMProvider(default_scenario="pass"), tel, MockTranscriptionProvider())
    graph.invoke({"raw_input": "privacy_voice.wav", "input_type": "voice"})["final_output"]

    telemetry_output = buf.getvalue()
    # Distinctive phrase from the canned mock voice transcript.
    assert "cloud-agnostic AI agents" not in telemetry_output, (
        "spoken transcript content leaked into the telemetry stream"
    )


def test_sensitive_keys_redacted_even_if_a_node_tried_to_log_content():
    """Defense-in-depth: even a direct attempt to log content-bearing keys is redacted.
    (Backstops the per-node 'never pass content to telemetry' discipline.)"""
    buf = io.StringIO()
    tel = StdoutTelemetry(service="privacy-test", stream=buf)
    tel.log("node.complete", raw_input=_SENTINEL, transcript=_SENTINEL, draft=_SENTINEL)
    out = buf.getvalue()
    assert _SENTINEL not in out
    assert "[REDACTED]" in out


# ---------------------------------------------------------------------------
# Retention: extracted temporary audio is removed after a full graph run
# ---------------------------------------------------------------------------

def test_voice_run_deletes_extracted_temp_audio_end_to_end():
    """With voice normalization enabled, the node extracts audio to a temp file and must
    delete it in its `finally` — verified after a COMPLETE graph invocation."""
    created: dict[str, str] = {}

    def fake_extract_audio(audio_ref, *, out_format="wav", max_duration_s=None):
        # Create a real temp file matching the owned-temp contract so the node's
        # delete_extracted_audio() will actually remove it.
        fd, path = tempfile.mkstemp(suffix=".wav", prefix=_OWNED_TEMP_PREFIX)
        with os.fdopen(fd, "wb") as fh:
            fh.write(b"\x00\x00" * 16000)  # ~nonempty WAV-ish bytes
        created["path"] = path
        assert os.path.exists(path)
        return path

    cfg = _cfg(transcription={"provider": "mock", "normalize_voice": True})
    buf = io.StringIO()
    tel = StdoutTelemetry(service="privacy-test", stream=buf)
    graph = build_graph(cfg, MockLLMProvider(default_scenario="pass"), tel, MockTranscriptionProvider())

    with patch("agent.nodes.transcribe.extract_audio", side_effect=fake_extract_audio):
        graph.invoke({"raw_input": "privacy_voice.wav", "input_type": "voice"})["final_output"]

    assert created.get("path"), "fake extract_audio was not invoked — test did not exercise cleanup"
    assert not os.path.exists(created["path"]), (
        "extracted temp audio was NOT deleted after the graph run — media retention contract broken"
    )
    # And the temp path itself must not have leaked into telemetry.
    assert created["path"] not in buf.getvalue()
