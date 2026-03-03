"""Agent class — wraps the agent loop with state management and subscriptions."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any, Literal

from pi_ai.api_registry import StreamFn
from pi_ai.types import (
    AssistantMessage,
    ImageContent,
    Message,
    Model,
    StreamOptions,
    TextContent,
    ToolResultMessage,
    Usage,
    UserMessage,
)

from pi_agent.agent_loop import agent_loop, agent_loop_continue
from pi_agent.types import (
    AgentContext,
    AgentEndEvent,
    AgentEvent,
    AgentLoopConfig,
    AgentTool,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    default_convert_to_llm,
)

SteeringMode = Literal["all", "one-at-a-time"]


class Agent:
    """Agent with state management, event subscription, steering/follow-up queues."""

    def __init__(
        self,
        model: Model | None = None,
        system_prompt: str = "",
        tools: list[AgentTool] | None = None,
        api_key: str | None = None,
        reasoning: str | None = None,
        convert_to_llm: Callable | None = None,
        transform_context: Callable | None = None,
        steering_mode: SteeringMode = "one-at-a-time",
        follow_up_mode: SteeringMode = "one-at-a-time",
        stream_fn: StreamFn | None = None,
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.tools: list[AgentTool] = tools or []
        self.messages: list[Message] = []
        self.is_streaming = False
        self.error: str | None = None
        self._listeners: list[Callable[[AgentEvent], None]] = []
        self._abort_signal: asyncio.Event | None = None
        self._idle_event: asyncio.Event | None = None
        self._api_key = api_key
        self._reasoning = reasoning
        self._convert_to_llm = convert_to_llm
        self._transform_context = transform_context
        self._steering_mode: SteeringMode = steering_mode
        self._follow_up_mode: SteeringMode = follow_up_mode
        self._stream_fn = stream_fn
        self._steering_queue: list[Message] = []
        self._follow_up_queue: list[Message] = []

    # --- Event subscription ---

    def subscribe(self, fn: Callable[[AgentEvent], None]) -> Callable[[], None]:
        """Subscribe to agent events. Returns unsubscribe function."""
        self._listeners.append(fn)
        return lambda: self._listeners.remove(fn) if fn in self._listeners else None

    def _emit(self, event: AgentEvent) -> None:
        for listener in self._listeners:
            listener(event)

    # --- State mutators ---

    def set_system_prompt(self, v: str) -> None:
        self.system_prompt = v

    def set_model(self, m: Model) -> None:
        self.model = m

    def set_tools(self, t: list[AgentTool]) -> None:
        self.tools = t

    def set_thinking_level(self, level: str | None) -> None:
        self._reasoning = level

    def replace_messages(self, ms: list[Message]) -> None:
        self.messages = list(ms)

    def append_message(self, m: Message) -> None:
        self.messages.append(m)

    def clear_messages(self) -> None:
        self.messages = []

    # --- Steering / follow-up queues ---

    def steer(self, m: Message) -> None:
        """Queue a steering message to interrupt the agent mid-run."""
        self._steering_queue.append(m)

    def follow_up(self, m: Message) -> None:
        """Queue a follow-up message for after the agent finishes its current work."""
        self._follow_up_queue.append(m)

    def clear_steering_queue(self) -> None:
        self._steering_queue.clear()

    def clear_follow_up_queue(self) -> None:
        self._follow_up_queue.clear()

    def clear_all_queues(self) -> None:
        self._steering_queue.clear()
        self._follow_up_queue.clear()

    def has_queued_messages(self) -> bool:
        return bool(self._steering_queue) or bool(self._follow_up_queue)

    def set_steering_mode(self, mode: SteeringMode) -> None:
        self._steering_mode = mode

    def get_steering_mode(self) -> SteeringMode:
        return self._steering_mode

    def set_follow_up_mode(self, mode: SteeringMode) -> None:
        self._follow_up_mode = mode

    def get_follow_up_mode(self) -> SteeringMode:
        return self._follow_up_mode

    def _dequeue_steering(self) -> list[Message]:
        if not self._steering_queue:
            return []
        if self._steering_mode == "one-at-a-time":
            return [self._steering_queue.pop(0)]
        msgs = list(self._steering_queue)
        self._steering_queue.clear()
        return msgs

    def _dequeue_follow_up(self) -> list[Message]:
        if not self._follow_up_queue:
            return []
        if self._follow_up_mode == "one-at-a-time":
            return [self._follow_up_queue.pop(0)]
        msgs = list(self._follow_up_queue)
        self._follow_up_queue.clear()
        return msgs

    # --- Execution control ---

    async def prompt(self, text: str, images: list[ImageContent] | None = None) -> None:
        """Send a prompt to the agent and wait for completion."""
        if self.is_streaming:
            raise RuntimeError(
                "Agent is already processing a prompt. "
                "Use steer() or follow_up() to queue messages, or wait for completion."
            )
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

    async def continue_(self) -> None:
        """Continue from current context (for retries or resuming queued messages)."""
        if self.is_streaming:
            raise RuntimeError("Agent is already processing. Wait for completion before continuing.")
        if not self.model:
            raise RuntimeError("No model configured.")
        if not self.messages:
            raise RuntimeError("No messages to continue from.")

        last = self.messages[-1]
        if isinstance(last, AssistantMessage):
            # Try to drain queued steering first, then follow-up
            queued = self._dequeue_steering()
            if not queued:
                queued = self._dequeue_follow_up()
            if queued:
                await self._run_loop(queued)
                return
            raise RuntimeError("Cannot continue from message role: assistant")

        # Last message is user or toolResult — use agent_loop_continue
        await self._run_loop(None)

    def abort(self) -> None:
        """Abort the current operation."""
        if self._abort_signal:
            self._abort_signal.set()

    async def wait_for_idle(self) -> None:
        """Wait for the agent to finish processing."""
        if self._idle_event:
            await self._idle_event.wait()

    def reset(self) -> None:
        """Reset agent state."""
        self.messages = []
        self.is_streaming = False
        self.error = None
        self._abort_signal = None
        self._steering_queue.clear()
        self._follow_up_queue.clear()

    # --- Internal loop ---

    async def _run_loop(self, prompt_messages: list[Message] | None) -> None:
        """Run the agent loop. If prompt_messages is None, uses agent_loop_continue."""
        self.is_streaming = True
        self.error = None
        self._abort_signal = asyncio.Event()
        self._idle_event = asyncio.Event()

        config = AgentLoopConfig(
            model=self.model,
            convert_to_llm=self._convert_to_llm or default_convert_to_llm,
            transform_context=self._transform_context,
            options=StreamOptions(
                api_key=self._api_key,
                reasoning=self._reasoning,
            ),
            abort_signal=self._abort_signal,
            stream_fn=self._stream_fn,
            get_steering_messages=self._get_steering_messages,
            get_follow_up_messages=self._get_follow_up_messages,
        )
        context = AgentContext(
            system_prompt=self.system_prompt,
            messages=list(self.messages),
            tools=self.tools,
        )

        try:
            if prompt_messages is not None:
                stream = agent_loop(
                    prompts=prompt_messages,
                    context=context,
                    config=config,
                )
            else:
                stream = agent_loop_continue(
                    context=context,
                    config=config,
                )

            async for event in stream:
                if self._abort_signal.is_set():
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
            self._abort_signal = None
            if self._idle_event:
                self._idle_event.set()

    async def _get_steering_messages(self) -> list[Message]:
        return self._dequeue_steering()

    async def _get_follow_up_messages(self) -> list[Message]:
        return self._dequeue_follow_up()
