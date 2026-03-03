"""Tests for the agent loop — mock LLM tests."""

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
from pi_agent.agent_loop import agent_loop
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
    assert "AgentEndEvent" in [type(e).__name__ for e in events]


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
    assert "AgentEndEvent" in [type(e).__name__ for e in events]
