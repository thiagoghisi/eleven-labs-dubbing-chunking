"""Click-based CLI for dub-chunk: chunked ElevenLabs voice dubbing from transcripts."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import click

from dub_chunk import __version__
from dub_chunk.clean import clean_for_tts
from dub_chunk.consolidate import consolidate
from dub_chunk.split import split_long_paragraphs
from dub_chunk.models import Paragraph, VoiceConfig, TimingEntry
from dub_chunk.parsers import parse_labeled_text, parse_srt, parse_plain_text
from dub_chunk.timing import build_timing_map, build_srt_timing_map
from dub_chunk.tts import generate_clip, estimate_cost
from dub_chunk.stitch import stitch_audio, check_ffmpeg, get_clip_duration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FORMAT_DISPATCH = {
    "srt": parse_srt,
    "labeled": parse_labeled_text,
    "plain": parse_plain_text,
}

_EXT_TO_FORMAT = {
    ".srt": "srt",
    ".txt": "labeled",
}


def _detect_format(path: Path, explicit: str | None) -> str:
    """Return format key from explicit flag or file extension."""
    if explicit:
        if explicit not in _FORMAT_DISPATCH:
            raise click.BadParameter(
                f"Unknown format '{explicit}'. Choose from: {', '.join(_FORMAT_DISPATCH)}"
            )
        return explicit
    ext = path.suffix.lower()
    fmt = _EXT_TO_FORMAT.get(ext)
    if fmt is None:
        raise click.BadParameter(
            f"Cannot auto-detect format from extension '{ext}'. "
            f"Use --format to specify one of: {', '.join(_FORMAT_DISPATCH)}"
        )
    return fmt


def _parse_voice_mappings(raw: tuple[str, ...]) -> dict[str, str]:
    """Parse --voice SPEAKER=VOICE_ID pairs into a dict."""
    mapping: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise click.BadParameter(
                f"Invalid --voice format: '{item}'. Expected SPEAKER=VOICE_ID"
            )
        speaker, voice_id = item.split("=", 1)
        mapping[speaker.strip()] = voice_id.strip()
    return mapping


def _parse_speed_mappings(raw: tuple[str, ...]) -> dict[str, float]:
    """Parse --speed SPEAKER=SPEED pairs into a dict."""
    mapping: dict[str, float] = {}
    for item in raw:
        if "=" not in item:
            raise click.BadParameter(
                f"Invalid --speed format: '{item}'. Expected SPEAKER=SPEED"
            )
        speaker, speed_str = item.split("=", 1)
        try:
            mapping[speaker.strip()] = float(speed_str.strip())
        except ValueError:
            raise click.BadParameter(
                f"Invalid speed value for '{speaker.strip()}': '{speed_str.strip()}'"
            )
    return mapping


def _build_voice_config(
    speaker: str,
    voice_map: dict[str, str],
    speed_map: dict[str, float],
    stability: float,
    similarity: float,
    style: float,
) -> VoiceConfig:
    """Build a VoiceConfig for a given speaker."""
    voice_id = voice_map.get(speaker) or voice_map.get("default")
    if not voice_id:
        raise click.ClickException(
            f"No voice ID mapped for speaker '{speaker}'. "
            f"Use --voice {speaker}=VOICE_ID or --voice default=VOICE_ID"
        )
    return VoiceConfig(
        voice_id=voice_id,
        speed=speed_map.get(speaker, speed_map.get("default", 1.0)),
        stability=stability,
        similarity_boost=similarity,
        style=style,
    )


def _read_input(path: Path) -> str:
    """Read input file with helpful error messages."""
    if not path.exists():
        raise click.ClickException(f"Input file not found: {path}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(version=__version__)
def main():
    """dub-chunk: Chunked ElevenLabs voice dubbing from transcripts."""
    pass


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--voice", "voices", multiple=True, required=True,
    help="Speaker=VoiceID mapping. For single speaker: --voice default=abc123",
)
@click.option(
    "--api-key", envvar="ELEVENLABS_API_KEY", default=None,
    help="ElevenLabs API key (default: ELEVENLABS_API_KEY env var).",
)
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None, help="Output MP3 path.")
@click.option(
    "--format", "fmt", type=click.Choice(["srt", "labeled", "plain"]), default=None,
    help="Force input format (default: auto-detect from extension).",
)
@click.option("--model", default="eleven_multilingual_v2", help="ElevenLabs model ID.")
@click.option("--stability", type=float, default=0.65, help="Voice stability (0-1).")
@click.option("--similarity", type=float, default=0.80, help="Voice similarity boost (0-1).")
@click.option("--style", type=float, default=0.35, help="Voice style (0-1).")
@click.option(
    "--speed", "speeds", multiple=True,
    help="Speaker=Speed mapping (e.g. --speed Jung=0.78).",
)
@click.option("--pause-same", type=float, default=0.4, help="Silence (seconds) between same-speaker paragraphs.")
@click.option("--pause-switch", type=float, default=0.8, help="Silence (seconds) on speaker switch.")
@click.option("--total-duration", type=float, default=None, help="Target total duration in seconds (for pacing).")
@click.option("--no-consolidate", is_flag=True, help="Skip paragraph merging.")
@click.option("--max-chunk-words", type=int, default=None, help="Split paragraphs exceeding N words. Reduces TTS hallucinations.")
@click.option("--match-srt-timing", is_flag=True, help="Adjust speed per paragraph to fit original SRT timing windows. SRT input only.")
@click.option("--resume", is_flag=True, help="Skip existing clips on disk.")
@click.option("--dry-run", is_flag=True, help="Show timing map without calling the API.")
@click.option("--limit", type=int, default=None, help="Process first N paragraphs only.")
@click.option("--rate-limit", type=float, default=0.5, help="Seconds between API calls.")
@click.option("--keep-clips", is_flag=True, help="Don't delete intermediate clips after stitching.")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output.")
def generate(
    input_file: Path,
    voices: tuple[str, ...],
    api_key: str | None,
    output: Path | None,
    fmt: str | None,
    model: str,
    stability: float,
    similarity: float,
    style: float,
    speeds: tuple[str, ...],
    pause_same: float,
    pause_switch: float,
    total_duration: float | None,
    no_consolidate: bool,
    max_chunk_words: int | None,
    match_srt_timing: bool,
    resume: bool,
    dry_run: bool,
    limit: int | None,
    rate_limit: float,
    keep_clips: bool,
    verbose: bool,
):
    """Generate dubbed audio from a transcript file.

    Pipeline: parse -> consolidate -> clean -> generate clips -> stitch.
    """
    if not dry_run and not api_key:
        raise click.ClickException(
            "API key required. Set ELEVENLABS_API_KEY or use --api-key."
        )

    # --- Parse voice/speed mappings ---
    voice_map = _parse_voice_mappings(voices)
    speed_map = _parse_speed_mappings(speeds)

    # --- Step 1: Parse transcript ---
    detected_fmt = _detect_format(input_file, fmt)
    raw_text = _read_input(input_file)
    parser = _FORMAT_DISPATCH[detected_fmt]
    paragraphs: list[Paragraph] = parser(raw_text)

    if not paragraphs:
        raise click.ClickException("No paragraphs found in input file.")

    click.echo(f"Parsed {len(paragraphs)} paragraphs ({detected_fmt} format)")

    # --- Step 2: Consolidate ---
    if not no_consolidate:
        before = len(paragraphs)
        paragraphs = consolidate(paragraphs)
        click.echo(f"Consolidated: {before} -> {len(paragraphs)} paragraphs")

    # --- Step 2b: Split long paragraphs ---
    if max_chunk_words is not None:
        before = len(paragraphs)
        paragraphs = split_long_paragraphs(paragraphs, max_chunk_words)
        if len(paragraphs) != before:
            click.echo(f"Split: {before} -> {len(paragraphs)} paragraphs (max {max_chunk_words} words)")

    # --- Apply limit ---
    if limit:
        paragraphs = paragraphs[:limit]
        click.echo(f"Limited to first {len(paragraphs)} paragraphs")

    # --- Step 3: Clean text ---
    for p in paragraphs:
        p.text = clean_for_tts(p.text)

    # --- Step 4: Build timing map ---
    srt_speeds: list[float] | None = None

    if match_srt_timing:
        if detected_fmt != "srt":
            raise click.ClickException(
                "--match-srt-timing requires SRT input. "
                f"Detected format is '{detected_fmt}'."
            )
        timing_map, srt_speeds, srt_warnings = build_srt_timing_map(paragraphs)
        click.echo(f"SRT timing: matching original durations (speed range 0.7x–1.2x)")
        for warn in srt_warnings:
            click.echo(f"  ⚠ {warn}", err=True)
    else:
        timing_map: list[TimingEntry] = build_timing_map(
            paragraphs,
            pause_same=pause_same,
            pause_switch=pause_switch,
            total_duration=total_duration or 0,
        )

    if verbose or dry_run:
        total_chars = sum(len(e.paragraph.text) for e in timing_map)
        click.echo(f"\nTiming map ({len(timing_map)} entries, {total_chars:,} chars):")
        for i, entry in enumerate(timing_map):
            p = entry.paragraph
            preview = p.text[:60] + ("..." if len(p.text) > 60 else "")
            speed_info = f" speed={srt_speeds[i]:.2f}x" if srt_speeds else ""
            click.echo(
                f"  [{p.id:3d}] {p.speaker:<15s} "
                f"pause={entry.pause_before:.2f}s "
                f"est={entry.estimated_duration:.1f}s"
                f"{speed_info} "
                f"| {preview}"
            )

    if dry_run:
        total_est = sum(e.estimated_duration + e.pause_before for e in timing_map)
        total_chars = sum(len(e.paragraph.text) for e in timing_map)
        click.echo(f"\n--- DRY RUN ---")
        click.echo(f"Paragraphs: {len(timing_map)}")
        click.echo(f"Characters:  {total_chars:,}")
        click.echo(f"Est. duration: {total_est:.1f}s ({total_est/60:.1f} min)")
        cost_info = estimate_cost([e.paragraph for e in timing_map])
        click.echo(f"Est. cost:     ${cost_info['estimated_cost_usd']:.4f}")
        return

    # --- Step 5: Create clips directory ---
    clips_dir = input_file.parent / f"{input_file.stem}_clips"
    clips_dir.mkdir(exist_ok=True)

    if not check_ffmpeg():
        raise click.ClickException(
            "ffmpeg not found in PATH. Install it: brew install ffmpeg"
        )

    # --- Step 6: Generate clips ---
    clip_paths: list[Path] = []
    total_entries = len(timing_map)

    for i, entry in enumerate(timing_map):
        p = entry.paragraph
        clip_path = clips_dir / f"p{p.id:04d}.mp3"

        if resume and clip_path.exists():
            if verbose:
                click.echo(f"  [{p.id}] Skipping (exists): {clip_path.name}")
            clip_paths.append(clip_path)
            continue

        voice_cfg = _build_voice_config(
            p.speaker, voice_map, speed_map, stability, similarity, style,
        )

        # Override speed with SRT-computed value when matching timing
        if srt_speeds is not None:
            voice_cfg = VoiceConfig(
                voice_id=voice_cfg.voice_id,
                speed=srt_speeds[i],
                stability=voice_cfg.stability,
                similarity_boost=voice_cfg.similarity_boost,
                style=voice_cfg.style,
                use_speaker_boost=voice_cfg.use_speaker_boost,
            )

        if verbose:
            speed_str = f" @ {voice_cfg.speed:.2f}x" if srt_speeds else ""
            click.echo(f"  [{p.id}] Generating: {p.speaker} ({len(p.text)} chars{speed_str})")

        generate_clip(
            text=p.text,
            voice_config=voice_cfg,
            output_path=clip_path,
            model_id=model,
            api_key=api_key,
        )
        clip_paths.append(clip_path)

        # Progress reporting every 10 clips
        if (i + 1) % 10 == 0 or (i + 1) == total_entries:
            click.echo(f"  Progress: {i + 1}/{total_entries} clips generated")

        # Rate limiting
        if rate_limit > 0 and i < total_entries - 1:
            time.sleep(rate_limit)

    # --- Step 7: Stitch ---
    if output is None:
        output = input_file.with_suffix(".mp3")

    click.echo(f"\nStitching {len(clip_paths)} clips...")
    stitch_audio(
        timing_entries=timing_map,
        clips_dir=clips_dir,
        output_path=output,
    )

    final_duration = get_clip_duration(output)
    click.echo(f"\nDone!")
    click.echo(f"  Output:   {output}")
    click.echo(f"  Duration: {final_duration:.1f}s ({final_duration/60:.1f} min)")
    click.echo(f"  Clips:    {len(clip_paths)}")

    if not keep_clips:
        import shutil
        shutil.rmtree(clips_dir)
        if verbose:
            click.echo(f"  Cleaned up: {clips_dir}")


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format", "fmt", type=click.Choice(["srt", "labeled", "plain"]), default=None,
    help="Force input format (default: auto-detect).",
)
def parse(input_file: Path, fmt: str | None):
    """Show parsed transcript preview. No API calls."""
    detected_fmt = _detect_format(input_file, fmt)
    raw_text = _read_input(input_file)
    parser = _FORMAT_DISPATCH[detected_fmt]
    paragraphs: list[Paragraph] = parser(raw_text)

    if not paragraphs:
        click.echo("No paragraphs found.")
        return

    # Gather stats
    speakers: dict[str, int] = {}
    total_words = 0
    for p in paragraphs:
        speakers[p.speaker] = speakers.get(p.speaker, 0) + 1
        total_words += p.word_count

    click.echo(f"Format:     {detected_fmt}")
    click.echo(f"Paragraphs: {len(paragraphs)}")
    click.echo(f"Words:      {total_words:,}")
    click.echo(f"Characters: {sum(len(p.text) for p in paragraphs):,}")
    click.echo(f"Speakers:   {len(speakers)}")
    for speaker, count in sorted(speakers.items(), key=lambda x: -x[1]):
        click.echo(f"  {speaker}: {count} paragraphs")

    click.echo(f"\nPreview (first 5 paragraphs):")
    for p in paragraphs[:5]:
        preview = p.text[:80] + ("..." if len(p.text) > 80 else "")
        click.echo(f"  [{p.id:3d}] {p.speaker}: {preview}")

    if len(paragraphs) > 5:
        click.echo(f"  ... and {len(paragraphs) - 5} more")


# ---------------------------------------------------------------------------
# estimate
# ---------------------------------------------------------------------------

@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format", "fmt", type=click.Choice(["srt", "labeled", "plain"]), default=None,
    help="Force input format (default: auto-detect).",
)
@click.option("--no-consolidate", is_flag=True, help="Skip paragraph merging for estimate.")
def estimate(input_file: Path, fmt: str | None, no_consolidate: bool):
    """Show character count, estimated cost, and estimated duration. No API calls."""
    detected_fmt = _detect_format(input_file, fmt)
    raw_text = _read_input(input_file)
    parser = _FORMAT_DISPATCH[detected_fmt]
    paragraphs: list[Paragraph] = parser(raw_text)

    if not paragraphs:
        click.echo("No paragraphs found.")
        return

    raw_count = len(paragraphs)
    if not no_consolidate:
        paragraphs = consolidate(paragraphs)

    # Clean text for accurate char count
    for p in paragraphs:
        p.text = clean_for_tts(p.text)

    total_chars = sum(len(p.text) for p in paragraphs)
    total_words = sum(p.word_count for p in paragraphs)

    # Rough duration estimate: ~150 words/min for TTS
    est_duration_min = total_words / 150
    est_duration_sec = est_duration_min * 60

    cost_info = estimate_cost(paragraphs)

    click.echo(f"Format:        {detected_fmt}")
    click.echo(f"Paragraphs:    {raw_count} raw -> {len(paragraphs)} consolidated")
    click.echo(f"Characters:    {total_chars:,}")
    click.echo(f"Words:         {total_words:,}")
    click.echo(f"Est. duration: {est_duration_sec:.0f}s ({est_duration_min:.1f} min)")
    click.echo(f"Est. cost:     ${cost_info['estimated_cost_usd']:.4f}")


# ---------------------------------------------------------------------------
# stitch
# ---------------------------------------------------------------------------

@main.command()
@click.argument("clips_dir", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), required=True, help="Output MP3 path.")
@click.option("--pause-same", type=float, default=0.4, help="Silence (seconds) between same-speaker clips.")
@click.option("--pause-switch", type=float, default=0.8, help="Silence (seconds) on speaker switch.")
@click.option("--total-duration", type=float, default=None, help="Target total duration in seconds.")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output.")
def stitch(
    clips_dir: Path,
    output: Path,
    pause_same: float,
    pause_switch: float,
    total_duration: float | None,
    verbose: bool,
):
    """Re-stitch from an existing clips directory with different pacing.

    CLIPS_DIR should contain numbered clip files (e.g., 0001_Speaker.mp3).
    """
    if not check_ffmpeg():
        raise click.ClickException(
            "ffmpeg not found in PATH. Install it: brew install ffmpeg"
        )

    # Discover clips sorted by filename
    clips = sorted(clips_dir.glob("*.mp3"))
    if not clips:
        raise click.ClickException(f"No .mp3 files found in {clips_dir}")

    click.echo(f"Found {len(clips)} clips in {clips_dir}")

    # Extract speaker from filename pattern: NNNN_Speaker.mp3
    paragraphs: list[Paragraph] = []
    for clip in clips:
        stem = clip.stem
        parts = stem.split("_", 1)
        idx = int(parts[0]) if parts[0].isdigit() else len(paragraphs)
        speaker = parts[1] if len(parts) > 1 else "Speaker"
        paragraphs.append(Paragraph(id=idx, speaker=speaker, text=""))

    timing_map: list[TimingEntry] = build_timing_map(
        paragraphs,
        pause_same=pause_same,
        pause_switch=pause_switch,
        total_duration=total_duration,
    )

    if verbose:
        for clip, entry in zip(clips, timing_map):
            dur = get_clip_duration(clip)
            click.echo(
                f"  {clip.name}: {dur:.1f}s + {entry.pause_before:.2f}s pause"
            )

    stitch_audio(
        timing_entries=timing_map,
        clips_dir=Path(clips_directory),
        output_path=output,
    )

    final_duration = get_clip_duration(output)
    click.echo(f"\nDone!")
    click.echo(f"  Output:   {output}")
    click.echo(f"  Duration: {final_duration:.1f}s ({final_duration/60:.1f} min)")
