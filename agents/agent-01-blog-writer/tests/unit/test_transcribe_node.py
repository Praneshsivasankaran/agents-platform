"""Unit tests for the transcribe node (Increment 6).

Tests:
- Voice path: uses raw_input as audio_ref.
- Video path: uses audio_ref from state (set by extract_audio node).
- Cost is recorded as a StageCost with tier="stt".
- Provider error → error_state, no crash.
- Cost ceiling exceeded → CostCeilingExceeded raised (propagates to guard).
- Transcript text is returned in state.
- transcript_meta contains required keys.
- No cloud SDK or network calls.
"""
from __future__ import annotations

import pytest

from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry
from core.providers.mock.transcription import MockTranscriptionProvider
from agent.nodes.transcribe import make_transcribe_node
from agent.schemas import StageCost


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(ceiling=50.0):
    return {
        "provider": "mock",
        "service": "test",
        "cost": {
            "ceiling_inr": ceiling,
            "is_mock": True,
            "fx_rates": {"USD": 83.0},
            "estimated_stage_cost_inr": {
                "normalize": 0.3,
                "extract_ideas": 0.3,
                "plan": 0.5,
                "draft": 12.0,
                "review": 6.0,
                "transcribe": 5.0,
            },
        },
    }


def _make_node(cfg=None, ceiling=50.0):
    cfg = cfg or _cfg(ceiling)
    llm = MockLLMProvider()
    tel = StdoutTelemetry(service="test")
    transcription = MockTranscriptionProvider()
    return make_transcribe_node(cfg, llm, tel, transcription)


def _voice_state(audio_ref="recording.wav"):
    return {"raw_input": audio_ref, "input_type": "voice", "cost_usage": []}


def _video_state(audio_ref="/tmp/extracted.wav"):
    return {
        "raw_input": "lecture.mp4",
        "input_type": "video",
        "audio_ref": audio_ref,
        "cost_usage": [],
    }


# ---------------------------------------------------------------------------
# Voice path
# ---------------------------------------------------------------------------

class TestTranscribeVoicePath:
    def test_voice_returns_transcript(self):
        node = _make_node()
        result = node(_voice_state())
        assert "transcript" in result
        assert isinstance(result["transcript"], str)
        assert result["transcript"].strip()

    def test_voice_returns_transcript_meta(self):
        node = _make_node()
        result = node(_voice_state())
        meta = result["transcript_meta"]
        assert "provider" in meta
        assert "duration_s" in meta
        assert "cost_inr" in meta
        assert "latency_ms" in meta
        assert "language" in meta
        assert "segments" in meta

    def test_voice_duration_non_negative(self):
        node = _make_node()
        result = node(_voice_state())
        assert result["transcript_meta"]["duration_s"] >= 0.0

    def test_voice_cost_non_negative(self):
        node = _make_node()
        result = node(_voice_state())
        assert result["transcript_meta"]["cost_inr"] >= 0.0

    def test_voice_stage_cost_recorded(self):
        node = _make_node()
        result = node(_voice_state())
        costs = result["cost_usage"]
        assert len(costs) == 1
        sc = costs[0]
        assert isinstance(sc, StageCost)
        assert sc.stage == "transcribe"
        assert sc.tier == "stt"

    def test_mock_cost_zero(self):
        """Mock provider returns synthetic=True → cost_inr must be 0."""
        node = _make_node()
        result = node(_voice_state())
        assert result["cost_usage"][0].cost_inr == 0.0


# ---------------------------------------------------------------------------
# Video path
# ---------------------------------------------------------------------------

