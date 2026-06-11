"""intake node — validates raw input and initialises per-run counters (DESIGN §1.2).

Increment 6 update:
- Supported modalities extended to text, voice, and video.
- For voice/video: validates that raw_input is a non-blank reference string and
  that the file extension is in the approved media set.  Content is NOT read here —
  only the reference string is checked.  Actual media validation (size, corruption,
  extraction) happens in extract_audio and transcribe nodes.

Earlier repairs (intact):
- Invalid input sets error_state so the finalize funnel is the single terminal path.
- revision_count initialised to 0 (counts completed revisions, not total drafts).
- writing_prefs: explicit rejection in v1 (silently ignoring would mislead callers).
"""
from __future__ import annotations

import os
from typing import Any

from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider
from ..state import BlogState

# Supported modalities in Increment 6.
_SUPPORTED_INPUT_TYPES: frozenset[str] = frozenset({"text", "voice", "video"})
# Finite set of known values for safe telemetry logging.
_KNOWN_INPUT_TYPES: frozenset[str] = frozenset({"text", "voice", "video"})

# Approved media extensions for voice and video inputs.
# Must stay in sync with core.media.extract_audio approved sets.
_APPROVED_VOICE_EXTS: frozenset[str] = frozenset(
    {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus", ".aac"}
)
_APPROVED_VIDEO_EXTS: frozenset[str] = frozenset(
    {".mp4", ".mkv", ".avi", ".mov", ".webm"}
)
_APPROVED_MEDIA_EXTS: frozenset[str] = _APPROVED_VOICE_EXTS | _APPROVED_VIDEO_EXTS


def make_intake_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def intake(state: BlogState) -> dict[str, Any]:
        with tel.span("intake") as span_id:
            raw_input: str = state.get("raw_input", "")  # type: ignore[assignment]

            # ── Modality detection ─────────────────────────────────────────────
            raw_type = state.get("input_type") or "text"
            input_type = raw_type if isinstance(raw_type, str) else "unknown"
            safe_type = input_type if input_type in _KNOWN_INPUT_TYPES else "unknown"

            if input_type not in _SUPPORTED_INPUT_TYPES:
                tel.log("intake.unsupported_input_type", span_id=span_id,
                        input_type=safe_type)
                return {
                    "revision_count": 0,
                    "cost_usage": [],
                    "hard_fail_flags": [],
                    "error_state": {
                        "node": "intake",
                        "kind": "unsupported_input_type",
                        "message": (
                            f"input_type={safe_type!r} is not supported "
                            "(supported: text, voice, video)"
                        ),
                    },
                }

            # ── Blank input check ──────────────────────────────────────────────
            if not isinstance(raw_input, str) or not raw_input.strip():
                tel.log("intake.invalid_input", span_id=span_id,
                        reason="raw_input missing or blank")
                return {
                    "revision_count": 0,
                    "cost_usage": [],
                    "hard_fail_flags": [],
                    "error_state": {
                        "node": "intake",
                        "kind": "invalid_input",
                        "message": "raw_input is missing or blank; cannot proceed.",
                    },
                }

            # ── Media reference validation (voice/video) ───────────────────────
            if input_type in ("voice", "video"):
                ext = os.path.splitext(raw_input)[1].lower()
                if not ext:
                    tel.log("intake.invalid_media_ref", span_id=span_id,
                            input_type=safe_type)
                    return {
                        "revision_count": 0,
                        "cost_usage": [],
                        "hard_fail_flags": [],
                        "error_state": {
                            "node": "intake",
                            "kind": "invalid_media_ref",
                            "message": (
                                f"media reference for {input_type!r} input has no file extension; "
                                f"expected one of: {sorted(_APPROVED_MEDIA_EXTS)}"
                            ),
                        },
                    }
                if input_type == "voice" and ext not in _APPROVED_VOICE_EXTS:
                    tel.log("intake.unsupported_media_format", span_id=span_id,
                            input_type=safe_type)
                    return {
                        "revision_count": 0,
                        "cost_usage": [],
                        "hard_fail_flags": [],
                        "error_state": {
                            "node": "intake",
                            "kind": "unsupported_media_format",
                            "message": (
                                f"unsupported voice format {ext!r}; "
                                f"approved: {sorted(_APPROVED_VOICE_EXTS)}"
                            ),
                        },
                    }
                if input_type == "video" and ext not in _APPROVED_VIDEO_EXTS:
                    tel.log("intake.unsupported_media_format", span_id=span_id,
                            input_type=safe_type)
                    return {
                        "revision_count": 0,
                        "cost_usage": [],
                        "hard_fail_flags": [],
                        "error_state": {
                            "node": "intake",
                            "kind": "unsupported_media_format",
                            "message": (
                                f"unsupported video format {ext!r}; "
                                f"approved: {sorted(_APPROVED_VIDEO_EXTS)}"
                            ),
                        },
                    }

            # ── writing_prefs: explicit rejection in v1 ──────────────────────
            writing_prefs = state.get("writing_prefs")
            if writing_prefs:
                tel.log("intake.writing_prefs_unsupported", span_id=span_id)
                return {
                    "revision_count": 0,
                    "cost_usage": [],
                    "hard_fail_flags": [],
                    "error_state": {
                        "node": "intake",
                        "kind": "writing_prefs_unsupported",
                        "message": (
                            "writing_prefs is not supported in v1; "
                            "omit writing_prefs to proceed without customisation"
                        ),
                    },
                }

            tel.log("intake.accepted", span_id=span_id, input_chars=len(raw_input))
            return {"revision_count": 0}

    return intake
