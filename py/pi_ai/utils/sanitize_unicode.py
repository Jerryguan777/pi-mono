"""Unicode sanitization utilities — ported from packages/ai/src/utils/sanitize-unicode.ts."""

from __future__ import annotations

import re

# Matches unpaired high surrogates (U+D800-U+DBFF not followed by low surrogate U+DC00-U+DFFF)
# or unpaired low surrogates (U+DC00-U+DFFF not preceded by high surrogate).
_SURROGATE_RE = re.compile(r"[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]")


def sanitize_surrogates(text: str) -> str:
    """Remove unpaired Unicode surrogate characters from a string.

    Unpaired surrogates cause JSON serialization errors in many API providers.
    Valid emoji and other characters outside the BMP that use properly paired
    surrogates are NOT affected.

    Args:
        text: The text to sanitize.

    Returns:
        The sanitized text with unpaired surrogates removed.
    """
    return _SURROGATE_RE.sub("", text)
