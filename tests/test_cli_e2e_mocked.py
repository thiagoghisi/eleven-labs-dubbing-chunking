"""Contract tests for the full generate pipeline with mocked system boundaries.

Mocks ONLY at the outbound I/O boundary:
  - requests.post  → intercepts ElevenLabs TTS API calls
  - subprocess.run  → intercepts ffmpeg/ffprobe CLI invocations

Everything else runs for real through the CLI: Click argument parsing,
voice mapping, format detection, transcript parsing, consolidation,
text cleaning, timing map construction, clip file writing, and stitch
orchestration.

This is NOT a unit test — it's a boundary contract test. If the pipeline
changes what it sends to the API or how it invokes ffmpeg, this test breaks 
and that is expected and normal, it is a trade-off we are making.
"""

import shutil
import subprocess as real_subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from dub_chunk.cli import main

FIXTURES = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.e2e


# ======================================================================
# Expected pipeline outputs per format
# ======================================================================
# Each entry is the EXACT text that should arrive at the TTS API boundary
# after parse → consolidate → clean_for_tts.

EXPECTED_LABELED = [
    {
        "id": 1,
        "speaker": "Dr. Jung",
        "voice_id": "jung_voice_id",
        "text": (
            "The unconscious is not just a repository of repressed material."
            " It is a living system, constantly producing symbols and images"
            " that compensate for the one-sidedness of consciousness."
        ),
    },
    {
        "id": 2,
        "speaker": "Eissler",
        "voice_id": "eissler_voice_id",
        "text": (
            "That is a remarkable claim. How would you distinguish between"
            " what is merely repressed and what is genuinely creative in"
            " the unconscious?"
        ),
    },
    {
        "id": 3,
        "speaker": "Dr. Jung",
        "voice_id": "jung_voice_id",
        "text": (
            "You see, the repressed material is personal. It belongs to the"
            " individual history. But beneath that lies the collective"
            " unconscious, which contains the archetypes, the primordial"
            " images shared by all of humanity."
        ),
    },
    {
        "id": 4,
        "speaker": "Eissler",
        "voice_id": "eissler_voice_id",
        "text": "And these archetypes manifest in dreams?",
    },
    {
        "id": 5,
        "speaker": "Dr. Jung",
        "voice_id": "jung_voice_id",
        "text": (
            "In dreams, yes, but also in myths, in fairy tales, in the"
            " spontaneous fantasies of psychotic patients. They appear"
            " wherever the conscious mind relaxes its grip and allows"
            " the deeper layers to surface."
        ),
    },
    {
        "id": 6,
        "speaker": "Eissler",
        "voice_id": "eissler_voice_id",
        "text": (
            "Some of your critics have argued that the collective"
            " unconscious is an unfalsifiable concept. How do you"
            " respond to that charge?"
        ),
    },
    {
        "id": 7,
        "speaker": "Dr. Jung",
        "voice_id": "jung_voice_id",
        "text": (
            "I would say they have not looked carefully enough at the"
            " evidence. When a patient who has never read a word of"
            " mythology produces a dream image that corresponds precisely"
            " to an ancient motif, that is empirical data. One must have"
            " eyes to see it."
        ),
    },
    {
        "id": 8,
        "speaker": "Eissler",
        "voice_id": "eissler_voice_id",
        "text": (
            "Let us turn to the question of individuation. You have"
            " described it as the central process of psychological"
            " development. Could you elaborate?"
        ),
    },
]

EXPECTED_SRT = [
    {
        "id": 1,
        "speaker": "JUNG",
        "voice_id": "jung_voice_id",
        "text": (
            "The unconscious is not just a repository of repressed"
            " material. It is a living system."
            " It constantly produces symbols and images that compensate"
            " for the one-sidedness of consciousness."
        ),
    },
    {
        "id": 2,
        "speaker": "EISSLER",
        "voice_id": "eissler_voice_id",
        "text": (
            "That is a remarkable claim. How would you distinguish"
            " between what is merely repressed and what is genuinely"
            " creative?"
        ),
    },
    {
        "id": 3,
        "speaker": "JUNG",
        "voice_id": "jung_voice_id",
        "text": (
            "The repressed material is personal. It belongs to the"
            " individual history."
            " But beneath that lies the collective unconscious, which"
            " contains the archetypes shared by all of humanity."
        ),
    },
    {
        "id": 4,
        "speaker": "EISSLER",
        "voice_id": "eissler_voice_id",
        "text": "And these archetypes manifest in dreams?",
    },
    {
        "id": 5,
        "speaker": "JUNG",
        "voice_id": "jung_voice_id",
        "text": (
            "In dreams, yes, but also in myths, in fairy tales, in the"
            " spontaneous fantasies of psychotic patients."
        ),
    },
    {
        "id": 6,
        "speaker": "EISSLER",
        "voice_id": "eissler_voice_id",
        "text": (
            "Some critics have argued that the collective unconscious"
            " is unfalsifiable. How do you respond?"
        ),
    },
]

