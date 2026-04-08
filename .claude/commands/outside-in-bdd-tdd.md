# /outside-in-bdd-tdd — Multi-Loop Outside-In Development Flow

```
         Thiago's Outside-In BDD/TDD — The Multi-Loop
         ═══════════════════════════════════════════════

                              start
                                │
                                ▼
         ╭─── ① ACCEPTANCE (BDD) LOOP ────────────────────────────╮
         │                                                         │
         │   Write Failing AC (Given-When-Then → pytest-bdd)       │
         │        │                                                │
         │     RED ✗  ◄──────────────────────────────────────╮    │
         │        │                                           │    │
         │        │  drop into inner loops                    │    │
         │        ▼                                           │    │
         │   ╭─── ② CONTRACT TEST LOOP ───────────────╮     │    │
         │   │                                         │     │    │
         │   │  Test boundaries:                       │     │    │
         │   │  • Parser output format (SRT/labeled)   │     │    │
         │   │  • Paragraph dataclass (roundtrip)      │     │    │
         │   │  • CLI output/exit codes                │     │    │
         │   │        │                                │     │    │
         │   │        ▼                                │     │    │
         │   │   ╭─── ③ UNIT (TDD) LOOP ────────╮    │     │    │
         │   │   │                                │    │     │    │
         │   │   │  Write Test ──▶ RED ✗          │    │     │    │
         │   │   │       ▲            │           │    │     │    │
         │   │   │       │       Implement        │    │     │    │
         │   │   │    n cycles        │           │    │     │    │
         │   │   │       │       GREEN ✓          │    │     │    │
         │   │   │       └────────────┘           │    │     │    │
         │   │   ╰────────────────────────────────╯    │     │    │
         │   ╰─────────────────────────────────────────╯     │    │
         │                                                    │    │
         │   All inner tests GREEN ──────────────────────────╯    │
         │        │                                                │
         │     GREEN ✓  (acceptance test passes)                   │
         │        │                                                │
         ╰────────┼────────────────────────────────────────────────╯
                  │
                  ▼
         ╭─── ④ REFACTOR ──────────────────────────────────────────╮
         │   Review smells · Extract abstractions · Clean up        │
         │   (at epic boundary, with full test safety net)          │
         ╰────────┬────────────────────────────────────────────────╯
                  │
                  ▼
         ╭─── ⑤ CHARACTERIZATION (if needed) ──────────────────────╮
         │   Lock performance · Lock output quality (audio format)  │
         │   Lock CLI behavior (exit codes, error messages)         │
         ╰────────┬────────────────────────────────────────────────╯
                  │
                  ▼
              next epic
```

Outside-in, multi-loop test-driven development. 3 nested loops (acceptance → contract → unit) plus 2 post-green lock phases (refactor → characterization). Start from acceptance criteria (Given-When-Then), see them fail at the E2E level, drop into contract and unit loops, implement, then verify the outer loop goes green.

Based on 18 years of BDD/ATDD practice (2007-2025): ThoughtWorks QA consulting, Amex Gherkin DoR at scale, Nubank contract tests. Influenced by BDD in Action (John Ferguson Smart), The RSpec Book, GOOS (Freeman & Pryce), Continuous Delivery (Humble & Farley), ATDD by Example (Gartner), Specification by Example (Adzic).

## Usage

```
/outside-in-bdd-tdd <epic-or-feature>                # Generate ACs + run flow for a feature
/outside-in-bdd-tdd <epic-or-feature> --ac-only       # Generate acceptance criteria only (no implementation)
/outside-in-bdd-tdd <task> --inner-only               # Run inner loop only (unit test → implement → green)
/outside-in-bdd-tdd --walking-skeleton                # Generate the thinnest E2E slice first
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| epic-or-feature or task | Yes | - | Feature name or task to work on |
| --ac-only | No | false | Generate Given-When-Then only, don't implement |
| --inner-only | No | false | Skip outer loop, just do unit TDD for a specific task |
| --walking-skeleton | No | false | Build the thinnest possible E2E slice |

---

## The Double Loop

```
                    ┌─────────────────────────────────────────┐
                    │           OUTER LOOP (E2E/Acceptance)    │
                    │                                          │
                    │  1. Read feature + acceptance criteria    │
                    │  2. Draft Given-When-Then scenarios       │
                    │  3. User reviews + adds edge cases        │
                    │  4. Write pytest-bdd feature + steps      │
                    │  5. Run → SEE IT FAIL (RED)               │
                    │  6. ─── Drop into inner loop ───          │
                    │  7. Run outer test → SEE IT PASS (GREEN)  │
                    │  8. Refactor pass (at epic boundary)      │
                    │                                          │
                    └──────────────┬───────────────────────────┘
                                   │
                    ┌──────────────▼───────────────────────────┐
                    │           INNER LOOP (Unit/Integration)   │
                    │                                          │
                    │  For each component in the chain:         │
                    │    a. Write unit test for the CONTRACT    │
                    │    b. Run → SEE IT FAIL (RED)            │
                    │    c. Write minimal production code       │
                    │    d. Run → SEE IT PASS (GREEN)          │
                    │    e. Next component                      │
                    │                                          │
                    │  When all components green → return to    │
                    │  outer loop (step 7)                      │
                    │                                          │
                    └──────────────────────────────────────────┘
