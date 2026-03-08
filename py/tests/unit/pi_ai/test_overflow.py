"""Tests for pi_ai.utils.overflow."""

from __future__ import annotations

from pi_ai.types import AssistantMessage, Usage
from pi_ai.utils.overflow import get_overflow_patterns, is_context_overflow


def _make_error_msg(error_message: str) -> AssistantMessage:
    return AssistantMessage(stop_reason="error", error_message=error_message)


def _make_ok_msg(input_tokens: int = 0, cache_read: int = 0) -> AssistantMessage:
    return AssistantMessage(
        stop_reason="stop",
        usage=Usage(input=input_tokens, cache_read=cache_read),
    )


class TestIsContextOverflow:
    def test_anthropic_error(self) -> None:
        msg = _make_error_msg("prompt is too long: 213462 tokens > 200000 maximum")
        assert is_context_overflow(msg) is True

    def test_openai_error(self) -> None:
        msg = _make_error_msg("Your input exceeds the context window of this model")
        assert is_context_overflow(msg) is True

    def test_google_error(self) -> None:
        msg = _make_error_msg("The input token count (1196265) exceeds the maximum number of tokens allowed (1048575)")
        assert is_context_overflow(msg) is True

    def test_xai_error(self) -> None:
        msg = _make_error_msg("This model's maximum prompt length is 131072 but the request contains 537812 tokens")
        assert is_context_overflow(msg) is True

    def test_groq_error(self) -> None:
        msg = _make_error_msg("Please reduce the length of the messages or completion")
        assert is_context_overflow(msg) is True

    def test_status_code_400(self) -> None:
        msg = _make_error_msg("400 status code (no body)")
        assert is_context_overflow(msg) is True

    def test_status_code_413(self) -> None:
        msg = _make_error_msg("413 (no body)")
        assert is_context_overflow(msg) is True

    def test_non_overflow_error(self) -> None:
        msg = _make_error_msg("rate limited")
        assert is_context_overflow(msg) is False

    def test_429_is_not_overflow(self) -> None:
        msg = _make_error_msg("429 status code (no body)")
        assert is_context_overflow(msg) is False

    def test_silent_overflow(self) -> None:
        msg = _make_ok_msg(input_tokens=150000, cache_read=60000)
        assert is_context_overflow(msg, context_window=200000) is True

    def test_within_context_window(self) -> None:
        msg = _make_ok_msg(input_tokens=100000, cache_read=0)
        assert is_context_overflow(msg, context_window=200000) is False

    def test_no_context_window_no_silent_check(self) -> None:
        msg = _make_ok_msg(input_tokens=999999)
        assert is_context_overflow(msg) is False


class TestGetOverflowPatterns:
    def test_returns_copy(self) -> None:
        p1 = get_overflow_patterns()
        p2 = get_overflow_patterns()
        assert p1 is not p2
        assert len(p1) > 0
