"""Azure AI Speech provider — interface-complete stub (v1; not wired).

Satisfies the ``TranscriptionProvider`` ABC. ``transcribe`` raises ``NotImplementedError``
loudly. When filled in, ``azure.cognitiveservices.speech`` is imported lazily here — never in
agent logic.
"""

from __future__ import annotations

from typing import Any

from ...interfaces.transcription import Transcript, TranscriptionProvider
from .._not_wired import not_wired


class AzureTranscriptionProvider(TranscriptionProvider):
    """Azure AI Speech speech-to-text backend (stub). Instantiable; ``transcribe`` fails loudly."""

    name = "azure"

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
        raise not_wired("Azure", "AI Speech", "transcribe")
