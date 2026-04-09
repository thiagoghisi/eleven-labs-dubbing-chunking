# Compound Rules — dub-chunk

Learnings extracted from development sessions. Each rule passed three filters:
generalizable (applies to future tasks), non-obvious (not already in CLAUDE.md),
and actionable (specific enough to apply).

## Quick Index

| Category | Code | Count |
|----------|------|------:|
| Testing/Test Strategy | TS | 11 |
| Python/Scripts | PY | 2 |
| Communication | CM | 1 |

---

## TS — Testing / Test Strategy

#### TS-001: Boundary contract tests mock at the last mile only
**Added:** 2026-04-09
**Context:** Needed E2E-level confidence that the pipeline sends correct text/args to ElevenLabs API and ffmpeg, without calling real external services.
**Rule:** Mock `requests.post` and `subprocess.run` at the module boundary — never mock internal functions (parsers, consolidation, timing). The full pipeline runs for real. Assert exact text, exact argv, exact call counts. When the pipeline changes what flows to boundaries, these tests break — that's the point.
**Evidence:** `tests/test_cli_e2e_mocked.py`
**Applies when:** Testing a pipeline that talks to external services (APIs, CLIs, databases). You want integration-level confidence without the infrastructure.

#### TS-002: Newspaper structure for test files
**Added:** 2026-04-09
**Context:** Test file had 200 lines of helpers and expected data before the actual test scenarios — the reader had to scroll past plumbing to find what was being tested.
**Rule:** Structure test files top-to-bottom: (1) Scenarios/test classes, (2) Expected data constants, (3) Plumbing (helpers, mocks, fixtures). Python doesn't care about definition order — structure for the reader, not the interpreter.
**Evidence:** Refactored `tests/test_cli_e2e_mocked.py` — scenarios moved to top, immediate readability improvement.
**Applies when:** Any test file with shared helpers, expected data constants, or mock factories.

#### TS-003: Capture side effects before cleanup destroys them
**Added:** 2026-04-09
**Context:** `stitch_audio()` writes `concat.txt` to a temp dir then cleans it up in a `finally` block. By the time test assertions run, the file is gone.
**Rule:** When mocking a function whose caller cleans up artifacts, capture the data inside the mock's side_effect (before cleanup runs). Example: read `concat.txt` content when the subprocess mock intercepts the ffmpeg concat call, not after the function returns.
**Evidence:** `_mock_subprocess_run` in `tests/test_cli_e2e_mocked.py` captures concat.txt content on the fly.
**Applies when:** Testing code that uses temp directories, temp files, or cleanup patterns (`finally`, context managers, `atexit`).

#### TS-004: Expected data as the spec — hardcode pipeline outputs
**Added:** 2026-04-09
**Context:** Boundary contract tests need to assert the exact text sent to the TTS API after the full pipeline (parse -> consolidate -> clean).
**Rule:** Run the pipeline once to capture actual outputs, then hardcode them as module-level constants (`EXPECTED_LABELED`, `EXPECTED_SRT`, etc.). These constants ARE the contract. Don't compute expected values from the same functions you're testing — that's tautological. If the pipeline changes, update the constants explicitly.
**Evidence:** `EXPECTED_LABELED`, `EXPECTED_SRT`, `EXPECTED_PLAIN`, `EXPECTED_SRT_TIMED` in `tests/test_cli_e2e_mocked.py`
**Applies when:** Writing contract/integration tests where exact output matters (API payloads, CLI arguments, file formats).

