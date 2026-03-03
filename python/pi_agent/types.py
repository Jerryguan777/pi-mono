"""Types for the agent runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Union

from pi_ai.api_registry import StreamFn
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    ImageContent,
    Message,
    Model,
    StreamOptions,
    TextContent,
    Tool,
    ToolCall,
    ToolResultMessage,
)


@dataclass
class AgentToolResult:
    """Result from executing a tool."""
    content: list[TextContent | ImageContent] = field(default_factory=list)
    details: Any = None


# Callback for streaming tool execution updates
AgentToolUpdateCallback = Callable[[AgentToolResult], None]


@dataclass
class AgentTool:
    """A tool the agent can use, with execution capability."""
    name: str = ""
    label: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)  # JSON Schema

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        on_update: AgentToolUpdateCallback | None = None,
        abort_signal: asyncio.Event | None = None,
    ) -> AgentToolResult:
        raise NotImplementedError


# Agent events
@dataclass
class AgentStartEvent:
    type: Literal["agent_start"] = "agent_start"


@dataclass
class AgentEndEvent:
    type: Literal["agent_end"] = "agent_end"
    messages: list[Message] = field(default_factory=list)


@dataclass
class TurnStartEvent:
    type: Literal["turn_start"] = "turn_start"


@dataclass
class TurnEndEvent:
    type: Literal["turn_end"] = "turn_end"
    message: Message = field(default_factory=lambda: AssistantMessage())
    tool_results: list[ToolResultMessage] = field(default_factory=list)


@dataclass
class MessageStartEvent:
    type: Literal["message_start"] = "message_start"
    message: Message = field(default_factory=lambda: AssistantMessage())


@dataclass
class MessageUpdateEvent:
    type: Literal["message_update"] = "message_update"
    message: Message = field(default_factory=lambda: AssistantMessage())
    assistant_message_event: AssistantMessageEvent | None = None


@dataclass
class MessageEndEvent:
    type: Literal["message_end"] = "message_end"
    message: Message = field(default_factory=lambda: AssistantMessage())


@dataclass
class ToolExecutionStartEvent:
    type: Literal["tool_execution_start"] = "tool_execution_start"
    tool_call_id: str = ""
    tool_name: str = ""
    args: Any = None


@dataclass
class ToolExecutionUpdateEvent:
    type: Literal["tool_execution_update"] = "tool_execution_update"
    tool_call_id: str = ""
    tool_name: str = ""
    args: Any = None
    partial_result: Any = None


@dataclass
class ToolExecutionEndEvent:
    type: Literal["tool_execution_end"] = "tool_execution_end"
    tool_call_id: str = ""
    tool_name: str = ""
    result: Any = None
    is_error: bool = False


AgentEvent = Union[
    AgentStartEvent,
    AgentEndEvent,
    TurnStartEvent,
    TurnEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    MessageEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolExecutionEndEvent,
]


# --- Agent context & config ---


def default_convert_to_llm(messages: list[Message]) -> list[Message]:
    """Default: keep only LLM-compatible messages (user, assistant, toolResult)."""
    return [m for m in messages if m.role in ("user", "assistant", "toolResult")]


@dataclass
class AgentContext:
    """Agent conversation context."""
    system_prompt: str = ""
    messages: list[Message] = field(default_factory=list)
    tools: list[AgentTool] | None = None


@dataclass
class AgentLoopConfig:
    """Configuration for the agent loop."""
    model: Model
    convert_to_llm: Callable[[list[Message]], list[Message]] = field(
        default_factory=lambda: default_convert_to_llm,
    )
    transform_context: Callable[[list[Message]], Awaitable[list[Message]]] | None = None
    get_steering_messages: Callable[[], Awaitable[list[Message]]] | None = None
    get_follow_up_messages: Callable[[], Awaitable[list[Message]]] | None = None
    options: StreamOptions | None = None
    abort_signal: asyncio.Event | None = None
    stream_fn: StreamFn | None = None
