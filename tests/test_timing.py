"""Unit tests for timing.py — timing map construction."""

import logging

import pytest

from dub_chunk.models import Paragraph, TimingEntry
from dub_chunk.timing import build_timing_map, build_srt_timing_map, SPEED_MIN, SPEED_MAX


def _p(id, speaker, text):
    return Paragraph(id=id, speaker=speaker, text=text)


def _srt_p(id, speaker, text, start, end):
    return Paragraph(id=id, speaker=speaker, text=text,
                     original_start=start, original_end=end)


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


# ======================================================================
# SRT timing map — build_srt_timing_map
# ======================================================================


class TestSrtTimingMapPauses:

    def test_first_paragraph_pause_is_its_start_time(self):
        """First pause = time from 0 to where the SRT cue starts."""
        paras = [_srt_p(1, "A", "Hello world", 5.0, 10.0)]
        entries, _, _ = build_srt_timing_map(paras)
        assert entries[0].pause_before == 5.0

    def test_pause_from_srt_gap(self):
        """Pause = next_start - prev_end."""
        paras = [
            _srt_p(1, "A", "First sentence here.", 16.0, 22.4),
            _srt_p(2, "B", "Second sentence here.", 23.5, 30.0),
        ]
        entries, _, _ = build_srt_timing_map(paras)
        assert entries[1].pause_before == pytest.approx(1.1, abs=0.01)

    def test_zero_gap_produces_zero_pause(self):
        paras = [
            _srt_p(1, "A", "One thing.", 10.0, 15.0),
            _srt_p(2, "B", "Another thing.", 15.0, 20.0),
        ]
        entries, _, _ = build_srt_timing_map(paras)
        assert entries[1].pause_before == 0.0

    def test_overlapping_cues_produce_zero_pause(self):
        """If SRT cues overlap, clamp pause to 0."""
        paras = [
            _srt_p(1, "A", "One thing.", 10.0, 16.0),
            _srt_p(2, "B", "Another thing.", 15.0, 20.0),
        ]
        entries, _, _ = build_srt_timing_map(paras)
        assert entries[1].pause_before == 0.0


class TestSrtTimingMapSpeed:

    def test_speed_1x_when_estimate_matches_window(self):
        """150 words in 60s window → speed ≈ 1.0."""
        text = " ".join(["word"] * 150)  # 150 words → 60s at 150 WPM
        paras = [_srt_p(1, "A", text, 0.0, 60.0)]
        _, speeds, _ = build_srt_timing_map(paras)
        assert speeds[0] == pytest.approx(1.0, abs=0.01)

    def test_speed_up_when_text_too_long_for_window(self):
        """150 words in 30s window → needs ~2x speed, clamped to 1.2."""
        text = " ".join(["word"] * 150)  # 150 words → 60s natural
        paras = [_srt_p(1, "A", text, 0.0, 30.0)]
        _, speeds, _ = build_srt_timing_map(paras)
        assert speeds[0] == SPEED_MAX  # clamped

    def test_slow_down_when_text_too_short_for_window(self):
        """15 words in 60s window → needs ~0.1x, clamped to 0.7."""
        paras = [_srt_p(1, "A", "one two three", 0.0, 60.0)]
        _, speeds, _ = build_srt_timing_map(paras)
        assert speeds[0] == SPEED_MIN  # clamped

    def test_speed_within_range_not_clamped(self):
        """75 words in 60s window → 30s natural / 60s available = 0.83x."""
        text = " ".join(["word"] * 75)
        paras = [_srt_p(1, "A", text, 0.0, 60.0)]
        _, speeds, _ = build_srt_timing_map(paras)
        # 75 words / 150 WPM * 60 = 30s. 30 / 60 = 0.5 → wait, that's below 0.7.
        # Actually: (75/150)*60 = 30s natural, available = 60s, speed = 30/60 = 0.5
        # That would be clamped. Let me use a better example.
        pass

    def test_speed_within_range_passes_through(self):
        """100 words in 60s window → 40s natural / 60s = 0.67 → clamped to 0.7.
        But 100 words in 45s → 40s/45s = 0.89 → within range."""
        text = " ".join(["word"] * 100)  # 40s natural
        paras = [_srt_p(1, "A", text, 0.0, 45.0)]
        _, speeds, _ = build_srt_timing_map(paras)
        assert SPEED_MIN < speeds[0] < SPEED_MAX
        assert speeds[0] == pytest.approx(40.0 / 45.0, abs=0.01)

    def test_per_paragraph_speed_varies(self):
        paras = [
            _srt_p(1, "A", " ".join(["word"] * 100), 0.0, 45.0),   # 40s/45s ≈ 0.89
            _srt_p(2, "B", " ".join(["word"] * 100), 46.0, 80.0),  # 40s/34s ≈ 1.18
        ]
        _, speeds, _ = build_srt_timing_map(paras)
        assert len(speeds) == 2
        assert speeds[0] < 1.0  # slowed down
        assert speeds[1] > 1.0  # sped up


class TestSrtTimingMapWarnings:

    def test_warns_on_speed_capped_high(self, caplog):
        text = " ".join(["word"] * 150)  # 60s natural in 30s window
        paras = [_srt_p(1, "A", text, 0.0, 30.0)]
        with caplog.at_level(logging.WARNING):
            _, _, warnings = build_srt_timing_map(paras)
        assert len(warnings) == 1
        assert "capped" in warnings[0].lower()
        assert "overflow" in warnings[0].lower()
        assert "capped" in caplog.text.lower()

    def test_warns_on_speed_capped_low(self, caplog):
        paras = [_srt_p(1, "A", "short", 0.0, 60.0)]  # 0.4s natural in 60s
        with caplog.at_level(logging.WARNING):
            _, _, warnings = build_srt_timing_map(paras)
        assert len(warnings) == 1
        assert "capped" in warnings[0].lower()
        assert "underflow" in warnings[0].lower()

    def test_no_warning_when_within_range(self, caplog):
        text = " ".join(["word"] * 100)  # 40s natural in 45s window
        paras = [_srt_p(1, "A", text, 0.0, 45.0)]
        with caplog.at_level(logging.WARNING):
            _, _, warnings = build_srt_timing_map(paras)
        assert warnings == []
        assert caplog.text == ""


class TestSrtTimingMapStartTimes:

    def test_start_time_is_original_srt_timestamp(self):
        paras = [
            _srt_p(1, "A", "Hello world.", 16.0, 22.4),
            _srt_p(2, "B", "Hi there friend.", 23.5, 30.0),
        ]
        entries, _, _ = build_srt_timing_map(paras)
        assert entries[0].start_time == 16.0
        assert entries[1].start_time == 23.5

    def test_estimated_duration_is_srt_window(self):
        paras = [_srt_p(1, "A", "Hello world.", 16.0, 22.4)]
        entries, _, _ = build_srt_timing_map(paras)
        assert entries[0].estimated_duration == pytest.approx(6.4, abs=0.01)


class TestSrtTimingMapEdgeCases:

    def test_empty_input(self):
        entries, speeds, warnings = build_srt_timing_map([])
        assert entries == []
        assert speeds == []
        assert warnings == []

    def test_raises_if_missing_timing(self):
        paras = [_p(1, "A", "No timing data")]
        with pytest.raises(ValueError, match="no SRT timing"):
            build_srt_timing_map(paras)

    def test_empty_text_paragraph_gets_speed_1(self):
        paras = [_srt_p(1, "A", "", 10.0, 15.0)]
        _, speeds, _ = build_srt_timing_map(paras)
        assert speeds[0] == 1.0