class TestTranscribeVideoPath:
    def test_video_uses_audio_ref(self):
        node = _make_node()
        result = node(_video_state(audio_ref="extracted.wav"))
        assert "transcript" in result
        assert isinstance(result["transcript"], str)

    def test_video_missing_audio_ref_returns_error(self):
        node = _make_node()
        state = {"raw_input": "lecture.mp4", "input_type": "video", "cost_usage": []}
        result = node(state)
        assert result["error_state"]["kind"] == "missing_audio_ref"

    def test_video_blank_audio_ref_returns_error(self):
        node = _make_node()
        state = {"raw_input": "lecture.mp4", "input_type": "video",
                 "audio_ref": "", "cost_usage": []}
        result = node(state)
        assert result["error_state"]["kind"] == "missing_audio_ref"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestTranscribeErrors:
    def test_provider_exception_returns_error_state(self):
        from unittest.mock import MagicMock
        cfg = _cfg()
        llm = MockLLMProvider()
        tel = StdoutTelemetry(service="test")

        broken_stt = MagicMock()
        broken_stt.transcribe.side_effect = RuntimeError("simulated STT failure")
        node = make_transcribe_node(cfg, llm, tel, broken_stt)

        result = node(_voice_state())
        assert result["error_state"]["node"] == "transcribe"
        assert "RuntimeError" in result["error_state"]["kind"]

    def test_missing_raw_input_for_voice_returns_error(self):
        node = _make_node()
        state = {"raw_input": "", "input_type": "voice", "cost_usage": []}
        result = node(state)
        assert result["error_state"]["kind"] == "missing_raw_input"

    def test_error_state_message_does_not_leak_paths(self):
        """Error messages must not contain file system paths."""
        from unittest.mock import MagicMock
        cfg = _cfg()
        llm = MockLLMProvider()
        tel = StdoutTelemetry(service="test")
        broken_stt = MagicMock()
        broken_stt.transcribe.side_effect = FileNotFoundError("/secret/path/audio.wav")
        node = make_transcribe_node(cfg, llm, tel, broken_stt)

        result = node(_voice_state())
        msg = result["error_state"].get("message", "")
        assert "/secret" not in msg
        assert "path" not in msg.lower() or "FileNotFoundError" in msg

    def test_billable_provider_error_preserves_stage_cost(self):
        from core.interfaces import BillableProviderError, Usage
        from agent.schemas import BillableNodeError
        from unittest.mock import MagicMock

        broken_stt = MagicMock()
        broken_stt.transcribe.side_effect = BillableProviderError(
            Usage(audio_seconds=15, cost_native=0.006, currency="USD"),
            "provider_call_failed",
        )
        node = make_transcribe_node(
            _cfg(), MockLLMProvider(), StdoutTelemetry(service="test"), broken_stt
        )
        with pytest.raises(BillableNodeError) as exc_info:
            node(_voice_state())
        assert exc_info.value.stage_cost.stage == "transcribe"
        assert exc_info.value.stage_cost.cost_inr > 0

    def test_video_owned_temp_audio_is_deleted_after_transcription(self):
        import os
        import tempfile

        fd, path = tempfile.mkstemp(prefix="blog_audio_", suffix=".wav")
        os.close(fd)
        node = _make_node()
        result = node(_video_state(audio_ref=path))
        assert "transcript" in result
        assert not os.path.exists(path)

    def test_real_provider_voice_path_normalizes_before_transcription(self):
        import os
        import tempfile
        from unittest.mock import patch

        cfg = _cfg()
        cfg["transcription"] = {
            "provider": "gcp",
            "normalize_voice": True,
            "max_duration_s": 60,
            "language": "en-US",
            "timestamps": True,
        }
        fd, normalized = tempfile.mkstemp(prefix="blog_audio_", suffix=".wav")
        os.close(fd)
        node = make_transcribe_node(
            cfg,
            MockLLMProvider(),
            StdoutTelemetry(service="test"),
            MockTranscriptionProvider(),
        )
        with patch("agent.nodes.transcribe.extract_audio", return_value=normalized) as extract:
            result = node(_voice_state("voice.mp3"))
        extract.assert_called_once()
        assert "transcript" in result
        assert not os.path.exists(normalized)

    def test_span_exit_failure_preserves_transcription_cost(self):
        from contextlib import contextmanager
        from core.interfaces import Transcript, Usage
        from agent.schemas import BillableNodeError

        class PaidSTT:
            def transcribe(self, *args, **kwargs):
                return Transcript(
                    text="paid transcript",
                    provider="test",
                    duration_s=15,
                    usage=Usage(audio_seconds=15, cost_native=0.006, currency="USD"),
                )

        class ExitFailTelemetry(StdoutTelemetry):
            @contextmanager
            def span(self, name, **attrs):
                with super().span(name, **attrs) as span_id:
                    yield span_id
                raise RuntimeError("span exit failure")

        node = make_transcribe_node(
            _cfg(), MockLLMProvider(), ExitFailTelemetry(service="test"), PaidSTT()
        )
        with pytest.raises(BillableNodeError) as exc_info:
            node(_voice_state())
        assert exc_info.value.stage_cost.cost_inr > 0

    def test_billable_provider_failure_plus_span_exit_failure_preserves_cost(self):
        from core.interfaces import BillableProviderError, Usage
        from agent.schemas import BillableNodeError
        from unittest.mock import MagicMock

        class AlwaysExitFailTelemetry(StdoutTelemetry):
            class _Context:
                def __init__(self, inner):
                    self._inner = inner

                def __enter__(self):
                    return self._inner.__enter__()

                def __exit__(self, exc_type, exc_value, traceback):
                    self._inner.__exit__(exc_type, exc_value, traceback)
                    raise RuntimeError("span exit failure while provider error unwinds")

            def span(self, name, **attrs):
                return self._Context(super().span(name, **attrs))

        broken_stt = MagicMock()
        broken_stt.transcribe.side_effect = BillableProviderError(
            Usage(audio_seconds=15, cost_native=0.006, currency="USD"),
            "provider_call_failed",
        )
        node = make_transcribe_node(
            _cfg(),
            MockLLMProvider(),
            AlwaysExitFailTelemetry(service="test"),
            broken_stt,
        )
        with pytest.raises(BillableNodeError) as exc_info:
            node(_voice_state())
        assert exc_info.value.stage_cost.stage == "transcribe"
        assert exc_info.value.stage_cost.cost_inr > 0

    def test_span_entry_failure_still_deletes_video_temp_audio(self):
        import os
        import tempfile

        class EntryFailTelemetry(StdoutTelemetry):
            def span(self, name, **attrs):
                raise RuntimeError("span entry failure")

        fd, path = tempfile.mkstemp(prefix="blog_audio_", suffix=".wav")
        os.close(fd)
        node = make_transcribe_node(
            _cfg(), MockLLMProvider(), EntryFailTelemetry(service="test"), MockTranscriptionProvider()
        )
        with pytest.raises(RuntimeError, match="span entry"):
            node(_video_state(audio_ref=path))
        assert not os.path.exists(path)


# ---------------------------------------------------------------------------
# Cost ceiling
# ---------------------------------------------------------------------------

class TestTranscribeCostCeiling:
    def test_ceiling_exceeded_raises_cost_ceiling_exceeded(self):
        """When the ceiling is effectively exhausted, CostCeilingExceeded must be raised."""
        from core.cost import CostCeilingExceeded

        node = _make_node(ceiling=0.0)  # ceiling=0 → cannot afford any transcription
        state = {"raw_input": "audio.wav", "input_type": "voice", "cost_usage": []}
        with pytest.raises(CostCeilingExceeded):
            node(state)

    def test_normal_ceiling_does_not_raise(self):
        node = _make_node(ceiling=50.0)
        result = node(_voice_state())
        assert "transcript" in result


# ---------------------------------------------------------------------------
# No cloud SDK
# ---------------------------------------------------------------------------

class TestTranscribeNoCloud:
    def test_no_cloud_env_needed(self, monkeypatch):
        for var in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT",
                    "AWS_ACCESS_KEY_ID", "AZURE_CLIENT_ID"):
            monkeypatch.delenv(var, raising=False)
        node = _make_node()
        result = node(_voice_state())
        assert "transcript" in result
