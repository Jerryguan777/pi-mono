"""Tests for the pi_agent agent_loop function.

Ported from python-superpowers. The rewrite's agent_loop uses:
- AgentContext + AgentLoopConfig instead of keyword args
- AsyncGenerator yielding AgentEvents instead of returning list[Message]
- stream_fn callback instead of provider registry
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import pytest
from pi_agent.agent_loop import agent_loop
from pi_agent.types import (
    AgentContext,
    AgentEndEvent,
    AgentEvent,
    AgentLoopConfig,
    AgentStartEvent,
    AgentTool,
    AgentToolResult,
    AgentToolUpdateCallback,
    MessageEndEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    DoneEvent,
    Model,
    SimpleStreamOptions,
    StartEvent,
    TextContent,
    TextDeltaEvent,
    TextStartEvent,
    ToolCall,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultMessage,
    UserMessage,
)

# ── Helpers ───────────────────────────────────────────────────────────

TEST_API = "test-mock-api"

TEST_MODEL = Model(
    id="test-model",
    name="Test Model",
    api=TEST_API,
    provider="test-provider",
)


def _text_events(text: str) -> list[AssistantMessageEvent]:
    """Events for a simple text-only response."""
    msg = AssistantMessage(
        api=TEST_API, provider="test-provider", model="test-model",
        content=[TextContent(text=text)], stop_reason="stop",
    )
    partial = AssistantMessage(api=TEST_API, provider="test-provider", model="test-model")
    return [
        StartEvent(partial=partial),
        TextStartEvent(partial=partial),
        TextDeltaEvent(delta=text, partial=partial),
        DoneEvent(reason="stop", message=msg),
    ]


def _tool_call_events(tool_id: str, tool_name: str, arguments: dict[str, Any]) -> list[AssistantMessageEvent]:
    """Events for a tool_use response."""
    msg = AssistantMessage(
        api=TEST_API, provider="test-provider", model="test-model",
        content=[ToolCall(id=tool_id, name=tool_name, arguments=arguments)],
        stop_reason="toolUse",
    )
    partial = AssistantMessage(api=TEST_API, provider="test-provider", model="test-model")
    return [
        StartEvent(partial=partial),
        ToolCallStartEvent(partial=partial),
        ToolCallDeltaEvent(delta=json.dumps(arguments), partial=partial),
        ToolCallEndEvent(tool_call=ToolCall(id=tool_id, name=tool_name, arguments=arguments), partial=partial),
        DoneEvent(reason="toolUse", message=msg),
    ]


def _make_stream_fn(responses: list[list[AssistantMessageEvent]]):
    """Create a stream function that yields predetermined responses, one per call."""
    call_count = 0

    async def stream_fn(
        model: Model, context: Context, options: SimpleStreamOptions | None = None
    ):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        for event in responses[idx]:
            yield event

    return stream_fn


async def _collect_events(gen) -> list[AgentEvent]:
    """Collect all events from an async generator."""
    events = []
    async for event in gen:
        events.append(event)
    return events


def _make_context(system_prompt: str = "You are helpful.") -> AgentContext:
    return AgentContext(system_prompt=system_prompt, messages=[], tools=[])


def _make_config(**kwargs) -> AgentLoopConfig:
    defaults = {"model": TEST_MODEL, "max_turns": 50}
    defaults.update(kwargs)
    return AgentLoopConfig(**defaults)


# ── Tool helpers ─────────────────────────────────────────────────────


class EchoTool(AgentTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def label(self) -> str:
        return "Echo"

    @property
    def description(self) -> str:
        return "Echoes input back"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"input": {"type": "string"}}}

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        return AgentToolResult(
            content=[TextContent(text=f"echoed: {params.get('input', '')}")],
            details={},
        )


class NoopTool(AgentTool):
    @property
    def name(self) -> str:
        return "noop"

    @property
    def label(self) -> str:
        return "Noop"

    @property
    def description(self) -> str:
        return "Does nothing"

    @property
    def parameters(self) -> dict[str, Any]:
        return {}

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        return AgentToolResult(content=[TextContent(text="ok")], details={})


class FailingTool(AgentTool):
    @property
    def name(self) -> str:
        return "failing"

    @property
    def label(self) -> str:
        return "Failing"

    @property
    def description(self) -> str:
        return "Always fails"

    @property
    def parameters(self) -> dict[str, Any]:
        return {}

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        raise RuntimeError("Something broke!")


# ── Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_simple_text_response() -> None:
    """Provider returns text with no tool calls -- loop should complete in one turn."""
    stream_fn = _make_stream_fn([_text_events("Hello, world!")])
    user_msg = UserMessage(content="Hi", timestamp=time.time() * 1000)
    context = _make_context()

    events = await _collect_events(
        agent_loop([user_msg], context, _make_config(), stream_fn=stream_fn)
    )

    event_types = [type(e).__name__ for e in events]
    assert "AgentStartEvent" in event_types
    assert "AgentEndEvent" in event_types

    # Find the AgentEndEvent and check its messages
    end_events = [e for e in events if isinstance(e, AgentEndEvent)]
    assert len(end_events) == 1

    # TS design: agent_loop does NOT mutate the original context.
    # New messages are returned via AgentEndEvent.messages.
    assert len(end_events[0].messages) >= 1  # at least the assistant response


@pytest.mark.asyncio
async def test_tool_call_and_continue() -> None:
    """Provider returns tool_use on first call, text on second."""
    stream_fn = _make_stream_fn([
        _tool_call_events("call-1", "echo", {"input": "ping"}),
        _text_events("Done!"),
    ])

    context = _make_context()
    context.tools = [EchoTool()]
    user_msg = UserMessage(content="Test tools", timestamp=time.time() * 1000)

    events = await _collect_events(
        agent_loop([user_msg], context, _make_config(), stream_fn=stream_fn)
    )

    event_types = [type(e).__name__ for e in events]
    assert "ToolExecutionStartEvent" in event_types
    assert "ToolExecutionEndEvent" in event_types

    # Verify tool execution result
    tool_end_events = [e for e in events if isinstance(e, ToolExecutionEndEvent)]
    assert len(tool_end_events) >= 1
    assert tool_end_events[0].tool_name == "echo"
    assert tool_end_events[0].is_error is False


@pytest.mark.asyncio
async def test_max_turns_guard() -> None:
    """Provider always returns tool_use -- verify loop stops at max_turns."""
    stream_fn = _make_stream_fn([
        _tool_call_events("call-1", "noop", {}),
    ])

    context = _make_context()
    context.tools = [NoopTool()]
    user_msg = UserMessage(content="Loop forever", timestamp=time.time() * 1000)

    events = await _collect_events(
        agent_loop([user_msg], context, _make_config(max_turns=3), stream_fn=stream_fn)
    )

    # Should have ended with AgentEndEvent
    end_events = [e for e in events if isinstance(e, AgentEndEvent)]
    assert len(end_events) == 1

    # Should not have more than max_turns turns
    turn_starts = [e for e in events if isinstance(e, TurnStartEvent)]
    assert len(turn_starts) <= 4  # 1 initial + up to 3 turns


@pytest.mark.asyncio
async def test_unknown_tool_name() -> None:
    """Provider calls a tool that doesn't exist -- should produce error tool result."""
    stream_fn = _make_stream_fn([
        _tool_call_events("call-1", "nonexistent_tool", {"x": 1}),
        _text_events("Acknowledged."),
    ])

    context = _make_context()
    context.tools = []  # No tools registered
    user_msg = UserMessage(content="Call unknown tool", timestamp=time.time() * 1000)

    events = await _collect_events(
        agent_loop([user_msg], context, _make_config(), stream_fn=stream_fn)
    )

    tool_end_events = [e for e in events if isinstance(e, ToolExecutionEndEvent)]
    assert len(tool_end_events) >= 1
    assert tool_end_events[0].is_error is True

    # Check that the error mentions the tool name
    error_text = tool_end_events[0].result.content[0].text
    assert "nonexistent_tool" in error_text


