"""Parse SRT subtitle files with optional [SPEAKER] labels."""

from __future__ import annotations

import re
from dataclasses import dataclass

from dub_chunk.models import Paragraph

_TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)
_SPEAKER_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)")


@dataclass
class _SrtCue:
    """Internal representation of a single SRT cue."""
    index: int
    start: float
    end: float
    speaker: str
    text: str


def _ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _parse_cues(text: str) -> list[_SrtCue]:
    """Parse raw SRT text into a list of cues."""
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: list[_SrtCue] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.splitlines()
        if len(lines) < 2:
            continue

        # Line 0: cue index (may be missing in malformed files -- tolerate it)
        idx_line = lines[0].strip()
        if not idx_line.isdigit():
            continue
        cue_index = int(idx_line)

        # Line 1: timestamps
        ts_match = _TIMESTAMP_RE.match(lines[1].strip())
        if not ts_match:
            continue
        g = ts_match.groups()
        start = _ts_to_seconds(g[0], g[1], g[2], g[3])
        end = _ts_to_seconds(g[4], g[5], g[6], g[7])

        # Lines 2+: text (possibly with [SPEAKER] prefix on first text line)
        text_lines = [l.strip() for l in lines[2:] if l.strip()]
        if not text_lines:
            continue

        speaker = "Speaker"
        first_line = text_lines[0]
        speaker_match = _SPEAKER_RE.match(first_line)
        if speaker_match:
            speaker = speaker_match.group(1).strip()
            first_line = speaker_match.group(2).strip()
            text_lines[0] = first_line

        cue_text = " ".join(text_lines).strip()
        if not cue_text:
            continue

        cues.append(
            _SrtCue(
                index=cue_index,
                start=start,
                end=end,
                speaker=speaker,
                text=cue_text,
            )
        )

    return cues


def parse_srt(text: str) -> list[Paragraph]:
    """Parse an SRT file into Paragraphs, grouping consecutive same-speaker cues.

    If cues contain ``[SPEAKER]`` prefixes, those are used as speaker names.
    Consecutive cues from the same speaker are merged into a single Paragraph.

    Timestamp metadata is stored on each Paragraph via ``original_start``
    and ``original_end`` fields (in seconds), covering the span from the
    first cue's start to the last cue's end in the group.

    Returns a list of :class:`Paragraph` with sequential IDs starting at 0.
    """
    cues = _parse_cues(text)
    if not cues:
        return []

    paragraphs: list[Paragraph] = []
    group_speaker = cues[0].speaker
    group_texts: list[str] = [cues[0].text]
    group_start = cues[0].start
    group_end = cues[0].end

    def _flush() -> None:
        p = Paragraph(
            id=len(paragraphs),
            speaker=group_speaker,
            text=" ".join(group_texts).strip(),
            original_start=group_start,
            original_end=group_end,
        )
        paragraphs.append(p)

    for cue in cues[1:]:
        if cue.speaker == group_speaker:
            group_texts.append(cue.text)
            group_end = cue.end
        else:
            _flush()
            group_speaker = cue.speaker
            group_texts = [cue.text]
            group_start = cue.start
            group_end = cue.end

    _flush()
    return paragraphs
