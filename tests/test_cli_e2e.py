"""E2E tests for CLI user journeys via Click's CliRunner.

These test the top-level user journeys without API calls or ffmpeg:
  - parse: preview a transcript (all 3 formats)
  - estimate: cost/duration estimate
  - generate --dry-run: full pipeline minus TTS + stitch
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from dub_chunk.cli import main

FIXTURES = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.e2e


@pytest.fixture
def runner():
    return CliRunner()


# ======================================================================
# Journey 1: Parse a transcript and see structured output
# ======================================================================


class TestParseJourney:
    """User parses a transcript to preview its structure before generating."""

    def test_parse_labeled_transcript_shows_speakers_and_stats(self, runner):
        result = runner.invoke(main, ["parse", str(FIXTURES / "sample_labeled.txt")])
        assert result.exit_code == 0
        assert "labeled" in result.output.lower()
        assert "Dr. Jung" in result.output
        assert "Eissler" in result.output
        assert "Paragraphs:" in result.output
        assert "Words:" in result.output

    def test_parse_srt_shows_speakers_and_stats(self, runner):
        result = runner.invoke(main, ["parse", str(FIXTURES / "sample.srt")])
        assert result.exit_code == 0
        assert "srt" in result.output.lower()
        assert "JUNG" in result.output
        assert "EISSLER" in result.output
        assert "Paragraphs:" in result.output

    def test_parse_plain_text_with_explicit_format(self, runner):
        result = runner.invoke(
            main, ["parse", str(FIXTURES / "sample_plain.txt"), "--format", "plain"]
        )
        assert result.exit_code == 0
        assert "plain" in result.output.lower()
        assert "Speaker" in result.output
        assert "Paragraphs:" in result.output

    def test_parse_shows_preview_of_first_paragraphs(self, runner):
        result = runner.invoke(main, ["parse", str(FIXTURES / "sample_labeled.txt")])
        assert result.exit_code == 0
        assert "Preview" in result.output
        # Should show paragraph IDs in preview
        assert "[" in result.output

    def test_parse_nonexistent_file_fails(self, runner):
        result = runner.invoke(main, ["parse", "/tmp/nonexistent_file.txt"])
        assert result.exit_code != 0

    def test_parse_unknown_extension_without_format_fails(self, runner, tmp_path):
        weird = tmp_path / "transcript.md"
        weird.write_text("Some text here")
        result = runner.invoke(main, ["parse", str(weird)])
        assert result.exit_code != 0
        assert "format" in result.output.lower()


# ======================================================================
# Journey 2: Estimate cost before committing to API calls
# ======================================================================


class TestEstimateJourney:
    """User checks cost and duration before running generate."""

    def test_estimate_labeled_shows_cost_and_duration(self, runner):
        result = runner.invoke(main, ["estimate", str(FIXTURES / "sample_labeled.txt")])
        assert result.exit_code == 0
        assert "$" in result.output
        assert "Characters:" in result.output
        assert "duration" in result.output.lower()
        assert "consolidated" in result.output.lower()

    def test_estimate_srt_shows_cost(self, runner):
        result = runner.invoke(main, ["estimate", str(FIXTURES / "sample.srt")])
        assert result.exit_code == 0
        assert "$" in result.output

    def test_estimate_with_no_consolidate_shows_raw_count(self, runner):
        result = runner.invoke(
            main,
            ["estimate", str(FIXTURES / "sample_labeled.txt"), "--no-consolidate"],
        )
        assert result.exit_code == 0
        assert "$" in result.output

    def test_estimate_plain_text_with_format_flag(self, runner):
        result = runner.invoke(
            main,
            ["estimate", str(FIXTURES / "sample_plain.txt"), "--format", "plain"],
        )
        assert result.exit_code == 0
        assert "$" in result.output


# ======================================================================
# Journey 3: Dry-run the full pipeline (no API, no ffmpeg)
# ======================================================================


class TestDryRunJourney:
    """User runs generate --dry-run to see timing map and cost without spending."""

    def test_dry_run_labeled_shows_timing_map(self, runner):
        result = runner.invoke(
            main,
            [
                "generate",
                str(FIXTURES / "sample_labeled.txt"),
                "--voice", "Dr. Jung=fake_voice_id",
                "--voice", "Eissler=fake_voice_id2",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Paragraphs:" in result.output
        assert "Est. cost:" in result.output
        assert "$" in result.output

    def test_dry_run_srt_shows_timing_map(self, runner):
        result = runner.invoke(
            main,
            [
                "generate",
                str(FIXTURES / "sample.srt"),
                "--voice", "JUNG=fake1",
                "--voice", "EISSLER=fake2",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    def test_dry_run_does_not_require_api_key(self, runner):
        """Dry-run should work without ELEVENLABS_API_KEY set."""
        result = runner.invoke(
            main,
            [
                "generate",
                str(FIXTURES / "sample_labeled.txt"),
                "--voice", "Dr. Jung=fake",
                "--voice", "Eissler=fake",
                "--dry-run",
            ],
            env={"ELEVENLABS_API_KEY": ""},
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    def test_dry_run_with_limit_restricts_paragraphs(self, runner):
        result = runner.invoke(
            main,
            [
                "generate",
                str(FIXTURES / "sample_labeled.txt"),
                "--voice", "Dr. Jung=fake",
                "--voice", "Eissler=fake",
                "--dry-run",
                "--limit", "2",
            ],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Limited to" in result.output

    def test_dry_run_with_total_duration_shows_scaled_timing(self, runner):
        result = runner.invoke(
            main,
            [
                "generate",
                str(FIXTURES / "sample_labeled.txt"),
                "--voice", "Dr. Jung=fake",
                "--voice", "Eissler=fake",
                "--dry-run",
                "--total-duration", "120",
            ],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    def test_dry_run_with_no_consolidate(self, runner):
        result = runner.invoke(
            main,
            [
                "generate",
                str(FIXTURES / "sample_labeled.txt"),
                "--voice", "Dr. Jung=fake",
                "--voice", "Eissler=fake",
                "--dry-run",
                "--no-consolidate",
            ],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    def test_dry_run_with_max_chunk_words_splits_long_paragraphs(self, runner):
        result = runner.invoke(
            main,
            [
                "generate",
                str(FIXTURES / "sample_labeled.txt"),
                "--voice", "Dr. Jung=fake",
                "--voice", "Eissler=fake",
                "--dry-run",
                "--max-chunk-words", "15",
            ],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Split:" in result.output


# ======================================================================
# Journey 4: Error handling — user provides bad input
# ======================================================================


class TestErrorJourneys:
    """User makes mistakes; CLI gives clear feedback."""

    def test_generate_without_api_key_fails(self, runner):
        result = runner.invoke(
            main,
            [
                "generate",
                str(FIXTURES / "sample_labeled.txt"),
                "--voice", "Dr. Jung=fake",
                "--voice", "Eissler=fake",
            ],
            env={"ELEVENLABS_API_KEY": ""},
        )
        assert result.exit_code != 0
        assert "API key" in result.output

    def test_generate_with_bad_voice_format_fails(self, runner):
        result = runner.invoke(
            main,
            [
                "generate",
                str(FIXTURES / "sample_labeled.txt"),
                "--voice", "no_equals_sign",
                "--dry-run",
            ],
        )
        assert result.exit_code != 0

    def test_generate_with_bad_speed_format_fails(self, runner):
        result = runner.invoke(
            main,
            [
                "generate",
                str(FIXTURES / "sample_labeled.txt"),
                "--voice", "Dr. Jung=fake",
                "--voice", "Eissler=fake",
                "--speed", "Jung=notanumber",
                "--dry-run",
            ],
        )
        assert result.exit_code != 0

    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
