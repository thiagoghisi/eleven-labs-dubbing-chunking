"""Build a timing map for audio assembly.

Distributes paragraphs proportionally by word count, optionally scaling to
match an original audio duration.  When SRT timing is available,
:func:`build_srt_timing_map` uses the original timestamps directly.
"""

from __future__ import annotations

import logging

from dub_chunk.models import Paragraph, TimingEntry

logger = logging.getLogger(__name__)

# Default speaking rate used when no total_duration is supplied.
_WORDS_PER_MINUTE = 150.0

# ElevenLabs speed parameter limits (API-enforced).
SPEED_MIN = 0.7
SPEED_MAX = 1.2


def build_timing_map(
    paragraphs: list[Paragraph],
    total_duration: float = 0,
    pause_same: float = 1.0,
    pause_switch: float = 2.5,
    pause_long_para: float = 1.0,
    long_para_threshold: int = 200,
) -> list[TimingEntry]:
    """Create a list of :class:`TimingEntry` objects with estimated timing.

    Two modes of operation:

    * **Scale mode** (``total_duration > 0``): speech durations are distributed
      proportionally by word count so that the sum of durations plus pauses
      equals *total_duration*.
    * **Estimate mode** (``total_duration == 0``): durations are derived from a
      ~150 WPM speaking rate plus the configured pauses.

    Args:
        paragraphs: Ordered list of paragraphs to schedule.
        total_duration: Target total duration in seconds.  ``0`` means
            estimate from word count.
        pause_same: Seconds of silence between consecutive paragraphs by
            the same speaker.
        pause_switch: Seconds of silence at a speaker change.
        pause_long_para: Additional pause appended after paragraphs that
            exceed *long_para_threshold* words.
        long_para_threshold: Word-count threshold above which
            *pause_long_para* is added.

    Returns:
        List of :class:`TimingEntry` in the same order as *paragraphs*.
    """
    if not paragraphs:
        return []

    # ------------------------------------------------------------------
    # 1. Compute per-paragraph pause durations
    # ------------------------------------------------------------------
    pauses: list[float] = []
    for idx, para in enumerate(paragraphs):
        if idx == 0:
            pauses.append(0.0)
        elif para.speaker == paragraphs[idx - 1].speaker:
            pauses.append(pause_same)
        else:
            pauses.append(pause_switch)

        # Extra pause after long paragraphs (applies to the *next* entry,
        # but we attribute it to the current one's trailing silence).
        if idx > 0 and paragraphs[idx - 1].word_count > long_para_threshold:
            pauses[idx] += pause_long_para

    total_pause = sum(pauses)
    total_words = sum(p.word_count for p in paragraphs)

    if total_words == 0:
        # Edge case: all paragraphs are empty
        return [
            TimingEntry(paragraph=p, start_time=0.0, estimated_duration=0.0, pause_before=0.0)
            for p in paragraphs
        ]

    # ------------------------------------------------------------------
    # 2. Compute per-paragraph durations
    # ------------------------------------------------------------------
    if total_duration > 0:
        # Scale mode: available speech time = total - pauses
        available_speech = max(total_duration - total_pause, 0.0)
        durations = [
            (p.word_count / total_words) * available_speech for p in paragraphs
        ]
    else:
        # Estimate mode: 150 WPM
        durations = [
            (p.word_count / _WORDS_PER_MINUTE) * 60.0 for p in paragraphs
        ]

    # ------------------------------------------------------------------
    # 3. Build TimingEntry objects with cumulative start times
    # ------------------------------------------------------------------
    entries: list[TimingEntry] = []
    cursor = 0.0

    for idx, para in enumerate(paragraphs):
        pause = pauses[idx]
        cursor += pause

        entry = TimingEntry(
            paragraph=para,
            start_time=round(cursor, 4),
            estimated_duration=round(durations[idx], 4),
            pause_before=round(pause, 4),
        )
        entries.append(entry)
        cursor += durations[idx]

    return entries


def build_srt_timing_map(
    paragraphs: list[Paragraph],
) -> tuple[list[TimingEntry], list[float], list[str]]:
    """Create timing entries and per-paragraph speeds from SRT timestamps.

    Uses ``original_start`` / ``original_end`` on each paragraph to:
      - Compute pauses from SRT gaps (``next_start - prev_end``).
      - Estimate a natural speech duration at 150 WPM.
      - Derive a speed factor so the TTS clip fits the original window.
      - Clamp speed to the ElevenLabs API range [0.7, 1.2] and collect warnings.

    Args:
        paragraphs: Ordered paragraphs **with** ``original_start`` and
            ``original_end`` set (i.e. parsed from SRT).

    Returns:
        A tuple of ``(timing_entries, speeds, warnings)`` where *speeds* is a
        list of per-paragraph speed values and *warnings* is a list of
        human-readable warning strings for clamped paragraphs.

    Raises:
        ValueError: If any paragraph lacks SRT timing data.
    """
    if not paragraphs:
        return [], [], []

    for p in paragraphs:
        if p.original_start is None or p.original_end is None:
            raise ValueError(
                f"Paragraph {p.id} ({p.speaker}) has no SRT timing data. "
                f"--match-srt-timing requires SRT input."
            )

    entries: list[TimingEntry] = []
    speeds: list[float] = []
    warnings: list[str] = []

    for idx, para in enumerate(paragraphs):
        # -- pause from SRT gap --
        if idx == 0:
            pause = para.original_start
        else:
            prev = paragraphs[idx - 1]
            pause = max(para.original_start - prev.original_end, 0.0)

        available = para.original_end - para.original_start

        # -- estimate natural duration at 150 WPM --
        if para.word_count > 0:
            estimated_natural = (para.word_count / _WORDS_PER_MINUTE) * 60.0
        else:
            estimated_natural = 0.0

        # -- compute speed to fit the window --
        if available > 0 and estimated_natural > 0:
            speed = estimated_natural / available
        else:
            speed = 1.0

        # -- clamp and warn --
        if speed > SPEED_MAX:
            msg = (
                f"Paragraph {para.id} ({para.speaker}): needs {speed:.2f}x "
                f"speed but capped at {SPEED_MAX}x — clip will overflow "
                f"its {available:.1f}s window"
            )
            logger.warning(msg)
            warnings.append(msg)
            speed = SPEED_MAX
        elif speed < SPEED_MIN:
            msg = (
                f"Paragraph {para.id} ({para.speaker}): needs {speed:.2f}x "
                f"speed but capped at {SPEED_MIN}x — clip will underflow "
                f"its {available:.1f}s window"
            )
            logger.warning(msg)
            warnings.append(msg)
            speed = SPEED_MIN

        speeds.append(round(speed, 4))

        entry = TimingEntry(
            paragraph=para,
            start_time=round(para.original_start, 4),
            estimated_duration=round(available, 4),
            pause_before=round(pause, 4),
        )
        entries.append(entry)

    return entries, speeds, warnings
