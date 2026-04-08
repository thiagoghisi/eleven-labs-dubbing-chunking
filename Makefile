# Makefile — dub-chunk: Chunked ElevenLabs voice dubbing
# Run `make setup` to install everything, or individual targets below.

VENV := venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip
CLI := $(VENV)/bin/dub-chunk

.PHONY: setup venv deps check test clean help parse estimate dry-run

# ─── Primary target ───────────────────────────────────────────────

setup: venv deps check  ## Full setup (run this first)
	@echo ""
	@echo "✅ Setup complete! Try it:"
	@echo "   $(CLI) parse tests/fixtures/sample_labeled.txt"
	@echo "   $(CLI) estimate tests/fixtures/sample_labeled.txt"
	@echo "   $(CLI) generate transcript.txt --voice default=YOUR_VOICE_ID --dry-run"
	@echo ""

# ─── Individual targets ──────────────────────────────────────────

venv: $(PYTHON)  ## Create Python virtual environment

$(PYTHON):
	@echo "=== Creating virtual environment ==="
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip -q
	@echo "  ✅ venv created"
	@echo ""

deps: $(PYTHON)  ## Install Python dependencies + CLI
	@echo "=== Installing dependencies ==="
	$(PIP) install -r requirements.txt -q
	$(PIP) install -e . -q
	@echo "  ✅ dub-chunk installed"
	@echo ""

check:  ## Verify all dependencies are installed
	@echo "=== Dependency Check ==="
	@printf "  python3:     "; command -v python3 >/dev/null 2>&1 && python3 --version | awk '{print $$2, "✅"}' || echo "❌"
	@printf "  venv:        "; test -x "$(PYTHON)" && echo "✅" || echo "❌ run: make venv"
	@printf "  dub-chunk:   "; test -x "$(CLI)" && $(CLI) --version | awk '{print $$NF, "✅"}' || echo "❌ run: make deps"
	@printf "  ffmpeg:      "; command -v ffmpeg >/dev/null 2>&1 && ffmpeg -version 2>/dev/null | head -1 | awk '{print $$3, "✅"}' || echo "❌ run: brew install ffmpeg"
	@printf "  ffprobe:     "; command -v ffprobe >/dev/null 2>&1 && echo "✅" || echo "❌ (comes with ffmpeg)"
	@echo ""
	@echo "  Environment variables:"
	@printf "  ELEVENLABS_API_KEY: "; test -n "$$ELEVENLABS_API_KEY" && echo "set ✅" || echo "not set ⚠️"
	@echo ""

test:  ## Run tests
	@echo "=== Running tests ==="
	$(PYTHON) -m pytest tests/ -v
	@echo ""

# ─── Quick shortcuts ─────────────────────────────────────────────

parse:  ## Parse sample transcript: make parse FILE=path/to/file.txt
	$(CLI) parse $(FILE)

estimate:  ## Estimate cost: make estimate FILE=path/to/file.txt
	$(CLI) estimate $(FILE)

dry-run:  ## Dry run generation: make dry-run FILE=path/to/file.txt VOICE="default=VOICE_ID"
	$(CLI) generate $(FILE) --voice $(VOICE) --dry-run

# ─── Cleanup ─────────────────────────────────────────────────────

clean:  ## Remove venv and build artifacts
	@echo "=== Cleaning ==="
	rm -rf $(VENV) build dist src/*.egg-info __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "  ✅ Clean"

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
