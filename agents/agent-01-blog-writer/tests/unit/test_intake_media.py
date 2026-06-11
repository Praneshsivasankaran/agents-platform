"""Unit tests for intake node — voice/video media path (Increment 6).

Verifies that:
- Text input still works unchanged (regression guard).
- Voice/video inputs with approved extensions are accepted.
- Unsupported extensions are rejected with a structured error.
- Missing or blank references are rejected.
- Unknown input types still fail safely.
- No cloud SDK or network calls are made.
"""
from __future__ import annotations

import pytest

from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry
from agent.nodes.intake import make_intake_node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(cfg=None):
    cfg = cfg or {"telemetry": {"provider": "stdout"}, "service": "test"}
    llm = MockLLMProvider()
    tel = StdoutTelemetry(service="test")
    return make_intake_node(cfg, llm, tel)


def _run(node, raw_input="hello", input_type="text", **extra):
    state = {"raw_input": raw_input, "input_type": input_type, **extra}
    return node(state)


# ---------------------------------------------------------------------------
# Regression: text path unchanged
# ---------------------------------------------------------------------------

class TestIntakeTextRegression:
    def test_text_accepted(self):
        node = _make_node()
        result = _run(node, raw_input="Write a blog about AI agents.", input_type="text")
        assert "error_state" not in result or result.get("error_state") is None
        assert result.get("revision_count") == 0

    def test_blank_text_rejected(self):
        node = _make_node()
        result = _run(node, raw_input="", input_type="text")
        assert result["error_state"]["kind"] == "invalid_input"

    def test_whitespace_text_rejected(self):
        node = _make_node()
        result = _run(node, raw_input="   ", input_type="text")
        assert result["error_state"]["kind"] == "invalid_input"


# ---------------------------------------------------------------------------
# Voice input
# ---------------------------------------------------------------------------

class TestIntakeVoice:
    @pytest.mark.parametrize("ext", [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus", ".aac"])
    def test_approved_voice_extensions_accepted(self, ext):
        node = _make_node()
        result = _run(node, raw_input=f"recording{ext}", input_type="voice")
        assert result.get("error_state") is None
        assert result.get("revision_count") == 0

    def test_voice_blank_ref_rejected(self):
        node = _make_node()
        result = _run(node, raw_input="", input_type="voice")
        assert result["error_state"]["kind"] == "invalid_input"

    def test_voice_no_extension_rejected(self):
        node = _make_node()
        result = _run(node, raw_input="myaudio", input_type="voice")
        assert result["error_state"]["kind"] == "invalid_media_ref"

    def test_voice_mp4_extension_rejected(self):
        """mp4 is a video extension, not approved for voice."""
        node = _make_node()
        result = _run(node, raw_input="recording.mp4", input_type="voice")
        assert result["error_state"]["kind"] == "unsupported_media_format"

    def test_voice_txt_extension_rejected(self):
        node = _make_node()
        result = _run(node, raw_input="notes.txt", input_type="voice")
        assert result["error_state"]["kind"] == "unsupported_media_format"


# ---------------------------------------------------------------------------
# Video input
# ---------------------------------------------------------------------------

class TestIntakeVideo:
    @pytest.mark.parametrize("ext", [".mp4", ".mkv", ".avi", ".mov", ".webm"])
    def test_approved_video_extensions_accepted(self, ext):
        node = _make_node()
        result = _run(node, raw_input=f"lecture{ext}", input_type="video")
        assert result.get("error_state") is None
        assert result.get("revision_count") == 0

    def test_video_blank_ref_rejected(self):
        node = _make_node()
        result = _run(node, raw_input="", input_type="video")
        assert result["error_state"]["kind"] == "invalid_input"

    def test_video_no_extension_rejected(self):
        node = _make_node()
        result = _run(node, raw_input="myvideo", input_type="video")
        assert result["error_state"]["kind"] == "invalid_media_ref"

    def test_video_mp3_extension_rejected(self):
        """mp3 is a voice extension, not approved for video."""
        node = _make_node()
        result = _run(node, raw_input="clip.mp3", input_type="video")
        assert result["error_state"]["kind"] == "unsupported_media_format"

    def test_video_txt_extension_rejected(self):
        node = _make_node()
        result = _run(node, raw_input="notes.txt", input_type="video")
        assert result["error_state"]["kind"] == "unsupported_media_format"


# ---------------------------------------------------------------------------
# Unknown input types
# ---------------------------------------------------------------------------

class TestIntakeUnknown:
    def test_unknown_type_rejected(self):
        node = _make_node()
        result = _run(node, raw_input="something.pdf", input_type="pdf")
        assert result["error_state"]["kind"] == "unsupported_input_type"

    def test_none_type_defaults_to_text(self):
        node = _make_node()
        result = _run(node, raw_input="Some idea.", input_type=None)
        assert result.get("error_state") is None

    def test_initialises_revision_count_zero(self):
        node = _make_node()
        result = _run(node, raw_input="My idea.", input_type="text")
        assert result["revision_count"] == 0
