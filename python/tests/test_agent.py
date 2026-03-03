"""Tests for the agent loop — mock LLM tests."""

import asyncio

import pytest

from pi_ai.types import (
    AssistantMessage,
    Context,
    DoneEvent,
    Model,
    ModelCost,
    StartEvent,
    StreamOptions,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ToolCall,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultMessage,
    Usage,
    UserMessage,
)
from pi_ai.api_registry import register_provider
from pi_agent.agent_loop import agent_loop, agent_loop_continue
from pi_agent.types import (
    AgentContext,
    AgentEndEvent,
    AgentLoopConfig,
    AgentStartEvent,
    AgentTool,
    AgentToolResult,
    MessageEndEvent,
    MessageStartEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    TurnStartEvent,
    default_convert_to_llm,
)


MOCK_MODEL = Model(
    id="mock-model",
    name="Mock",
    api="mock-api",
    provider="mock",
    base_url="",
    reasoning=False,
    input=["text"],
    cost=ModelCost(),
    context_window=128000,
    max_tokens=4096,
)


class MockTool(AgentTool):
    """A mock tool for testing."""
    def __init__(self, name: str = "test_tool", response: str = "tool result"):
        self.name = name
        self.label = name
        self.description = f"Mock {name}"
        self.parameters = {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        }
        self._response = response

    async def execute(self, tool_call_id, params, on_update=None):
        return AgentToolResult(
            content=[TextContent(text=self._response)],
            details={},
        )


async def mock_text_stream(model, context, options=None):
    """Mock stream that returns a simple text response."""
    output = AssistantMessage(
        api="mock-api", provider="mock", model="mock-model",
        content=[TextContent(text="Hello from mock!")],
        usage=Usage(), stop_reason="stop",
    )
    yield StartEvent(partial=output)
    yield TextStartEvent(content_index=0, partial=output)
    yield TextDeltaEvent(content_index=0, delta="Hello from mock!", partial=output)
    yield TextEndEvent(content_index=0, content="Hello from mock!", partial=output)
    yield DoneEvent(reason="stop", message=output)


async def mock_tool_call_stream(model, context, options=None):
    """Mock stream that returns a tool call, then text on second call."""
    # Check if this is a follow-up (has tool results in context)
    has_tool_result = any(m.role == "toolResult" for m in context.messages)

    if has_tool_result:
        # Second call: return text
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[TextContent(text="Done!")],
            usage=Usage(), stop_reason="stop",
        )
        yield StartEvent(partial=output)
        yield DoneEvent(reason="stop", message=output)
    else:
        # First call: return tool call
        tc = ToolCall(id="tc1", name="test_tool", arguments={"input": "hello"})
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[tc],
            usage=Usage(), stop_reason="toolUse",
        )
        yield StartEvent(partial=output)
        yield ToolCallStartEvent(content_index=0, partial=output)
        yield ToolCallEndEvent(content_index=0, tool_call=tc, partial=output)
        yield DoneEvent(reason="toolUse", message=output)


@pytest.mark.asyncio
async def test_agent_loop_text_response():
    """Test agent loop with a simple text response."""
    register_provider("mock-api", mock_text_stream)

    context = AgentContext(system_prompt="You are helpful.", messages=[], tools=[])
    config = AgentLoopConfig(model=MOCK_MODEL)

    events = []
    async for event in agent_loop(
        prompts=[UserMessage(content="hi")],
        context=context,
        config=config,
    ):
        events.append(event)

    types = [type(e).__name__ for e in events]

    assert "AgentStartEvent" in types
    assert "TurnStartEvent" in types
    assert "MessageStartEvent" in types
    assert "MessageEndEvent" in types
    assert "TurnEndEvent" in types
    assert "AgentEndEvent" in types


@pytest.mark.asyncio
async def test_agent_loop_tool_execution():
    """Test agent loop with tool call → tool result → text response."""
    register_provider("mock-api", mock_tool_call_stream)

    tool = MockTool()
    context = AgentContext(system_prompt="You are helpful.", messages=[], tools=[tool])
    config = AgentLoopConfig(model=MOCK_MODEL)

    events = []
    async for event in agent_loop(
        prompts=[UserMessage(content="use the tool")],
        context=context,
        config=config,
    ):
        events.append(event)

    types = [type(e).__name__ for e in events]

    # Should have: agent_start, turn_start (user), messages, turn_end,
    # then turn_start (tool response), messages, turn_end, agent_end
    assert "AgentStartEvent" in types
    assert "ToolExecutionStartEvent" in types
    assert "ToolExecutionEndEvent" in types
    assert "AgentEndEvent" in types

    # Check that tool result was created
    tool_results = [e for e in events if isinstance(e, MessageEndEvent)
                    and isinstance(e.message, ToolResultMessage)]
    assert len(tool_results) == 1
    assert tool_results[0].message.tool_name == "test_tool"


