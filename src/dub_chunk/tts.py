"""ElevenLabs text-to-speech API client.

Uses ``requests`` for HTTP.  Retries transient errors (429, 500, 502, 503)
with exponential back-off.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from dub_chunk.models import Paragraph, VoiceConfig

_API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"

# Approximate ElevenLabs pricing for multilingual_v2 (as of early 2025).
_PRICE_PER_1K_CHARS = 0.30

# HTTP status codes eligible for automatic retry.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}

# Retry budget.
_MAX_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 2.0


def generate_clip(
    text: str,
    voice_config: VoiceConfig,
    api_key: str,
    output_path: Path,
    model_id: str = "eleven_multilingual_v2",
    timeout: int = 120,
) -> Path:
    """Generate a TTS audio clip via the ElevenLabs API.

    Args:
        text: The text to synthesise.
        voice_config: Voice and prosody settings.
        api_key: ElevenLabs API key.
        output_path: Where to write the resulting MP3 bytes.
        model_id: ElevenLabs model identifier.
        timeout: HTTP request timeout in seconds.

    Returns:
        *output_path* on success (allows easy chaining).

    Raises:
        requests.HTTPError: After exhausting retries on a non-2xx response.
    """
    url = f"{_API_BASE}/{voice_config.voice_id}"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": voice_config.stability,
            "similarity_boost": voice_config.similarity_boost,
            "style": voice_config.style,
            "use_speaker_boost": voice_config.use_speaker_boost,
        },
    }

    backoff = _INITIAL_BACKOFF_SECONDS
    last_response: requests.Response | None = None

    for attempt in range(_MAX_RETRIES + 1):
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)

        if response.status_code == 200:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)
            return output_path

        last_response = response

        if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
            time.sleep(backoff)
            backoff *= 2
            continue

        # Non-retryable error or retries exhausted
        break

    # If we get here we never got a 200
    if last_response is not None:
        last_response.raise_for_status()

    # Defensive: should never reach here, but satisfy the type checker
    raise RuntimeError("TTS request failed without a response")  # pragma: no cover


def estimate_cost(paragraphs: list[Paragraph]) -> dict:
    """Estimate ElevenLabs API cost for synthesising *paragraphs*.

    Uses approximate multilingual_v2 pricing of $0.30 per 1,000 characters.

    Args:
        paragraphs: List of paragraphs whose text will be synthesised.

    Returns:
        Dict with keys ``characters`` (int) and ``estimated_cost_usd`` (float).
    """
    total_chars = sum(len(p.text) for p in paragraphs)
    cost = (total_chars / 1000.0) * _PRICE_PER_1K_CHARS

    return {
        "characters": total_chars,
        "estimated_cost_usd": round(cost, 4),
    }
