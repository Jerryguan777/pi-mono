"""Streaming JSON parser for partial JSON from LLM tool calls.

Ported from packages/ai/src/utils/json-parse.ts.
"""

from __future__ import annotations

import json
from typing import Any


def parse_streaming_json(partial_json: str | None) -> dict[str, Any]:
    """Parse potentially incomplete JSON during streaming.

    Always returns a valid dict, even if the JSON is incomplete.
    """
    if not partial_json or partial_json.strip() == "":
        return {}

    # Try standard parsing first (fastest for complete JSON)
    try:
        result = json.loads(partial_json)
        if isinstance(result, dict):
            return result
        return {}
    except json.JSONDecodeError:
        pass

    # Try to fix incomplete JSON by closing open braces/brackets
    fixed = partial_json.rstrip()
    open_braces = fixed.count("{") - fixed.count("}")
    open_brackets = fixed.count("[") - fixed.count("]")

    # Remove trailing comma if present
    if fixed.endswith(","):
        fixed = fixed[:-1]

    fixed += "]" * max(0, open_brackets)
    fixed += "}" * max(0, open_braces)

    try:
        result = json.loads(fixed)
        if isinstance(result, dict):
            return result
        return {}
    except json.JSONDecodeError:
        return {}