#### TS-005: Return warnings as data, not just log them
**Added:** 2026-04-09
**Context:** `build_srt_timing_map()` logged warnings via `logger.warning()` but the CLI never showed them to the user. Warnings were invisible.
**Rule:** When a function needs to warn about degraded behavior, return warnings as a `list[str]` alongside the main return value. The caller (CLI) can then display them via `click.echo(err=True)`. This makes warnings testable at both the unit level (check returned list) and E2E level (check CLI output), and keeps the domain function free of UI dependencies.
**Evidence:** `build_srt_timing_map()` returns `(entries, speeds, warnings)` — tested at unit level in `test_timing.py::TestSrtTimingMapWarnings` and at CLI level in `test_cli_e2e_mocked.py::TestFullGenerateSrtWithTimingSync::test_warnings_shown_for_clamped_paragraphs`.
**Applies when:** Domain functions that detect edge cases, clamp values, or degrade gracefully. The function shouldn't own the display — return the data, let the caller decide how to present it.

#### TS-006: Characterization tests for hard-to-TDD properties
**Added:** 2026-04-09
**Context:** Some properties can't be test-driven — audio quality, ffmpeg output format, animation frame timing, export quality. Writing a failing test first doesn't work because you don't know what "correct" looks like until after implementation.
**Rule:** Implement the feature first (inner loop still applies for logic parts), then write a characterization test that captures current behavior as the baseline. Mark it explicitly: `# CHARACTERIZATION: locks current behavior, not a specification`. Examples: assert render < 16ms, assert output is valid H.264, assert stitch produces valid MP3 with correct duration.
**Evidence:** OI-005 in `.claude/commands/outside-in-bdd-tdd.md`; `tests/test_stitch.py::TestStitchAudio` validates real ffmpeg output.
**Applies when:** Testing non-functional properties (performance, output quality, format correctness) where the "spec" is "it works like it does now."

#### TS-007: Base green + tip red = wiring issue
**Added:** 2026-04-09
**Context:** Test pyramid debugging heuristic learned from 18 years of BDD practice. When all unit/contract tests pass but the E2E acceptance test fails, the bug is never in the logic — it's in how the components are wired together.
**Rule:** If unit tests are green and E2E is red, don't re-examine the unit-tested logic. Look at the integration points: argument passing between functions, import paths, CLI option wiring, data transformation at boundaries. The logic is tested; the plumbing is not.
**Evidence:** OI-009/OI-010 in `.claude/commands/outside-in-bdd-tdd.md`; GOOS (Freeman & Pryce).
**Applies when:** Debugging a failing E2E test when all inner tests pass. Saves time by narrowing the search space.

#### TS-008: Real fixtures at E2E, synthetic data at unit
**Added:** 2026-04-09
**Context:** E2E tests in dub-chunk use real fixture files (`sample_labeled.txt`, `sample.srt`), while unit tests use inline synthetic data (`_p(1, "A", "Hello world")`).
**Rule:** E2E tests should use real fixture files that represent actual user input — they test the full pipeline against realistic data. Unit tests should use minimal inline data that isolates the specific behavior being tested. Mixing these (real fixtures in unit tests, synthetic data in E2E) weakens both: unit tests become slow and brittle, E2E tests don't catch real-world parsing issues.
**Evidence:** `tests/test_cli_e2e.py` uses `FIXTURES / "sample_labeled.txt"`; `tests/test_parsers.py` uses inline strings.
**Applies when:** Deciding what test data to use. Rule of thumb: if the test class name contains "E2E" or "Journey" → real fixtures. Otherwise → inline.

#### TS-009: pytest markers + make targets for test categories
**Added:** 2026-04-09
**Context:** Needed to run only E2E tests or only unit tests during development. Running the full 197-test suite is fast (1s) but during TDD you want the tightest possible feedback loop.
**Rule:** Add pytest markers (`@pytest.mark.e2e`) to test files and register them in `pyproject.toml`. Create matching Makefile targets (`make test-e2e`, `make test-unit`, `make test`). This gives developers three speeds: fast inner loop (`make test-unit`, <0.3s), E2E validation (`make test-e2e`, <0.2s), full suite (`make test`, <1s).
**Evidence:** `pyproject.toml` marker registration; `Makefile` targets; `pytestmark = pytest.mark.e2e` in E2E test files.
**Applies when:** Any project with >50 tests or tests with different execution profiles (fast unit vs slower integration/E2E).

