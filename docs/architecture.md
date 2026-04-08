# Architecture — dub-chunk

C4 model diagrams for the chunked ElevenLabs voice dubbing tool.

## Level 1: System Context

Who uses dub-chunk and what external systems does it talk to?

```
┌─────────────────────────────────────────────────────────────────────┐
│                        System Context                               │
│                                                                     │
│                                                                     │
│    ┌──────────┐         ┌──────────────────┐       ┌─────────────┐ │
│    │          │  runs   │                  │ calls │             │ │
│    │   User   │────────>│    dub-chunk     │──────>│ ElevenLabs  │ │
│    │          │         │   CLI tool       │       │   TTS API   │ │
│    │ Content  │         │                  │       │             │ │
│    │ creator, │<────────│ Python CLI that   │       │ /v1/text-to │ │
│    │ podcaster│ dubbed  │ chunks transcripts│       │ -speech/    │ │
│    │ dubber   │  MP3    │ into paragraphs   │       │ {voice_id}  │ │
│    │          │         │ and generates TTS │       │             │ │
│    └──────────┘         │ per chunk         │       └─────────────┘ │
│                         │                  │                        │
│                         └────────┬─────────┘                        │
│                                  │ shells out                       │
│                                  v                                  │
│                         ┌──────────────────┐                        │
│                         │                  │                        │
│                         │     ffmpeg       │                        │
│                         │                  │                        │
│                         │ Silence gen,     │                        │
│                         │ format convert,  │                        │
│                         │ concat, encode   │                        │
│                         │                  │                        │
│                         └──────────────────┘                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Actors:**
- **User** — content creator, podcaster, dubber who has a transcript and wants dubbed audio

**External systems:**
- **ElevenLabs TTS API** — generates speech audio from text using cloned voices
- **ffmpeg** — system binary for audio manipulation (silence generation, format conversion, concatenation, MP3 encoding)

## Level 2: Container Diagram

What are the major components inside dub-chunk?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          dub-chunk                                      │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         CLI Layer                                  │ │
│  │                        (cli.py)                                    │ │
│  │                                                                    │ │
│  │  dub-chunk generate   parse   estimate   stitch                    │ │
│  │                                                                    │ │
│  │  Orchestrates the full pipeline. Routes user commands to           │ │
│  │  the appropriate modules. Handles flags, voice mapping,            │ │
│  │  progress display, and error reporting.                            │ │
│  └──────────────────────────┬─────────────────────────────────────────┘ │
│                             │ calls                                     │
│  ┌──────────────────────────┼─────────────────────────────────────────┐ │
│  │                    Processing Pipeline                             │ │
│  │                                                                    │ │
│  │  ┌──────────┐ ┌─────────────┐ ┌───────┐ ┌────────┐               │ │
│  │  │ Parsers  │ │ Consolidate │ │ Clean │ │ Timing │               │ │
│  │  │          │ │             │ │       │ │        │               │ │
│  │  │ SRT      │ │ Merge same  │ │ Strip │ │ Build  │               │ │
│  │  │ Labeled  │ │ speaker,    │ │ stage │ │ pause  │               │ │
│  │  │ Plain    │ │ absorb      │ │ dirs, │ │ map    │               │ │
│  │  │          │ │ interjec-   │ │ emph- │ │ from   │               │ │
│  │  │ Detect   │ │ tions       │ │ asis  │ │ word   │               │ │
│  │  │ format,  │ │             │ │       │ │ counts │               │ │
│  │  │ extract  │ │ Re-number   │ │ Fix   │ │        │               │ │
│  │  │ speakers │ │ IDs         │ │ a/an  │ │ Scale  │               │ │
│  │  │          │ │             │ │       │ │ to     │               │ │
│  │  │          │ │             │ │       │ │ target │               │ │
│  │  └──────────┘ └─────────────┘ └───────┘ └────────┘               │ │
│  │       │              │             │          │                    │ │
│  │       v              v             v          v                    │ │
│  │  ┌────────────────────────────────────────────────┐               │ │
│  │  │              Data Model (models.py)            │               │ │
│  │  │                                                │               │ │
│  │  │  Paragraph    VoiceConfig    TimingEntry       │               │ │
│  │  │  (id, speaker, (voice_id,   (paragraph,        │               │ │
│  │  │   text,        speed,        start_time,       │               │ │
│  │  │   word_count)  stability,    pause_before,     │               │ │
│  │  │                similarity,   est_duration)     │               │ │
│  │  │                style)                          │               │ │
│  │  └────────────────────────────────────────────────┘               │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                             │                                          │
│  ┌──────────────────────────┼─────────────────────────────────────────┐ │
│  │                    Audio Generation                                │ │
│  │                                                                    │ │
│  │  ┌──────────────────────┐    ┌───────────────────────────────┐    │ │
│  │  │     TTS Client       │    │         Stitcher              │    │ │
│  │  │     (tts.py)         │    │        (stitch.py)            │    │ │
│  │  │                      │    │                               │    │ │
│  │  │ generate_clip()      │    │ Generate silence WAVs         │    │ │
│  │  │   POST /v1/text-to-  │    │ Convert clips to WAV          │    │ │
│  │  │   speech/{voice_id}  │    │ Write ffmpeg concat list      │    │ │
│  │  │                      │    │ Encode final MP3              │    │ │
│  │  │ estimate_cost()      │    │                               │    │ │
│  │  │   $0.30/1K chars     │    │ get_clip_duration()           │    │ │
│  │  │                      │    │ check_ffmpeg()                │    │ │
│  │  │ Retry w/ backoff     │    │                               │    │ │
│  │  │ (429, 5xx)           │    │                               │    │ │
│  │  └──────────┬───────────┘    └──────────────┬────────────────┘    │ │
│  │             │                               │                     │ │
│  └─────────────┼───────────────────────────────┼─────────────────────┘ │
│                │                               │                       │
└────────────────┼───────────────────────────────┼───────────────────────┘
                 │                               │
                 v                               v
        ┌──────────────────┐            ┌──────────────────┐
        │   ElevenLabs     │            │     ffmpeg        │
        │   TTS API        │            │                   │
        │                  │            │  silence gen      │
        │  POST /v1/text-  │            │  WAV conversion   │
        │  to-speech/      │            │  concat           │
        │  {voice_id}      │            │  MP3 encoding     │
        └──────────────────┘            └──────────────────┘
```

