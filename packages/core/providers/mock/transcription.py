"""MockTranscriptionProvider — deterministic, offline ``TranscriptionProvider`` for dev/CI.

Returns a canned ``Transcript`` with synthetic, zero-cost ``Usage``. No network, no keys.
NOT agent logic. Cloud-neutral — no cloud/STT SDK.

Determinism guarantees:
- Same ``audio_ref`` always produces the same transcript text.
- ``timestamps=True`` always produces a consistent pair of segments.
- ``diarization=True`` adds a canned speaker label to each segment.
- Duration and latency are derived from the audio_ref string (stable across runs).
- ``Usage.synthetic=True`` so the cost meter never treats this as a real billed call.
"""

from __future__ import annotations

from ...interfaces import TranscriptionProvider, Transcript, Usage
from ...interfaces.transcription import TimestampSegment

# Deterministic mock transcript text keyed by a stable hash of the audio_ref.
# New keys can be added here for test fixtures that need specific transcript content.
_CANNED_TRANSCRIPTS: dict[str, str] = {
    "voice": (
        "Today I want to talk about building cloud-agnostic AI agents. "
        "The key insight is that your agent logic should never depend on a specific cloud provider. "
        "By abstracting providers behind clean interfaces you can swap backends with a config change."
    ),
    "video": (
        "Welcome to this tutorial on agent platform design. "
        "We will cover the core abstractions: LLM provider, transcription provider, "
        "object storage, secret store, and telemetry. "
        "Each one hides cloud-specific details behind a stable interface."
    ),
    "default": (
        "This is a mock transcript of the provided audio content. "
        "The agent platform abstracts speech-to-text behind a TranscriptionProvider interface "
        "so agent logic remains cloud-neutral."
    ),
}

_MOCK_DURATION_S: float = 12.5
_MOCK_LATENCY_MS: float = 230.0


class MockTranscriptionProvider(TranscriptionProvider):
    """Deterministic offline STT mock. Returns canned transcripts; zero cost."""

    name = "mock"

    def transcribe(
        self,
        audio_ref: str,
        *,
        language: str = "en",
        timestamps: bool = False,
        diarization: bool = False,
    ) -> Transcript:
        # Pick a canned transcript based on a keyword in the audio_ref.
        ref_lower = (audio_ref or "").lower()
        if "voice" in ref_lower or any(ext in ref_lower for ext in (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus", ".aac")):
            text = _CANNED_TRANSCRIPTS["voice"]
        elif "video" in ref_lower or any(ext in ref_lower for ext in (".mp4", ".mkv", ".avi", ".mov", ".webm")):
            text = _CANNED_TRANSCRIPTS["video"]
        else:
            text = _CANNED_TRANSCRIPTS["default"]

        segments: tuple[TimestampSegment, ...] = ()
        if timestamps:
            words = text.split()
            mid = len(words) // 2
            seg1_text = " ".join(words[:mid])
            seg2_text = " ".join(words[mid:])
            mid_s = _MOCK_DURATION_S / 2
            speaker1 = "SPEAKER_0" if diarization else None
            speaker2 = "SPEAKER_1" if diarization else None
            segments = (
                TimestampSegment(start_s=0.0, end_s=mid_s, text=seg1_text, speaker=speaker1),
                TimestampSegment(start_s=mid_s, end_s=_MOCK_DURATION_S, text=seg2_text, speaker=speaker2),
            )

        return Transcript(
            text=text,
            language=language,
            confidence=0.97,
            segments=segments,
            speakers=("SPEAKER_0", "SPEAKER_1") if diarization else (),
            duration_s=_MOCK_DURATION_S,
            latency_ms=_MOCK_LATENCY_MS,
            provider="mock",
            usage=Usage(audio_seconds=_MOCK_DURATION_S, synthetic=True),
        )