#### TS-010: E2E assertions test behavior, not exact output
**Added:** 2026-04-09
**Context:** E2E tests for the `parse` command assert `"Dr. Jung" in result.output` and `"Paragraphs:" in result.output` — not the exact output string. This makes them resilient to formatting changes.
**Rule:** At the E2E level, assert on behavioral markers (exit code, presence of key strings, absence of error messages) not exact output. `assert "$" in result.output` survives a formatting change; `assert result.output == "Est. cost: $0.3000\n"` does not. Save exact-value assertions for boundary contract tests where precision is the point.
**Evidence:** `tests/test_cli_e2e.py` — all assertions use `in` checks and exit codes.
**Applies when:** Writing E2E/acceptance tests for CLI tools or any system with human-readable output.

#### TS-011: One boundary contract test per input variant
**Added:** 2026-04-09
**Context:** dub-chunk supports 3 input formats (SRT, labeled, plain text). Each exercises a different parser, different consolidation behavior (plain text merges all paragraphs), and different speaker mappings.
**Rule:** Write one boundary contract test per input format/variant, not just one happy path. Each variant may trigger different pipeline behavior that wouldn't be caught by a single test. In dub-chunk: labeled (8 paragraphs, alternating speakers), SRT (6 paragraphs, with timing), plain (7 paragraphs collapsed to 1).
**Evidence:** `TestFullGenerateLabeledPipeline`, `TestFullGenerateSrtPipeline`, `TestFullGeneratePlainPipeline` in `tests/test_cli_e2e_mocked.py`.
**Applies when:** Pipeline accepts multiple input formats, modes, or configuration variants that change internal behavior.

---

## CM — Communication

#### CM-001: Stuck protocol — structured format for blocked tests
**Added:** 2026-04-09
**Context:** When a test is unexpectedly hard to pass, Claude needs to communicate the blockage clearly and let the user decide direction — never silently change a test (the test is the spec).
**Rule:** Use this format: `STUCK: {test_name}` / `Issue: {what's happening}` / `Options: 1. ... 2. ... 3. ...` / `Which direction?`. Always distinguish infrastructure issues (ffmpeg quirks, API limitations) from business logic issues (spec is wrong, edge case not considered). Never change a failing test without user approval.
**Evidence:** Stuck Protocol section in `.claude/commands/outside-in-bdd-tdd.md`; OI-004.
**Applies when:** A test is failing and the fix isn't obvious. Especially when working with AI assistants that might silently "fix" the test instead of the code.

---

## PY — Python / Scripts

#### PY-001: Editable install required for dataclass changes
**Added:** 2026-04-09
**Context:** Added `original_start`/`original_end` fields to the Paragraph dataclass. Tests failed with `AttributeError` because the installed package was stale (non-editable install).
**Rule:** After modifying dataclasses or adding new fields, if tests fail with `AttributeError` on fields you just added, run `pip install -e .` to switch to editable mode. Non-editable installs copy source to site-packages at install time and don't pick up changes.
**Evidence:** This session — test_parsers.py failed after adding fields to Paragraph until `venv/bin/pip install -e .` was run.
**Applies when:** Developing Python packages with `pyproject.toml` / `setup.py`. Any time you modify a dataclass, model, or add new modules.

#### PY-002: Verify API constraints before designing around assumptions
**Added:** 2026-04-09
**Context:** Designed speed clamping with [0.5, 2.0] range based on assumption. ElevenLabs actual range is [0.7, 1.2] — much tighter. Would have needed redesign if discovered later.
**Rule:** Before implementing features that depend on external API parameters (ranges, formats, limits), verify the actual constraints from docs or a test call. Don't design around assumed ranges — the real limits might invalidate the approach entirely.
**Evidence:** ElevenLabs speed range discovery mid-implementation changed the clamp boundaries and surfaced that ffmpeg atempo might be needed later.
**Applies when:** Implementing features that wrap external API parameters, rate limits, or format constraints.
