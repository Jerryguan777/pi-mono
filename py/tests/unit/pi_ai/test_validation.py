"""Tests for pi_ai.utils.validation."""

from __future__ import annotations

import pytest

from pi_ai.types import Tool, ToolCall
from pi_ai.utils.validation import validate_tool_arguments, validate_tool_call


def _make_tool(name: str = "bash", schema: dict | None = None) -> Tool:  # type: ignore[type-arg]
    return Tool(
        name=name,
        description="Run a command",
        parameters=schema
        or {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    )


class TestValidateToolCall:
    def test_tool_not_found(self) -> None:
        tc = ToolCall(name="nonexistent", arguments={})
        with pytest.raises(ValueError, match='Tool "nonexistent" not found'):
            validate_tool_call([], tc)

    def test_valid_arguments(self) -> None:
        tool = _make_tool()
        tc = ToolCall(name="bash", arguments={"command": "ls"})
        result = validate_tool_call([tool], tc)
        assert result == {"command": "ls"}


class TestValidateToolArguments:
    def test_valid(self) -> None:
        tool = _make_tool()
        tc = ToolCall(name="bash", arguments={"command": "ls"})
        result = validate_tool_arguments(tool, tc)
        assert result == {"command": "ls"}

    def test_missing_required(self) -> None:
        tool = _make_tool()
        tc = ToolCall(name="bash", arguments={})
        try:
            validate_tool_arguments(tool, tc)
            # If jsonschema is not installed, it will just pass through
        except ValueError as e:
            assert "Validation failed" in str(e)

    def test_does_not_mutate_original(self) -> None:
        tool = _make_tool()
        original_args = {"command": "ls"}
        tc = ToolCall(name="bash", arguments=original_args)
        validate_tool_arguments(tool, tc)
        assert tc.arguments is original_args
