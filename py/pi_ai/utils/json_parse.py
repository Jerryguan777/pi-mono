"""Streaming JSON parser — ported from packages/ai/src/utils/json-parse.ts."""

from __future__ import annotations

import json
from typing import Any


def _try_repair(partial: str) -> dict[str, Any] | None:
    """Try to repair incomplete JSON by appending missing closing brackets."""
    s = partial.strip()
    # Count open/close chars to append the minimum needed closers
    for closer in ("}", "]"):
        trial = s
        for _ in range(20):  # limit iterations
            trial = trial + closer
            try:
                result = json.loads(trial)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass
    # Try combinations of } and ]
    for suffix in ["}", "]}", "}]", "}}", "]]", "}]}", "]}}", "}}}", "]]]"]:
        try:
            result = json.loads(s + suffix)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue
    return None


def parse_streaming_json(partial_json: str | None) -> dict[str, Any]:
    """Attempt to parse potentially incomplete JSON during streaming.

    Always returns a valid dict, even if the JSON is incomplete.

    Args:
        partial_json: Partial JSON string from streaming.

    Returns:
        Parsed dict or empty dict if parsing fails.
    """
    if not partial_json or not partial_json.strip():
        return {}

    # Fast path: try standard parsing first (handles complete JSON)
    try:
        result = json.loads(partial_json)
        if isinstance(result, dict):
            return result
        return {}
    except json.JSONDecodeError:
        pass

    # Slow path: try repairing incomplete JSON
    repaired = _try_repair(partial_json)
    return repaired if repaired is not None else {}
