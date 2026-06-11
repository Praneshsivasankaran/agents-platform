"""Offline tests for the GCP transcription provider using a stubbed SDK."""

from __future__ import annotations

import os
import sys
import types
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.interfaces import BillableProviderError
from core.providers.gcp.transcription import GCPTranscriptionProvider


def _cfg(**overrides):
    transcription = {
        "provider": "gcp",
        "provider_currency": "USD",
        "cost_per_second_native": 0.0004,
        "billing_increment_seconds": 15,
        "max_duration_s": 60,
        "max_audio_bytes": 5_000_000,
    }
    transcription.update(overrides)
    return {
        "transcription": transcription,
        "cost": {"ceiling_inr": 50.0, "fx_rates": {"USD": 83.0}},
    }


def _wav(tmp_path, seconds=1):
    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * (16000 * seconds))
    return str(path)


def _speech_modules(*, response=None, side_effect=None, long_response=None):
    client = MagicMock()
    client.recognize.side_effect = side_effect
    client.recognize.return_value = response
    operation = MagicMock()
    operation.result.return_value = long_response
    client.long_running_recognize.return_value = operation

    class RecognitionConfig:
        class AudioEncoding:
            LINEAR16 = "LINEAR16"

        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class RecognitionAudio:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    speech = types.ModuleType("google.cloud.speech")
    speech.RecognitionConfig = RecognitionConfig
    speech.RecognitionAudio = RecognitionAudio
    speech.SpeechClient = lambda: client
    cloud = types.ModuleType("google.cloud")
    cloud.speech = speech
    google = types.ModuleType("google")
    google.cloud = cloud
    return client, {"google": google, "google.cloud": cloud, "google.cloud.speech": speech}


def _response(text="hello"):
    alt = SimpleNamespace(transcript=text, confidence=0.9, words=[])
    result = SimpleNamespace(alternatives=[alt])
    return SimpleNamespace(results=[result])


def _response_with_word(*, start_s: float, end_s: float):
    word = SimpleNamespace(
        start_time=SimpleNamespace(total_seconds=lambda: start_s),
        end_time=SimpleNamespace(total_seconds=lambda: end_s),
        word="hello",
    )
    alt = SimpleNamespace(transcript="hello", confidence=0.9, words=[word])
    return SimpleNamespace(results=[SimpleNamespace(alternatives=[alt])])


def test_constructor_requires_nonzero_pricing():
    with pytest.raises(ValueError, match="cost_per_second_native"):
        GCPTranscriptionProvider({"transcription": {"provider_currency": "USD"}})


def test_constructor_rejects_sync_duration_above_api_limit():
    with pytest.raises(ValueError, match="<= 60"):
        GCPTranscriptionProvider(_cfg(sync_max_duration_s=61))


def test_constructor_accepts_long_form_duration_limit():
    provider = GCPTranscriptionProvider(_cfg(max_duration_s=900))
    assert provider._max_duration_s == 900


def test_constructor_requires_max_duration_s_explicitly():
    """max_duration_s is required (not defaulted) — omitting it must fail loudly, not silently
    fall back to a value that always trips the ceiling guard."""
    with pytest.raises(ValueError, match="max_duration_s is required"):
        GCPTranscriptionProvider({
            "transcription": {
                "provider": "gcp",
                "provider_currency": "USD",
                "cost_per_second_native": 0.0004,
                "billing_increment_seconds": 15,
            },
            "cost": {"ceiling_inr": 50.0, "fx_rates": {"USD": 83.0}},
        })


def test_constructor_rejects_duration_that_can_exceed_run_ceiling():
    with pytest.raises(ValueError, match="cost.ceiling_inr"):
        GCPTranscriptionProvider(_cfg(max_duration_s=1800))


def test_constructor_requires_cost_ceiling_and_currency_fx():
    cfg = _cfg()
    del cfg["cost"]["ceiling_inr"]
    with pytest.raises(ValueError, match="cost.ceiling_inr"):
        GCPTranscriptionProvider(cfg)

    cfg = _cfg()
    del cfg["cost"]["fx_rates"]["USD"]
    with pytest.raises(ValueError, match="fx_rates"):
        GCPTranscriptionProvider(cfg)


def test_pre_call_usage_is_nonzero_and_uses_billing_increment(tmp_path):
    provider = GCPTranscriptionProvider(_cfg())
    _, duration, usage = provider._read_validated_wav(_wav(tmp_path, seconds=1))
    assert duration == pytest.approx(1.0)
    assert usage.cost_native == pytest.approx(0.006)
    assert usage.currency == "USD"
    assert usage.synthetic is False


def test_oversized_audio_rejected_before_sdk_import(tmp_path):
    provider = GCPTranscriptionProvider(_cfg(max_audio_bytes=100))
    with pytest.raises(ValueError, match="size limit"):
        provider.transcribe(_wav(tmp_path))


def test_long_audio_rejected_before_sdk_import(tmp_path):
    provider = GCPTranscriptionProvider(_cfg(max_duration_s=0.5, sync_max_duration_s=0.5))
    with pytest.raises(ValueError, match="duration"):
        provider.transcribe(_wav(tmp_path))


def test_invalid_wav_rejected_before_sdk_import(tmp_path):
    path = tmp_path / "invalid.wav"
    path.write_bytes(b"not-a-wave-file" * 10)
    provider = GCPTranscriptionProvider(_cfg())
    with pytest.raises(ValueError, match="valid WAV"):
        provider.transcribe(str(path))


