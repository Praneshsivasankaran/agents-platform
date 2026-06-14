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

from pydantic import ValidationError

from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider
from ..schemas import Agent03BlogBrief
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


def _append_tuple_lines(lines: list[str], label: str, values: tuple[str, ...]) -> None:
    if not values:
        return
    lines.append(f"{label}:")
    lines.extend(f"- {value}" for value in values)


def _format_agent03_blog_brief(brief: Agent03BlogBrief, raw_input: str) -> str:
    lines = ["Agent 03 blog brief (primary source of truth for this run):"]
    scalar_fields = (
        ("Selected idea title", brief.selected_idea_title),
        ("Suggested title", brief.suggested_title),
        ("Target audience", brief.target_audience),
        ("Campaign goal", brief.campaign_goal),
        ("Content angle", brief.content_angle),
        ("Core message", brief.core_message),
        ("Value proposition", brief.value_proposition),
        ("Suggested CTA", brief.cta),
        ("Brand tone", brief.tone),
    )
    for label, value in scalar_fields:
        if value:
            lines.append(f"{label}: {value}")

    _append_tuple_lines(lines, "Title options", brief.title_options)
    _append_tuple_lines(lines, "Audience pain points", brief.pain_points)
    _append_tuple_lines(lines, "Suggested outline", brief.suggested_outline)
    _append_tuple_lines(lines, "Proof points or evidence placeholders", brief.proof_points_or_placeholders)
    _append_tuple_lines(lines, "Optional keywords", brief.keywords)
    _append_tuple_lines(lines, "Constraints and things to avoid", brief.constraints)
    _append_tuple_lines(lines, "Risk flags", brief.risk_flags)
    _append_tuple_lines(lines, "Quality notes", brief.quality_notes)

    if raw_input.strip():
        lines.extend((
            "",
            "Supplemental user material (secondary to Agent 03 brief):",
            raw_input.strip(),
        ))
    return "\n".join(lines)


def make_intake_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def intake(state: BlogState) -> dict[str, Any]:
        with tel.span("intake") as span_id:
            raw_input_value = state.get("raw_input", "")
            raw_input: str = raw_input_value if isinstance(raw_input_value, str) else ""

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
            brief_payload = state.get("blog_brief_from_agent_03")
            blog_brief: Agent03BlogBrief | None = None
            if brief_payload is not None:
                try:
                    blog_brief = Agent03BlogBrief.model_validate(brief_payload)
                except ValidationError:
                    tel.log("intake.invalid_agent03_blog_brief", span_id=span_id)
                    return {
                        "revision_count": 0,
                        "cost_usage": [],
                        "hard_fail_flags": [],
                        "error_state": {
                            "node": "intake",
                            "kind": "invalid_agent03_blog_brief",
                            "message": (
                                "blog_brief_from_agent_03 is missing required campaign "
                                "context or contains invalid fields."
                            ),
                        },
                    }
                raw_input = _format_agent03_blog_brief(blog_brief, raw_input)
                input_type = "text"
                safe_type = "text"

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
            accepted: dict[str, Any] = {"revision_count": 0}
            if blog_brief is not None:
                accepted.update({
                    "blog_brief_from_agent_03": blog_brief,
                    "raw_input": raw_input,
                    "input_type": safe_type,
                })
            return accepted

    return intake