```

---

## Phase 1: Acceptance Criteria Generation

**Trigger:** `/outside-in-bdd-tdd <feature>` or `/outside-in-bdd-tdd <feature> --ac-only`

**Process:**

1. **Read feature context** — understand the feature's goal and scope from CLAUDE.md, docs, and existing code
2. **Draft Given-When-Then scenarios** — Claude generates happy path scenarios
3. **Present to user for review** — show scenarios, ask user to add edge cases and error scenarios
4. **Apply formality level:**
   - **Complex features** (pipeline, multi-format parsing, TTS): Full Gherkin with Background, Scenario Outline, Examples tables
   - **Simple features** (config, CLI flags): Lightweight Given-When-Then in markdown

### Scenario Philosophy: User Journeys, Not Screens

Scenarios describe **system behavior at the journey level**, not implementation details. You're testing
what the user accomplishes, not which functions get called. If you can swap the entire implementation
and the scenario still reads correctly, you've written it right.

> "My ideal is to build my automated tests structured by user journeys (as opposed to feature)
> where each story contributes to the overall user journey."
> — From Thiago's "Patterns for Effective Acceptance Criteria" (2013, ThoughtWorks/Amex)

**Anti-pattern (implementation-level):**
```gherkin
# BAD — couples to implementation, brittle
Given I call parse_labeled_text() with "tests/fixtures/sample_labeled.txt"
When the function returns a list of Paragraph objects
Then the first Paragraph has speaker="Jung" and word_count=45
And consolidate_paragraphs() merges adjacent same-speaker paragraphs
```

**Correct (journey-level):**
```gherkin
# GOOD — describes behavior, survives refactoring
Given a labeled transcript with two speakers
When the user parses the transcript
Then the output shows each paragraph with its speaker and text
And consecutive paragraphs by the same speaker are consolidated
```

### Thiago's 10 Effective Patterns for Acceptance Criteria

Developed 2013 (ThoughtWorks), refined 2019 (Amex). These are the quality bar for every scenario.

| # | Pattern | Rule | Anti-Pattern |
|---|---------|------|-------------|
| EP1 | **Readable** | Does this AC read well to a non-developer? | Obscure technical language |
| EP2 | **Testable** | Can I unambiguously verify the THEN? | "within acceptable time" (acceptable to whom?) |
| EP3 | **Implementation Agnostic** | No function names, class names, file paths | "call parse_srt()" → "parse the transcript" |
| EP4 | **Actionable WHEN** | The real action is in WHEN, not hidden in GIVEN | Action buried in GIVEN, WHEN says "I look at the output" |
| EP5 | **Strong Verbs** | "displays" not "should display" | Weak verbs: should, could, might |
| EP6 | **Tell a Story** | Scenarios in realistic order, exception cases at end | Random order, no narrative flow |
| EP7 | **Small ACs** | 3 steps perfect, 4 good, 5 max | 8-step scenarios (refactor into sub-steps) |
| EP8 | **Independent ACs** | Each scenario runnable alone, no shared state | Scenario 3 depends on Scenario 2 having run |
| EP9 | **Test Pyramid** | Not every AC through E2E (70/25/5) | Automating every scenario as CLI integration test |
| EP10 | **One WHEN** | Multiple WHENs = a flow, name it | When X / And Y / And Z → "When I generate dubbed audio" |

### GIVEN / WHEN / THEN Role Definitions

Each keyword has a strict role. Mixing them produces confusing, untestable scenarios.

| Keyword | Role | Is | Is NOT |
|---------|------|-----|--------|
| **GIVEN** | Pre-existing condition (setup) | "a labeled transcript exists" | An action ("a user creates a transcript") |
| **WHEN** | What the USER does | "the user runs the generate command" | What the SYSTEM does ("audio is generated") |
| **THEN** | What the SYSTEM does in response | "dubbed audio is produced" | What the USER does ("the user listens to audio") |

### Test Pyramid Discipline: Few E2E, But Deep Slices

The acceptance tests (BDD/Given-When-Then) sit at the TOP of the pyramid. They are **few in number
but each one tests a deep slice** of the entire system. Don't write 20 E2E scenarios for parsing —
write 1-2 that prove the whole pipeline is wired together, and push the exhaustive testing down to
unit/contract level.

```
        ╱╲          Few E2E tests, but each one is a DEEP SLICE
       ╱  ╲         through the entire pipeline (user journey).
      ╱ E2E╲        "Enough to convince you everything is joined up."
     ╱──────╲
    ╱Contract╲      Boundary tests at every seam.
   ╱──────────╲     Parser output, Paragraph format, timing map.
  ╱   Unit     ╲    Exhaustive: edge cases, error paths, None, empty.
 ╱──────────────╲   "Does it handle empty, None, error, failure,
