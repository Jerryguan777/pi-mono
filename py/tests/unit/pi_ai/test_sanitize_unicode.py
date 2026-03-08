"""Tests for pi_ai.utils.sanitize_unicode — surrogate removal."""

from __future__ import annotations

from pi_ai.utils.sanitize_unicode import sanitize_surrogates


class TestSanitizeSurrogates:
    def test_plain_ascii(self) -> None:
        assert sanitize_surrogates("hello world") == "hello world"

    def test_empty_string(self) -> None:
        assert sanitize_surrogates("") == ""

    def test_valid_emoji_preserved(self) -> None:
        assert sanitize_surrogates("hello 🌍🎉") == "hello 🌍🎉"

    def test_valid_cjk_preserved(self) -> None:
        assert sanitize_surrogates("你好世界") == "你好世界"

    def test_valid_multibyte_preserved(self) -> None:
        assert sanitize_surrogates("café résumé naïve") == "café résumé naïve"

    def test_unpaired_surrogate_stripped(self) -> None:
        # \ud800 is a high surrogate without a matching low surrogate
        text = "hello\ud800world"
        result = sanitize_surrogates(text)
        assert result == "helloworld"

    def test_low_surrogate_alone_stripped(self) -> None:
        text = "abc\udc00def"
        result = sanitize_surrogates(text)
        assert result == "abcdef"

    def test_multiple_surrogates_stripped(self) -> None:
        text = "\ud800\ud801hello\udc00"
        result = sanitize_surrogates(text)
        assert result == "hello"

    def test_surrogate_pair_stripped(self) -> None:
        # In Python, \ud800\udc00 is NOT treated as a valid surrogate pair
        # in a str — it's two separate codepoints
        text = "a\ud800\udc00b"
        result = sanitize_surrogates(text)
        # Both surrogates should be stripped
        assert "\ud800" not in result
        assert "\udc00" not in result

    def test_only_surrogates(self) -> None:
        text = "\ud800\udbff\udc00\udfff"
        result = sanitize_surrogates(text)
        assert result == ""

    def test_whitespace_preserved(self) -> None:
        assert sanitize_surrogates("  \t\n  ") == "  \t\n  "
