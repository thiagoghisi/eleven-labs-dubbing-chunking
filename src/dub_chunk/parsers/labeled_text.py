"""Parse 'Speaker: text' format with double-newline paragraph separation."""

from __future__ import annotations

import re

from dub_chunk.models import Paragraph

_SPEAKER_RE = re.compile(r"^([A-Za-z0-9_ .\-]+):\s*(.*)", re.DOTALL)


def parse_labeled_text(text: str) -> list[Paragraph]:
    """Parse labeled transcript text into Paragraphs.

    Format::

        Speaker A: Some text here that goes on
        across multiple lines.

        Speaker B: Response text here...

    Paragraphs are separated by one or more blank lines.
    A line matching ``Speaker: ...`` starts a new speaker turn;
    continuation lines (no speaker prefix) append to the current paragraph.

    Returns a list of :class:`Paragraph` with sequential IDs starting at 0.
    """
    raw_blocks = re.split(r"\n\s*\n", text.strip())
    paragraphs: list[Paragraph] = []

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.splitlines()
        speaker: str | None = None
        parts: list[str] = []

        for line in lines:
            match = _SPEAKER_RE.match(line)
            if match:
                # If we already accumulated text under a previous speaker
                # within the same block, flush it first.
                if speaker is not None and parts:
                    paragraphs.append(
                        Paragraph(
                            id=len(paragraphs),
                            speaker=speaker,
                            text=" ".join(parts).strip(),
                        )
                    )
                    parts = []
                speaker = match.group(1).strip()
                remainder = match.group(2).strip()
                if remainder:
                    parts.append(remainder)
            else:
                # Continuation line -- append to current paragraph.
                stripped = line.strip()
                if stripped:
                    parts.append(stripped)

        # Flush the last speaker/text accumulated in this block.
        if parts:
            paragraphs.append(
                Paragraph(
                    id=len(paragraphs),
                    speaker=speaker or "Speaker",
                    text=" ".join(parts).strip(),
                )
            )

    return paragraphs