## Level 3: Component Diagram

Detailed view of modules, their responsibilities, and data flow.

```
                            ┌───────────────────┐
                            │    User Input      │
                            │                    │
                            │  transcript.txt    │
                            │  interview.srt     │
                            │  plain.txt         │
                            └────────┬───────────┘
                                     │
                                     v
                  ┌──────────────────────────────────────┐
                  │           cli.py (489 lines)         │
                  │                                      │
                  │  Commands:                           │
                  │    generate  - full pipeline          │
                  │    parse     - preview only           │
                  │    estimate  - cost calculator        │
                  │    stitch    - re-assemble clips      │
                  │                                      │
                  │  Responsibilities:                    │
                  │    - Auto-detect input format         │
                  │    - Map --voice flags to VoiceConfig │
                  │    - Map --speed flags per speaker    │
                  │    - Progress display                 │
                  │    - Resume logic (skip existing)     │
                  │    - Rate limiting between API calls  │
                  └──────┬──────┬──────┬──────┬──────────┘
                         │      │      │      │
             ┌───────────┘      │      │      └───────────┐
             v                  v      v                  v
   ┌─────────────────┐  ┌──────────┐ ┌──────────┐ ┌──────────────┐
   │ parsers/        │  │consolidat│ │ clean.py │ │  timing.py   │
   │                 │  │ e.py     │ │ (63 ln)  │ │  (112 ln)    │
   │ srt.py (132 ln) │  │ (112 ln) │ │          │ │              │
   │ labeled_text.py │  │          │ │ clean_   │ │ build_       │
   │   (74 ln)       │  │ consoli- │ │ for_tts()│ │ timing_map() │
   │ plain_text.py   │  │ date()   │ │          │ │              │
   │   (41 ln)       │  │          │ │ /stage/  │ │ Word-count   │
   │                 │  │ Merge    │ │ _emph_   │ │ proportional │
   │ Auto-detect     │  │ same-    │ │ a -> an  │ │ distribution │
   │ speaker labels  │  │ speaker  │ │ spaces   │ │              │
   │ Group into      │  │ Absorb   │ │ dashes   │ │ Pause modes: │
   │ paragraphs      │  │ short    │ │ ellipsis │ │  same-speaker│
   │                 │  │ turns    │ │          │ │  switch      │
   │                 │  │ Re-ID    │ │          │ │  long-para   │
   └────────┬────────┘  └────┬─────┘ └────┬─────┘ └──────┬───────┘
            │                │            │               │
            v                v            v               v
   ┌─────────────────────────────────────────────────────────────┐
   │                    models.py (44 lines)                     │
   │                                                             │
   │  @dataclass Paragraph    id: int                            │
   │                          speaker: str                       │
   │                          text: str                          │
   │                          word_count: int (auto-computed)    │
   │                                                             │
   │  @dataclass VoiceConfig  voice_id: str                      │
   │                          speed, stability, similarity,      │
   │                          style, use_speaker_boost            │
   │                                                             │
   │  @dataclass TimingEntry  paragraph: Paragraph               │
   │                          start_time, estimated_duration,    │
   │                          pause_before                       │
   │                                                             │
   │  @dataclass ProjectState paragraphs, generated_clips,      │
   │                          clip_durations                     │
   └─────────────────────────────────────────────────────────────┘
            │                                         │
            v                                         v
   ┌──────────────────┐                    ┌───────────────────┐
   │   tts.py         │                    │   stitch.py       │
   │   (118 lines)    │                    │   (222 lines)     │
   │                  │                    │                   │
   │  generate_clip() │                    │  stitch_audio()   │
   │    POST request  │                    │    silence WAVs   │
   │    to ElevenLabs │                    │    clip -> WAV    │
   │    Save MP3      │                    │    concat list    │
   │                  │                    │    ffmpeg encode  │
   │  estimate_cost() │                    │                   │
   │    chars * rate   │                    │  check_ffmpeg()   │
   │                  │                    │  get_duration()   │
   │  Retry: 3x w/   │                    │                   │
   │  exp. backoff    │                    │  Cleanup tmp WAVs │
   └────────┬─────────┘                    └─────────┬─────────┘
            │                                        │
            v                                        v
   ┌──────────────────┐                    ┌──────────────────┐
   │  ElevenLabs API  │                    │     ffmpeg        │
   │  (external)      │                    │  (system binary)  │
   │                  │                    │                   │
   │  HTTPS POST      │                    │  subprocess calls │
   │  Returns MP3     │                    │  Returns MP3      │
   │  bytes           │                    │                   │
   └──────────────────┘                    └──────────────────┘
```

