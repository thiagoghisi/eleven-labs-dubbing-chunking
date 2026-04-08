"""Unit tests for consolidate.py — absorption and merging logic."""

from dub_chunk.models import Paragraph
from dub_chunk.consolidate import consolidate, _is_absorbable


def _p(id, speaker, text):
    """Shorthand for creating test Paragraphs."""
    return Paragraph(id=id, speaker=speaker, text=text)


# ======================================================================
# Absorption rules
# ======================================================================


class TestAbsorption:

    def test_very_short_utterance_is_absorbable(self):
        """3 words or fewer → always absorbable regardless of punctuation."""
        assert _is_absorbable(_p(1, "X", "Yeah."), threshold=5)
        assert _is_absorbable(_p(1, "X", "Okay, sure."), threshold=5)
        assert _is_absorbable(_p(1, "X", "Hmm"), threshold=5)

    def test_medium_short_without_sentence_ending_is_absorbable(self):
        """4-5 words, no sentence-ending punctuation → absorbable."""
        assert _is_absorbable(_p(1, "X", "I see what you"), threshold=5)

    def test_medium_short_with_sentence_ending_is_not_absorbable(self):
        """4-5 words ending with .!? → NOT absorbable (substantive)."""
        assert not _is_absorbable(_p(1, "X", "I see what you mean."), threshold=5)

    def test_long_utterance_never_absorbable(self):
        """Above threshold → never absorbable."""
        assert not _is_absorbable(
            _p(1, "X", "This is a longer utterance that should stay"),
            threshold=5,
        )

    def test_absorption_removes_short_interjections(self):
        paragraphs = [
            _p(0, "Jung", "The unconscious is real."),
            _p(1, "Eissler", "Hmm"),
            _p(2, "Jung", "It produces symbols constantly."),
        ]
        result = consolidate(paragraphs, merge_same_speaker=False)
        speakers = [p.speaker for p in result]
        assert "Eissler" not in speakers
        assert len(result) == 2

    def test_absorption_disabled_with_threshold_zero(self):
        paragraphs = [
            _p(0, "A", "Long sentence here."),
            _p(1, "B", "Ok"),
            _p(2, "A", "Another long sentence."),
        ]
        result = consolidate(paragraphs, merge_same_speaker=False, absorb_threshold=0)
        assert len(result) == 3


# ======================================================================
# Same-speaker merging
# ======================================================================


class TestMerging:

    def test_consecutive_same_speaker_merged(self):
        paragraphs = [
            _p(0, "Jung", "First part."),
            _p(1, "Jung", "Second part."),
            _p(2, "Eissler", "Response."),
        ]
        result = consolidate(paragraphs, absorb_threshold=0)
        assert len(result) == 2
        assert "First part" in result[0].text
        assert "Second part" in result[0].text
        assert result[1].speaker == "Eissler"

    def test_non_consecutive_same_speaker_not_merged(self):
        paragraphs = [
            _p(0, "A", "Hello."),
            _p(1, "B", "World."),
            _p(2, "A", "Again."),
        ]
        result = consolidate(paragraphs, absorb_threshold=0)
        assert len(result) == 3

    def test_merge_disabled(self):
        paragraphs = [
            _p(0, "A", "First."),
            _p(1, "A", "Second."),
        ]
        result = consolidate(paragraphs, merge_same_speaker=False, absorb_threshold=0)
        assert len(result) == 2

    def test_three_consecutive_same_speaker_all_merged(self):
        paragraphs = [
            _p(0, "A", "One."),
            _p(1, "A", "Two."),
            _p(2, "A", "Three."),
        ]
        result = consolidate(paragraphs, absorb_threshold=0)
        assert len(result) == 1
        assert "One." in result[0].text
        assert "Three." in result[0].text


# ======================================================================
# ID re-numbering
# ======================================================================


class TestRenumbering:

    def test_ids_start_at_one_after_consolidation(self):
        paragraphs = [
            _p(0, "A", "First."),
            _p(1, "B", "Second."),
        ]
        result = consolidate(paragraphs, absorb_threshold=0)
        assert [p.id for p in result] == [1, 2]

    def test_ids_sequential_after_absorption(self):
        paragraphs = [
            _p(0, "A", "Long sentence stays."),
            _p(1, "B", "Ok"),
            _p(2, "C", "Another long sentence."),
        ]
        result = consolidate(paragraphs, merge_same_speaker=False)
        ids = [p.id for p in result]
        assert ids == list(range(1, len(result) + 1))


# ======================================================================
# Edge cases
# ======================================================================


class TestEdgeCases:

    def test_empty_input(self):
        assert consolidate([]) == []

    def test_single_paragraph_above_threshold(self):
        result = consolidate([_p(0, "A", "This is a substantive paragraph.")])
        assert len(result) == 1
        assert result[0].id == 1

    def test_single_short_paragraph_gets_absorbed(self):
        """A single paragraph ≤3 words is absorbed even if it's the only one."""
        result = consolidate([_p(0, "A", "Only one.")])
        assert result == []

    def test_all_paragraphs_absorbed(self):
        """If every paragraph is absorbable, return empty list."""
        paragraphs = [
            _p(0, "A", "Ok"),
            _p(1, "B", "Yeah"),
            _p(2, "A", "Hmm"),
        ]
        result = consolidate(paragraphs, merge_same_speaker=False)
        assert result == []

    def test_word_count_recomputed_after_merge(self):
        paragraphs = [
            _p(0, "A", "One two."),
            _p(1, "A", "Three four five."),
        ]
        result = consolidate(paragraphs, absorb_threshold=0)
        assert result[0].word_count == 5

    def test_absorption_then_merge_combined(self):
        """Absorb interjection, then merge the now-adjacent same-speaker paragraphs."""
        paragraphs = [
            _p(0, "Jung", "The unconscious is extraordinarily deep."),
            _p(1, "Eissler", "Hmm"),  # absorbed (≤3 words)
            _p(2, "Jung", "It produces symbols and images constantly."),
        ]
        result = consolidate(paragraphs)
        # After absorbing "Hmm", two Jung paragraphs are adjacent → merged
        assert len(result) == 1
        assert result[0].speaker == "Jung"
        assert "deep" in result[0].text
        assert "symbols" in result[0].text