╱________________╲   all the different scenarios you can imagine."
```

**The pyramid rule for Given-When-Then scenarios:**
- **1-2 happy path scenarios per feature** at E2E level (CLI integration test)
- **All edge cases and error paths** tested at unit/contract level (pytest)
- **If base is green and tip is red** → the failure is an integration/wiring issue, not a logic bug

### Gherkin Rules (Hard — Always Enforced)
- **One WHEN per scenario** — multiple WHENs = you're describing a flow, name it (EP10)
- **Given-When-Then structure** — no Given-Then without When
- **Implementation-agnostic language** — no function names, class names, file paths, API endpoints (EP3)
- **Strong verbs** — "produces", "creates", "rejects" not "should produce" (EP5)
- **GIVEN is never an action** — pre-existing condition only
- **WHEN is what the user does** — never what the system does
- **THEN is what the system does** — never what the user does

### Gherkin Rules (Soft — Guidance Only)
- Scenarios organized by feature, not by story
- Scenarios tell a story in realistic order (EP6)
- Background for shared preconditions (avoid repetition)
- Examples tables for data-driven scenarios
- Scenario names as behavior descriptions ("produces dubbed audio from labeled transcript" not "test_generate")
- 3-5 steps max per scenario (EP7)

**Output:** Markdown with Given-When-Then scenarios per feature. NOT Python code — Gherkin text only.

**Example output for parsing feature:**

```gherkin
Feature: Transcript Parsing

  Scenario: Parses a labeled transcript with multiple speakers
    Given a labeled transcript with speaker annotations
    When the user parses the transcript
    Then each paragraph is identified with its speaker
    And the text content is preserved without speaker labels

  Scenario: Parses an SRT subtitle file
    Given an SRT file with numbered entries and timestamps
    When the user parses the transcript
    Then paragraphs are extracted from the subtitle text
    And timing information is used for pause calculation

  Scenario: Handles an empty transcript gracefully
    Given an empty transcript file
    When the user parses the transcript
    Then a clear error message indicates the file has no content

  Scenario: Auto-detects transcript format
    Given a transcript file without explicit format specification
    When the user parses the transcript
    Then the correct parser is selected based on file content
```

---

## Phase 2: Outer Loop (Red)

**Trigger:** After AC approval, skill proceeds automatically

**Process:**

1. **Translate scenarios to test method names** — each scenario becomes a test function
2. **Write pytest-bdd feature file + step definitions** — or plain pytest integration test
3. **Run tests → confirm RED** — every test should fail (feature not implemented yet)
4. **Report:** "Outer loop RED. {N} acceptance tests failing. Dropping into inner loop."

**pytest-bdd patterns (Python defaults):**
```python
# tests/acceptance/test_parsing.py
import subprocess

def test_parses_labeled_transcript_with_multiple_speakers(tmp_path):
    """Given a labeled transcript with speaker annotations
    When the user parses the transcript
    Then each paragraph is identified with its speaker."""
    transcript = tmp_path / "input.txt"
    transcript.write_text("Jung: This is my statement.\nEissler: And this is mine.\n")

    result = subprocess.run(
        ["dub-chunk", "parse", str(transcript)],
        capture_output=True, text=True,
    )

    assert result.returncode == 0
    assert "Jung" in result.stdout
    assert "Eissler" in result.stdout