@pytest.mark.asyncio
async def test_agent_loop_tool_not_found():
    """Test agent loop when tool is not found."""
    register_provider("mock-api", mock_tool_call_stream)

    context = AgentContext(system_prompt="You are helpful.", messages=[], tools=[])
    config = AgentLoopConfig(model=MOCK_MODEL)

    events = []
    async for event in agent_loop(
        prompts=[UserMessage(content="use the tool")],
        context=context,
        config=config,
    ):
        events.append(event)

    # Should still complete but with error in tool result
    tool_ends = [e for e in events if isinstance(e, ToolExecutionEndEvent)]
    assert len(tool_ends) == 1
    assert tool_ends[0].is_error is True


@pytest.mark.asyncio
async def test_custom_convert_to_llm():
    """Test that a custom convert_to_llm function is called."""
    register_provider("mock-api", mock_text_stream)

    called_with: list[list] = []

    def custom_convert(messages):
        called_with.append(list(messages))
        return default_convert_to_llm(messages)

    context = AgentContext(system_prompt="You are helpful.", messages=[], tools=[])
    config = AgentLoopConfig(model=MOCK_MODEL, convert_to_llm=custom_convert)

    events = []
    async for event in agent_loop(
        prompts=[UserMessage(content="hi")],
        context=context,
        config=config,
    ):
        events.append(event)

    assert len(called_with) >= 1
    # The convert function should have received messages including the user prompt
    assert any(
        any(m.role == "user" for m in msgs)
        for msgs in called_with
    )
    assert "AgentEndEvent" in [type(e).__name__ for e in events]  # custom_convert


@pytest.mark.asyncio
async def test_transform_context():
    """Test that transform_context modifies messages before LLM call."""
    register_provider("mock-api", mock_text_stream)

    transform_called: list[list] = []

    async def custom_transform(messages):
        transform_called.append(list(messages))
        # Pass through unchanged
        return messages

    context = AgentContext(system_prompt="You are helpful.", messages=[], tools=[])
    config = AgentLoopConfig(model=MOCK_MODEL, transform_context=custom_transform)

    events = []
    async for event in agent_loop(
        prompts=[UserMessage(content="hi")],
        context=context,
        config=config,
    ):
        events.append(event)

    assert len(transform_called) >= 1
    # transform_context should have received messages including the user prompt
    assert any(
        any(m.role == "user" for m in msgs)
        for msgs in transform_called
    )
    assert "AgentEndEvent" in [type(e).__name__ for e in events]  # transform_context


# ---------------------------------------------------------------------------
# Mock streams for steering / follow-up / continue tests
# ---------------------------------------------------------------------------

async def mock_two_tool_calls_stream(model, context, options=None):
    """Return 2 tool calls on first call, text on subsequent calls."""
    has_tool_result = any(m.role == "toolResult" for m in context.messages)
    if has_tool_result:
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[TextContent(text="Processed steering.")],
            usage=Usage(), stop_reason="stop",
        )
        yield StartEvent(partial=output)
        yield DoneEvent(reason="stop", message=output)
    else:
        tc1 = ToolCall(id="tc1", name="tool_a", arguments={"input": "a"})
        tc2 = ToolCall(id="tc2", name="tool_b", arguments={"input": "b"})
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[tc1, tc2],
            usage=Usage(), stop_reason="toolUse",
        )
        yield StartEvent(partial=output)
        yield ToolCallStartEvent(content_index=0, partial=output)
        yield ToolCallEndEvent(content_index=0, tool_call=tc1, partial=output)
        yield ToolCallStartEvent(content_index=1, partial=output)
        yield ToolCallEndEvent(content_index=1, tool_call=tc2, partial=output)
        yield DoneEvent(reason="toolUse", message=output)


_follow_up_llm_call_count = 0


async def mock_follow_up_stream(model, context, options=None):
    """Text response that increments a global call counter."""
    global _follow_up_llm_call_count
    _follow_up_llm_call_count += 1
    output = AssistantMessage(
        api="mock-api", provider="mock", model="mock-model",
        content=[TextContent(text=f"Response {_follow_up_llm_call_count}")],
        usage=Usage(), stop_reason="stop",
    )
    yield StartEvent(partial=output)
    yield DoneEvent(reason="stop", message=output)


