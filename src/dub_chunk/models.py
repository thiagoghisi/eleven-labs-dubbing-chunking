"""Data models for the dubbing pipeline."""

from dataclasses import dataclass, field


@dataclass
class Paragraph:
    """A single paragraph/turn in the transcript."""
    id: int
    speaker: str
    text: str
    word_count: int = 0
    original_start: float | None = None
    original_end: float | None = None

    def __post_init__(self):
        if not self.word_count:
            self.word_count = len(self.text.split())

    @property
    def original_duration(self) -> float | None:
        """Duration of the original SRT window in seconds, if available."""
        if self.original_start is not None and self.original_end is not None:
            return self.original_end - self.original_start
        return None


@dataclass
class VoiceConfig:
    """ElevenLabs voice configuration for a speaker."""
    voice_id: str
    speed: float = 1.0
    stability: float = 0.65
    similarity_boost: float = 0.80
    style: float = 0.35
    use_speaker_boost: bool = True


@dataclass
class TimingEntry:
    """A paragraph with timing information for audio assembly."""
    paragraph: Paragraph
    start_time: float = 0.0
    estimated_duration: float = 0.0
    pause_before: float = 0.0


@dataclass
class ProjectState:
    """Tracks generation progress for resume support."""
    paragraphs: list[Paragraph] = field(default_factory=list)
    generated_clips: dict[int, str] = field(default_factory=dict)  # id -> clip path
    clip_durations: dict[int, float] = field(default_factory=dict)  # id -> seconds
