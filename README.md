# dub-chunk

Chunked voice dubbing from transcripts using ElevenLabs TTS.

Turns any transcript into a natural-sounding dubbed audio file by generating one audio clip per paragraph and stitching them with natural pauses. Works with multi-speaker transcripts and cloned voices.

## Why chunking?

ElevenLabs TTS can struggle with consistency on long texts (30+ minutes). By splitting a transcript into individual paragraphs (median ~3 seconds, max ~5 minutes each), each API call is short enough for consistent voice quality. The final audio is assembled with configurable silence gaps between turns, producing natural conversational pacing.

This approach was developed while dubbing a 96-minute German interview into English with two cloned voices (204 API calls, ~102 minutes of output, zero consistency issues).

## Requirements

### System dependencies

| Dependency | Version | Purpose | Install |
|------------|---------|---------|---------|
| **Python** | 3.10+ | Runtime | Pre-installed on macOS, or `brew install python` |
| **ffmpeg** | any | Audio stitching (concat clips + silence gaps into final MP3) | `brew install ffmpeg` |
| **ffprobe** | any | Measuring clip durations (bundled with ffmpeg) | Comes with ffmpeg |

### Python dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| **click** | >= 8.0 | CLI framework (commands, flags, help text) |
| **requests** | >= 2.28 | HTTP client for ElevenLabs API calls |

Both are installed automatically by `make setup`. No other Python packages are needed.

### API access

| Requirement | How to get it |
|-------------|---------------|
| **ElevenLabs API key** | Sign up at [elevenlabs.io](https://elevenlabs.io), go to Profile > API Keys |
| **Voice ID(s)** | Clone a voice in ElevenLabs, then copy the Voice ID from the voice settings page |
| **Sufficient character quota** | ~5.5 credits per word. A 1-hour transcript (~9,000 words) needs ~50,000 credits |

## Setup

```bash
git clone https://github.com/thiagoghisi/eleven-labs-dubbing-chunking.git
cd eleven-labs-dubbing-chunking
make setup
```

This creates a Python virtual environment, installs all dependencies, and verifies everything is working:

```
=== Creating virtual environment ===
  ✅ venv created

=== Installing dependencies ===
  ✅ dub-chunk installed

=== Dependency Check ===
  python3:     3.12.0 ✅
  venv:        ✅
  dub-chunk:   0.1.0 ✅
  ffmpeg:      7.1 ✅
  ffprobe:     ✅

  Environment variables:
  ELEVENLABS_API_KEY: not set ⚠️
```

Then set your API key:

```bash
export ELEVENLABS_API_KEY=sk_your_key_here
```

### For developers

If you're modifying the source code, use `make setup-dev` instead. This installs in editable mode so code changes take effect immediately without reinstalling:

```bash
make setup-dev
```

### Makefile targets

| Target | What it does |
|--------|-------------|
| `make setup` | Full setup: venv + install + check (start here) |
| `make setup-dev` | Dev setup: same but with editable install for live code reloading |
| `make check` | Verify python, ffmpeg, venv, API key are all present |
| `make test` | Run test suite |
| `make clean` | Remove venv and build artifacts |
| `make help` | Show all available targets |
| `make parse FILE=...` | Shortcut for `dub-chunk parse` |
| `make estimate FILE=...` | Shortcut for `dub-chunk estimate` |
| `make dry-run FILE=... VOICE=...` | Shortcut for `dub-chunk generate --dry-run` |

## Usage

### Single speaker

```bash
dub-chunk generate transcript.txt \
  --voice default=YOUR_VOICE_ID
```

### Multi-speaker

```bash
dub-chunk generate interview.srt \
  --voice "Host=abc123" \
  --voice "Guest=def456" \
  --speed "Host=0.9" \
  --speed "Guest=0.85"
```

### Estimate cost before generating

```bash
dub-chunk estimate transcript.txt
```

```
Format:        labeled
Paragraphs:    204 raw -> 180 consolidated
Characters:    52,340
Words:         8,912
Est. duration: 3,565s (59.4 min)
Est. cost:     $15.7020
```

### Preview parsed transcript

```bash
dub-chunk parse transcript.txt
```

### Dry run (shows timing map, no API calls)

```bash
dub-chunk generate transcript.txt \
  --voice default=YOUR_VOICE_ID \
  --dry-run
```

### Re-stitch with different pacing (no API calls)

```bash
dub-chunk stitch ./output/clips/ \
  --pause-switch 3.0 \
  --pause-same 1.5
```

### Resume interrupted generation

```bash
dub-chunk generate transcript.txt \
  --voice default=YOUR_VOICE_ID \
  --resume
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
       |
       v
   +---------+
   |  Parse   |  SRT / labeled text / plain text
   +----+-----+
        |
        v
  +---------------+
  |  Consolidate  |  Merge same-speaker, absorb short interjections
  +------+--------+
         |
         v
   +----------+
   |  Clean   |  Strip /stage directions/, _emphasis_, fix grammar
   +----+-----+
        |
        v
  +---------------+
  |  Timing Map   |  Calculate pauses proportional to word count
  +------+--------+
         |
         v
  +---------------+
  |  TTS (chunks) |  1 ElevenLabs API call per paragraph
  +------+--------+
         |
         v
  +---------------+
  |  Stitch       |  ffmpeg concat with silence gaps -> final MP3
  +------+--------+
         |
         v
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

## How It Works

1. **Parse**: Detect input format and extract paragraphs with speaker labels
2. **Consolidate**: Merge consecutive same-speaker paragraphs; absorb short interjections (e.g., "Yes", "Mm-hmm") into adjacent paragraphs
3. **Clean**: Strip stage directions (`/laughs/`), emphasis markers (`_word_`), and other non-speakable elements
4. **Timing**: Calculate pause durations between paragraphs based on word count ratios
5. **Generate**: One ElevenLabs API call per paragraph, with resume support
6. **Stitch**: ffmpeg concatenates clips with silence gaps into a single MP3

## Architecture

See [docs/architecture.md](docs/architecture.md) for C4 diagrams covering:
- **Level 1 — System Context**: users, ElevenLabs API, ffmpeg
- **Level 2 — Container**: CLI layer, processing pipeline, audio generation
- **Level 3 — Component**: all 12 modules with line counts and responsibilities
- **Data Flow**: transcript in, MP3 out, every step in between
- **Use Cases**: YouTube dubbing, podcast dubbing, audiobooks, historical recordings, pacing iteration

## License

MIT
