"""Strip non-speakable elements from text for TTS consumption.

All transformations are language-agnostic where possible. The a/an correction
applies to English only but is harmless for other languages (the pattern
simply won't match).
"""

from __future__ import annotations

import re


def clean_for_tts(text: str) -> str:
    """Clean *text* so it is ready for a text-to-speech engine.

    Transformations (in order):
        1. Remove /stage directions/ (content between forward slashes, up to 60 chars).
        2. Remove _emphasis_ markers while keeping the enclosed word(s).
        3. Fix English indefinite article: "a" -> "an" before vowel sounds.
        4. Collapse runs of whitespace to a single space.
        5. Remove errant space before punctuation (,.:;!?).
        6. Normalise em-dashes (``—`` and ``--`` surrounded by spaces).
        7. Remove empty parentheses and brackets.
        8. Normalise long ellipsis runs (4+ dots) to three dots.

    Args:
        text: Raw transcript text, possibly containing markup.

    Returns:
        Cleaned string suitable for TTS input.
    """
    result = text

    # 1. Stage directions: /whispers/, /laughs/, etc.
    result = re.sub(r"\s*/[^/]{1,60}/\s*", " ", result)

    # 2. Emphasis markers: _word_ -> word
    result = re.sub(r"_([^_]+)_", r"\1", result)

    # 3. a -> an before vowel (English)
    result = re.sub(r"\ba ([aeiouAEIOU])", r"an \1", result)

    # 4. Collapse multiple spaces
    result = re.sub(r"  +", " ", result)

    # 5. Space before punctuation
    result = re.sub(r" ([,.:;!?])", r"\1", result)

    # Strip leading/trailing whitespace
    result = result.strip()

    # 6. Normalise dashes
    result = re.sub(r"\s+—\s+", " — ", result)
    result = re.sub(r"\s+--\s+", " — ", result)

    # 7. Empty brackets / parens
    result = re.sub(r"\(\s*\)", "", result)
    result = re.sub(r"\[\s*\]", "", result)

    # 8. Long ellipsis (4+ dots -> 3)
    result = re.sub(r"\.{4,}", "...", result)

    return result
