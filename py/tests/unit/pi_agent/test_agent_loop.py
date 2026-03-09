"""Tests for pi_agent.agent_loop — using mock stream functions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, ClassVar

import pytest

from pi_agent.agent_loop import _call_async, _call_get_messages, _skip_tool_call, agent_loop, agent_loop_continue
from pi_agent.types import (
    AgentContext,
    AgentEndEvent,
    AgentLoopConfig,
    AgentStartEvent,
    AgentTool,
    AgentToolResult,
    MessageUpdateEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from pi_ai.types import (
    AssistantMessage,
    Context,
    DoneEvent,
    Model,
    SimpleStreamOptions,
    StartEvent,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


def make_simple_response(text: str = "Hello!", model_id: str = "test-model") -> AssistantMessage:
    """Build a completed AssistantMessage with text content."""
    return AssistantMessage(
        api="test-api",
        provider="test",
        model=model_id,
        stop_reason="stop",
        content=[TextContent(text=text)],
    )


def make_stream_fn_simple(response: AssistantMessage) -> Any:
    """Return a stream function that yields a simple done response."""

    async def stream_fn(
        model: Model,
        context: Context,
        options: SimpleStreamOptions | None,
    ) -> AsyncIterator[Any]:
        partial = AssistantMessage(api=response.api, provider=response.provider, model=response.model)
        yield StartEvent(partial=partial)
        yield TextStartEvent(content_index=0, partial=partial)
        partial.content = [TextContent(text="")]
        text = response.content[0].text if response.content else ""  # type: ignore[union-attr]
        yield TextDeltaEvent(content_index=0, delta=text, partial=partial)
        if partial.content:
            block = partial.content[0]
            if isinstance(block, TextContent):
                block.text = text
        yield TextEndEvent(content_index=0, content=text, partial=partial)
        yield DoneEvent(reason="stop", message=response)

    return stream_fn


def make_stream_fn_with_tool_call(tool_name: str, tool_id: str = "tc1") -> Any:
    """Return a stream function that requests a tool call."""

    async def stream_fn(
        model: Model,
        context: Context,
        options: SimpleStreamOptions | None,
    ) -> AsyncIterator[Any]:
        response = AssistantMessage(
            api="test-api",
            provider="test",
            model="test-model",
            stop_reason="toolUse",
            content=[ToolCall(id=tool_id, name=tool_name, arguments={"input": "test"})],
        )
        yield DoneEvent(reason="toolUse", message=response)

    return stream_fn


def make_stream_fn_error(error_msg: str = "LLM error") -> Any:
    """Return a stream function that yields an error response."""

    async def stream_fn(
        model: Model,
        context: Context,
        options: SimpleStreamOptions | None,
    ) -> AsyncIterator[Any]:
        error_response = AssistantMessage(
            api="test-api",
            provider="test",
            model="test-model",
            stop_reason="error",
            error_message=error_msg,
        )
        yield DoneEvent(reason="error", message=error_response)

    return stream_fn


def make_config(model_id: str = "test-model") -> AgentLoopConfig:
    """Create a minimal AgentLoopConfig for tests."""
    return AgentLoopConfig(
        model=Model(id=model_id, api="test-api", provider="test"),
    )


def make_context(system: str = "You are helpful.") -> AgentContext:
    return AgentContext(system_prompt=system, messages=[])


class EchoTool(AgentTool):
    """Simple tool that echoes its input."""

    name = "echo"
    label = "Echo"
    description = "Echoes the input"
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"input": {"type": "string"}},
        "required": ["input"],
    }

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: Any = None,
    ) -> AgentToolResult:
        return AgentToolResult(
            content=[TextContent(text=f"Echo: {params.get('input', '')}")],
            details=None,
        )


class FailTool(AgentTool):
    """Tool that always raises an exception."""

    name = "fail"
    label = "Fail"
    description = "Always fails"
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: Any = None,
    ) -> AgentToolResult:
        raise RuntimeError("Tool execution failed")


class TestCallAsync:
    @pytest.mark.asyncio
    async def test_sync_fn(self) -> None:
        result = await _call_async(lambda x: x * 2, 5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_async_fn(self) -> None:
        async def afn(x: int) -> int:
            return x * 3

        result = await _call_async(afn, 4)
        assert result == 12


class TestCallGetMessages:
    @pytest.mark.asyncio
    async def test_none_fn(self) -> None:
        result = await _call_get_messages(None)
        assert result == []

    @pytest.mark.asyncio
    async def test_sync_fn(self) -> None:
        msg = UserMessage(content="hello")
        result = await _call_get_messages(lambda: [msg])
        assert result == [msg]

    @pytest.mark.asyncio
    async def test_async_fn(self) -> None:
        msg = UserMessage(content="async hello")

        async def get_msgs() -> list[UserMessage]:
            return [msg]

        result = await _call_get_messages(get_msgs)
        assert result == [msg]


class TestSkipToolCall:
    def test_skip_creates_error_result(self) -> None:
        tool_call = ToolCall(id="tc1", name="bash", arguments={"cmd": "ls"})
        result, events = _skip_tool_call(tool_call)
        assert result.is_error is True
        assert result.tool_call_id == "tc1"
        # Should emit start, end, message start, message end
        assert len(events) == 4
        assert isinstance(events[0], ToolExecutionStartEvent)
        assert isinstance(events[1], ToolExecutionEndEvent)
        assert events[1].is_error is True


class TestAgentLoop:
    @pytest.mark.asyncio
    async def test_simple_prompt(self) -> None:
        """Agent loop should yield proper events for a simple prompt/response."""
        user_msg = UserMessage(content="Hello")
        ctx = make_context()
        config = make_config()
        response = make_simple_response("Hi there!")
        stream_fn = make_stream_fn_simple(response)

        events = []
        async for event in agent_loop([user_msg], ctx, config, stream_fn=stream_fn):
            events.append(event)

        event_types = [type(e).__name__ for e in events]
        assert "AgentStartEvent" in event_types
        assert "TurnStartEvent" in event_types
        assert "MessageStartEvent" in event_types
        assert "MessageEndEvent" in event_types
        assert "TurnEndEvent" in event_types
        assert "AgentEndEvent" in event_types

    @pytest.mark.asyncio
    async def test_agent_end_contains_messages(self) -> None:
        """AgentEndEvent should contain all new messages."""
        user_msg = UserMessage(content="Hello")
        ctx = make_context()
        config = make_config()
        response = make_simple_response("Hi!")
        stream_fn = make_stream_fn_simple(response)

        end_event = None
        async for event in agent_loop([user_msg], ctx, config, stream_fn=stream_fn):
            if isinstance(event, AgentEndEvent):
                end_event = event

        assert end_event is not None
        # Should contain user message + assistant message
        assert len(end_event.messages) >= 2

    @pytest.mark.asyncio
    async def test_error_response_ends_loop(self) -> None:
        """Error response should terminate the loop gracefully."""
        user_msg = UserMessage(content="Hello")
        ctx = make_context()
        config = make_config()
        stream_fn = make_stream_fn_error("Something went wrong")

        events = []
        async for event in agent_loop([user_msg], ctx, config, stream_fn=stream_fn):
            events.append(event)

        assert any(isinstance(e, AgentEndEvent) for e in events)

    @pytest.mark.asyncio
    async def test_tool_call_execution(self) -> None:
        """Tool calls should trigger tool execution events."""
        user_msg = UserMessage(content="Echo test")
        echo_tool = EchoTool()
        ctx = AgentContext(system_prompt="sys", messages=[], tools=[echo_tool])
        config = make_config()

        call_count = 0

        async def stream_fn(
            model: Model,
            context: Context,
            options: SimpleStreamOptions | None,
        ) -> AsyncIterator[Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: return tool call
                response = AssistantMessage(
                    api="test-api",
                    provider="test",
                    model="test-model",
                    stop_reason="toolUse",
                    content=[ToolCall(id="tc1", name="echo", arguments={"input": "hello"})],
                )
                yield DoneEvent(reason="toolUse", message=response)
            else:
                # Second call: return final response
                response = AssistantMessage(
                    api="test-api",
                    provider="test",
                    model="test-model",
                    stop_reason="stop",
                    content=[TextContent(text="Done!")],
                )
                yield DoneEvent(reason="stop", message=response)

        events = []
        async for event in agent_loop([user_msg], ctx, config, stream_fn=stream_fn):
            events.append(event)

        tool_start_events = [e for e in events if isinstance(e, ToolExecutionStartEvent)]
        tool_end_events = [e for e in events if isinstance(e, ToolExecutionEndEvent)]
        assert len(tool_start_events) == 1
        assert len(tool_end_events) == 1
        assert tool_end_events[0].is_error is False

    @pytest.mark.asyncio
    async def test_unknown_tool_call_is_error(self) -> None:
        """Tool call for unknown tool should result in error."""
        user_msg = UserMessage(content="Run unknown")
        ctx = AgentContext(system_prompt="sys", messages=[], tools=[])
        config = make_config()
        call_count = 0

        async def stream_fn(
            model: Model,
            context: Context,
            options: SimpleStreamOptions | None,
        ) -> AsyncIterator[Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First: return unknown tool call
                response = AssistantMessage(
                    api="test-api",
                    provider="test",
                    model="test-model",
                    stop_reason="toolUse",
                    content=[ToolCall(id="tc1", name="unknown_tool", arguments={})],
                )
                yield DoneEvent(reason="toolUse", message=response)
            else:
                # Second: final response after error tool result
                response = AssistantMessage(
                    api="test-api",
                    provider="test",
                    model="test-model",
                    stop_reason="stop",
                    content=[TextContent(text="I couldn't run that tool.")],
                )
                yield DoneEvent(reason="stop", message=response)

        events = []
        async for event in agent_loop([user_msg], ctx, config, stream_fn=stream_fn):
            events.append(event)

        tool_end_events = [e for e in events if isinstance(e, ToolExecutionEndEvent)]
        # Unknown tool should produce an error
        assert any(e.is_error for e in tool_end_events)

    @pytest.mark.asyncio
    async def test_failing_tool_produces_error_result(self) -> None:
        """Exception in tool.execute() should not crash the loop."""
        user_msg = UserMessage(content="Fail please")
        fail_tool = FailTool()
        ctx = AgentContext(system_prompt="sys", messages=[], tools=[fail_tool])
        config = make_config()

        call_count = 0

        async def stream_fn(
            model: Model,
            context: Context,
            options: SimpleStreamOptions | None,
        ) -> AsyncIterator[Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                response = AssistantMessage(
                    api="test-api",
                    provider="test",
                    model="test-model",
                    stop_reason="toolUse",
                    content=[ToolCall(id="tc1", name="fail", arguments={})],
                )
                yield DoneEvent(reason="toolUse", message=response)
            else:
                response = AssistantMessage(
                    api="test-api",
                    provider="test",
                    model="test-model",
                    stop_reason="stop",
                    content=[TextContent(text="Recovered")],
                )
                yield DoneEvent(reason="stop", message=response)

        events = []
        async for event in agent_loop([user_msg], ctx, config, stream_fn=stream_fn):
            events.append(event)

        tool_end_events = [e for e in events if isinstance(e, ToolExecutionEndEvent)]
        assert len(tool_end_events) == 1
        assert tool_end_events[0].is_error is True

    @pytest.mark.asyncio
    async def test_streaming_events_order(self) -> None:
        """Events should be emitted in correct order."""
        user_msg = UserMessage(content="Stream me")
        ctx = make_context()
        config = make_config()
        response = make_simple_response("Streamed response")
        stream_fn = make_stream_fn_simple(response)

        events = []
        async for event in agent_loop([user_msg], ctx, config, stream_fn=stream_fn):
            events.append(event)

        # AgentStart must come first
        assert isinstance(events[0], AgentStartEvent)
        # AgentEnd must come last
        assert isinstance(events[-1], AgentEndEvent)
        # TurnStart before TurnEnd
        turn_start_idx = next(i for i, e in enumerate(events) if isinstance(e, TurnStartEvent))
        turn_end_idx = next(i for i, e in enumerate(events) if isinstance(e, TurnEndEvent))
        assert turn_start_idx < turn_end_idx

    @pytest.mark.asyncio
    async def test_message_update_events(self) -> None:
        """Streaming events should generate MessageUpdateEvent instances."""
        user_msg = UserMessage(content="Stream delta")
        ctx = make_context()
        config = make_config()
        response = make_simple_response("Delta response")
        stream_fn = make_stream_fn_simple(response)

        events = []
        async for event in agent_loop([user_msg], ctx, config, stream_fn=stream_fn):
            events.append(event)

        update_events = [e for e in events if isinstance(e, MessageUpdateEvent)]
        # The simple stream fn emits text_delta, so should have at least one update
        assert len(update_events) >= 1


class TestAgentLoopContinue:
    @pytest.mark.asyncio
    async def test_continue_from_user_message(self) -> None:
        """agent_loop_continue from a user message should work."""
        user_msg = UserMessage(content="Continue this")
        ctx = AgentContext(system_prompt="sys", messages=[user_msg])
        config = make_config()
        response = make_simple_response("Continued!")
        stream_fn = make_stream_fn_simple(response)

        events = []
        async for event in agent_loop_continue(ctx, config, stream_fn=stream_fn):
            events.append(event)

        assert any(isinstance(e, AgentStartEvent) for e in events)
        assert any(isinstance(e, AgentEndEvent) for e in events)

    @pytest.mark.asyncio
    async def test_continue_from_empty_messages_raises(self) -> None:
        """agent_loop_continue with no messages should raise ValueError."""
        ctx = AgentContext(system_prompt="sys", messages=[])
        config = make_config()

        with pytest.raises(ValueError, match="Cannot continue"):
            async for _ in agent_loop_continue(ctx, config):
                pass

    @pytest.mark.asyncio
    async def test_continue_from_assistant_message_raises(self) -> None:
        """agent_loop_continue from an assistant message should raise ValueError."""
        assistant_msg = AssistantMessage(model="test", content=[TextContent(text="I responded")])
        ctx = AgentContext(system_prompt="sys", messages=[assistant_msg])
        config = make_config()

        with pytest.raises(ValueError, match="assistant"):
            async for _ in agent_loop_continue(ctx, config):
                pass

    @pytest.mark.asyncio
    async def test_continue_from_tool_result(self) -> None:
        """agent_loop_continue from a ToolResultMessage should work."""
        tool_result = ToolResultMessage(
            tool_call_id="tc1",
            tool_name="bash",
            content=[TextContent(text="result")],
        )
        ctx = AgentContext(system_prompt="sys", messages=[tool_result])
        config = make_config()
        response = make_simple_response("Processed!")
        stream_fn = make_stream_fn_simple(response)

        events = []
        async for event in agent_loop_continue(ctx, config, stream_fn=stream_fn):
            events.append(event)

        assert any(isinstance(e, AgentEndEvent) for e in events)


class TestSteeringMessages:
    @pytest.mark.asyncio
    async def test_steering_skips_remaining_tools(self) -> None:
        """Steering messages during tool execution should skip remaining tools."""
        user_msg = UserMessage(content="Do multiple things")
        echo_tool = EchoTool()
        ctx = AgentContext(system_prompt="sys", messages=[], tools=[echo_tool])

        steering_calls = 0
        steering_sent = False

        def get_steering() -> list[UserMessage]:
            nonlocal steering_calls, steering_sent
            steering_calls += 1
            if steering_calls == 1:
                # First poll at loop start — no steering
                return []
            if not steering_sent:
                # Inject steering message exactly once after first tool call
                steering_sent = True
                return [UserMessage(content="Stop!")]
            return []

        config = AgentLoopConfig(
            model=Model(id="test", api="test-api", provider="test"),
            get_steering_messages=get_steering,
        )

        call_count = 0

        async def stream_fn(
            model: Model,
            context: Context,
            options: SimpleStreamOptions | None,
        ) -> AsyncIterator[Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Return two tool calls
                response = AssistantMessage(
                    api="test-api",
                    provider="test",
                    model="test-model",
                    stop_reason="toolUse",
                    content=[
                        ToolCall(id="tc1", name="echo", arguments={"input": "first"}),
                        ToolCall(id="tc2", name="echo", arguments={"input": "second"}),
                    ],
                )
                yield DoneEvent(reason="toolUse", message=response)
            else:
                response = AssistantMessage(
                    api="test-api",
                    provider="test",
                    model="test-model",
                    stop_reason="stop",
                    content=[TextContent(text="Done")],
                )
                yield DoneEvent(reason="stop", message=response)

        events = []
        async for event in agent_loop([user_msg], ctx, config, stream_fn=stream_fn):
            events.append(event)

        # Both tool calls should appear (second skipped)
        tool_end_events = [e for e in events if isinstance(e, ToolExecutionEndEvent)]
        assert len(tool_end_events) == 2
        # Second should be skipped (error)
        assert tool_end_events[1].is_error is True