# ---------------------------------------------------------------------------
# New tests: steering, follow-up, agent_loop_continue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_steering_messages():
    """Steering interrupts tool execution — second tool is skipped."""
    register_provider("mock-api", mock_two_tool_calls_stream)

    tool_a = MockTool(name="tool_a", response="result_a")
    tool_b = MockTool(name="tool_b", response="result_b")

    steering_call_count = 0

    async def steering():
        nonlocal steering_call_count
        steering_call_count += 1
        # Call 1: initial poll before inner loop → nothing yet
        # Call 2: after tool_a executes → inject steering message
        if steering_call_count == 2:
            return [UserMessage(content="Stop! Do something else.")]
        return []

    context = AgentContext(
        system_prompt="test", messages=[], tools=[tool_a, tool_b],
    )
    config = AgentLoopConfig(
        model=MOCK_MODEL, get_steering_messages=steering,
    )

    events = []
    async for event in agent_loop(
        prompts=[UserMessage(content="go")], context=context, config=config,
    ):
        events.append(event)

    # tool_b should have been skipped (is_error=True, "Skipped" text)
    tool_ends = [e for e in events if isinstance(e, ToolExecutionEndEvent)]
    assert len(tool_ends) == 2  # both tools got end events
    tool_b_end = [e for e in tool_ends if e.tool_name == "tool_b"][0]
    assert tool_b_end.is_error is True

    # The steering user message should appear in message events
    user_msg_events = [
        e for e in events
        if isinstance(e, MessageEndEvent) and hasattr(e.message, "role") and e.message.role == "user"
    ]
    assert any("Stop" in getattr(m.message, "content", "") for m in user_msg_events)

    # Agent should end successfully
    assert any(isinstance(e, AgentEndEvent) for e in events)


@pytest.mark.asyncio
async def test_get_follow_up_messages():
    """Follow-up causes a second LLM round after the first completes."""
    global _follow_up_llm_call_count
    _follow_up_llm_call_count = 0

    register_provider("mock-api", mock_follow_up_stream)

    follow_up_call_count = 0

    async def follow_up():
        nonlocal follow_up_call_count
        follow_up_call_count += 1
        if follow_up_call_count == 1:
            return [UserMessage(content="One more thing.")]
        return []

    context = AgentContext(system_prompt="test", messages=[], tools=[])
    config = AgentLoopConfig(
        model=MOCK_MODEL, get_follow_up_messages=follow_up,
    )

    events = []
    async for event in agent_loop(
        prompts=[UserMessage(content="hello")], context=context, config=config,
    ):
        events.append(event)

    # Should have made 2 LLM calls
    assert _follow_up_llm_call_count == 2

    # Both assistant responses should be in the final messages
    end_event = [e for e in events if isinstance(e, AgentEndEvent)][0]
    assistant_msgs = [m for m in end_event.messages if isinstance(m, AssistantMessage)]
    assert len(assistant_msgs) == 2


@pytest.mark.asyncio
async def test_agent_loop_continue():
    """agent_loop_continue resumes from existing context without adding prompts."""
    register_provider("mock-api", mock_text_stream)

    # Pre-populate context with user message + tool result (simulating prior turn)
    existing_messages = [
        UserMessage(content="original prompt"),
        ToolResultMessage(
            tool_call_id="old_tc",
            tool_name="some_tool",
            content=[TextContent(text="old result")],
        ),
    ]

    context = AgentContext(
        system_prompt="test", messages=existing_messages, tools=[],
    )
    config = AgentLoopConfig(model=MOCK_MODEL)

    events = []
    async for event in agent_loop_continue(context=context, config=config):
        events.append(event)

    types = [type(e).__name__ for e in events]
    assert "AgentStartEvent" in types
    assert "AgentEndEvent" in types

    # No prompt MessageStart/End should be emitted (we didn't add prompts)
    end_event = [e for e in events if isinstance(e, AgentEndEvent)][0]
    # new_messages should only contain the assistant response, not the existing context
    assert len(end_event.messages) == 1
    assert isinstance(end_event.messages[0], AssistantMessage)


@pytest.mark.asyncio
async def test_agent_loop_continue_rejects_empty():
    """agent_loop_continue raises on empty context."""
    context = AgentContext(system_prompt="test", messages=[], tools=[])
    config = AgentLoopConfig(model=MOCK_MODEL)

    with pytest.raises(ValueError, match="non-empty"):
        async for _ in agent_loop_continue(context=context, config=config):
            pass


@pytest.mark.asyncio
async def test_agent_loop_continue_rejects_assistant_last():
    """agent_loop_continue raises when last message is assistant."""
    context = AgentContext(
        system_prompt="test",
        messages=[AssistantMessage(content=[TextContent(text="hi")])],
        tools=[],
    )
    config = AgentLoopConfig(model=MOCK_MODEL)

    with pytest.raises(ValueError, match="must not be assistant"):
        async for _ in agent_loop_continue(context=context, config=config):
            pass


# ---------------------------------------------------------------------------
# Abort signal tests
# ---------------------------------------------------------------------------


