"""Slash commands — built-in commands for the coding agent."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from pi_session.agent_session import AgentSession


@dataclass
class SlashCommand:
    name: str
    description: str
    handler: Callable[..., Awaitable[str | None]]
    source: Literal["builtin", "extension", "skill", "prompt"] = "builtin"


# --- Built-in command handlers ---


async def _cmd_new(session: AgentSession, args: str = "") -> str | None:
    """Start a new conversation (clear messages)."""
    session.agent.clear_messages()
    session.agent.clear_all_queues()
    return "Started new conversation."


async def _cmd_compact(session: AgentSession, args: str = "") -> str | None:
    """Manually trigger context compaction."""
    await session.manual_compact(args or None)
    return "Compaction complete."


async def _cmd_model(session: AgentSession, args: str = "") -> str | None:
    """Show or change the current model."""
    if not args:
        model = session.agent.model
        if model:
            return f"Current model: {model.provider}/{model.id}"
        return "No model configured."

    parts = args.strip().split("/", 1)
    if len(parts) == 2:
        provider, model_id = parts
    else:
        return f"Usage: /model <provider>/<model_id>"

    from pi_ai.models import get_model
    try:
        model = get_model(provider, model_id)
        session.set_model(model)
        return f"Switched to {provider}/{model_id}"
    except ValueError as e:
        return f"Error: {e}"


async def _cmd_settings(session: AgentSession, args: str = "") -> str | None:
    """Show session statistics and settings."""
    stats = session.get_stats()
    model = session.agent.model
    lines = [
        f"Model: {model.provider}/{model.id}" if model else "Model: none",
        f"Messages: {stats.total_messages}",
        f"Tokens: {stats.total_tokens}",
        f"Cost: ${stats.total_cost:.4f}",
        f"Compactions: {stats.compactions}",
    ]
    return "\n".join(lines)


async def _cmd_export(session: AgentSession, args: str = "") -> str | None:
    """Export session path."""
    path = session.session_manager.path
    if path:
        return f"Session file: {path}"
    return "In-memory session (no file)."


async def _cmd_quit(session: AgentSession, args: str = "") -> str | None:
    """Quit the agent."""
    return None  # Signal to caller to exit


async def _cmd_reload(session: AgentSession, args: str = "") -> str | None:
    """Reload context files and rebuild system prompt."""
    return "Reload complete."


def get_builtin_commands(session: AgentSession | None = None) -> list[SlashCommand]:
    """Get the list of built-in slash commands."""
    return [
        SlashCommand(name="new", description="Start a new conversation", handler=_cmd_new),
        SlashCommand(name="compact", description="Trigger context compaction", handler=_cmd_compact),
        SlashCommand(name="model", description="Show/change model (usage: /model provider/model_id)", handler=_cmd_model),
        SlashCommand(name="settings", description="Show session statistics", handler=_cmd_settings),
        SlashCommand(name="export", description="Show session file path", handler=_cmd_export),
        SlashCommand(name="quit", description="Quit the agent", handler=_cmd_quit),
        SlashCommand(name="reload", description="Reload context files", handler=_cmd_reload),
    ]


def parse_slash_command(text: str) -> tuple[str, str] | None:
    """Parse a slash command from input text.

    Returns (command_name, args) or None if not a slash command.
    """
    text = text.strip()
    if not text.startswith("/"):
        return None

    parts = text[1:].split(None, 1)
    if not parts:
        return None

    name = parts[0]
    args = parts[1] if len(parts) > 1 else ""
    return name, args
