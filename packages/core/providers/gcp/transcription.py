"""GCP Cloud Speech-to-Text provider with fail-closed cost accounting."""

from __future__ import annotations

import math
import os
import time
import uuid
import wave
from typing import Any

from ...interfaces.errors import BillableProviderError
from ...interfaces.object_storage import ObjectStorage
from ...interfaces.transcription import TimestampSegment, Transcript, TranscriptionProvider
from ...interfaces.usage import Usage

_WAV_HEADER_BYTES = 44


def _positive_finite(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"transcription.{name} must be a positive finite number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"transcription.{name} must be a positive finite number")
    return result


def _nonempty_str(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"transcription.{name} must be a non-empty string")
    return value.strip()


class GCPTranscriptionProvider(TranscriptionProvider):
    """Speech-to-text via Google Cloud Speech using validated local WAV audio."""

    name = "gcp"

    def __init__(
        self,
        cfg: dict[str, Any],
        *,
        secret_store=None,
        object_storage: ObjectStorage | None = None,
    ) -> None:
        tcfg = cfg.get("transcription") or {}
        if not isinstance(tcfg, dict):
            raise ValueError("cfg.transcription must be a mapping")
        self._language = _nonempty_str(tcfg.get("language", "en-US"), name="language")
        self._model = _nonempty_str(tcfg.get("model", "latest_long"), name="model")
        self._currency = _nonempty_str(
            tcfg.get("provider_currency"), name="provider_currency"
        ).upper()
        self._cost_per_second_native = _positive_finite(
            tcfg.get("cost_per_second_native"), name="cost_per_second_native"
        )
        self._billing_increment_s = _positive_finite(
            tcfg.get("billing_increment_seconds"), name="billing_increment_seconds"
        )
        if "max_duration_s" not in tcfg:
            # Required, not defaulted: it bounds worst-case STT cost against the run ceiling.
            # A silent 2-hour default would always trip the ceiling guard below — confusing.
            # Fail loudly with a clear, actionable message instead.
            raise ValueError(
                "transcription.max_duration_s is required for real GCP transcription — it caps "
                "audio length so worst-case STT cost stays under cost.ceiling_inr. Set it explicitly "
                "(e.g. 900 for a 15-minute / ~Rs30 cap). Do not omit it."
            )
        self._max_duration_s = _positive_finite(
            tcfg.get("max_duration_s"), name="max_duration_s"
        )
        self._sync_max_duration_s = _positive_finite(
            tcfg.get("sync_max_duration_s", 55), name="sync_max_duration_s"
        )
        if self._sync_max_duration_s > 60:
            raise ValueError(
                "transcription.sync_max_duration_s must be <= 60"
            )
        if self._sync_max_duration_s > self._max_duration_s:
            raise ValueError(
                "transcription.sync_max_duration_s must not exceed max_duration_s"
            )
        self._long_running_timeout_s = _positive_finite(
            tcfg.get("long_running_timeout_s", 1800), name="long_running_timeout_s"
        )
        for value, name in (
            (tcfg.get("sample_rate_hertz", 16000), "sample_rate_hertz"),
            (tcfg.get("audio_channel_count", 1), "audio_channel_count"),
            (tcfg.get("max_audio_bytes", 500 * 1024 * 1024), "max_audio_bytes"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"transcription.{name} must be a positive integer")
        self._sample_rate = tcfg.get("sample_rate_hertz", 16000)
        self._channels = tcfg.get("audio_channel_count", 1)
        self._max_audio_bytes = tcfg.get("max_audio_bytes", 500 * 1024 * 1024)
        cost_cfg = cfg.get("cost") or {}
        if not isinstance(cost_cfg, dict):
            raise ValueError("cfg.cost must be a mapping")
        ceiling_inr = _positive_finite(cost_cfg.get("ceiling_inr"), name="cost.ceiling_inr")
        fx_rates = cost_cfg.get("fx_rates") or {}
        if not isinstance(fx_rates, dict) or self._currency not in fx_rates:
            raise ValueError(
                f"cost.fx_rates must include transcription currency {self._currency!r}"
            )
        fx_rate = _positive_finite(
            fx_rates[self._currency],
            name=f"cost.fx_rates.{self._currency}",
        )
        max_billed_s = (
            math.ceil(self._max_duration_s / self._billing_increment_s)
            * self._billing_increment_s
        )
        self._max_transcription_cost_inr = (
            max_billed_s * self._cost_per_second_native * fx_rate
        )
        if self._max_transcription_cost_inr > ceiling_inr:
            raise ValueError(
                "configured transcription.max_duration_s can exceed cost.ceiling_inr"
            )
        self._cfg = cfg
        self._secret_store = secret_store
        self._object_storage = object_storage

    def _get_long_form_storage(self):
        if self._object_storage is None:
            from .storage import GCSObjectStorage

            self._object_storage = GCSObjectStorage(
                self._cfg,
                secret_store=self._secret_store,
            )
        if not hasattr(self._object_storage, "uri_for"):
            raise ValueError(
                "long-form GCP transcription requires GCSObjectStorage with uri_for()"
            )
        return self._object_storage

    def _read_validated_wav(self, audio_ref: str) -> tuple[bytes, float, Usage]:
        if not isinstance(audio_ref, str) or not audio_ref.strip():
            raise ValueError("GCPTranscriptionProvider: audio_ref must be non-empty")
        if os.path.splitext(audio_ref)[1].lower() != ".wav":
            raise ValueError("GCPTranscriptionProvider: audio_ref must be normalized WAV audio")
        try:
            stat = os.stat(audio_ref)
        except OSError:
            raise ValueError("GCPTranscriptionProvider: audio file is unavailable") from None
        if not os.path.isfile(audio_ref):
            raise ValueError("GCPTranscriptionProvider: audio_ref is not a regular file")
        if stat.st_size <= _WAV_HEADER_BYTES:
            raise ValueError("GCPTranscriptionProvider: audio file is empty or corrupt")
        if stat.st_size > self._max_audio_bytes:
            raise ValueError("GCPTranscriptionProvider: audio file exceeds configured size limit")

        try:
            with wave.open(audio_ref, "rb") as wav:
                if wav.getcomptype() != "NONE":
                    raise ValueError(
                        "GCPTranscriptionProvider: audio file must be uncompressed PCM WAV"
                    )
                if wav.getnchannels() != self._channels:
                    raise ValueError(
                        "GCPTranscriptionProvider: audio channel count does not match configuration"
                    )
                if wav.getsampwidth() != 2:
                    raise ValueError(
                        "GCPTranscriptionProvider: audio sample width must be 16-bit"
                    )
                if wav.getframerate() != self._sample_rate:
                    raise ValueError(
                        "GCPTranscriptionProvider: audio sample rate does not match configuration"
                    )
                frames = wav.getnframes()
                if frames <= 0:
                    raise ValueError(
                        "GCPTranscriptionProvider: audio file is empty or corrupt"
                    )
                duration_s = frames / wav.getframerate()
        except (EOFError, wave.Error):
            raise ValueError(
                "GCPTranscriptionProvider: audio file is not a valid WAV"
            ) from None
        if duration_s > self._max_duration_s:
            raise ValueError("GCPTranscriptionProvider: audio duration exceeds configured limit")
        billed_s = math.ceil(duration_s / self._billing_increment_s) * self._billing_increment_s
        usage = Usage(
            audio_seconds=duration_s,
            cost_native=billed_s * self._cost_per_second_native,
            currency=self._currency,
            synthetic=False,
        )
        try:
            with open(audio_ref, "rb") as fh:
                return fh.read(), duration_s, usage
        except OSError:
            raise ValueError("GCPTranscriptionProvider: audio file could not be read") from None

    def transcribe(
        self,
        audio_ref: str,
        *,
        language: str = "en",
        timestamps: bool = False,
        diarization: bool = False,
    ) -> Transcript:
        audio_bytes, duration_s, usage = self._read_validated_wav(audio_ref)
        try:
            from google.cloud import speech as gcp_speech  # type: ignore[import]
        except ImportError:
            raise RuntimeError(
                "google-cloud-speech is not installed in the GCP provider environment"
            ) from None

        effective_language = (
            language.strip()
            if isinstance(language, str) and language.strip()
            else self._language
        )
        bcp47 = _to_bcp47(effective_language)
        recognition_kwargs = dict(
            encoding=gcp_speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self._sample_rate,
            audio_channel_count=self._channels,
            language_code=bcp47,
            model=self._model,
            enable_word_time_offsets=timestamps,
            enable_automatic_punctuation=True,
        )
        if diarization:
            recognition_kwargs["diarization_config"] = gcp_speech.SpeakerDiarizationConfig(
                enable_speaker_diarization=True
            )
        rec_config = gcp_speech.RecognitionConfig(**recognition_kwargs)
        client = gcp_speech.SpeechClient()

        started = time.monotonic()
        pending_error: BillableProviderError | None = None
        response = None
        if duration_s <= self._sync_max_duration_s and len(audio_bytes) <= 10_000_000:
            audio = gcp_speech.RecognitionAudio(content=audio_bytes)
            try:
                response = client.recognize(config=rec_config, audio=audio)
            except Exception:
                pending_error = BillableProviderError(usage, "provider_call_failed")
        else:
            storage = self._get_long_form_storage()
            key = f"transcription/{uuid.uuid4().hex}.wav"
            stored = False
            cleanup_failed = False
            try:
                storage.put(key, audio_bytes)
                stored = True
                audio = gcp_speech.RecognitionAudio(uri=storage.uri_for(key))
                operation = client.long_running_recognize(config=rec_config, audio=audio)
                response = operation.result(timeout=self._long_running_timeout_s)
            except Exception:
                pending_error = BillableProviderError(usage, "provider_call_failed")
            finally:
                if stored:
                    try:
                        storage.delete(key)
                    except Exception:
                        cleanup_failed = True
            if cleanup_failed:
                pending_error = BillableProviderError(usage, "unknown")
        if pending_error is not None:
            raise pending_error
        latency_ms = (time.monotonic() - started) * 1000.0

        pending_error = None
        transcript: Transcript | None = None
        try:
            text_parts: list[str] = []
            segments: list[TimestampSegment] = []
            confidence_sum = 0.0
            confidence_count = 0
            for result in response.results:
                alt = result.alternatives[0] if result.alternatives else None
                if alt is None:
                    continue
                text_parts.append(alt.transcript)
                if alt.confidence:
                    confidence_sum += alt.confidence
                    confidence_count += 1
                if timestamps and alt.words:
                    for word_info in alt.words:
                        start_s = word_info.start_time.total_seconds()
                        end_s = word_info.end_time.total_seconds()
                        bounded_start_s = min(duration_s, max(0.0, start_s))
                        bounded_end_s = min(
                            duration_s,
                            max(bounded_start_s, end_s),
                        )
                        segments.append(
                            TimestampSegment(
                                start_s=bounded_start_s,
                                end_s=bounded_end_s,
                                text=word_info.word,
                            )
                        )
            full_text = " ".join(text_parts).strip()
            if not full_text:
                pending_error = BillableProviderError(usage, "response_empty")
            else:
                transcript = Transcript(
                    text=full_text,
                    language=bcp47,
                    confidence=(
                        confidence_sum / confidence_count if confidence_count else None
                    ),
                    segments=tuple(segments),
                    duration_s=duration_s,
                    latency_ms=latency_ms,
                    provider="gcp",
                    usage=usage,
                )
        except Exception:
            pending_error = BillableProviderError(usage, "response_shape_invalid")
        if pending_error is not None:
            raise pending_error
        if transcript is None:
            raise BillableProviderError(usage, "response_shape_invalid")
        return transcript


def _to_bcp47(lang: str) -> str:
    mapping = {"en": "en-US", "hi": "hi-IN", "fr": "fr-FR", "de": "de-DE", "es": "es-US"}
    return mapping.get(lang.lower(), lang)
