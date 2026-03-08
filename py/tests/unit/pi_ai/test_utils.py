"""Tests for pi_ai utility functions."""

from __future__ import annotations

from pi_ai.utils.json_parse import parse_streaming_json
from pi_ai.utils.sanitize_unicode import sanitize_surrogates

# ---------------------------------------------------------------------------
# parse_streaming_json
# ---------------------------------------------------------------------------


def test_parse_complete_json() -> None:
    assert parse_streaming_json('{"key": "value"}') == {"key": "value"}


def test_parse_empty_string() -> None:
    assert parse_streaming_json("") == {}


def test_parse_none() -> None:
    assert parse_streaming_json(None) == {}


def test_parse_whitespace() -> None:
    assert parse_streaming_json("   ") == {}


def test_parse_incomplete_json_object() -> None:
    result = parse_streaming_json('{"key": "val')
    assert isinstance(result, dict)


def test_parse_partial_with_string_value() -> None:
    result = parse_streaming_json('{"name": "hello"')
    assert isinstance(result, dict)


def test_parse_nested_object() -> None:
    result = parse_streaming_json('{"a": {"b": 1}}')
    assert result == {"a": {"b": 1}}


def test_parse_invalid_returns_empty() -> None:
    result = parse_streaming_json("not json at all !@#$")
    assert result == {}


def test_parse_number_returns_empty() -> None:
    # Top-level number is not a dict
    result = parse_streaming_json("42")
    assert result == {}


def test_parse_array_returns_empty() -> None:
    # Top-level array is not a dict
    result = parse_streaming_json("[1, 2, 3]")
    assert result == {}


def test_parse_bool_returns_empty() -> None:
    result = parse_streaming_json("true")
    assert result == {}


def test_parse_empty_object() -> None:
    assert parse_streaming_json("{}") == {}


def test_parse_complex() -> None:
    result = parse_streaming_json('{"cmd": "ls -la", "path": "/tmp"}')
    assert result == {"cmd": "ls -la", "path": "/tmp"}


# ---------------------------------------------------------------------------
# sanitize_surrogates
# ---------------------------------------------------------------------------


def test_sanitize_normal_text() -> None:
    assert sanitize_surrogates("Hello World") == "Hello World"


def test_sanitize_emoji_preserved() -> None:
    # Valid emoji use properly paired surrogates — should be preserved
    text = "Hello \U0001f648 World"
    assert sanitize_surrogates(text) == text


def test_sanitize_unpaired_high_surrogate() -> None:
    unpaired = "\ud83d"  # high surrogate without matching low surrogate
    result = sanitize_surrogates(f"Text {unpaired} here")
    assert "\ud83d" not in result
    assert "Text" in result
    assert "here" in result


def test_sanitize_unpaired_low_surrogate() -> None:
    unpaired = "\ude00"  # low surrogate without matching high surrogate
    result = sanitize_surrogates(f"Text {unpaired} here")
    assert "\ude00" not in result


def test_sanitize_empty_string() -> None:
    assert sanitize_surrogates("") == ""


def test_sanitize_clean_unicode() -> None:
    text = "Hello \u4e16\u754c"  # Chinese characters
    assert sanitize_surrogates(text) == text


def test_sanitize_newlines_tabs() -> None:
    text = "line1\nline2\ttab"
    assert sanitize_surrogates(text) == text
