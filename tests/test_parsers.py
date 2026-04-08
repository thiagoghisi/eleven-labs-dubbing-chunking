"""Unit tests for parsers: srt, labeled_text, plain_text.

Tests the input contract: raw text → list[Paragraph] with correct
speaker, text, word_count, and sequential IDs starting at 0.
"""

from pathlib import Path

import pytest

from dub_chunk.parsers.srt import parse_srt
from dub_chunk.parsers.labeled_text import parse_labeled_text
from dub_chunk.parsers.plain_text import parse_plain_text

FIXTURES = Path(__file__).parent / "fixtures"


# ======================================================================
# SRT Parser
# ======================================================================


class TestParseSrt:

    def test_groups_consecutive_same_speaker_cues(self):
        text = (
            "1\n00:00:01,000 --> 00:00:05,000\n[JUNG] First part.\n\n"
            "2\n00:00:06,000 --> 00:00:10,000\n[JUNG] Second part.\n\n"
            "3\n00:00:11,000 --> 00:00:15,000\n[EISSLER] A response.\n"
        )
        result = parse_srt(text)
        assert len(result) == 2
        assert result[0].speaker == "JUNG"
        assert "First part" in result[0].text
        assert "Second part" in result[0].text
        assert result[1].speaker == "EISSLER"

    def test_speaker_change_creates_new_paragraph(self):
        text = (
            "1\n00:00:01,000 --> 00:00:05,000\n[A] Hello.\n\n"
            "2\n00:00:06,000 --> 00:00:10,000\n[B] Hi.\n\n"
            "3\n00:00:11,000 --> 00:00:15,000\n[A] How are you?\n"
        )
        result = parse_srt(text)
        assert len(result) == 3
        assert [p.speaker for p in result] == ["A", "B", "A"]

    def test_ids_are_sequential_from_zero(self):
        text = (
            "1\n00:00:01,000 --> 00:00:05,000\n[X] One.\n\n"
            "2\n00:00:06,000 --> 00:00:10,000\n[Y] Two.\n"
        )
        result = parse_srt(text)
        assert [p.id for p in result] == [0, 1]

    def test_default_speaker_when_no_label(self):
        text = "1\n00:00:01,000 --> 00:00:05,000\nNo speaker label here.\n"
        result = parse_srt(text)
        assert len(result) == 1
        assert result[0].speaker == "Speaker"

    def test_timestamp_with_period_separator(self):
        text = "1\n00:00:01.000 --> 00:00:05.000\n[JUNG] Period separator.\n"
        result = parse_srt(text)
        assert len(result) == 1
        assert result[0].speaker == "JUNG"

    def test_timing_metadata_attached(self):
        text = "1\n00:01:30,500 --> 00:02:00,000\n[X] Timed text.\n"
        result = parse_srt(text)
        assert hasattr(result[0], "_timing")
        start, end = result[0]._timing
        assert start == 90.5
        assert end == 120.0

    def test_empty_text_returns_empty_list(self):
        assert parse_srt("") == []
        assert parse_srt("   \n\n  ") == []

    def test_malformed_blocks_are_skipped(self):
        text = (
            "not_a_number\n00:00:01,000 --> 00:00:05,000\nBad index.\n\n"
            "2\n00:00:06,000 --> 00:00:10,000\n[GOOD] Valid cue.\n"
        )
        result = parse_srt(text)
        assert len(result) == 1
        assert result[0].speaker == "GOOD"

    def test_multiline_cue_text_joined(self):
        text = (
            "1\n00:00:01,000 --> 00:00:05,000\n[JUNG] Line one.\n"
            "Line two continues.\n"
        )
        result = parse_srt(text)
        assert "Line one." in result[0].text
        assert "Line two continues." in result[0].text

    def test_parses_real_fixture(self):
        text = (FIXTURES / "sample.srt").read_text()
        result = parse_srt(text)
        assert len(result) > 0
        speakers = {p.speaker for p in result}
        assert "JUNG" in speakers
        assert "EISSLER" in speakers
        assert all(p.word_count > 0 for p in result)

    def test_word_count_computed_for_merged_cues(self):
        text = (
            "1\n00:00:01,000 --> 00:00:05,000\n[A] One two.\n\n"
            "2\n00:00:06,000 --> 00:00:10,000\n[A] Three four five.\n"
        )
        result = parse_srt(text)
        assert len(result) == 1
        assert result[0].word_count == 5


