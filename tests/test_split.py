"""Unit tests for split.py — paragraph splitting to reduce TTS hallucinations."""

import pytest

from dub_chunk.models import Paragraph
from dub_chunk.split import split_long_paragraphs


def _p(id, speaker, text, start=None, end=None):
    return Paragraph(id=id, speaker=speaker, text=text,
                     original_start=start, original_end=end)


# ======================================================================
# No splitting needed
# ======================================================================


class TestNoSplit:

    def test_short_paragraph_unchanged(self):
        paras = [_p(1, "A", "Short sentence here.")]
        result = split_long_paragraphs(paras, max_words=10)
        assert len(result) == 1
        assert result[0].text == "Short sentence here."

    def test_exact_limit_not_split(self):
        text = " ".join(["word"] * 10)
        paras = [_p(1, "A", text)]
        result = split_long_paragraphs(paras, max_words=10)
        assert len(result) == 1

    def test_empty_list(self):
        assert split_long_paragraphs([], max_words=10) == []

    def test_multiple_short_paragraphs_unchanged(self):
        paras = [
            _p(1, "A", "First."),
            _p(2, "B", "Second."),
            _p(3, "A", "Third."),
        ]
        result = split_long_paragraphs(paras, max_words=10)
        assert len(result) == 3


# ======================================================================
# Sentence boundary splitting
# ======================================================================


class TestSentenceSplitting:

    def test_splits_on_sentence_boundary(self):
        text = "First sentence here. Second sentence here. Third sentence here."
        paras = [_p(1, "A", text)]
        result = split_long_paragraphs(paras, max_words=5)
        assert len(result) >= 2
        # Each chunk should be within the limit
        for p in result:
            assert p.word_count <= 5

    def test_groups_sentences_greedily(self):
        """Short sentences should be grouped together up to the limit."""
        text = "Yes. No. Maybe. Definitely not. Absolutely."
        paras = [_p(1, "A", text)]
        result = split_long_paragraphs(paras, max_words=5)
        # Should group "Yes. No. Maybe." (3 words) and
        # "Definitely not. Absolutely." (3 words) — 2 chunks
        assert len(result) <= 3
        for p in result:
            assert p.word_count <= 5

    def test_speaker_preserved_across_chunks(self):
        text = "First sentence. Second sentence. Third sentence."
        paras = [_p(1, "Jung", text)]
        result = split_long_paragraphs(paras, max_words=3)
        assert all(p.speaker == "Jung" for p in result)


# ======================================================================
# Clause boundary fallback
# ======================================================================


class TestClauseSplitting:

    def test_splits_long_sentence_on_clause(self):
        """Single sentence exceeding limit splits on comma."""
        text = "The unconscious is not just a repository, it is a living system"
        paras = [_p(1, "A", text)]
        result = split_long_paragraphs(paras, max_words=8)
        assert len(result) >= 2
        for p in result:
            assert p.word_count <= 8


# ======================================================================
# Hard word split fallback
# ======================================================================


class TestHardSplit:

    def test_splits_on_word_boundary_as_last_resort(self):
        """No punctuation at all — falls back to hard word split."""
        text = " ".join(["word"] * 20)
        paras = [_p(1, "A", text)]
        result = split_long_paragraphs(paras, max_words=7)
        assert len(result) == 3  # 7 + 7 + 6
        assert all(p.word_count <= 7 for p in result)


# ======================================================================
# SRT timing distribution
# ======================================================================


class TestTimingDistribution:

    def test_timing_distributed_proportionally(self):
        """SRT window should be split proportionally by word count."""
        text = "Short. " + " ".join(["word"] * 20) + "."
        paras = [_p(1, "A", text, start=10.0, end=30.0)]
        result = split_long_paragraphs(paras, max_words=10)
        assert len(result) >= 2

        # All sub-chunks should have timing
        for p in result:
            assert p.original_start is not None
            assert p.original_end is not None

        # First starts where original started
        assert result[0].original_start == 10.0
        # Last ends where original ended
        assert result[-1].original_end == pytest.approx(30.0, abs=0.01)

        # Chunks are contiguous (no gaps)
        for i in range(1, len(result)):
            assert result[i].original_start == pytest.approx(
                result[i - 1].original_end, abs=0.01
            )

    def test_no_timing_when_original_has_none(self):
        text = " ".join(["word"] * 20)
        paras = [_p(1, "A", text)]
        result = split_long_paragraphs(paras, max_words=7)
        for p in result:
            assert p.original_start is None
            assert p.original_end is None

    def test_timing_duration_sums_to_original(self):
        text = " ".join(["word"] * 30)
        paras = [_p(1, "A", text, start=5.0, end=35.0)]
        result = split_long_paragraphs(paras, max_words=10)
        total_dur = sum(
            p.original_end - p.original_start for p in result
        )
        assert total_dur == pytest.approx(30.0, abs=0.01)


# ======================================================================
# ID re-numbering
# ======================================================================


class TestRenumbering:

    def test_ids_sequential_from_one(self):
        paras = [
            _p(1, "A", " ".join(["word"] * 20)),
            _p(2, "B", "Short."),
        ]
        result = split_long_paragraphs(paras, max_words=7)
        assert [p.id for p in result] == list(range(1, len(result) + 1))

    def test_mixed_split_and_unsplit(self):
        """Long paragraph splits, short one stays — IDs re-numbered across all."""
        paras = [
            _p(1, "A", "Short."),
            _p(2, "B", " ".join(["word"] * 20)),
            _p(3, "A", "Also short."),
        ]
        result = split_long_paragraphs(paras, max_words=7)
        assert result[0].text == "Short."
        assert result[-1].text == "Also short."
        assert [p.id for p in result] == list(range(1, len(result) + 1))
