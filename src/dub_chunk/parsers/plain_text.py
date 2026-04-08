"""Parse plain text (no speaker labels) split on double newlines."""

from __future__ import annotations

import re

from dub_chunk.models import Paragraph


def parse_plain_text(
    text: str,
    default_speaker: str = "Speaker",
) -> list[Paragraph]:
    """Parse plain text into Paragraphs, splitting on blank lines.

    Each resulting paragraph is assigned *default_speaker* since the format
    carries no speaker information.

    Args:
        text: Raw transcript text.
        default_speaker: Speaker name to assign to every paragraph.

    Returns a list of :class:`Paragraph` with sequential IDs starting at 0.
    """
    blocks = re.split(r"\n\s*\n", text.strip())
    paragraphs: list[Paragraph] = []

    for block in blocks:
        # Collapse internal newlines into spaces (paragraph may wrap).
        cleaned = " ".join(block.split()).strip()
        if not cleaned:
            continue
        paragraphs.append(
            Paragraph(
                id=len(paragraphs),
                speaker=default_speaker,
                text=cleaned,
            )
        )

    return paragraphs
