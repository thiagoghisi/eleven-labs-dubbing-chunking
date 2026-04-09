"""Split paragraphs that exceed a word-count limit.

Splits on sentence boundaries first, then clause boundaries, to preserve
natural prosody for TTS.  When the source paragraph carries SRT timing
(``original_start`` / ``original_end``), the window is distributed
proportionally by word count across the resulting sub-chunks.
"""

from __future__ import annotations

import re

from dub_chunk.models import Paragraph

# Sentence-ending punctuation followed by whitespace.
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# Clause boundaries (comma, semicolon, em-dash) followed by whitespace.
_CLAUSE_RE = re.compile(r"(?<=[,;])\s+|(?<=—)\s*")


def split_long_paragraphs(
    paragraphs: list[Paragraph],
    max_words: int,
) -> list[Paragraph]:
    """Split any paragraph exceeding *max_words* into smaller chunks.

    Splitting strategy (in priority order):
      1. **Sentence boundaries** (``.``, ``!``, ``?`` followed by space).
      2. **Clause boundaries** (``,``, ``;``, ``—``) if a single sentence
         still exceeds the limit.
      3. **Hard word split** as a last resort.

    When a paragraph has ``original_start`` and ``original_end`` set (SRT
    input), the timing window is distributed proportionally across
    sub-chunks by word count.

    IDs are re-numbered sequentially starting at 1.

    Args:
        paragraphs: Ordered list of paragraphs.
        max_words: Maximum words per chunk.  Must be >= 1.

    Returns:
        New list of Paragraph objects, with long ones split and IDs
        re-numbered.
    """
    result: list[Paragraph] = []

    for para in paragraphs:
        if para.word_count <= max_words:
            result.append(para)
        else:
            result.extend(_split_paragraph(para, max_words))

    # Re-number IDs sequentially
    return [
        Paragraph(
            id=idx,
            speaker=p.speaker,
            text=p.text,
            original_start=p.original_start,
            original_end=p.original_end,
        )
        for idx, p in enumerate(result, start=1)
    ]


def _split_paragraph(para: Paragraph, max_words: int) -> list[Paragraph]:
    """Split a single paragraph into chunks of <= max_words."""
    # First try sentence boundaries
    chunks = _split_by_pattern(_SENTENCE_RE, para.text, max_words)

    # If any chunk is still too long, split those on clause boundaries
    refined: list[str] = []
    for chunk in chunks:
        if len(chunk.split()) > max_words:
            refined.extend(_split_by_pattern(_CLAUSE_RE, chunk, max_words))
        else:
            refined.append(chunk)

    # Last resort: hard split on word boundary
    final: list[str] = []
    for chunk in refined:
        words = chunk.split()
        if len(words) > max_words:
            for i in range(0, len(words), max_words):
                final.append(" ".join(words[i : i + max_words]))
        else:
            final.append(chunk)

    # Remove empty chunks
    final = [c.strip() for c in final if c.strip()]

    return _distribute_timing(para, final)


def _split_by_pattern(pattern: re.Pattern, text: str, max_words: int) -> list[str]:
    """Split text by regex pattern, then greedily group segments to stay under max_words."""
    segments = pattern.split(text)
    segments = [s.strip() for s in segments if s.strip()]

    if not segments:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for seg in segments:
        seg_words = len(seg.split())
        if current and current_words + seg_words > max_words:
            chunks.append(" ".join(current))
            current = [seg]
            current_words = seg_words
        else:
            current.append(seg)
            current_words += seg_words

    if current:
        chunks.append(" ".join(current))

    return chunks


def _distribute_timing(
    para: Paragraph, text_chunks: list[str]
) -> list[Paragraph]:
    """Create Paragraph objects from text chunks, distributing SRT timing."""
    if not text_chunks:
        return []

    has_timing = para.original_start is not None and para.original_end is not None

    if not has_timing:
        return [
            Paragraph(id=0, speaker=para.speaker, text=chunk)
            for chunk in text_chunks
        ]

    total_words = sum(len(c.split()) for c in text_chunks)
    if total_words == 0:
        return [
            Paragraph(
                id=0, speaker=para.speaker, text=chunk,
                original_start=para.original_start,
                original_end=para.original_end,
            )
            for chunk in text_chunks
        ]

    total_duration = para.original_end - para.original_start
    cursor = para.original_start
    result: list[Paragraph] = []

    for chunk in text_chunks:
        chunk_words = len(chunk.split())
        chunk_duration = (chunk_words / total_words) * total_duration
        chunk_end = cursor + chunk_duration

        result.append(
            Paragraph(
                id=0,
                speaker=para.speaker,
                text=chunk,
                original_start=round(cursor, 4),
                original_end=round(chunk_end, 4),
            )
        )
        cursor = chunk_end

    return result
