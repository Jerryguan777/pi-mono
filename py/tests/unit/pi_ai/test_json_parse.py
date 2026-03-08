"""Tests for pi_ai.utils.json_parse."""

from __future__ import annotations

from pi_ai.utils.json_parse import parse_streaming_json


class TestParseStreamingJson:
    def test_none_returns_empty(self) -> None:
        assert parse_streaming_json(None) == {}

    def test_empty_string_returns_empty(self) -> None:
        assert parse_streaming_json("") == {}

    def test_whitespace_returns_empty(self) -> None:
        assert parse_streaming_json("   ") == {}

    def test_complete_json(self) -> None:
        result = parse_streaming_json('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_non_dict_json_returns_empty(self) -> None:
        assert parse_streaming_json("[1, 2, 3]") == {}
        assert parse_streaming_json('"just a string"') == {}
        assert parse_streaming_json("42") == {}

    def test_incomplete_json_missing_close_brace(self) -> None:
        result = parse_streaming_json('{"key": "value"')
        assert result == {"key": "value"}

    def test_incomplete_json_trailing_comma(self) -> None:
        result = parse_streaming_json('{"key": "value",')
        assert result == {"key": "value"}

    def test_incomplete_json_nested(self) -> None:
        result = parse_streaming_json('{"outer": {"inner": 1}')
        assert result == {"outer": {"inner": 1}}

    def test_incomplete_json_with_array(self) -> None:
        result = parse_streaming_json('{"items": [1, 2')
        assert result == {"items": [1, 2]}

    def test_totally_invalid_json(self) -> None:
        assert parse_streaming_json("not json at all") == {}

    def test_partial_key(self) -> None:
        # This is too broken to fix
        assert parse_streaming_json('{"ke') == {}

    def test_complete_nested(self) -> None:
        result = parse_streaming_json('{"a": {"b": [1, 2, 3]}, "c": true}')
        assert result == {"a": {"b": [1, 2, 3]}, "c": True}
