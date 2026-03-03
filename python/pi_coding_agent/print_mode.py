"""Print mode — single-shot execution with text or JSON output."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Literal

from pi_ai.types import AssistantMessage, ImageContent, TextContent
from pi_agent.types import (
    AgentEndEvent,
    AgentEvent,
    MessageEndEvent,
    TurnEndEvent,
)

from pi_session.agent_session import AgentSession, SessionEvent


async def run_print_mode(
    session: AgentSession,
    messages: list[str],
    output_mode: Literal["text", "json"] = "text",
    images: list[ImageContent] | None = None,
) -> int:
    """Run the agent in print mode (non-interactive).

    Args:
        session: The agent session to use.
        messages: List of prompt strings to send sequentially.
        output_mode: "text" for final text only, "json" for JSONL events.
        images: Optional images to include with the first message.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    collected_events: list[SessionEvent] = []
    last_assistant_text: str = ""
    had_error = False

    def on_event(event: SessionEvent) -> None:
        nonlocal last_assistant_text, had_error

        collected_events.append(event)

        if output_mode == "json":
            _emit_json_event(event)

        if isinstance(event, MessageEndEvent) and isinstance(event.message, AssistantMessage):
            msg = event.message
            text_parts = [b.text for b in msg.content if isinstance(b, TextContent)]
            if text_parts:
                last_assistant_text = "\n".join(text_parts)
            if msg.stop_reason == "error":
                had_error = True

    session.subscribe(on_event)

    try:
        for i, text in enumerate(messages):
            img = images if i == 0 else None
            await session.prompt(text, img)

        if output_mode == "text" and last_assistant_text:
            sys.stdout.write(last_assistant_text)
            if not last_assistant_text.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()

        return 1 if had_error else 0

    except Exception as e:
        if output_mode == "json":
            _emit_json_event({"type": "error", "message": str(e)})
        else:
            sys.stderr.write(f"Error: {e}\n")
        return 1


def _emit_json_event(event: SessionEvent | dict) -> None:
    """Write a single event as JSON line to stdout."""
    if isinstance(event, dict):
        sys.stdout.write(json.dumps(event) + "\n")
    else:
        try:
            d = asdict(event)
            d["_event_type"] = type(event).__name__
            sys.stdout.write(json.dumps(d, default=str) + "\n")
        except (TypeError, ValueError):
            d = {"_event_type": type(event).__name__, "type": getattr(event, "type", "")}
            sys.stdout.write(json.dumps(d) + "\n")
    sys.stdout.flush()
