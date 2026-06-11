"""Unit tests for core.media.extract_audio (Increment 6).

All tests mock subprocess.run and os.stat so no ffmpeg binary is needed.
No cloud SDK. No network. No credentials.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from core.media.extract_audio import (
    MAX_INPUT_BYTES,
    MediaExtractionError,
    extract_audio,
)

# Mirror the approved sets here so tests don't import private symbols.
_APPROVED_VOICE_EXTS = frozenset({".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus", ".aac"})
_APPROVED_VIDEO_EXTS = frozenset({".mp4", ".mkv", ".avi", ".mov", ".webm"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stat(size: int = 1024):
    stat = MagicMock()
    stat.st_size = size
    return stat


def _successful_run():
    run = MagicMock()
    run.returncode = 0
    run.stderr = b""
    return run


# ---------------------------------------------------------------------------
# Extension validation
# ---------------------------------------------------------------------------

class TestExtensionValidation:
    def test_rejects_unsupported_extension(self):
        with pytest.raises(MediaExtractionError, match="unsupported file extension"):
            with patch("os.stat", return_value=_stat()), \
                 patch("os.path.isfile", return_value=True):
                extract_audio("clip.txt")

    def test_rejects_no_extension(self):
        with pytest.raises(MediaExtractionError, match="unsupported file extension"):
            with patch("os.stat", return_value=_stat()), \
                 patch("os.path.isfile", return_value=True):
                extract_audio("audiofile")

    @pytest.mark.parametrize("ext", sorted(_APPROVED_VOICE_EXTS))
    def test_accepts_all_voice_extensions(self, ext, tmp_path):
        dummy = tmp_path / f"audio{ext}"
        dummy.write_bytes(b"x" * 100)
        with patch("subprocess.run", return_value=_successful_run()), \
             patch("os.path.getsize", return_value=100), \
             patch("tempfile.mkstemp", return_value=(0, str(tmp_path / f"out.wav"))), \
             patch("os.close"), \
             patch("os.path.isfile", return_value=True):
            result = extract_audio(str(dummy))
            assert result.endswith(".wav")

    @pytest.mark.parametrize("ext", sorted(_APPROVED_VIDEO_EXTS))
    def test_accepts_all_video_extensions(self, ext, tmp_path):
        dummy = tmp_path / f"clip{ext}"
        dummy.write_bytes(b"x" * 100)
        with patch("subprocess.run", return_value=_successful_run()), \
             patch("os.path.getsize", return_value=100), \
             patch("tempfile.mkstemp", return_value=(0, str(tmp_path / f"out.wav"))), \
             patch("os.close"), \
             patch("os.path.isfile", return_value=True):
            result = extract_audio(str(dummy))
            assert result.endswith(".wav")


# ---------------------------------------------------------------------------
# File existence and size validation
# ---------------------------------------------------------------------------

class TestFileValidation:
    def test_rejects_missing_file(self):
        with pytest.raises(MediaExtractionError, match="not found"):
            with patch("os.stat", side_effect=FileNotFoundError):
                extract_audio("missing.mp4")

    def test_rejects_non_regular_file(self, tmp_path):
        # Simulate a directory
        d = tmp_path / "dir.mp4"
        d.mkdir()
        with pytest.raises(MediaExtractionError, match="not a regular file"):
            extract_audio(str(d))

    def test_rejects_oversized_file(self):
        with pytest.raises(MediaExtractionError, match="exceeds maximum"):
            with patch("os.stat", return_value=_stat(MAX_INPUT_BYTES + 1)), \
                 patch("os.path.isfile", return_value=True):
                extract_audio("big.mp4")

    def test_rejects_empty_file(self):
        with pytest.raises(MediaExtractionError, match="empty"):
            with patch("os.stat", return_value=_stat(0)), \
                 patch("os.path.isfile", return_value=True):
                extract_audio("empty.mp4")

    def test_rejects_blank_ref(self):
        with pytest.raises(MediaExtractionError, match="non-empty string"):
            extract_audio("")

    def test_rejects_whitespace_ref(self):
        with pytest.raises(MediaExtractionError, match="non-empty string"):
            extract_audio("   ")


# ---------------------------------------------------------------------------
# subprocess argument safety
# ---------------------------------------------------------------------------

class TestSubprocessSafety:
    def test_shell_false(self, tmp_path):
        """shell=False must always be used — never shell=True."""
        dummy = tmp_path / "clip.mp4"
        dummy.write_bytes(b"x" * 100)
        captured_calls = []

        def mock_run(cmd, **kwargs):
            captured_calls.append(kwargs)
            return _successful_run()

        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.path.getsize", return_value=100), \
             patch("tempfile.mkstemp", return_value=(0, str(tmp_path / "out.wav"))), \
             patch("os.close"):
            extract_audio(str(dummy))

        assert len(captured_calls) == 1
        assert captured_calls[0]["shell"] is False

    def test_vn_flag_present(self, tmp_path):
        """Audio-only extraction: -vn must appear in the ffmpeg command."""
        dummy = tmp_path / "clip.mp4"
        dummy.write_bytes(b"x" * 100)
        captured_cmd = []

        def mock_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return _successful_run()

        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.path.getsize", return_value=100), \
             patch("tempfile.mkstemp", return_value=(0, str(tmp_path / "out.wav"))), \
             patch("os.close"):
            extract_audio(str(dummy))

        assert "-vn" in captured_cmd

    def test_cmd_is_list_not_string(self, tmp_path):
        """Command must be a list, not a string (required for shell=False safety)."""
        dummy = tmp_path / "clip.mp4"
        dummy.write_bytes(b"x" * 100)
        captured_cmds = []

        def mock_run(cmd, **kwargs):
            captured_cmds.append(cmd)
            return _successful_run()

        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.path.getsize", return_value=100), \
             patch("tempfile.mkstemp", return_value=(0, str(tmp_path / "out.wav"))), \
             patch("os.close"):
            extract_audio(str(dummy))

        assert len(captured_cmds) == 1
        assert isinstance(captured_cmds[0], list)


# ---------------------------------------------------------------------------
# Timeout and process failures
# ---------------------------------------------------------------------------

class TestProcessFailures:
    def test_timeout_raises_extraction_error(self, tmp_path):
        dummy = tmp_path / "slow.mp4"
        dummy.write_bytes(b"x" * 100)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 120)):
            with pytest.raises(MediaExtractionError, match="timeout"):
                extract_audio(str(dummy))

    def test_ffmpeg_not_found_raises_extraction_error(self, tmp_path):
        dummy = tmp_path / "clip.mp4"
        dummy.write_bytes(b"x" * 100)
        with patch("subprocess.run", side_effect=FileNotFoundError), \
             patch("tempfile.mkstemp", return_value=(0, str(tmp_path / "out.wav"))), \
             patch("os.close"):
            with pytest.raises(MediaExtractionError, match="ffmpeg binary not found"):
                extract_audio(str(dummy))

    def test_nonzero_exit_raises_extraction_error(self, tmp_path):
        dummy = tmp_path / "corrupt.mp4"
        dummy.write_bytes(b"x" * 100)
        failed_run = MagicMock()
        failed_run.returncode = 1
        failed_run.stderr = b"Invalid data found when processing input"
        with patch("subprocess.run", return_value=failed_run), \
             patch("tempfile.mkstemp", return_value=(0, str(tmp_path / "out.wav"))), \
             patch("os.close"):
            with pytest.raises(MediaExtractionError, match="non-zero status"):
                extract_audio(str(dummy))

    def test_nonzero_exit_never_surfaces_stderr(self, tmp_path):
        dummy = tmp_path / "corrupt.mp4"
        dummy.write_bytes(b"x" * 100)
        failed_run = MagicMock()
        failed_run.returncode = 1
        failed_run.stderr = b"C:\\secret\\client\\recording.mp4 RAW_CANARY"
        with patch("subprocess.run", return_value=failed_run):
            with pytest.raises(MediaExtractionError) as exc_info:
                extract_audio(str(dummy))
        message = str(exc_info.value)
        assert "RAW_CANARY" not in message
        assert "secret" not in message.lower()

    def test_output_too_small_raises_extraction_error(self, tmp_path):
        dummy = tmp_path / "clip.mp4"
        dummy.write_bytes(b"x" * 100)
        with patch("subprocess.run", return_value=_successful_run()), \
             patch("os.path.getsize", return_value=10), \
             patch("tempfile.mkstemp", return_value=(0, str(tmp_path / "out.wav"))), \
             patch("os.close"):
            with pytest.raises(MediaExtractionError, match="too small"):
                extract_audio(str(dummy))

    def test_custom_timeout_is_passed_to_subprocess(self, tmp_path):
        dummy = tmp_path / "clip.mp4"
        dummy.write_bytes(b"x" * 100)
        captured_kwargs = []

        def mock_run(cmd, **kwargs):
            captured_kwargs.append(kwargs)
            return _successful_run()

        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.path.getsize", return_value=100), \
             patch("tempfile.mkstemp", return_value=(0, str(tmp_path / "out.wav"))), \
             patch("os.close"):
            extract_audio(str(dummy), timeout_s=30)

        assert captured_kwargs[0]["timeout"] == 30


# ---------------------------------------------------------------------------
# Successful extraction
# ---------------------------------------------------------------------------

class TestSuccessfulExtraction:
    def test_returns_wav_path(self, tmp_path):
        dummy = tmp_path / "clip.mp4"
        dummy.write_bytes(b"x" * 100)
        out_path = str(tmp_path / "out.wav")
        with patch("subprocess.run", return_value=_successful_run()), \
             patch("os.path.getsize", return_value=200), \
             patch("tempfile.mkstemp", return_value=(0, out_path)), \
             patch("os.close"):
            result = extract_audio(str(dummy))
            assert result == out_path

    def test_wav_codec_flags_in_command(self, tmp_path):
        dummy = tmp_path / "clip.mp4"
        dummy.write_bytes(b"x" * 100)
        captured_cmd = []

        def mock_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return _successful_run()

        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.path.getsize", return_value=200), \
             patch("tempfile.mkstemp", return_value=(0, str(tmp_path / "out.wav"))), \
             patch("os.close"):
            extract_audio(str(dummy), out_format="wav")

        assert "pcm_s16le" in captured_cmd
        assert "16000" in captured_cmd
        assert "1" in captured_cmd  # mono


class TestDurationAndCleanup:
    def test_rejects_extracted_audio_over_duration_limit(self, tmp_path):
        dummy = tmp_path / "clip.mp4"
        dummy.write_bytes(b"x" * 100)
        out_path = str(tmp_path / "out.wav")
        with patch("subprocess.run", return_value=_successful_run()), \
             patch("os.path.getsize", return_value=44 + 32000 * 11), \
             patch("tempfile.mkstemp", return_value=(0, out_path)), \
             patch("os.close"), \
             patch("os.unlink") as unlink:
            with pytest.raises(MediaExtractionError, match="duration"):
                extract_audio(str(dummy), max_duration_s=10)
        unlink.assert_called_once_with(out_path)

    def test_delete_extracted_audio_deletes_only_owned_temp_file(self):
        from core.media import delete_extracted_audio

        fd, owned = tempfile.mkstemp(prefix="blog_audio_", suffix=".wav")
        os.close(fd)
        assert delete_extracted_audio(owned) is True
        assert not os.path.exists(owned)

    def test_delete_extracted_audio_refuses_arbitrary_file(self, tmp_path):
        from core.media import delete_extracted_audio

        arbitrary = tmp_path / "user.wav"
        arbitrary.write_bytes(b"user")
        assert delete_extracted_audio(str(arbitrary)) is False
        assert arbitrary.exists()
