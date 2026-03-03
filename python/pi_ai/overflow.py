"""Context overflow detection for 15+ LLM providers.

Detects two kinds of overflow:

1. **Error-based** — provider returns stop_reason "error" with a recognisable
   error message (Anthropic, OpenAI, Google, xAI, Groq, OpenRouter, etc.).
2. **Silent overflow** — provider accepts the request but usage.input exceeds
   the model's context window (z.ai).  Pass *context_window* to enable this.
"""

from __future__ import annotations

import re

from pi_ai.types import AssistantMessage

# fmt: off
OVERFLOW_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"prompt is too long",                     re.IGNORECASE),  # Anthropic
    re.compile(r"input is too long for requested model",  re.IGNORECASE),  # Amazon Bedrock
    re.compile(r"exceeds the context window",             re.IGNORECASE),  # OpenAI
    re.compile(r"input token count.*exceeds the maximum", re.IGNORECASE),  # Google Gemini
    re.compile(r"maximum prompt length is \d+",           re.IGNORECASE),  # xAI (Grok)
    re.compile(r"reduce the length of the messages",      re.IGNORECASE),  # Groq
    re.compile(r"maximum context length is \d+ tokens",   re.IGNORECASE),  # OpenRouter
    re.compile(r"exceeds the limit of \d+",               re.IGNORECASE),  # GitHub Copilot
    re.compile(r"exceeds the available context size",     re.IGNORECASE),  # llama.cpp
    re.compile(r"greater than the context length",        re.IGNORECASE),  # LM Studio
    re.compile(r"context window exceeds limit",           re.IGNORECASE),  # MiniMax
    re.compile(r"exceeded model token limit",             re.IGNORECASE),  # Kimi For Coding
    re.compile(r"context[_ ]length[_ ]exceeded",          re.IGNORECASE),  # Generic
    re.compile(r"too many tokens",                        re.IGNORECASE),  # Generic
    re.compile(r"token limit exceeded",                   re.IGNORECASE),  # Generic
]
# fmt: on

# Cerebras / Mistral return "400/413 (no body)" — separate pattern.
_STATUS_CODE_PATTERN = re.compile(
    r"^4(?:00|13)\s*(?:status code)?\s*\(no body\)", re.IGNORECASE
)


def is_context_overflow(
    message: AssistantMessage,
    context_window: int | None = None,
) -> bool:
    """Return *True* if *message* indicates a context-overflow error.

    Parameters
    ----------
    message:
        The assistant message to inspect.
    context_window:
        Optional context-window size (tokens).  When provided, silent overflow
        is detected by comparing ``usage.input + usage.cache_read`` against
        this value.
    """
    # Case 1: error message pattern matching
    if message.stop_reason == "error" and message.error_message:
        err = message.error_message
        if any(p.search(err) for p in OVERFLOW_PATTERNS):
            return True
        if _STATUS_CODE_PATTERN.search(err):
            return True

    # Case 2: silent overflow (z.ai style)
    if context_window and message.stop_reason == "stop":
        input_tokens = message.usage.input + message.usage.cache_read
        if input_tokens > context_window:
            return True

    return False


def get_overflow_patterns() -> list[re.Pattern[str]]:
    """Return a copy of the overflow patterns (for testing)."""
    return list(OVERFLOW_PATTERNS)