EXPECTED_PLAIN = [
    {
        "id": 1,
        "speaker": "Speaker",
        "voice_id": "narrator_voice_id",
        "text": (
            "The unconscious is not just a repository of repressed"
            " material. It is a living system, constantly producing"
            " symbols and images that compensate for the one-sidedness"
            " of consciousness."
            " That is a remarkable claim. How would you distinguish"
            " between what is merely repressed and what is genuinely"
            " creative in the unconscious?"
            " The repressed material is personal. It belongs to the"
            " individual history. But beneath that lies the collective"
            " unconscious, which contains the archetypes, the primordial"
            " images shared by all of humanity."
            " And these archetypes manifest in dreams?"
            " In dreams, yes, but also in myths, in fairy tales, in the"
            " spontaneous fantasies of psychotic patients. They appear"
            " wherever the conscious mind relaxes its grip and allows"
            " the deeper layers to surface."
            " Some critics have argued that the collective unconscious"
            " is an unfalsifiable concept. How do you respond to that"
            " charge?"
            " I would say they have not looked carefully enough at the"
            " evidence. When a patient who has never read a word of"
            " mythology produces a dream image that corresponds precisely"
            " to an ancient motif, that is empirical data."
        ),
    },
]


# ======================================================================
# Shared mock factories
# ======================================================================


def _make_tts_mock(captures):
    """Create a requests.post mock that captures TTS API calls."""

    def mock_post(url, json=None, headers=None, timeout=None):
        captures["tts_calls"].append({
            "url": url,
            "text": json["text"],
            "model_id": json["model_id"],
            "voice_settings": json["voice_settings"],
            "api_key": headers.get("xi-api-key"),
        })
        response = MagicMock()
        response.status_code = 200
        response.content = b"FAKE_MP3_BYTES"
        return response

    return mock_post


