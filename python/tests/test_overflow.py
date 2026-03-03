"""Tests for pi_ai.overflow — context overflow detection."""

from pi_ai.overflow import is_context_overflow, get_overflow_patterns
from pi_ai.types import AssistantMessage, Usage


def _error_msg(error_message: str) -> AssistantMessage:
    return AssistantMessage(stop_reason="error", error_message=error_message)


def _ok_msg(input_tokens: int = 0, cache_read: int = 0) -> AssistantMessage:
    return AssistantMessage(
        stop_reason="stop",
        usage=Usage(input=input_tokens, cache_read=cache_read),
    )


# ---------- error-based overflow detection ----------

def test_anthropic_overflow():
    msg = _error_msg("prompt is too long: 213462 tokens > 200000 maximum")
    assert is_context_overflow(msg) is True


def test_amazon_bedrock_overflow():
    msg = _error_msg("input is too long for requested model")
    assert is_context_overflow(msg) is True


def test_openai_overflow():
    msg = _error_msg("Your input exceeds the context window of this model")
    assert is_context_overflow(msg) is True


def test_google_gemini_overflow():
    msg = _error_msg(
        "The input token count (1196265) exceeds the maximum number of "
        "tokens allowed (1048575)"
    )
    assert is_context_overflow(msg) is True


def test_xai_grok_overflow():
    msg = _error_msg(
        "This model's maximum prompt length is 131072 but the request "
        "contains 537812 tokens"
    )
    assert is_context_overflow(msg) is True


def test_groq_overflow():
    msg = _error_msg("Please reduce the length of the messages or completion")
    assert is_context_overflow(msg) is True


def test_openrouter_overflow():
    msg = _error_msg(
        "This endpoint's maximum context length is 128000 tokens. "
        "However, you requested about 200000 tokens"
    )
    assert is_context_overflow(msg) is True


def test_github_copilot_overflow():
    msg = _error_msg("prompt token count of 150000 exceeds the limit of 128000")
    assert is_context_overflow(msg) is True


def test_llamacpp_overflow():
    msg = _error_msg(
        "the request exceeds the available context size, try increasing it"
    )
    assert is_context_overflow(msg) is True


def test_lm_studio_overflow():
    msg = _error_msg(
        "tokens to keep from the initial prompt is greater than the context length"
    )
    assert is_context_overflow(msg) is True


def test_minimax_overflow():
    msg = _error_msg("invalid params, context window exceeds limit")
    assert is_context_overflow(msg) is True


def test_kimi_overflow():
    msg = _error_msg(
        "Your request exceeded model token limit: 128000 (requested: 200000)"
    )
    assert is_context_overflow(msg) is True


def test_generic_context_length_exceeded():
    msg = _error_msg("context_length_exceeded")
    assert is_context_overflow(msg) is True


def test_generic_context_length_exceeded_spaces():
    msg = _error_msg("context length exceeded for this request")
    assert is_context_overflow(msg) is True


def test_generic_too_many_tokens():
    msg = _error_msg("too many tokens in the request")
    assert is_context_overflow(msg) is True


def test_generic_token_limit_exceeded():
    msg = _error_msg("token limit exceeded")
    assert is_context_overflow(msg) is True


# ---------- status code overflow (Cerebras / Mistral) ----------

def test_cerebras_400_no_body():
    msg = _error_msg("400 (no body)")
    assert is_context_overflow(msg) is True


def test_mistral_413_no_body():
    msg = _error_msg("413 status code (no body)")
    assert is_context_overflow(msg) is True


def test_413_no_body_case_insensitive():
    msg = _error_msg("413 Status Code (No Body)")
    assert is_context_overflow(msg) is True


def test_429_is_not_overflow():
    """429 is rate limiting, not context overflow."""
    msg = _error_msg("429 (no body)")
    assert is_context_overflow(msg) is False


# ---------- silent overflow ----------

def test_silent_overflow_detected():
    msg = _ok_msg(input_tokens=250000)
    assert is_context_overflow(msg, context_window=200000) is True


def test_silent_overflow_with_cache_read():
    msg = _ok_msg(input_tokens=150000, cache_read=100000)
    assert is_context_overflow(msg, context_window=200000) is True


def test_no_silent_overflow_within_limit():
    msg = _ok_msg(input_tokens=100000)
    assert is_context_overflow(msg, context_window=200000) is False


def test_silent_overflow_not_checked_without_context_window():
    msg = _ok_msg(input_tokens=999999)
    assert is_context_overflow(msg) is False


# ---------- non-overflow cases ----------

def test_normal_error_not_overflow():
    msg = _error_msg("Internal server error")
    assert is_context_overflow(msg) is False


def test_normal_stop_not_overflow():
    msg = _ok_msg(input_tokens=1000)
    assert is_context_overflow(msg) is False


def test_none_error_message():
    msg = AssistantMessage(stop_reason="error", error_message=None)
    assert is_context_overflow(msg) is False


# ---------- utility ----------

def test_get_overflow_patterns_returns_copy():
    patterns = get_overflow_patterns()
    assert len(patterns) == 15
    patterns.pop()
    assert len(get_overflow_patterns()) == 15  # original unaffected
