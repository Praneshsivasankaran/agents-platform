"""Amazon Transcribe provider — interface-complete stub (v1; not wired).

Satisfies the ``TranscriptionProvider`` ABC. ``transcribe`` raises ``NotImplementedError``
loudly. When filled in, the Amazon Transcribe client is imported lazily here — never in
agent logic.
"""

from __future__ import annotations

from typing import Any

from ...interfaces.transcription import Transcript, TranscriptionProvider
from .._not_wired import not_wired


class BedrockTranscriptionProvider(TranscriptionProvider):
    """AWS Transcribe speech-to-text backend (stub). Instantiable; ``transcribe`` fails loudly."""

    name = "bedrock"

    def __init__(
        self,
        cfg: dict[str, Any] | None = None,
        *,
        secret_store=None,
        object_storage=None,
        **_: Any,
    ) -> None:
        self._cfg = cfg or {}
        self._secret_store = secret_store
        self._object_storage = object_storage

    def transcribe(
        self,
        audio_ref: str,
        *,
        language: str = "en",
        timestamps: bool = False,
        diarization: bool = False,
    ) -> Transcript:
        raise not_wired("AWS", "Transcribe", "transcribe")
