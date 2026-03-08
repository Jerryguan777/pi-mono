"""Tests for pi_ai.utils.sanitize_unicode."""

from __future__ import annotations

from pi_ai.utils.sanitize_unicode import sanitize_surrogates


class TestSanitizeSurrogates:
    def test_normal_text(self) -> None:
        assert sanitize_surrogates("Hello World") == "Hello World"

    def test_empty_string(self) -> None:
        assert sanitize_surrogates("") == ""

    def test_valid_emoji_preserved(self) -> None:
        # Valid emoji uses properly paired surrogates
        assert sanitize_surrogates("Hello \U0001f648 World") == "Hello \U0001f648 World"

    def test_ascii_text(self) -> None:
        assert sanitize_surrogates("abc123!@#") == "abc123!@#"
