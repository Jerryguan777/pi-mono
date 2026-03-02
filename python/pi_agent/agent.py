"""Agent class — wraps the agent loop with state management and subscriptions."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from pi_ai.types import (
    AssistantMessage,
    ImageContent,
    Message,
    Model,
    StreamOptions,
    TextContent,
    ToolResultMessage,
    Usage,
    Cost,
    UserMessage,
)

from pi_agent.agent_loop import agent_loop
from pi_agent.types import (
    AgentEndEvent,
    AgentEvent,
    AgentTool,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
)


class Agent:
    """Agent with state management, event subscription, and prompt interface."""

    def __init__(
        self,
        model: Model | None = None,
        system_prompt: str = "",
        tools: list[AgentTool] | None = None,
        api_key: str | None = None,
        reasoning: str | None = None,
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.tools: list[AgentTool] = tools or []
        self.messages: list[Message] = []
        self.is_streaming = False
        self.error: str | None = None
        self._listeners: list[Callable[[AgentEvent], None]] = []
        self._abort = False
        self._running_task: asyncio.Task | None = None
        self._api_key = api_key
        self._reasoning = reasoning

    def subscribe(self, fn: Callable[[AgentEvent], None]) -> Callable[[], None]:
        """Subscribe to agent events. Returns unsubscribe function."""
        self._listeners.append(fn)
        return lambda: self._listeners.remove(fn) if fn in self._listeners else None

    def _emit(self, event: AgentEvent) -> None:
        for listener in self._listeners:
            listener(event)

    async def prompt(self, text: str, images: list[ImageContent] | None = None) -> None:
        """Send a prompt to the agent and wait for completion."""
        if self.is_streaming:
            raise RuntimeError("Agent is already processing a prompt.")
        if not self.model:
            raise RuntimeError("No model configured.")

        content: list[TextContent | ImageContent] = [TextContent(text=text)]
        if images:
            content.extend(images)

        user_msg = UserMessage(
            content=content,
            timestamp=int(time.time() * 1000),
        )

        await self._run_loop([user_msg])

    async def prompt_messages(self, messages: list[Message]) -> None:
        """Send multiple messages as a prompt."""
        if self.is_streaming:
            raise RuntimeError("Agent is already processing.")
        if not self.model:
            raise RuntimeError("No model configured.")
        await self._run_loop(messages)

    def abort(self) -> None:
        """Abort the current operation."""
        self._abort = True

    def reset(self) -> None:
        """Reset agent state."""
        self.messages = []
        self.is_streaming = False
        self.error = None
        self._abort = False

    async def _run_loop(self, prompt_messages: list[Message]) -> None:
        """Run the agent loop with given prompt messages."""
        self.is_streaming = True
        self.error = None
        self._abort = False

        options = StreamOptions(
            api_key=self._api_key,
            reasoning=self._reasoning,
        )

        try:
            async for event in agent_loop(
                prompts=prompt_messages,
                system_prompt=self.system_prompt,
                messages=list(self.messages),
                tools=self.tools,
                model=self.model,
                options=options,
            ):
                if self._abort:
                    break

                # Update internal state
                if isinstance(event, MessageEndEvent):
                    self.messages.append(event.message)
                elif isinstance(event, TurnEndEvent):
                    if (
                        isinstance(event.message, AssistantMessage)
                        and event.message.error_message
                    ):
                        self.error = event.message.error_message
                elif isinstance(event, AgentEndEvent):
                    self.is_streaming = False

                self._emit(event)

        except Exception as e:
            error_msg = AssistantMessage(
                api=self.model.api if self.model else "",
                provider=self.model.provider if self.model else "",
                model=self.model.id if self.model else "",
                usage=Usage(),
                stop_reason="error",
                error_message=str(e),
                timestamp=int(time.time() * 1000),
            )
            self.messages.append(error_msg)
            self.error = str(e)
            self._emit(AgentEndEvent(messages=[error_msg]))
        finally:
            self.is_streaming = False
            self._abort = False
