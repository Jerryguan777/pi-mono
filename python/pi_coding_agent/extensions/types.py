"""Extension context and runtime types."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pi_ai.types import Model
from pi_agent.types import AgentEvent, AgentTool

from pi_session.session_manager import SessionManager


@dataclass
class ExtensionContext:
    """Context passed to extensions during setup."""
    cwd: str = ""
    session_manager: SessionManager | None = None
    model: Model | None = None


class ExtensionRuntime:
    """Runtime API available to extensions for registering capabilities."""

    def __init__(self) -> None:
        self._event_handlers: list[Callable[[AgentEvent], Awaitable[None]]] = []
        self._tools: list[AgentTool] = []
        self._commands: list[dict[str, Any]] = []

    def on_event(self, handler: Callable[[AgentEvent], Awaitable[None]]) -> None:
        """Register an event handler."""
        self._event_handlers.append(handler)

    def register_tool(self, tool: AgentTool) -> None:
        """Register a custom tool."""
        self._tools.append(tool)

    def register_command(self, name: str, description: str, handler: Callable) -> None:
        """Register a slash command."""
        self._commands.append({
            "name": name,
            "description": description,
            "handler": handler,
        })

    @property
    def event_handlers(self) -> list[Callable[[AgentEvent], Awaitable[None]]]:
        return self._event_handlers

    @property
    def tools(self) -> list[AgentTool]:
        return self._tools

    @property
    def commands(self) -> list[dict[str, Any]]:
        return self._commands
