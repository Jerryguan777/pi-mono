"""Print mode (single-shot): Send prompts, output result, exit.

Python port of packages/coding-agent/src/modes/print-mode.ts.

Used for:
  - pi -p "prompt"         (text output)
  - pi --mode json "prompt" (JSON event stream)
"""

from __future__ import annotations

import dataclasses
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Literal


def _to_json(obj: Any) -> str:
    """Serialize an object to JSON, handling dataclasses."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return json.dumps(dataclasses.asdict(obj))
    return json.dumps(obj)


@dataclass
class PrintModeOptions:
    """Options for print mode."""

    # Output mode: "text" for final response only, "json" for all events
    mode: Literal["text", "json"]
    # Additional prompts to send after initial_message
    messages: list[str] = field(default_factory=list)
    # First message to send (may contain @file content)
    initial_message: str | None = None
    # Images to attach to the initial message
    initial_images: list[Any] | None = None


async def run_print_mode(session: Any, options: PrintModeOptions) -> None:
    """Run in print (single-shot) mode.

    Sends prompts to the agent and outputs the result.

    Args:
        session: AgentSession instance (typed as Any at runtime due to parallel task).
        options: PrintModeOptions controlling output mode and messages.
    """
    mode = options.mode
    messages = options.messages
    initial_message = options.initial_message
    initial_images = options.initial_images

    if mode == "json":
        # Output the session header if available
        session_manager = getattr(session, "session_manager", None)
        if session_manager is not None:
            header = session_manager.get_header()
            if header is not None:
                print(_to_json(header))

    # Set up extensions for print mode (no UI)
    await session.bind_extensions(
        {
            "command_context_actions": {
                "wait_for_idle": lambda: session.agent.wait_for_idle(),
                "new_session": _make_new_session_action(session),
                "fork": _make_fork_action(session),
                "navigate_tree": _make_navigate_tree_action(session),
                "switch_session": _make_switch_session_action(session),
                "reload": lambda: session.reload(),
            },
            "on_error": lambda err: print(
                f"Extension error ({err.get('extension_path', '?')}): {err.get('error', '?')}",
                file=sys.stderr,
            ),
        }
    )

    # Subscribe to events - always needed for session persistence
    def handle_event(event: Any) -> None:
        if mode == "json":
            print(_to_json(event))

    session.subscribe(handle_event)

    # Send initial message with attachments
    if initial_message:
        await session.prompt(initial_message, images=initial_images)

    # Send remaining messages
    for message in messages:
        await session.prompt(message)

    # In text mode, output the final response
    if mode == "text":
        state = session.state
        state_messages: list[Any] = getattr(state, "messages", [])
        if state_messages:
            last_message = state_messages[-1]
            if getattr(last_message, "role", None) == "assistant":
                stop_reason = getattr(last_message, "stop_reason", None)
                if stop_reason in ("error", "aborted"):
                    error_msg = getattr(last_message, "error_message", None) or f"Request {stop_reason}"
                    print(error_msg, file=sys.stderr)
                    sys.exit(1)

                content_list: list[Any] = getattr(last_message, "content", [])
                for content_item in content_list:
                    if getattr(content_item, "type", None) == "text":
                        print(content_item.text)

    # Flush stdout
    sys.stdout.flush()


def _make_new_session_action(session: Any) -> Any:
    """Create the new_session action callback."""

    async def new_session(opts: Any = None) -> dict[str, bool]:
        success = await session.new_session(parent_session=getattr(opts, "parent_session", None) if opts else None)
        if success and opts and hasattr(opts, "setup") and opts.setup is not None:
            await opts.setup(session.session_manager)
        return {"cancelled": not success}

    return new_session


def _make_fork_action(session: Any) -> Any:
    """Create the fork action callback."""

    async def fork(entry_id: Any) -> dict[str, bool]:
        result = await session.fork(entry_id)
        return {"cancelled": result.cancelled}

    return fork


def _make_navigate_tree_action(session: Any) -> Any:
    """Create the navigate_tree action callback."""

    async def navigate_tree(target_id: Any, opts: Any = None) -> dict[str, bool]:
        result = await session.navigate_tree(
            target_id,
            summarize=getattr(opts, "summarize", None) if opts else None,
            custom_instructions=getattr(opts, "custom_instructions", None) if opts else None,
            replace_instructions=getattr(opts, "replace_instructions", None) if opts else None,
            label=getattr(opts, "label", None) if opts else None,
        )
        return {"cancelled": result.cancelled}

    return navigate_tree


def _make_switch_session_action(session: Any) -> Any:
    """Create the switch_session action callback."""

    async def switch_session(session_path: str) -> dict[str, bool]:
        success = await session.switch_session(session_path)
        return {"cancelled": not success}

    return switch_session
