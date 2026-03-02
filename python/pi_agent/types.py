"""Types for the agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Literal, Protocol, Union

from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    ImageContent,
    Message,
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
