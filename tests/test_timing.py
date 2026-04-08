"""Unit tests for timing.py — timing map construction."""

import pytest

from dub_chunk.models import Paragraph, TimingEntry
from dub_chunk.timing import build_timing_map


def _p(id, speaker, text):
    return Paragraph(id=id, speaker=speaker, text=text)


# ======================================================================
# Estimate mode (total_duration == 0, uses 150 WPM)
# ======================================================================


class TestEstimateMode:

    def test_single_paragraph_duration_at_150wpm(self):
        paras = [_p(1, "A", " ".join(["word"] * 150))]  # 150 words = 60s
        result = build_timing_map(paras, total_duration=0)
        assert len(result) == 1
        assert result[0].estimated_duration == pytest.approx(60.0, abs=0.01)

    def test_first_paragraph_has_zero_pause(self):
        result = build_timing_map([_p(1, "A", "Hello world")])
        assert result[0].pause_before == 0.0

    def test_start_time_is_zero_for_first(self):
        result = build_timing_map([_p(1, "A", "Hello world")])
        assert result[0].start_time == 0.0

    def test_duration_proportional_to_word_count(self):
        paras = [
            _p(1, "A", "one two three"),  # 3 words
            _p(2, "B", "one two three four five six"),  # 6 words
        ]
        result = build_timing_map(paras, total_duration=0)
        assert result[1].estimated_duration == pytest.approx(
            result[0].estimated_duration * 2, abs=0.01
        )


# ======================================================================
# Scale mode (total_duration > 0)
# ======================================================================


class TestScaleMode:

    def test_speech_durations_sum_to_available_time(self):
        paras = [
            _p(1, "A", "one two three"),
            _p(2, "A", "four five six"),
        ]
        total = 120.0
        result = build_timing_map(paras, total_duration=total, pause_same=1.0)
        speech_sum = sum(e.estimated_duration for e in result)
        pause_sum = sum(e.pause_before for e in result)
        assert speech_sum + pause_sum == pytest.approx(total, abs=0.1)

    def test_proportional_distribution_by_word_count(self):
        paras = [
            _p(1, "A", "short"),  # 1 word
            _p(2, "A", "longer text here yes"),  # 4 words
        ]
        result = build_timing_map(paras, total_duration=100, pause_same=0)
        # 4:1 ratio
        assert result[1].estimated_duration == pytest.approx(
            result[0].estimated_duration * 4, abs=0.1
        )

    def test_pauses_not_scaled(self):
        """Pauses are fixed, only speech durations scale."""
        paras = [
            _p(1, "A", "hello"),
            _p(2, "B", "world"),
        ]
        result = build_timing_map(
            paras, total_duration=100, pause_same=1.0, pause_switch=2.5
        )
        assert result[1].pause_before == 2.5  # fixed, not scaled


# ======================================================================
# Pause logic
# ======================================================================


class TestPauseLogic:

    def test_same_speaker_pause(self):
        paras = [_p(1, "A", "First."), _p(2, "A", "Second.")]
        result = build_timing_map(paras, pause_same=1.5)
        assert result[1].pause_before == 1.5

    def test_speaker_switch_pause(self):
        paras = [_p(1, "A", "Hello."), _p(2, "B", "Hi.")]
        result = build_timing_map(paras, pause_switch=3.0)
        assert result[1].pause_before == 3.0

    def test_long_paragraph_adds_extra_pause(self):
        long_text = " ".join(["word"] * 201)  # > 200 threshold
        paras = [
            _p(1, "A", long_text),
            _p(2, "B", "Response."),
        ]
        result = build_timing_map(
            paras, pause_switch=2.5, pause_long_para=1.0, long_para_threshold=200
        )
        # Switch pause + long-para bonus
        assert result[1].pause_before == 3.5

    def test_no_extra_pause_below_threshold(self):
        paras = [
            _p(1, "A", "Short paragraph."),
            _p(2, "B", "Response."),
        ]
        result = build_timing_map(
            paras, pause_switch=2.5, pause_long_para=1.0, long_para_threshold=200
        )
        assert result[1].pause_before == 2.5  # no bonus


# ======================================================================
# Cumulative start times
# ======================================================================


class TestStartTimes:

    def test_start_time_accumulates_pauses_and_durations(self):
        paras = [_p(1, "A", "First."), _p(2, "B", "Second.")]
        result = build_timing_map(paras, total_duration=0, pause_switch=2.0)
        # Second starts at: duration_of_first + pause_before_second
        expected = result[0].estimated_duration + 2.0
        assert result[1].start_time == pytest.approx(expected, abs=0.01)

    def test_three_entries_cumulative(self):
        paras = [
            _p(1, "A", "One."),
            _p(2, "A", "Two."),
            _p(3, "B", "Three."),
        ]
        result = build_timing_map(paras, pause_same=1.0, pause_switch=2.0)
        # Each start_time should be greater than the previous
        assert result[0].start_time < result[1].start_time < result[2].start_time


# ======================================================================
# Edge cases
# ======================================================================


class TestEdgeCases:

    def test_empty_input(self):
        assert build_timing_map([]) == []

    def test_all_empty_text_paragraphs(self):
        """When total_words == 0, durations are 0 but pauses still apply."""
        paras = [_p(1, "A", ""), _p(2, "B", "")]
        result = build_timing_map(paras)
        assert len(result) == 2
        assert all(e.estimated_duration == 0.0 for e in result)

    def test_values_rounded_to_four_decimals(self):
        paras = [_p(1, "A", "one two three four five six seven")]
        result = build_timing_map(paras)
        # Check rounding by verifying decimal places
        dur_str = str(result[0].estimated_duration)
        if "." in dur_str:
            decimals = len(dur_str.split(".")[1])
            assert decimals <= 4

    def test_single_paragraph_no_pause(self):
        result = build_timing_map([_p(1, "A", "Hello world")])
        assert result[0].pause_before == 0.0
        assert result[0].start_time == 0.0
        assert result[0].estimated_duration > 0