```

**Important:** Run the outer test ONCE to see it fail. Do NOT keep running it during the inner loop. Return to it only when inner loop is complete.

---

## Phase 3: Inner Loop (Red-Green per Component)

**Trigger:** After outer loop is confirmed RED

**Process:**

For each component in the feature chain (e.g., for parsing: `labeled_text.py → consolidate.py → clean.py → models.py`):

1. **Write unit test for the component's CONTRACT** (interface, not implementation)
2. **Run → confirm RED**
3. **Write minimal production code to make it GREEN**
4. **Run → confirm GREEN**
5. **Move to next component in the chain**

**Strict red-green-refactor discipline:**
- NEVER write production code without a failing test first
- Write the MINIMUM code to make the test pass (no gold-plating)
- Refactoring is batched at epic boundary (not after every green)

**Contract test examples (Python defaults):**

```python
# Parser output contract
def test_labeled_parser_returns_paragraphs_with_speakers():
    text = "Jung: The unconscious is not merely dark.\nEissler: Please elaborate."
    paragraphs = parse_labeled_text(text)
    assert len(paragraphs) == 2
    assert paragraphs[0].speaker == "Jung"
    assert paragraphs[1].speaker == "Eissler"

# Paragraph dataclass contract
def test_paragraph_word_count_matches_text():
    p = Paragraph(id=1, speaker="Jung", text="The unconscious is real")
    assert p.word_count == 4

# Consolidation contract
def test_consecutive_same_speaker_paragraphs_are_merged():
    paragraphs = [
        Paragraph(id=1, speaker="Jung", text="First part."),
        Paragraph(id=2, speaker="Jung", text="Second part."),
        Paragraph(id=3, speaker="Eissler", text="Response."),
    ]
    consolidated = consolidate_paragraphs(paragraphs)
    assert len(consolidated) == 2
    assert "First part" in consolidated[0].text
    assert "Second part" in consolidated[0].text

# Timing map contract
def test_build_timing_map_assigns_pauses_between_paragraphs():
    paragraphs = [
        Paragraph(id=1, speaker="Jung", text="Short."),
        Paragraph(id=2, speaker="Eissler", text="Also short."),
    ]
    timing = build_timing_map(paragraphs, total_duration=0)
    assert len(timing) == 2
    assert timing[1].pause_before >= 0

# Clean contract
def test_clean_strips_stage_directions():
    text = "Hello /pauses thoughtfully/ world"
    cleaned = clean_for_tts(text)
    assert "/pauses thoughtfully/" not in cleaned
    assert "Hello" in cleaned
    assert "world" in cleaned
```

---

## Phase 4: Outer Loop (Green)

**Trigger:** All inner loop components implemented and unit-tested

**Process:**

1. **Run outer acceptance tests** — all integration tests for this feature
2. **If GREEN:** Proceed to refactor
3. **If still RED:** Diagnose gap between unit-tested components and E2E behavior. Usually a wiring issue.

---

## Phase 5: Refactor Pass (Epic Boundary)

**Trigger:** All acceptance tests for the feature are GREEN

**Process:**

1. **Review production code** for smells: duplication, unclear names, too-long functions, missing abstractions
2. **Review test code** for smells: brittle assertions, test interdependence, unclear intent
3. **Refactor** with all tests as safety net (run full test suite after each refactor)
4. **Commit:** Atomic commit with refactoring changes only

---

## Hard-to-TDD Properties

Some properties can't be test-driven (audio quality, ffmpeg output, API response handling). For these, use **characterization tests after implementation:**

1. **Implement the feature** (inner loop still applies for the logic parts)
2. **Write a characterization test** that captures the CURRENT behavior as the baseline
3. **Mark the test explicitly** as `# CHARACTERIZATION: locks current behavior, not a specification`
4. **Examples:**
   - Stitch output: assert final MP3 is valid, duration is sum of clips + pauses
   - TTS response: assert API returns valid MP3 bytes, content-type header is correct
   - ffmpeg subprocess: assert exit code 0, output file exists and is non-empty

---

## Stuck Protocol

When a test is unexpectedly hard to make pass:

1. **Distinguish infrastructure vs business logic:**
   - **Infrastructure** (ffmpeg quirks, API rate limits, subprocess issues): Claude asks user before adapting the test
   - **Business logic** (the spec is wrong, edge case not considered): Claude asks user before changing anything

2. **Claude ALWAYS asks before changing a test.** The test is the spec. Changing it without approval is changing the requirements.

3. **Format for asking:**
   ```
   STUCK: test_parses_labeled_transcript_with_multiple_speakers
   
   Issue: Parser splits on newlines but the fixture uses double-newlines 
   as paragraph separators, so we get empty paragraphs.
   
   Options:
   1. Change parser to skip empty lines (behavioral change)
   2. Change test fixture to use single newlines
   3. This is a real bug — empty lines between paragraphs should be handled
   
   Which direction?
   ```