@pytest.mark.asyncio
async def test_tool_execution_error() -> None:
    """tool.execute raises an exception -- should produce error tool result."""
    stream_fn = _make_stream_fn([
        _tool_call_events("call-1", "failing", {}),
        _text_events("I see the error."),
    ])

    context = _make_context()
    context.tools = [FailingTool()]
    user_msg = UserMessage(content="Call failing tool", timestamp=time.time() * 1000)

    events = await _collect_events(
        agent_loop([user_msg], context, _make_config(), stream_fn=stream_fn)
    )

    tool_end_events = [e for e in events if isinstance(e, ToolExecutionEndEvent)]
    assert len(tool_end_events) >= 1
    assert tool_end_events[0].is_error is True
    assert "Something broke!" in tool_end_events[0].result.content[0].text


@pytest.mark.asyncio
async def test_event_lifecycle() -> None:
    """Verify event lifecycle: AgentStart, TurnStart, ..., TurnEnd, AgentEnd."""
    stream_fn = _make_stream_fn([_text_events("Hi!")])
    user_msg = UserMessage(content="Hello", timestamp=time.time() * 1000)
    context = _make_context()

    events = await _collect_events(
        agent_loop([user_msg], context, _make_config(), stream_fn=stream_fn)
    )

    event_types = [type(e).__name__ for e in events]

    # Basic lifecycle ordering
    assert event_types[0] == "AgentStartEvent"
    assert event_types[1] == "TurnStartEvent"
    assert event_types[-1] == "AgentEndEvent"

    # Should have at least one TurnEndEvent
    assert "TurnEndEvent" in event_types
