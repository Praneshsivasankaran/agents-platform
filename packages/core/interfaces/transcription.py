"""TranscriptionProvider — speech-to-text seam (ADR-0003, accepted).

Voice and video-derived audio are transcribed ONLY through this interface; agent logic never
calls a cloud STT SDK directly. Audio extraction from video is a separate deterministic, local
utility (``core.media.extract_audio``), NOT a provider. GCP wired first; AWS/Azure stubbed
behind this same interface. See DESIGN.md §1.2, §3, §4.

Typed I/O per ADR-0003 (§Decision 2: ``transcribe(audio_ref, options) -> Transcript``, Pydantic):
this module uses Pydantic models. Cloud-neutral by construction — imports only Pydantic + the
standard library; never a cloud SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import Field, model_validator

from .base import CoreContractModel
from .usage import Usage


class TimestampSegment(CoreContractModel):
    """One transcript segment. Immutable; ``start_s``/``end_s`` are non-negative, finite, and ordered."""

    start_s: float = Field(ge=0.0, allow_inf_nan=False)
    end_s: float = Field(ge=0.0, allow_inf_nan=False)
    text: str
    speaker: str | None = None

    @model_validator(mode="after")
    def _ordered(self) -> "TimestampSegment":
        if self.end_s < self.start_s:
            raise ValueError("TimestampSegment requires start_s <= end_s")
        return self


class Transcript(CoreContractModel):
    """Provider-neutral transcription result + accounting (DESIGN §1.2 ``transcript_meta``).

    Immutable + copy-safe (via ``CoreContractModel``). Numeric metadata is non-negative and finite
    (``allow_inf_nan=False``); ``confidence`` (if present) is in ``[0, 1]``. Nested collections are
    immutable (``tuple``). Segment consistency is validated: segments must be chronological
    (non-decreasing ``start_s``), each ``start_s <= end_s``, and — when ``duration_s`` is known
    (> 0) — no segment may end past it.
    """

    text: str
    language: str = "en"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    segments: tuple[TimestampSegment, ...] = Field(default_factory=tuple)
    speakers: tuple[str, ...] = Field(default_factory=tuple)
    duration_s: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    latency_ms: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    provider: str = ""
    # Cost lives in ``usage`` (provider-native), feeding the SAME central cost meter as LLM usage
    # — one cost path, no separate cost_inr field (DESIGN §8).
    usage: Usage = Field(default_factory=Usage)

    @model_validator(mode="after")
    def _consistent_segments(self) -> "Transcript":
        segs = self.segments
        for i in range(1, len(segs)):
            if segs[i].start_s < segs[i - 1].start_s:
                raise ValueError("Transcript segments must be chronological (non-decreasing start_s)")
        if self.duration_s > 0:
            for s in segs:
                if s.end_s > self.duration_s:
                    raise ValueError("Transcript segment end_s exceeds transcript duration_s")
        return self


class TranscriptionProvider(ABC):
    """Abstract speech-to-text provider. The only STT seam agent logic may import."""

    name: str = "base"

    @abstractmethod
    def transcribe(
        self,
        audio_ref: str,
        *,
        language: str = "en",
        timestamps: bool = False,
        diarization: bool = False,
    ) -> Transcript:
        """Transcribe audio referenced by ``audio_ref`` (an ObjectStorage key or local path).

        Reads bytes via ``ObjectStorage`` where applicable; STT credentials come from
        ``SecretStore``. Returns a typed ``Transcript``; cost/latency live in ``Transcript.usage``
        / ``Transcript.latency_ms`` and feed the one central cost ledger (``core.cost``).
        """
        raise NotImplementedError
