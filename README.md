# dub-chunk

Chunked voice dubbing from transcripts using ElevenLabs TTS.

Turns any transcript into a natural-sounding dubbed audio file by generating one audio clip per paragraph and stitching them with natural pauses. Works with multi-speaker transcripts and cloned voices.

## Why chunking?

ElevenLabs TTS can struggle with consistency on long texts (30+ minutes). By splitting a transcript into individual paragraphs (median ~3 seconds, max ~5 minutes each), each API call is short enough for consistent voice quality. The final audio is assembled with configurable silence gaps between turns, producing natural conversational pacing.

This approach was developed while dubbing a 96-minute German interview into English with two cloned voices (204 API calls, ~102 minutes of output, zero consistency issues).

## Quick Start

```bash
# Install
pip install -e .

# Single speaker, simple transcript
dub-chunk generate transcript.txt \
  --voice default=YOUR_VOICE_ID \
  --api-key YOUR_API_KEY

# Multi-speaker from SRT
dub-chunk generate interview.srt \
  --voice "Host=abc123" \
  --voice "Guest=def456" \
  --speed "Host=0.9" \
  --speed "Guest=0.85" \
  --api-key YOUR_API_KEY

# Estimate cost before generating
dub-chunk estimate transcript.txt

# Preview parsed transcript
dub-chunk parse transcript.txt

# Re-stitch with different pacing (no API calls)
dub-chunk stitch ./output/clips/ \
  --pause-switch 3.0 \
  --pause-same 1.5
```

## Supported Input Formats

### Labeled text (`.txt` with speaker labels)
```
Host: Welcome to the show. Today we have a special guest.

Guest: Thank you for having me. I'm excited to be here.

Host: Let's dive right in.
```

### SRT subtitles (`.srt`)
```
1
00:00:01,000 --> 00:00:05,000
[HOST] Welcome to the show.

2
00:00:06,000 --> 00:00:10,000
[GUEST] Thank you for having me.
```

### Plain text (`.txt` without speaker labels)
```
Welcome to the show. Today we have a special guest.

Thank you for having me. I'm excited to be here.
```
Auto-detected as plain text when no `Speaker:` pattern is found.

## Pipeline

```
Input transcript
       │
       ▼
   ┌─────────┐
   │  Parse   │  SRT / labeled text / plain text
   └────┬─────┘
        │
        ▼
  ┌───────────────┐
  │  Consolidate  │  Merge same-speaker, absorb short interjections
  └──────┬────────┘
         │
         ▼
   ┌──────────┐
   │  Clean   │  Strip /stage directions/, _emphasis_, fix grammar
   └────┬─────┘
        │
        ▼
  ┌───────────────┐
  │  Timing Map   │  Calculate pauses proportional to word count
  └──────┬────────┘
         │
         ▼
  ┌───────────────┐
  │  TTS (chunks) │  1 ElevenLabs API call per paragraph
  └──────┬────────┘
         │
         ▼
  ┌───────────────┐
  │  Stitch       │  ffmpeg concat with silence gaps → final MP3
  └──────┬────────┘
         │
         ▼
   Output MP3
```

## Configuration

### Voice Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--stability` | 0.65 | Voice consistency (higher = more monotone) |
| `--similarity` | 0.80 | How closely to match the cloned voice |
| `--style` | 0.35 | Emotional expressiveness |
| `--speed SPEAKER=N` | 1.0 | Speech rate per speaker |

### Pacing

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--pause-same` | 1.0s | Silence between same-speaker paragraphs |
| `--pause-switch` | 2.5s | Silence on speaker change |
| `--total-duration` | 0 | Scale pacing to match original audio length (seconds) |

### Execution

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--resume` | off | Skip already-generated clips |
| `--dry-run` | off | Show timing map without API calls |
| `--limit N` | all | Process only first N paragraphs |
| `--rate-limit` | 0.5s | Delay between API calls |
| `--keep-clips` | off | Keep intermediate MP3 clips after stitching |

## Requirements

- Python 3.10+
- ffmpeg (on PATH)
- ElevenLabs API key with sufficient character quota

## How It Works

1. **Parse**: Detect input format and extract paragraphs with speaker labels
2. **Consolidate**: Merge consecutive same-speaker paragraphs; absorb short interjections (e.g., "Yes", "Mm-hmm") into adjacent paragraphs
3. **Clean**: Strip stage directions (`/laughs/`), emphasis markers (`_word_`), and other non-speakable elements
4. **Timing**: Calculate pause durations between paragraphs based on word count ratios
5. **Generate**: One ElevenLabs API call per paragraph, with resume support
6. **Stitch**: ffmpeg concatenates clips with silence gaps into a single MP3

## License

MIT
