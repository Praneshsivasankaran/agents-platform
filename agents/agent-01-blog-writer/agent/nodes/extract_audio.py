"""extract_audio node — deterministic local audio extraction for video input (DESIGN §1.2).

This node calls the ``core.media.extract_audio`` utility (ffmpeg-backed, local-only, no cloud).
It is skipped for text and voice inputs; only video inputs route here.

On success: writes ``audio_ref`` (path to the extracted WAV) to state.
On failure: writes ``error_state`` so the finalize funnel handles the error gracefully.

Security:
- No cloud SDK, no network, no credentials.
- Error messages are type-name-only (no raw exception text; no path disclosure).
- The extracted WAV path is a temp-file path managed by the utility; the caller
  (transcribe node) is responsible for cleanup after use.
"""

from __future__ import annotations

from typing import Any

from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider
from core.media.extract_audio import MediaExtractionError, extract_audio
from ..state import BlogState


def make_extract_audio_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    # llm is accepted for signature consistency with other node factories but is not used.
    _ = llm
    max_duration_s = float(cfg.get("transcription", {}).get("max_duration_s", 7200.0))

    def extract_audio_node(state: BlogState) -> dict[str, Any]:
        with tel.span("extract_audio") as span_id:
            video_ref: str = state.get("raw_input", "")  # type: ignore[assignment]
            if not isinstance(video_ref, str) or not video_ref.strip():
                tel.log("extract_audio.invalid_ref", span_id=span_id)
                return {
                    "error_state": {
                        "node": "extract_audio",
                        "kind": "invalid_ref",
                        "message": "video reference is missing or blank",
                    }
                }

            try:
                audio_path = extract_audio(video_ref, max_duration_s=max_duration_s)
            except MediaExtractionError:
                tel.log("extract_audio.error", span_id=span_id, kind="MediaExtractionError")
                return {
                    "error_state": {
                        "node": "extract_audio",
                        "kind": "MediaExtractionError",
                        "message": "media audio extraction failed",
                    }
                }
            except Exception as exc:
                tel.log("extract_audio.error", span_id=span_id, kind=type(exc).__name__)
                return {
                    "error_state": {
                        "node": "extract_audio",
                        "kind": type(exc).__name__,
                        "message": f"{type(exc).__name__} in extract_audio",
                    }
                }

            tel.log("extract_audio.complete", span_id=span_id)
            return {"audio_ref": audio_path}

    return extract_audio_node