---

## Walking Skeleton

**Trigger:** `/outside-in-bdd-tdd --walking-skeleton`

The walking skeleton is the THINNEST possible end-to-end slice:

**For dub-chunk:** Plain text file in → parsed paragraphs printed to stdout.

**Acceptance test:**
```gherkin
Scenario: Walking skeleton - parse and display a plain text transcript
  Given a plain text file with two paragraphs
  When the user runs the parse command
  Then the paragraphs are displayed with IDs and word counts
```

This proves: CLI launches → file is read → parser runs → output is formatted. Every component in the chain exists, even if minimal.

**Build order:** Walking skeleton FIRST, before any feature work. This is the GOOS principle — "deploy the walking skeleton before you grow it."

---

## Workflow Per Feature

```
/outside-in-bdd-tdd "multi-format parsing"
    │
    ├── 1. Read feature context from CLAUDE.md + existing code
    │
    ├── 2. Generate Given-When-Then scenarios (Claude drafts)
    │      → Present to user
    │      → User adds edge cases
    │      → Agree on formality level
    │
    ├── 3. Write pytest file with all scenarios as failing tests
    │      → Run → ALL RED ✗
    │      → "Outer loop RED. 4 acceptance tests failing."
    │
    ├── 4. Inner loop for each component:
    │      srt.py parser
    │        → Unit test (contract) → RED → implement → GREEN
    │      labeled_text.py parser
    │        → Unit test → RED → implement → GREEN
    │      consolidate.py
    │        → Unit test → RED → implement → GREEN
    │      ... (continue through pipeline)
    │
    ├── 5. Run outer acceptance tests
    │      → ALL GREEN ✓
    │      → "Outer loop GREEN. All 4 acceptance tests passing."
    │
    ├── 6. Refactor pass
    │      → Review code smells
    │      → Refactor with test safety net
    │      → Commit
    │
    └── 7. Characterization tests (if applicable)
           → Stitch output: assert valid MP3, correct duration
           → Commit
```

---

## Contract Test Types

Three contract boundaries in dub-chunk (and in any pipeline tool with parsing + transformation + output):

| Contract | What It Tests | Example |
|----------|--------------|---------|
| **Input contract** | Transcript formats parse correctly into Paragraphs | `parse_srt()` produces correct `list[Paragraph]` from SRT content |
| **Transform contract** | Pipeline stages preserve/transform data correctly | `consolidate_paragraphs()` merges same-speaker, `clean_for_tts()` strips directions |
| **Output contract** | Final output matches expected format and structure | `stitch()` produces valid MP3, `build_timing_map()` assigns correct pauses |

These tests are FAST (no I/O, no API calls, no ffmpeg) and form the backbone of the inner loop.

---

## Compound Rules

- `OI-001`: Outer test runs ONCE to see red, then drop into inner loop. Don't re-run outer test until inner loop is complete.
- `OI-002`: Inner loop is strict red-green. Never write production code without a failing test.
- `OI-003`: Refactor at epic boundary, not after every green.
- `OI-004`: Claude ALWAYS asks before changing a test. The test is the spec.
- `OI-005`: Characterization tests for hard-to-TDD properties (audio quality, ffmpeg output, API behavior).
- `OI-006`: Walking skeleton first — thinnest E2E slice before any feature work.
- `OI-007`: Gherkin text only for ACs — implementation-agnostic. Python code comes from the developer/Claude.
- `OI-008`: One WHEN per scenario. No compound actions. No implementation-specific language.
- `OI-009`: Contract tests for every boundary: input (parsers), transform (consolidate/clean/timing), output (stitch/TTS).
- `OI-010`: Test pyramid discipline — 1-2 happy paths at E2E, exhaustive edge cases at unit level.

---

## References

### Books (Thiago's Canon)
- **BDD in Action** — John Ferguson Smart (108+ Kindle highlights, 2017)
- **The RSpec Book** — David Chelimsky et al.
- **GOOS** — Steve Freeman & Nat Pryce (638 highlights, #12 Top 22 Tech Books)
- **Continuous Delivery** — Jez Humble & Dave Farley (#20 Top 22 Tech Books)
- **ATDD by Example** — Markus Gartner
- **Specification by Example** — Gojko Adzic (purchased 2012, ThoughtWorks era)
- **Fifty Quick Ideas to Improve Your Tests** — Gojko Adzic

---

## Arguments
$ARGUMENTS
