"""Stub for messages module — will be replaced when pi_coding_agent is implemented."""

from __future__ import annotations

from pi_agent.types import AgentMessage
from pi_ai.types import Message


def convert_to_llm(messages: list[AgentMessage]) -> list[Message]:
    """Convert agent messages to LLM API format."""
    return [m for m in messages if hasattr(m, "role") and m.role in ("user", "assistant", "toolResult")]