# ======================================================================
# Labeled Text Parser
# ======================================================================


class TestParseLabeledText:

    def test_parses_speaker_and_text(self):
        text = "Jung: The unconscious is real.\n\nEissler: Tell me more."
        result = parse_labeled_text(text)
        assert len(result) == 2
        assert result[0].speaker == "Jung"
        assert result[0].text == "The unconscious is real."
        assert result[1].speaker == "Eissler"

    def test_ids_sequential_from_zero(self):
        text = "A: First.\n\nB: Second.\n\nC: Third."
        result = parse_labeled_text(text)
        assert [p.id for p in result] == [0, 1, 2]

    def test_continuation_lines_appended(self):
        text = "Jung: First line\nsecond line\nthird line."
        result = parse_labeled_text(text)
        assert len(result) == 1
        assert "First line" in result[0].text
        assert "second line" in result[0].text
        assert "third line" in result[0].text

    def test_multiple_speakers_in_one_block(self):
        text = "Jung: My part.\nEissler: Your part."
        result = parse_labeled_text(text)
        assert len(result) == 2
        assert result[0].speaker == "Jung"
        assert result[1].speaker == "Eissler"

    def test_default_speaker_when_no_label(self):
        text = "Text without any speaker label at all."
        result = parse_labeled_text(text)
        assert len(result) == 1
        assert result[0].speaker == "Speaker"

    def test_empty_text_returns_empty_list(self):
        assert parse_labeled_text("") == []
        assert parse_labeled_text("   \n\n  ") == []

    def test_speaker_with_special_chars(self):
        """Speaker names can include dots, hyphens, underscores, spaces."""
        text = "Dr. Jung-Senior: Some text."
        result = parse_labeled_text(text)
        assert result[0].speaker == "Dr. Jung-Senior"

    def test_parses_real_fixture(self):
        text = (FIXTURES / "sample_labeled.txt").read_text()
        result = parse_labeled_text(text)
        assert len(result) > 0
        speakers = {p.speaker for p in result}
        assert "Dr. Jung" in speakers
        assert "Eissler" in speakers
        assert all(p.word_count > 0 for p in result)

    def test_word_count_correct(self):
        text = "Jung: One two three four five."
        result = parse_labeled_text(text)
        assert result[0].word_count == 5


# ======================================================================
# Plain Text Parser
# ======================================================================


class TestParsePlainText:

    def test_splits_on_double_newlines(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = parse_plain_text(text)
        assert len(result) == 3

    def test_all_assigned_default_speaker(self):
        text = "One.\n\nTwo.\n\nThree."
        result = parse_plain_text(text)
        assert all(p.speaker == "Speaker" for p in result)

    def test_custom_default_speaker(self):
        text = "One.\n\nTwo."
        result = parse_plain_text(text, default_speaker="Narrator")
        assert all(p.speaker == "Narrator" for p in result)

    def test_ids_sequential_from_zero(self):
        text = "A.\n\nB.\n\nC."
        result = parse_plain_text(text)
        assert [p.id for p in result] == [0, 1, 2]

    def test_line_wrapping_collapsed(self):
        text = "Line one\nline two\nline three."
        result = parse_plain_text(text)
        assert len(result) == 1
        assert result[0].text == "Line one line two line three."

    def test_empty_text_returns_empty_list(self):
        assert parse_plain_text("") == []
        assert parse_plain_text("   \n\n  ") == []

    def test_multiple_blank_lines_treated_as_one_separator(self):
        text = "First.\n\n\n\nSecond."
        result = parse_plain_text(text)
        assert len(result) == 2

    def test_parses_real_fixture(self):
        text = (FIXTURES / "sample_plain.txt").read_text()
        result = parse_plain_text(text)
        assert len(result) > 0
        assert all(p.speaker == "Speaker" for p in result)
        assert all(p.word_count > 0 for p in result)

    def test_word_count_correct(self):
        text = "One two three."
        result = parse_plain_text(text)
        assert result[0].word_count == 3
