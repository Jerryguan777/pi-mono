"""Tool argument validation using JSON Schema."""

from __future__ import annotations

import json

import jsonschema

from pi_ai.types import Tool, ToolCall


def validate_tool_arguments(tool: Tool, tool_call: ToolCall) -> dict:
    """Validate tool call arguments against the tool's JSON Schema.

    Returns the validated arguments, or raises an error if validation fails.
    """
    schema = tool.parameters
    if not schema:
        return tool_call.arguments

    try:
        jsonschema.validate(instance=tool_call.arguments, schema=schema)
    except jsonschema.ValidationError as e:
        path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        error_msg = (
            f'Validation failed for tool "{tool_call.name}":\n'
            f"  - {path}: {e.message}\n\n"
            f"Received arguments:\n{json.dumps(tool_call.arguments, indent=2)}"
        )
        raise ValueError(error_msg) from e

    return tool_call.arguments
