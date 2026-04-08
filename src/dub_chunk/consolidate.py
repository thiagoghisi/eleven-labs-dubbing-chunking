"""Merge consecutive same-speaker paragraphs and absorb short interjections.

Language-agnostic: heuristics are purely structural (word count + punctuation).
"""

from __future__ import annotations

from dub_chunk.models import Paragraph


def consolidate(
    paragraphs: list[Paragraph],
    merge_same_speaker: bool = True,
    absorb_threshold: int = 5,
) -> list[Paragraph]:
    """Consolidate paragraphs by absorbing interjections and merging same-speaker runs.

    Args:
        paragraphs: Ordered list of transcript paragraphs.
        merge_same_speaker: If True, merge consecutive paragraphs from the same speaker.
        absorb_threshold: Word-count ceiling for absorption candidates.
            Set to 0 to disable absorption entirely.

    Returns:
        New list of Paragraph objects with sequential IDs starting at 1.
    """
    if not paragraphs:
        return []

    working = list(paragraphs)

    # ------------------------------------------------------------------
    # Step 1 + 2: Mark and remove absorbable short interjections
    # ------------------------------------------------------------------
    if absorb_threshold > 0:
        working = _remove_absorbable(working, absorb_threshold)

    # ------------------------------------------------------------------
    # Step 3: Merge consecutive same-speaker paragraphs
    # ------------------------------------------------------------------
    if merge_same_speaker:
        working = _merge_same_speaker(working)

    # ------------------------------------------------------------------
    # Re-number IDs sequentially starting at 1
    # ------------------------------------------------------------------
    result: list[Paragraph] = []
    for idx, p in enumerate(working, start=1):
        result.append(Paragraph(
            id=idx, speaker=p.speaker, text=p.text,
            original_start=p.original_start, original_end=p.original_end,
        ))
    return result


# ======================================================================
# Internal helpers
# ======================================================================


def _is_absorbable(paragraph: Paragraph, threshold: int) -> bool:
    """Decide whether a paragraph is a short interjection that can be dropped.

    A paragraph is absorbable when:
      - its word count is at or below *threshold*, AND
      - it does NOT end with sentence-ending punctuation (.!?), OR
      - it has 3 or fewer words (regardless of punctuation).

    The 3-word rule catches filler like "Yeah." or "Okay, sure." that technically
    end with punctuation but carry no semantic weight worth preserving.
    """
    if paragraph.word_count > threshold:
        return False

    # Very short utterances are always absorbable
    if paragraph.word_count <= 3:
        return True

    # Longer-but-still-short utterances: only absorb if they lack a sentence ending
    text = paragraph.text.rstrip()
    if text and text[-1] in ".!?":
        return False

    return True


def _remove_absorbable(
    paragraphs: list[Paragraph], threshold: int
) -> list[Paragraph]:
    """Return a copy of *paragraphs* with absorbable entries removed."""
    return [p for p in paragraphs if not _is_absorbable(p, threshold)]


def _merge_same_speaker(paragraphs: list[Paragraph]) -> list[Paragraph]:
    """Merge consecutive paragraphs that share the same speaker."""
    if not paragraphs:
        return []

    merged: list[Paragraph] = []
    current = paragraphs[0]

    for p in paragraphs[1:]:
        if p.speaker == current.speaker:
            # Combine text with a single space; extend timing to cover both spans
            current = Paragraph(
                id=current.id,
                speaker=current.speaker,
                text=current.text.rstrip() + " " + p.text.lstrip(),
                original_start=current.original_start,
                original_end=p.original_end if p.original_end is not None else current.original_end,
            )
        else:
            merged.append(current)
            current = p

    merged.append(current)
    return merged