## Data Flow

```
transcript.txt ──> parse ──> list[Paragraph]
                                  │
                                  v
                            consolidate ──> list[Paragraph] (fewer, merged)
                                  │
                                  v
                         clean_for_tts() applied to each .text
                                  │
                                  v
                          build_timing_map ──> list[TimingEntry]
                                  │
                                  v
                    ┌─────────────┴─────────────┐
                    │   For each TimingEntry:    │
                    │                            │
                    │   generate_clip(text,      │
                    │     voice_config, api_key) │
                    │        │                   │
                    │        v                   │
                    │   para_NNN.mp3             │
                    └─────────────┬──────────────┘
                                  │
                                  v
                          stitch_audio()
                    ┌─────────────┴─────────────┐
                    │  For each TimingEntry:     │
                    │    1. silence_{N}.wav      │
                    │    2. para_{N}.wav         │
                    │                            │
                    │  concat.txt listing all    │
                    │                            │
                    │  ffmpeg -f concat -> MP3   │
                    └─────────────┬──────────────┘
                                  │
                                  v
                    output/interview_dubbed.mp3
```

## Use Cases

```
┌─────────────────────────────────────────────────────────────────┐
│                        Use Cases                                │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ UC1: Dub a YouTube video into another language           │  │
│  │                                                          │  │
│  │  1. Download SRT/transcript from YouTube                 │  │
│  │  2. Translate transcript (external: Claude, GPT, etc.)   │  │
│  │  3. Clone your voice on ElevenLabs (2 min sample)        │  │
│  │  4. dub-chunk generate translated.txt --voice ...        │  │
│  │  5. Replace audio track with ffmpeg                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ UC2: Dub a podcast/interview (multi-speaker)             │  │
│  │                                                          │  │
│  │  1. Transcribe with Whisper (speaker labels)             │  │
│  │  2. Translate transcript                                 │  │
│  │  3. Clone each speaker's voice on ElevenLabs             │  │
│  │  4. dub-chunk generate --voice Host=X --voice Guest=Y    │  │
│  │  5. Configure speed per speaker for natural pacing       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ UC3: Generate audiobook from text                        │  │
│  │                                                          │  │
│  │  1. Prepare plain text (one paragraph per double-newline)│  │
│  │  2. dub-chunk generate book.txt --voice default=X        │  │
│  │  3. Adjust pacing with --pause-same and --pause-switch   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ UC4: Re-dub historical recordings                        │  │
│  │                                                          │  │
│  │  1. Obtain typed transcript (e.g., Library of Congress)  │  │
│  │  2. Translate from source language                       │  │
│  │  3. Clone speakers' voices from available audio samples  │  │
│  │  4. dub-chunk generate --total-duration 5744             │  │
│  │     (match original recording length)                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ UC5: Iterate on pacing without re-generating audio       │  │
│  │                                                          │  │
│  │  1. Run generate once (clips saved to disk)              │  │
│  │  2. dub-chunk stitch clips/ --pause-switch 3.0           │  │
│  │  3. Listen, adjust, re-stitch. No API calls.             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## File Map

```
eleven-labs-dubbing-chunking/
├── Makefile              # setup, check, clean, shortcuts
├── pyproject.toml        # package metadata + entry point
├── requirements.txt      # click, requests
├── README.md             # user-facing docs
├── LICENSE               # MIT
├── docs/
│   └── architecture.md   # this file
├── src/
│   └── dub_chunk/
│       ├── __init__.py   #   3 lines  package version
│       ├── models.py     #  44 lines  Paragraph, VoiceConfig, TimingEntry
│       ├── parsers/
│       │   ├── __init__.py     #   7 lines  re-exports
│       │   ├── srt.py          # 132 lines  SRT with [SPEAKER] labels
│       │   ├── labeled_text.py #  74 lines  "Speaker: text" format
│       │   └── plain_text.py   #  41 lines  plain paragraphs
│       ├── consolidate.py      # 112 lines  merge + absorb
│       ├── clean.py            #  63 lines  strip for TTS
│       ├── timing.py           # 112 lines  pause map builder
│       ├── tts.py              # 118 lines  ElevenLabs API client
│       ├── stitch.py           # 222 lines  ffmpeg stitcher
│       └── cli.py              # 489 lines  Click commands
├── tests/
│   ├── __init__.py
│   └── fixtures/
│       ├── sample.srt
│       ├── sample_labeled.txt
│       └── sample_plain.txt
└── examples/              # (future) shell script examples
```

**Total: 1,417 lines of Python across 12 modules.**