class AbortingTool(AgentTool):
    """A tool that sets the abort signal during execution."""
    def __init__(self, name: str = "abort_tool", signal: asyncio.Event | None = None):
        self.name = name
        self.label = name
        self.description = f"Tool that aborts: {name}"
        self.parameters = {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        }
        self._signal = signal

    async def execute(self, tool_call_id, params, on_update=None, abort_signal=None):
        # Trigger abort during execution
        if self._signal:
            self._signal.set()
        return AgentToolResult(
            content=[TextContent(text="done before abort")],
            details={},
        )


async def mock_abort_tool_call_stream(model, context, options=None):
    """Mock stream that returns a tool call; if abort is set, returns aborted."""
    if options and options.abort_signal and options.abort_signal.is_set():
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[], usage=Usage(), stop_reason="aborted",
        )
        yield StartEvent(partial=output)
        yield DoneEvent(reason="aborted", message=output)
        return

    has_tool_result = any(m.role == "toolResult" for m in context.messages)
    if has_tool_result:
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[TextContent(text="Final answer")],
            usage=Usage(), stop_reason="stop",
        )
        yield StartEvent(partial=output)
        yield DoneEvent(reason="stop", message=output)
    else:
        tc = ToolCall(id="tc1", name="abort_tool", arguments={"input": "go"})
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[tc],
            usage=Usage(), stop_reason="toolUse",
        )
        yield StartEvent(partial=output)
        yield ToolCallStartEvent(content_index=0, partial=output)
        yield ToolCallEndEvent(content_index=0, tool_call=tc, partial=output)
        yield DoneEvent(reason="toolUse", message=output)


async def mock_two_abort_tool_calls_stream(model, context, options=None):
    """Mock stream returning 2 tool calls; respects abort signal."""
    if options and options.abort_signal and options.abort_signal.is_set():
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[], usage=Usage(), stop_reason="aborted",
        )
        yield StartEvent(partial=output)
        yield DoneEvent(reason="aborted", message=output)
        return

    has_tool_result = any(m.role == "toolResult" for m in context.messages)
    if has_tool_result:
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[TextContent(text="Final")],
            usage=Usage(), stop_reason="stop",
        )
        yield StartEvent(partial=output)
        yield DoneEvent(reason="stop", message=output)
    else:
        tc1 = ToolCall(id="tc1", name="abort_tool", arguments={"input": "a"})
        tc2 = ToolCall(id="tc2", name="second_tool", arguments={"input": "b"})
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[tc1, tc2],
            usage=Usage(), stop_reason="toolUse",
        )
        yield StartEvent(partial=output)
        yield ToolCallStartEvent(content_index=0, partial=output)
        yield ToolCallEndEvent(content_index=0, tool_call=tc1, partial=output)
        yield ToolCallStartEvent(content_index=1, partial=output)
        yield ToolCallEndEvent(content_index=1, tool_call=tc2, partial=output)
        yield DoneEvent(reason="toolUse", message=output)


@pytest.mark.asyncio
async def test_abort_signal():
    """abort_signal stops the agent loop mid-stream."""
    register_provider("mock-api", mock_abort_tool_call_stream)

    abort_signal = asyncio.Event()
    tool = AbortingTool(name="abort_tool", signal=abort_signal)

    context = AgentContext(system_prompt="test", messages=[], tools=[tool])
    config = AgentLoopConfig(model=MOCK_MODEL, abort_signal=abort_signal)

    events = []
    async for event in agent_loop(
        prompts=[UserMessage(content="go")],
        context=context,
        config=config,
    ):
        events.append(event)

    # The tool fires abort, so the loop should end
    assert any(isinstance(e, AgentEndEvent) for e in events)
    # The second LLM call should see abort and return "aborted" stop_reason,
    # OR the loop exits before making a second call
    types = [type(e).__name__ for e in events]
    assert "AgentEndEvent" in types


@pytest.mark.asyncio
async def test_abort_signal_skips_remaining_tools():
    """When abort fires during first tool, second tool is skipped."""
    register_provider("mock-api", mock_two_abort_tool_calls_stream)

    abort_signal = asyncio.Event()
    abort_tool = AbortingTool(name="abort_tool", signal=abort_signal)
    second_tool = MockTool(name="second_tool", response="should not run")

    context = AgentContext(
        system_prompt="test", messages=[], tools=[abort_tool, second_tool],
    )
    config = AgentLoopConfig(model=MOCK_MODEL, abort_signal=abort_signal)

    events = []
    async for event in agent_loop(
        prompts=[UserMessage(content="go")],
        context=context,
        config=config,
    ):
        events.append(event)

    # second_tool should have been skipped (is_error=True)
    tool_ends = [e for e in events if isinstance(e, ToolExecutionEndEvent)]
    assert len(tool_ends) == 2
    second_end = [e for e in tool_ends if e.tool_name == "second_tool"][0]
    assert second_end.is_error is True

    assert any(isinstance(e, AgentEndEvent) for e in events)