def _make_subprocess_mock(captures):
    """Create a subprocess.run mock that captures ffmpeg/ffprobe calls.

    Side effects:
      - ffmpeg concat: creates a dummy output file (so ffprobe path check passes)
      - ffmpeg concat: reads concat.txt content before temp cleanup
      - ffprobe: returns fake duration JSON
    """

    def mock_run(cmd, **kwargs):
        cmd = list(cmd)
        captures["subprocess_calls"].append(cmd)

        if cmd[0] == "ffprobe":
            return real_subprocess.CompletedProcess(
                cmd, 0,
                stdout='{"format": {"duration": "42.5"}}',
                stderr="",
            )

        if cmd[0] == "ffmpeg":
            if "-f" in cmd and "concat" in cmd:
                i_idx = cmd.index("-i")
                concat_file = Path(cmd[i_idx + 1])
                if concat_file.exists():
                    captures["concat_file_content"] = concat_file.read_text()
                out = Path(cmd[-1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"FAKE_STITCHED_MP3")

            return real_subprocess.CompletedProcess(
                cmd, 0, stdout="", stderr=""
            )

        return real_subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return mock_run


def _run_pipeline(tmp_path, fixture_name, cli_args, captures):
    """Run the generate pipeline with mocked boundaries.

    Returns the CliRunner result.
    """
    input_file = tmp_path / fixture_name
    shutil.copy(FIXTURES / fixture_name, input_file)

    runner = CliRunner()
    with (
        patch(
            "dub_chunk.tts.requests.post",
            side_effect=_make_tts_mock(captures),
        ),
        patch(
            "dub_chunk.stitch.subprocess.run",
            side_effect=_make_subprocess_mock(captures),
        ),
    ):
        result = runner.invoke(main, cli_args(input_file))

    return result, input_file


def _extract_concat_filenames(captures):
    """Parse concat.txt content into a list of WAV filenames."""
    content = captures["concat_file_content"]
    assert content is not None, "concat.txt was not captured"
    lines = [line for line in content.strip().split("\n") if line]
    return [Path(line.split("'")[1]).name for line in lines]


def _assert_tts_calls(captures, expected_paragraphs):
    """Assert TTS API calls match expected paragraphs exactly."""
    tts_calls = captures["tts_calls"]

    assert len(tts_calls) == len(expected_paragraphs), (
        f"Expected {len(expected_paragraphs)} TTS calls, "
        f"got {len(tts_calls)}"
    )

    for i, (call, expected) in enumerate(
        zip(tts_calls, expected_paragraphs)
    ):
        assert call["url"] == (
            f"https://api.elevenlabs.io/v1/text-to-speech/"
            f"{expected['voice_id']}"
        ), f"TTS call {i}: unexpected URL '{call['url']}'"

        assert call["api_key"] == "test_api_key_123", (
            f"TTS call {i}: wrong API key"
        )

        assert call["model_id"] == "eleven_multilingual_v2", (
            f"TTS call {i}: wrong model_id"
        )

        assert call["text"] == expected["text"], (
            f"TTS call {i} (paragraph {expected['id']}, "
            f"{expected['speaker']}): text mismatch.\n"
            f"  Expected: {expected['text']!r}\n"
            f"  Got:      {call['text']!r}"
        )

        assert call["voice_settings"] == {
            "stability": 0.65,
            "similarity_boost": 0.80,
            "style": 0.35,
            "use_speaker_boost": True,
        }, f"TTS call {i}: wrong voice_settings"


def _assert_clip_files(clips_dir, expected_paragraphs):
    """Assert clip MP3 files were written to disk."""
    for expected in expected_paragraphs:
        clip_file = clips_dir / f"p{expected['id']:04d}.mp3"
        assert clip_file.exists(), f"Clip file missing: {clip_file.name}"
        assert clip_file.read_bytes() == b"FAKE_MP3_BYTES", (
            f"Clip {clip_file.name}: content mismatch"
        )


def _assert_ffmpeg_conversions(ffmpeg_calls, expected_paragraphs):
    """Assert clip-to-WAV conversion calls have correct argv."""
    n = len(expected_paragraphs)
    conversion_calls = ffmpeg_calls[:n]

    for i, (cmd, expected) in enumerate(
        zip(conversion_calls, expected_paragraphs)
    ):
        pid = expected["id"]
        assert cmd[0:3] == ["ffmpeg", "-y", "-i"], (
            f"Conversion {i}: wrong prefix"
        )
        assert Path(cmd[3]).name == f"p{pid:04d}.mp3", (
            f"Conversion {i}: expected input p{pid:04d}.mp3, "
            f"got {Path(cmd[3]).name}"
        )
        assert cmd[4:8] == ["-ar", "44100", "-ac", "1"], (
            f"Conversion {i}: wrong audio params"
        )
        assert cmd[8:10] == ["-sample_fmt", "s16"], (
            f"Conversion {i}: wrong sample format"
        )
        assert Path(cmd[10]).name == f"clip_{pid:04d}.wav", (
            f"Conversion {i}: expected output clip_{pid:04d}.wav, "
            f"got {Path(cmd[10]).name}"
        )


def _assert_ffmpeg_concat(concat_cmd, output_name):
    """Assert the final ffmpeg concat call has correct argv."""
    assert concat_cmd[0:2] == ["ffmpeg", "-y"]
    assert concat_cmd[2:4] == ["-f", "concat"]
    assert concat_cmd[4:6] == ["-safe", "0"]
    assert concat_cmd[6] == "-i"
    assert Path(concat_cmd[7]).name == "concat.txt"
    assert concat_cmd[8:10] == ["-ab", "192k"]
    assert concat_cmd[10:12] == ["-ar", "44100"]
    assert concat_cmd[12:14] == ["-ac", "1"]
    assert Path(concat_cmd[14]).name == output_name


def _assert_ffprobe(ffprobe_calls, output_name):
    """Assert the ffprobe duration call has correct argv."""
    assert len(ffprobe_calls) == 1, (
        f"Expected 1 ffprobe call, got {len(ffprobe_calls)}"
    )
    cmd = ffprobe_calls[0]
    assert cmd[0] == "ffprobe"
    assert cmd[1:3] == ["-v", "error"]
    assert cmd[3:5] == ["-show_entries", "format=duration"]
    assert cmd[5:7] == ["-of", "json"]
    assert Path(cmd[7]).name == output_name


# ======================================================================
# Test: sample_labeled.txt (8 paragraphs, 2 speakers, alternating)
# ======================================================================


class TestFullGenerateLabeledPipeline:
    """Labeled format: 8 paragraphs, alternating Dr. Jung / Eissler."""

    def test_boundary_contracts(self, tmp_path):
        captures = {
            "tts_calls": [],
            "subprocess_calls": [],
            "concat_file_content": None,
        }
        output_name = "dubbed_output.mp3"

        result, input_file = _run_pipeline(
            tmp_path,
            "sample_labeled.txt",
            lambda f: [
                "generate", str(f),
                "--voice", "Dr. Jung=jung_voice_id",
                "--voice", "Eissler=eissler_voice_id",
                "--api-key", "test_api_key_123",
                "--output", str(tmp_path / output_name),
                "--keep-clips", "--rate-limit", "0",
            ],
            captures,
        )

        assert result.exit_code == 0, (
            f"CLI failed:\n{result.output}"
        )

        # -- TTS API calls: 8 paragraphs, exact text ---
        _assert_tts_calls(captures, EXPECTED_LABELED)

        # -- Clip files on disk ---
        clips_dir = tmp_path / "sample_labeled_clips"
        _assert_clip_files(clips_dir, EXPECTED_LABELED)

        # -- ffmpeg: 8 conversions + 1 concat = 9 calls ---
        ffmpeg_calls = [
            c for c in captures["subprocess_calls"] if c[0] == "ffmpeg"
        ]
        ffprobe_calls = [
            c for c in captures["subprocess_calls"] if c[0] == "ffprobe"
        ]
        assert len(ffmpeg_calls) == 9, (
            f"Expected 9 ffmpeg calls, got {len(ffmpeg_calls)}"
        )

        _assert_ffmpeg_conversions(ffmpeg_calls, EXPECTED_LABELED)
        _assert_ffmpeg_concat(ffmpeg_calls[8], output_name)

        # -- concat.txt: 1 clip + 7 × (silence + clip) = 15 entries ---
        # All speaker switches (0.8s pause each)
        filenames = _extract_concat_filenames(captures)
        expected_concat = [
            "clip_0001.wav",
            "silence_0002.wav", "clip_0002.wav",
            "silence_0003.wav", "clip_0003.wav",
            "silence_0004.wav", "clip_0004.wav",
            "silence_0005.wav", "clip_0005.wav",
            "silence_0006.wav", "clip_0006.wav",
            "silence_0007.wav", "clip_0007.wav",
            "silence_0008.wav", "clip_0008.wav",
        ]
        assert filenames == expected_concat, (
            f"concat.txt mismatch.\n"
            f"  Expected: {expected_concat}\n"
            f"  Got:      {filenames}"
        )

        # -- ffprobe ---
        _assert_ffprobe(ffprobe_calls, output_name)

        # -- CLI output ---
        assert "Done!" in result.output
        assert "42.5" in result.output


# ======================================================================
# Test: sample.srt (6 paragraphs, 2 speakers, alternating)
# ======================================================================


class TestFullGenerateSrtPipeline:
    """SRT format: 6 paragraphs, alternating JUNG / EISSLER."""

    def test_boundary_contracts(self, tmp_path):
        captures = {
            "tts_calls": [],
            "subprocess_calls": [],
            "concat_file_content": None,
        }
        output_name = "dubbed_output.mp3"

        result, input_file = _run_pipeline(
            tmp_path,
            "sample.srt",
            lambda f: [
                "generate", str(f),
                "--voice", "JUNG=jung_voice_id",
                "--voice", "EISSLER=eissler_voice_id",
                "--api-key", "test_api_key_123",
                "--output", str(tmp_path / output_name),
                "--keep-clips", "--rate-limit", "0",
            ],
            captures,
        )

        assert result.exit_code == 0, (
            f"CLI failed:\n{result.output}"
        )

        # -- TTS API calls: 6 paragraphs, exact text ---
        _assert_tts_calls(captures, EXPECTED_SRT)

        # -- Clip files on disk ---
        clips_dir = tmp_path / "sample_clips"
        _assert_clip_files(clips_dir, EXPECTED_SRT)

        # -- ffmpeg: 6 conversions + 1 concat = 7 calls ---
        ffmpeg_calls = [
            c for c in captures["subprocess_calls"] if c[0] == "ffmpeg"
        ]
        ffprobe_calls = [
            c for c in captures["subprocess_calls"] if c[0] == "ffprobe"
        ]
        assert len(ffmpeg_calls) == 7, (
            f"Expected 7 ffmpeg calls, got {len(ffmpeg_calls)}"
        )

        _assert_ffmpeg_conversions(ffmpeg_calls, EXPECTED_SRT)
        _assert_ffmpeg_concat(ffmpeg_calls[6], output_name)

        # -- concat.txt: 1 clip + 5 × (silence + clip) = 11 entries ---
        # All speaker switches (0.8s pause each)
        filenames = _extract_concat_filenames(captures)
        expected_concat = [
            "clip_0001.wav",
            "silence_0002.wav", "clip_0002.wav",
            "silence_0003.wav", "clip_0003.wav",
            "silence_0004.wav", "clip_0004.wav",
            "silence_0005.wav", "clip_0005.wav",
            "silence_0006.wav", "clip_0006.wav",
        ]
        assert filenames == expected_concat, (
            f"concat.txt mismatch.\n"
            f"  Expected: {expected_concat}\n"
            f"  Got:      {filenames}"
        )

        # -- ffprobe ---
        _assert_ffprobe(ffprobe_calls, output_name)

        # -- CLI output ---
        assert "Done!" in result.output
        assert "42.5" in result.output


# ======================================================================
# Test: sample_plain.txt (7 paragraphs → 1 after consolidation)
# ======================================================================


class TestFullGeneratePlainPipeline:
    """Plain text: 7 paragraphs, all same speaker → consolidated to 1."""

    def test_boundary_contracts(self, tmp_path):
        captures = {
            "tts_calls": [],
            "subprocess_calls": [],
            "concat_file_content": None,
        }
        output_name = "dubbed_output.mp3"

        result, input_file = _run_pipeline(
            tmp_path,
            "sample_plain.txt",
            lambda f: [
                "generate", str(f),
                "--format", "plain",
                "--voice", "Speaker=narrator_voice_id",
                "--api-key", "test_api_key_123",
                "--output", str(tmp_path / output_name),
                "--keep-clips", "--rate-limit", "0",
            ],
            captures,
        )

        assert result.exit_code == 0, (
            f"CLI failed:\n{result.output}"
        )

        # -- TTS API calls: 1 paragraph (all merged) ---
        _assert_tts_calls(captures, EXPECTED_PLAIN)

        # -- Clip files on disk ---
        clips_dir = tmp_path / "sample_plain_clips"
        _assert_clip_files(clips_dir, EXPECTED_PLAIN)

        # -- ffmpeg: 1 conversion + 1 concat = 2 calls ---
        ffmpeg_calls = [
            c for c in captures["subprocess_calls"] if c[0] == "ffmpeg"
        ]
        ffprobe_calls = [
            c for c in captures["subprocess_calls"] if c[0] == "ffprobe"
        ]
        assert len(ffmpeg_calls) == 2, (
            f"Expected 2 ffmpeg calls, got {len(ffmpeg_calls)}"
        )

        _assert_ffmpeg_conversions(ffmpeg_calls, EXPECTED_PLAIN)
        _assert_ffmpeg_concat(ffmpeg_calls[1], output_name)

        # -- concat.txt: just 1 clip (no pauses — single paragraph) ---
        filenames = _extract_concat_filenames(captures)
        expected_concat = ["clip_0001.wav"]
        assert filenames == expected_concat, (
            f"concat.txt mismatch.\n"
            f"  Expected: {expected_concat}\n"
            f"  Got:      {filenames}"
        )

        # -- ffprobe ---
        _assert_ffprobe(ffprobe_calls, output_name)

        # -- CLI output ---
        assert "Done!" in result.output
        assert "42.5" in result.output