def test_wrong_wav_format_rejected_before_sdk_import(tmp_path):
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00\x00\x00" * 16000)
    provider = GCPTranscriptionProvider(_cfg())
    with pytest.raises(ValueError, match="channel count"):
        provider.transcribe(str(path))


def test_provider_failure_raises_billable_error_with_cost(tmp_path):
    provider = GCPTranscriptionProvider(_cfg())
    client, modules = _speech_modules(side_effect=RuntimeError("RAW_PROVIDER_CANARY"))
    with patch.dict(sys.modules, modules):
        with pytest.raises(BillableProviderError) as exc_info:
            provider.transcribe(_wav(tmp_path))
    assert client.recognize.call_count == 1
    assert exc_info.value.usage.cost_native > 0
    assert "RAW_PROVIDER_CANARY" not in repr(exc_info.value)


def test_success_returns_typed_transcript_and_nonzero_usage(tmp_path):
    provider = GCPTranscriptionProvider(_cfg())
    client, modules = _speech_modules(response=_response())
    with patch.dict(sys.modules, modules):
        transcript = provider.transcribe(_wav(tmp_path), timestamps=True)
    assert client.recognize.call_count == 1
    assert transcript.text == "hello"
    assert transcript.usage.cost_native > 0
    assert transcript.provider == "gcp"


def test_timestamp_segments_are_bounded_to_validated_audio_duration(tmp_path):
    provider = GCPTranscriptionProvider(_cfg())
    _, modules = _speech_modules(response=_response_with_word(start_s=2.0, end_s=3.0))
    with patch.dict(sys.modules, modules):
        transcript = provider.transcribe(_wav(tmp_path), timestamps=True)
    assert transcript.duration_s == pytest.approx(1.0)
    assert len(transcript.segments) == 1
    assert transcript.segments[0].start_s == pytest.approx(1.0)
    assert transcript.segments[0].end_s == pytest.approx(1.0)


def test_empty_provider_response_is_billable_failure(tmp_path):
    provider = GCPTranscriptionProvider(_cfg())
    _, modules = _speech_modules(response=_response(text=" "))
    with patch.dict(sys.modules, modules):
        with pytest.raises(BillableProviderError) as exc_info:
            provider.transcribe(_wav(tmp_path))
    assert exc_info.value.category == "response_empty"
    assert exc_info.value.usage.cost_native > 0


def test_long_form_uses_gcs_uri_and_deletes_transient_object(tmp_path):
    class FakeStorage:
        def __init__(self):
            self.put_keys = []
            self.deleted_keys = []

        def put(self, key, data):
            self.put_keys.append(key)
            return key

        def uri_for(self, key):
            return f"gs://bucket/{key}"

        def delete(self, key):
            self.deleted_keys.append(key)

    storage = FakeStorage()
    provider = GCPTranscriptionProvider(
        _cfg(max_duration_s=120, sync_max_duration_s=55),
        object_storage=storage,
    )
    client, modules = _speech_modules(long_response=_response("long transcript"))
    with patch.dict(sys.modules, modules):
        transcript = provider.transcribe(_wav(tmp_path, seconds=56))
    assert transcript.text == "long transcript"
    assert client.recognize.call_count == 0
    assert client.long_running_recognize.call_count == 1
    assert len(storage.put_keys) == 1
    assert storage.deleted_keys == storage.put_keys


def test_long_form_provider_failure_still_deletes_transient_object(tmp_path):
    class FakeStorage:
        def __init__(self):
            self.put_keys = []
            self.deleted_keys = []

        def put(self, key, data):
            self.put_keys.append(key)
            return key

        def uri_for(self, key):
            return f"gs://bucket/{key}"

        def delete(self, key):
            self.deleted_keys.append(key)

    storage = FakeStorage()
    provider = GCPTranscriptionProvider(
        _cfg(max_duration_s=120, sync_max_duration_s=55),
        object_storage=storage,
    )
    client, modules = _speech_modules()
    client.long_running_recognize.side_effect = RuntimeError("RAW_PROVIDER_CANARY")
    with patch.dict(sys.modules, modules):
        with pytest.raises(BillableProviderError) as exc_info:
            provider.transcribe(_wav(tmp_path, seconds=56))
    assert exc_info.value.category == "provider_call_failed"
    assert exc_info.value.usage.cost_native > 0
    assert storage.deleted_keys == storage.put_keys
    assert "RAW_PROVIDER_CANARY" not in repr(exc_info.value)


def test_long_form_cleanup_failure_is_billable_and_content_free(tmp_path):
    class FakeStorage:
        def put(self, key, data):
            return key

        def uri_for(self, key):
            return f"gs://bucket/{key}"

        def delete(self, key):
            raise RuntimeError("RAW_DELETE_CANARY")

    provider = GCPTranscriptionProvider(
        _cfg(max_duration_s=120, sync_max_duration_s=55),
        object_storage=FakeStorage(),
    )
    _, modules = _speech_modules(long_response=_response("long transcript"))
    with patch.dict(sys.modules, modules):
        with pytest.raises(BillableProviderError) as exc_info:
            provider.transcribe(_wav(tmp_path, seconds=56))
    assert exc_info.value.category == "unknown"
    assert exc_info.value.usage.cost_native > 0
    assert "RAW_DELETE_CANARY" not in repr(exc_info.value)
