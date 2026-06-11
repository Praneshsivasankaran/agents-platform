"""Unit tests for MockTranscriptionProvider (Increment 6).

Verifies determinism, Usage honesty, timestamp/diarization options, and
that the mock never makes network calls or requires credentials.
"""
from __future__ import annotations

import pytest

from core.interfaces.transcription import TimestampSegment, Transcript
from core.interfaces.usage import Usage
from core.providers.mock.transcription import MockTranscriptionProvider


@pytest.fixture()
def mock_stt():
    return MockTranscriptionProvider()


class TestMockTranscriptionValidity:
    def test_returns_transcript_type(self, mock_stt):
        result = mock_stt.transcribe("audio.wav")
        assert isinstance(result, Transcript)

    def test_text_non_empty(self, mock_stt):
        result = mock_stt.transcribe("audio.wav")
        assert result.text.strip()

    def test_provider_is_mock(self, mock_stt):
        result = mock_stt.transcribe("audio.wav")
        assert result.provider == "mock"

    def test_duration_positive(self, mock_stt):
        result = mock_stt.transcribe("audio.wav")
        assert result.duration_s > 0.0

    def test_latency_non_negative(self, mock_stt):
        result = mock_stt.transcribe("audio.wav")
        assert result.latency_ms >= 0.0

    def test_usage_is_synthetic(self, mock_stt):
        result = mock_stt.transcribe("audio.wav")
        assert result.usage.synthetic is True

    def test_usage_audio_seconds_positive(self, mock_stt):
        result = mock_stt.transcribe("audio.wav")
        assert result.usage.audio_seconds > 0.0

    def test_usage_cost_native_zero(self, mock_stt):
        """Mock must never report a real cost."""
        result = mock_stt.transcribe("audio.wav")
        assert result.usage.cost_native == 0.0

    def test_confidence_in_range(self, mock_stt):
        result = mock_stt.transcribe("audio.wav")
        if result.confidence is not None:
            assert 0.0 <= result.confidence <= 1.0

    def test_language_preserved(self, mock_stt):
        result = mock_stt.transcribe("audio.wav", language="hi")
        assert result.language == "hi"


class TestMockTranscriptionDeterminism:
    def test_same_ref_same_text(self, mock_stt):
        r1 = mock_stt.transcribe("audio.wav")
        r2 = mock_stt.transcribe("audio.wav")
        assert r1.text == r2.text

    def test_voice_keyword_selects_voice_transcript(self, mock_stt):
        r = mock_stt.transcribe("voice_recording.wav")
        # Voice transcript mentions "cloud-agnostic" (from the canned text).
        assert "cloud" in r.text.lower() or "agent" in r.text.lower()

    def test_video_keyword_selects_video_transcript(self, mock_stt):
        r = mock_stt.transcribe("lecture_video.mp4")
        assert "tutorial" in r.text.lower() or "agent" in r.text.lower()

    def test_default_key_for_unknown_ref(self, mock_stt):
        r = mock_stt.transcribe("some_unknown_key_xyz")
        assert "mock" in r.text.lower() or "transcript" in r.text.lower()


class TestMockTranscriptionTimestamps:
    def test_no_timestamps_by_default(self, mock_stt):
        result = mock_stt.transcribe("audio.wav")
        assert result.segments == ()

    def test_timestamps_returns_segments(self, mock_stt):
        result = mock_stt.transcribe("audio.wav", timestamps=True)
        assert len(result.segments) >= 1

    def test_segments_are_timestamp_segment_instances(self, mock_stt):
        result = mock_stt.transcribe("audio.wav", timestamps=True)
        for seg in result.segments:
            assert isinstance(seg, TimestampSegment)

    def test_segments_are_chronological(self, mock_stt):
        result = mock_stt.transcribe("audio.wav", timestamps=True)
        starts = [s.start_s for s in result.segments]
        assert starts == sorted(starts)

    def test_segment_end_within_duration(self, mock_stt):
        result = mock_stt.transcribe("audio.wav", timestamps=True)
        for seg in result.segments:
            assert seg.end_s <= result.duration_s + 1e-9  # float tolerance

    def test_segment_start_le_end(self, mock_stt):
        result = mock_stt.transcribe("audio.wav", timestamps=True)
        for seg in result.segments:
            assert seg.start_s <= seg.end_s


class TestMockTranscriptionDiarization:
    def test_no_speakers_by_default(self, mock_stt):
        result = mock_stt.transcribe("audio.wav")
        assert result.speakers == ()

    def test_diarization_adds_speakers(self, mock_stt):
        result = mock_stt.transcribe("audio.wav", timestamps=True, diarization=True)
        assert len(result.speakers) > 0

    def test_diarization_segments_have_speaker(self, mock_stt):
        result = mock_stt.transcribe("audio.wav", timestamps=True, diarization=True)
        for seg in result.segments:
            # Speaker may be None for non-diarized segments; with diarization it should be set.
            assert seg.speaker is not None


class TestMockTranscriptionNoNetworkNoCreds:
    def test_transcribes_without_any_env_vars(self, monkeypatch, mock_stt):
        """Mock must succeed with all cloud-related env vars absent."""
        for var in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT",
                    "AWS_ACCESS_KEY_ID", "AZURE_CLIENT_ID"):
            monkeypatch.delenv(var, raising=False)
        result = mock_stt.transcribe("audio.wav")
        assert result.text
