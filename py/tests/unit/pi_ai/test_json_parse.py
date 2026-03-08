"""Tests for pi_ai.utils.json_parse."""

from __future__ import annotations

from pi_ai.utils.json_parse import parse_streaming_json


class TestParseStreamingJson:
    def test_empty_string(self) -> None:
        assert parse_streaming_json("") == {}

    def test_none(self) -> None:
        assert parse_streaming_json(None) == {}

    def test_whitespace(self) -> None:
        assert parse_streaming_json("   ") == {}

    def test_complete_json(self) -> None:
        result = parse_streaming_json('{"name": "test", "value": 42}')
        assert result == {"name": "test", "value": 42}

    def test_partial_json(self) -> None:
        result = parse_streaming_json('{"name": "test", "val')
        # Should return at least the first valid key
        assert isinstance(result, dict)

    def test_invalid_json(self) -> None:
        assert parse_streaming_json("not json at all") == {}

    def test_array_returns_empty(self) -> None:
        # Arrays are not expected — return empty dict
        assert parse_streaming_json("[1, 2, 3]") == {}

    def test_nested_json(self) -> None:
        result = parse_streaming_json('{"a": {"b": 1}}')
        assert result == {"a": {"b": 1}}

    def test_partial_with_open_brace(self) -> None:
        result = parse_streaming_json('{"key": "value"')
        assert result == {"key": "value"}
