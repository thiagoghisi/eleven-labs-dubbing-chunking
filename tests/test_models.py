"""Unit tests for models.py — dataclass contracts."""

from dub_chunk.models import Paragraph, VoiceConfig, TimingEntry, ProjectState


class TestParagraph:

    def test_word_count_auto_computed_from_text(self):
        p = Paragraph(id=1, speaker="Jung", text="The unconscious is real")
        assert p.word_count == 4

    def test_word_count_single_word(self):
        p = Paragraph(id=1, speaker="Jung", text="Yes")
        assert p.word_count == 1

    def test_word_count_empty_text(self):
        p = Paragraph(id=1, speaker="Jung", text="")
        assert p.word_count == 0

    def test_word_count_not_overridden_when_zero(self):
        """word_count=0 triggers auto-computation (falsy)."""
        p = Paragraph(id=1, speaker="Jung", text="one two three", word_count=0)
        assert p.word_count == 3

    def test_explicit_word_count_preserved(self):
        """When explicitly set to non-zero, auto-computation is skipped."""
        p = Paragraph(id=1, speaker="Jung", text="one two three", word_count=99)
        assert p.word_count == 99

    def test_whitespace_only_text_counts_zero(self):
        p = Paragraph(id=1, speaker="Jung", text="   ")
        assert p.word_count == 0

    def test_multiline_text_word_count(self):
        p = Paragraph(id=1, speaker="Jung", text="line one\nline two\nline three")
        assert p.word_count == 6


class TestVoiceConfig:

    def test_defaults(self):
        vc = VoiceConfig(voice_id="abc123")
        assert vc.speed == 1.0
        assert vc.stability == 0.65
        assert vc.similarity_boost == 0.80
        assert vc.style == 0.35
        assert vc.use_speaker_boost is True

    def test_custom_values(self):
        vc = VoiceConfig(voice_id="xyz", speed=0.8, stability=0.5)
        assert vc.voice_id == "xyz"
        assert vc.speed == 0.8
        assert vc.stability == 0.5


class TestTimingEntry:

    def test_defaults(self):
        p = Paragraph(id=1, speaker="Jung", text="hello")
        te = TimingEntry(paragraph=p)
        assert te.start_time == 0.0
        assert te.estimated_duration == 0.0
        assert te.pause_before == 0.0

    def test_custom_values(self):
        p = Paragraph(id=1, speaker="Jung", text="hello")
        te = TimingEntry(paragraph=p, start_time=5.0, estimated_duration=3.2, pause_before=1.0)
        assert te.start_time == 5.0
        assert te.estimated_duration == 3.2
        assert te.pause_before == 1.0


class TestProjectState:

    def test_defaults_empty(self):
        ps = ProjectState()
        assert ps.paragraphs == []
        assert ps.generated_clips == {}
        assert ps.clip_durations == {}

    def test_no_shared_mutable_defaults(self):
        """Each instance should get its own lists/dicts."""
        ps1 = ProjectState()
        ps2 = ProjectState()
        ps1.paragraphs.append(Paragraph(id=1, speaker="X", text="y"))
        assert len(ps2.paragraphs) == 0
