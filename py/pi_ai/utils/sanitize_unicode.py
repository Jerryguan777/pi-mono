"""Remove unpaired Unicode surrogates from strings.

Ported from packages/ai/src/utils/sanitize-unicode.ts.
In Python 3, strings are proper Unicode and don't have surrogate issues
the same way JavaScript does. However, we keep this function for API parity
and to handle any edge cases with surrogatepass encoding.
"""

from __future__ import annotations


def sanitize_surrogates(text: str) -> str:
    """Remove unpaired Unicode surrogate characters from a string.

    Valid emoji and other characters outside the BMP are preserved.
    """
    # In Python, encode with surrogatepass to handle any surrogates,
    # then decode ignoring errors to strip them
    return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="ignore")
