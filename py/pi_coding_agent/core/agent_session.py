"""Stub for AgentSession — will be replaced when pi_coding_agent is fully implemented."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from pi_agent.types import AgentEvent, AgentMessage
from pi_ai.types import ImageContent


@runtime_checkable
class AgentSession(Protocol):
    """Protocol for agent session - stub until pi_coding_agent is implemented."""

    @property
    def messages(self) -> list[AgentMessage]: ...

    def subscribe(self, fn: Callable[[AgentEvent], None]) -> Callable[[], None]: ...

    async def prompt(self, text: str, images: list[ImageContent] | None = None) -> None: ...

    def abort(self) -> None: ...

    def set_system_prompt(self, prompt: str) -> None: ...

    def replace_messages(self, messages: list[AgentMessage]) -> None: ...
