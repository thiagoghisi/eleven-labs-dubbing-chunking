"""FFmpeg-based audio stitching.

Combines individual TTS clips with silence gaps into a single MP3, using
the timing information from :mod:`dub_chunk.timing`.
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

from dub_chunk.models import TimingEntry


def check_ffmpeg() -> bool:
    """Return ``True`` if ``ffmpeg`` is available on PATH."""
    return shutil.which("ffmpeg") is not None


def get_clip_duration(clip_path: Path) -> float:
    """Return the duration of an audio file in seconds via ``ffprobe``.

    Args:
        clip_path: Path to the audio file.

    Returns:
        Duration in seconds.

    Raises:
        FileNotFoundError: If *clip_path* does not exist.
        RuntimeError: If ffprobe fails or returns unexpected output.
    """
    if not clip_path.exists():
        raise FileNotFoundError(f"Clip not found: {clip_path}")

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(clip_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    try:
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise RuntimeError(
            f"Could not parse duration from ffprobe output: {result.stdout}"
        ) from exc


def stitch_audio(
    timing_entries: list[TimingEntry],
    clips_dir: Path,
    output_path: Path,
    sample_rate: int = 44100,
    bitrate: str = "192k",
) -> Path:
    """Concatenate TTS clips with silence gaps into a single MP3.

    For each :class:`TimingEntry`:
        1. Generate a silence WAV whose length equals ``pause_before``.
        2. Convert the paragraph's TTS clip to WAV (ensures uniform format).
        3. Append both to an ffmpeg concat list.

    Finally, ``ffmpeg -f concat`` produces the output MP3.

    Clip files are expected at ``clips_dir / f"p{entry.paragraph.id:04d}.mp3"``.

    Args:
        timing_entries: Ordered timing entries (from :func:`timing.build_timing_map`).
        clips_dir: Directory containing per-paragraph MP3 clips.
        output_path: Destination path for the stitched MP3.
        sample_rate: Sample rate for intermediate WAV files.
        bitrate: MP3 encoding bitrate.

    Returns:
        *output_path* on success.

    Raises:
        FileNotFoundError: If a required clip is missing.
        RuntimeError: If ffmpeg is not installed or a conversion fails.
    """
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg is not installed or not on PATH")

    tmp_dir = Path(tempfile.mkdtemp(prefix="dub_stitch_"))
    wav_files: list[Path] = []

    try:
        for entry in timing_entries:
            pid = entry.paragraph.id

            # -- silence for pause_before ----------------------------------
            if entry.pause_before > 0:
                silence_path = tmp_dir / f"silence_{pid:04d}.wav"
                _generate_silence_wav(silence_path, entry.pause_before, sample_rate)
                wav_files.append(silence_path)

            # -- convert clip to WAV ---------------------------------------
            clip_path = clips_dir / f"p{pid:04d}.mp3"
            if not clip_path.exists():
                raise FileNotFoundError(
                    f"Expected clip at {clip_path} for paragraph {pid}"
                )

            wav_path = tmp_dir / f"clip_{pid:04d}.wav"
            _to_wav(clip_path, wav_path, sample_rate)
            wav_files.append(wav_path)

        # -- write ffmpeg concat list --------------------------------------
        concat_list = tmp_dir / "concat.txt"
        with concat_list.open("w") as fh:
            for wav in wav_files:
                # ffmpeg concat demuxer requires single-quoted paths
                safe = str(wav).replace("'", "'\\''")
                fh.write(f"file '{safe}'\n")

        # -- produce final MP3 ---------------------------------------------
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-ab", bitrate,
                "-ar", str(sample_rate),
                "-ac", "1",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        return output_path

    finally:
        # Clean up temp directory
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ======================================================================
# Internal helpers
# ======================================================================


def _generate_silence_wav(
    path: Path, duration: float, sample_rate: int = 44100
) -> None:
    """Write a mono 16-bit PCM WAV file containing silence.

    Avoids shelling out to ffmpeg for trivial silence segments.

    Args:
        path: Output WAV file path.
        duration: Length in seconds.
        sample_rate: Samples per second.
    """
    num_samples = int(sample_rate * duration)
    data_size = num_samples * 2  # 16-bit = 2 bytes per sample
    channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)

    with path.open("wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")

        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))                   # chunk size
        f.write(struct.pack("<H", 1))                    # PCM format
        f.write(struct.pack("<H", channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))

        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)


def _to_wav(src: Path, dst: Path, sample_rate: int = 44100) -> None:
    """Convert any audio file to mono 16-bit WAV via ffmpeg.

    Args:
        src: Input audio file.
        dst: Output WAV path.
        sample_rate: Target sample rate.
    """
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", str(src),
            "-ar", str(sample_rate),
            "-ac", "1",
            "-sample_fmt", "s16",
            str(dst),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
