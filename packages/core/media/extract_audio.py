"""Deterministic local audio extraction for voice/video media.

This utility is cloud-neutral and invokes a local ffmpeg binary with ``shell=False``.
It validates references before the subprocess, bounds extracted WAV duration before
any STT provider call, and never includes ffmpeg stderr or local paths in errors.
"""

from __future__ import annotations

import math
import os
import subprocess
import tempfile

_VOICE_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus", ".aac"})
_VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".avi", ".mov", ".webm"})
_ALL_APPROVED_EXTENSIONS = _VOICE_EXTENSIONS | _VIDEO_EXTENSIONS
_SUPPORTED_OUTPUT_FORMATS = frozenset({"wav", "mp3"})

MAX_INPUT_BYTES: int = 500 * 1024 * 1024
MAX_AUDIO_DURATION_S: float = 2 * 60 * 60
_DEFAULT_TIMEOUT_S: int = 120
_MIN_OUTPUT_BYTES: int = 44
_WAV_BYTES_PER_SECOND: int = 16000 * 2
_OWNED_TEMP_PREFIX = "blog_audio_"


class MediaExtractionError(ValueError):
    """Raised for a sanitized media-validation or extraction failure."""


def _safe_ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def extract_audio(
    video_ref: str,
    *,
    out_format: str = "wav",
    timeout_s: int = _DEFAULT_TIMEOUT_S,
    max_duration_s: float = MAX_AUDIO_DURATION_S,
) -> str:
    """Extract audio to an owned temp file and return its path.

    The caller must call :func:`delete_extracted_audio` when the artifact is no
    longer needed.
    """
    if not isinstance(video_ref, str) or not video_ref.strip():
        raise MediaExtractionError("input reference must be a non-empty string")
    if out_format not in _SUPPORTED_OUTPUT_FORMATS:
        raise MediaExtractionError("unsupported output audio format")
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, int) or timeout_s <= 0:
        raise MediaExtractionError("timeout_s must be a positive integer")
    if (
        isinstance(max_duration_s, bool)
        or not isinstance(max_duration_s, (int, float))
        or not math.isfinite(float(max_duration_s))
        or float(max_duration_s) <= 0
    ):
        raise MediaExtractionError("max_duration_s must be a positive finite number")

    ext = _safe_ext(video_ref)
    if ext not in _ALL_APPROVED_EXTENSIONS:
        raise MediaExtractionError(
            f"unsupported file extension {ext!r}; "
            f"approved voice: {sorted(_VOICE_EXTENSIONS)}, "
            f"approved video: {sorted(_VIDEO_EXTENSIONS)}"
        )

    try:
        stat = os.stat(video_ref)
    except FileNotFoundError:
        raise MediaExtractionError("input file not found") from None
    except OSError:
        raise MediaExtractionError("input file could not be accessed") from None
    if not os.path.isfile(video_ref):
        raise MediaExtractionError("input path is not a regular file")
    if stat.st_size > MAX_INPUT_BYTES:
        raise MediaExtractionError(
            f"input file exceeds maximum allowed size "
            f"({stat.st_size} bytes > {MAX_INPUT_BYTES} bytes)"
        )
    if stat.st_size == 0:
        raise MediaExtractionError("input file is empty")

    suffix = f".{out_format}"
    fd, out_path = tempfile.mkstemp(suffix=suffix, prefix=_OWNED_TEMP_PREFIX)
    os.close(fd)
    if out_format == "wav":
        audio_flags = ["-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1"]
    else:
        audio_flags = ["-ac", "1"]
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_ref,
        "-vn",
        *audio_flags,
        "-loglevel",
        "error",
        out_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        _safe_remove(out_path)
        raise MediaExtractionError(f"ffmpeg did not complete within {timeout_s}s timeout") from None
    except FileNotFoundError:
        _safe_remove(out_path)
        raise MediaExtractionError(
            "ffmpeg binary not found; ensure ffmpeg is installed in the container"
        ) from None
    except OSError as exc:
        _safe_remove(out_path)
        raise MediaExtractionError(
            f"ffmpeg subprocess failed to start: {type(exc).__name__}"
        ) from None

    if result.returncode != 0:
        _safe_remove(out_path)
        # stderr may contain user paths, media metadata, or content. Never surface it.
        raise MediaExtractionError("ffmpeg exited with non-zero status")

    try:
        out_size = os.path.getsize(out_path)
    except OSError:
        _safe_remove(out_path)
        raise MediaExtractionError("output file could not be read after extraction") from None
    if out_size < _MIN_OUTPUT_BYTES:
        _safe_remove(out_path)
        raise MediaExtractionError(
            f"extracted audio file is too small ({out_size} bytes); "
            "input may be corrupt or contain no audio track"
        )
    if out_format == "wav":
        duration_s = max(0.0, (out_size - _MIN_OUTPUT_BYTES) / _WAV_BYTES_PER_SECOND)
        if duration_s > float(max_duration_s):
            _safe_remove(out_path)
            raise MediaExtractionError("media duration exceeds maximum allowed duration")
    return out_path


def _safe_remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def delete_extracted_audio(path: str) -> bool:
    """Delete only temp audio artifacts owned by this utility."""
    if not isinstance(path, str) or not path.strip():
        return False
    resolved = os.path.realpath(path)
    temp_root = os.path.realpath(tempfile.gettempdir())
    if os.path.dirname(resolved) != temp_root:
        return False
    if not os.path.basename(resolved).startswith(_OWNED_TEMP_PREFIX):
        return False
    try:
        os.unlink(resolved)
        return True
    except OSError:
        return False
