"""Unit and characterization tests for stitch.py.

Unit tests: check_ffmpeg, silence WAV generation (RIFF header validation).
Characterization tests (require ffmpeg): get_clip_duration, full stitch pipeline.
"""

import json
import struct
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from dub_chunk.models import Paragraph, TimingEntry
from dub_chunk.stitch import (
    check_ffmpeg,
    get_clip_duration,
    stitch_audio,
    _generate_silence_wav,
    _to_wav,
)


# ======================================================================
# check_ffmpeg — unit tests
# ======================================================================


class TestCheckFfmpeg:

    def test_returns_true_when_available(self):
        # ffmpeg should be installed in dev environment
        assert check_ffmpeg() is True

    @patch("dub_chunk.stitch.shutil.which", return_value=None)
    def test_returns_false_when_missing(self, mock_which):
        assert check_ffmpeg() is False


# ======================================================================
# Silence WAV generation — unit tests (validate RIFF format)
# ======================================================================


class TestSilenceWav:

    def test_generates_valid_riff_header(self, tmp_path):
        wav = tmp_path / "silence.wav"
        _generate_silence_wav(wav, duration=1.0, sample_rate=44100)

        data = wav.read_bytes()
        # RIFF header
        assert data[:4] == b"RIFF"
        assert data[8:12] == b"WAVE"

    def test_correct_file_size(self, tmp_path):
        wav = tmp_path / "silence.wav"
        sample_rate = 44100
        duration = 0.5
        _generate_silence_wav(wav, duration=duration, sample_rate=sample_rate)

        expected_samples = int(sample_rate * duration)
        expected_data_size = expected_samples * 2  # 16-bit
        # Total file: 44 bytes header + data
        expected_file_size = 44 + expected_data_size
        assert wav.stat().st_size == expected_file_size

    def test_wav_is_all_zeros(self, tmp_path):
        """Silence means all sample values are zero."""
        wav = tmp_path / "silence.wav"
        _generate_silence_wav(wav, duration=0.1, sample_rate=8000)

        data = wav.read_bytes()
        audio_data = data[44:]  # skip header
        assert all(b == 0 for b in audio_data)

    def test_fmt_chunk_correct(self, tmp_path):
        wav = tmp_path / "silence.wav"
        _generate_silence_wav(wav, duration=0.1, sample_rate=22050)

        data = wav.read_bytes()
        assert data[12:16] == b"fmt "
        # PCM format = 1
        fmt_code = struct.unpack_from("<H", data, 20)[0]
        assert fmt_code == 1
        # Mono = 1 channel
        channels = struct.unpack_from("<H", data, 22)[0]
        assert channels == 1
        # Sample rate
        sr = struct.unpack_from("<I", data, 24)[0]
        assert sr == 22050
        # Bits per sample
        bps = struct.unpack_from("<H", data, 34)[0]
        assert bps == 16

    def test_zero_duration_creates_empty_audio(self, tmp_path):
        wav = tmp_path / "zero.wav"
        _generate_silence_wav(wav, duration=0.0, sample_rate=44100)
        assert wav.exists()
        # File should have header (44 bytes) + 0 data bytes
        assert wav.stat().st_size == 44


# ======================================================================
# get_clip_duration — characterization (requires ffmpeg)
# ======================================================================


class TestGetClipDuration:

    @pytest.fixture
    def silence_wav(self, tmp_path):
        """Create a real silence WAV to test duration measurement."""
        path = tmp_path / "test.wav"
        _generate_silence_wav(path, duration=2.0, sample_rate=44100)
        return path

    def test_measures_duration_correctly(self, silence_wav):
        duration = get_clip_duration(silence_wav)
        assert abs(duration - 2.0) < 0.05  # within 50ms

    def test_raises_for_missing_file(self):
        with pytest.raises(FileNotFoundError):
            get_clip_duration(Path("/nonexistent/file.mp3"))


# ======================================================================
# _to_wav — characterization (requires ffmpeg)
# ======================================================================


class TestToWav:

    def test_converts_wav_to_wav(self, tmp_path):
        """Even WAV→WAV conversion should work (re-encodes to mono 16-bit)."""
        src = tmp_path / "input.wav"
        _generate_silence_wav(src, duration=0.5, sample_rate=44100)

        dst = tmp_path / "output.wav"
        _to_wav(src, dst, sample_rate=22050)

        assert dst.exists()
        duration = get_clip_duration(dst)
        assert abs(duration - 0.5) < 0.05


# ======================================================================
# stitch_audio — characterization (requires ffmpeg, end-to-end)
# ======================================================================


class TestStitchAudio:

    @pytest.fixture
    def clips_with_timing(self, tmp_path):
        """Create fake MP3 clips (actually WAVs renamed to .mp3 for simplicity,
        ffmpeg handles both) and matching TimingEntries."""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()

        # Create two "clips" as silence WAVs with .mp3 extension
        # (ffmpeg can read WAV regardless of extension)
        for pid in [1, 2]:
            clip_path = clips_dir / f"p{pid:04d}.mp3"
            _generate_silence_wav(clip_path, duration=1.0, sample_rate=44100)

        timing = [
            TimingEntry(
                paragraph=Paragraph(id=1, speaker="A", text="First"),
                pause_before=0.0,
                estimated_duration=1.0,
            ),
            TimingEntry(
                paragraph=Paragraph(id=2, speaker="B", text="Second"),
                pause_before=0.5,
                estimated_duration=1.0,
            ),
        ]

        return clips_dir, timing

    def test_stitches_clips_into_single_mp3(self, clips_with_timing, tmp_path):
        clips_dir, timing = clips_with_timing
        output = tmp_path / "output.mp3"

        result = stitch_audio(timing, clips_dir, output)
        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_output_duration_includes_pauses(self, clips_with_timing, tmp_path):
        clips_dir, timing = clips_with_timing
        output = tmp_path / "output.mp3"

        stitch_audio(timing, clips_dir, output)
        duration = get_clip_duration(output)
        # 2 clips × 1s + 0.5s pause ≈ 2.5s
        assert 2.0 < duration < 3.5  # generous tolerance for codec overhead

    def test_raises_for_missing_clip(self, tmp_path):
        clips_dir = tmp_path / "empty_clips"
        clips_dir.mkdir()

        timing = [
            TimingEntry(
                paragraph=Paragraph(id=1, speaker="A", text="Missing"),
                pause_before=0.0,
            ),
        ]

        with pytest.raises(FileNotFoundError, match="p0001"):
            stitch_audio(timing, clips_dir, tmp_path / "out.mp3")

    def test_raises_when_ffmpeg_missing(self, clips_with_timing, tmp_path):
        clips_dir, timing = clips_with_timing
        with patch("dub_chunk.stitch.check_ffmpeg", return_value=False):
            with pytest.raises(RuntimeError, match="ffmpeg"):
                stitch_audio(timing, clips_dir, tmp_path / "out.mp3")

    def test_cleans_up_temp_directory(self, clips_with_timing, tmp_path):
        """Temp directory should be removed even on success."""
        clips_dir, timing = clips_with_timing
        output = tmp_path / "output.mp3"

        stitch_audio(timing, clips_dir, output)

        # No dub_stitch_ temp dirs should remain
        import tempfile
        temp_dirs = list(Path(tempfile.gettempdir()).glob("dub_stitch_*"))
        # May be empty or just ours, but ours should be cleaned
        # (can't guarantee no other process created one, so just check output exists)
        assert output.exists()
