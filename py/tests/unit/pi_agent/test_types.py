"""Tests for pi_agent.types — verifying instantiation and structure."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import pytest

from pi_agent.types import (
    AgentContext,
    AgentEndEvent,
    AgentLoopConfig,
    AgentStartEvent,
    AgentState,
    AgentTool,
    AgentToolResult,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    ProxyDoneEvent,
    ProxyErrorEvent,
    ProxyStartEvent,
    ProxyStreamOptions,
    ProxyTextDeltaEvent,
    ProxyTextEndEvent,
    ProxyTextStartEvent,
    ProxyThinkingDeltaEvent,
    ProxyThinkingEndEvent,
    ProxyThinkingStartEvent,
    ProxyToolCallDeltaEvent,
    ProxyToolCallEndEvent,
    ProxyToolCallStartEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from pi_ai.types import AssistantMessage, ImageContent, TextContent, Usage


class _DummyTool(AgentTool):
    """Minimal concrete AgentTool for testing."""

    name = "dummy"
    label = "Dummy"
    description = "A dummy tool for testing"
    parameters: ClassVar[dict[str, Any]] = {}

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: Any = None,
    ) -> AgentToolResult:
        return AgentToolResult(content=[TextContent(text="ok")], details=None)


class TestAgentToolResult:
    def test_instantiation(self) -> None:
        result = AgentToolResult(content=[], details=None)
        assert result.content == []
        assert result.details is None

    def test_with_content(self) -> None:
        result = AgentToolResult(
            content=[TextContent(text="hello"), ImageContent(data="abc", mime_type="image/png")],
            details={"key": "value"},
        )
        assert len(result.content) == 2
        assert result.details == {"key": "value"}


class TestAgentTool:
    def test_abstract_base(self) -> None:
        # AgentTool is abstract and cannot be instantiated directly
        with pytest.raises(TypeError):
            AgentTool()  # type: ignore[abstract]

    def test_concrete_subclass(self) -> None:
        tool = _DummyTool()
        assert tool.name == "dummy"
        assert tool.description == "A dummy tool for testing"

    @pytest.mark.asyncio
    async def test_execute(self) -> None:
        tool = _DummyTool()
        result = await tool.execute("id1", {})
        assert isinstance(result, AgentToolResult)
        assert len(result.content) == 1


class TestAgentState:
    def test_instantiation(self) -> None:
        from pi_ai.types import Model

        state = AgentState(
            system_prompt="test",
            model=Model(),
            thinking_level="off",
            tools=[],
            messages=[],
            is_streaming=False,
            stream_message=None,
            pending_tool_calls=set(),
        )
        assert state.system_prompt == "test"
        assert state.error is None
        assert state.thinking_level == "off"


class TestAgentContext:
    def test_instantiation(self) -> None:
        ctx = AgentContext(system_prompt="sys", messages=[])
        assert ctx.system_prompt == "sys"
        assert ctx.tools is None

    def test_with_tools(self) -> None:
        tool = _DummyTool()
        ctx = AgentContext(system_prompt="sys", messages=[], tools=[tool])
        assert ctx.tools is not None
        assert len(ctx.tools) == 1


class TestAgentLoopConfig:
    def test_default_instantiation(self) -> None:
        config = AgentLoopConfig()
        assert config.model.id == ""
        assert config.convert_to_llm is None
        assert config.get_steering_messages is None

    def test_with_values(self) -> None:
        from pi_ai.types import Model

        model = Model(id="gpt-4", api="openai", provider="openai")
        config = AgentLoopConfig(model=model, api_key="sk-test")
        assert config.model.id == "gpt-4"
        assert config.api_key == "sk-test"


class TestAgentEvents:
    def test_agent_start_event(self) -> None:
        e = AgentStartEvent()
        assert e.type == "agent_start"

    def test_agent_end_event(self) -> None:
        e = AgentEndEvent()
        assert e.type == "agent_end"
        assert e.messages == []

    def test_turn_start_event(self) -> None:
        e = TurnStartEvent()
        assert e.type == "turn_start"

    def test_turn_end_event_default(self) -> None:
        e = TurnEndEvent()
        assert e.type == "turn_end"
        # Default message is AssistantMessage
        assert isinstance(e.message, AssistantMessage)

    def test_turn_end_event_with_message(self) -> None:
        msg = AssistantMessage(model="gpt-4")
        e = TurnEndEvent(message=msg)
        assert e.message is msg

    def test_message_start_event(self) -> None:
        e = MessageStartEvent()
        assert e.type == "message_start"

    def test_message_update_event_default(self) -> None:
        from pi_ai.types import StartEvent

        e = MessageUpdateEvent()
        assert e.type == "message_update"
        # Default assistant_message_event is StartEvent
        assert isinstance(e.assistant_message_event, StartEvent)

    def test_message_end_event(self) -> None:
        e = MessageEndEvent()
        assert e.type == "message_end"

    def test_tool_execution_start(self) -> None:
        e = ToolExecutionStartEvent(tool_call_id="id1", tool_name="bash", args={"cmd": "ls"})
        assert e.type == "tool_execution_start"
        assert e.tool_call_id == "id1"

    def test_tool_execution_update(self) -> None:
        partial = AgentToolResult(content=[TextContent(text="partial...")], details=None)
        e = ToolExecutionUpdateEvent(
            tool_call_id="id1",
            tool_name="bash",
            args={},
            partial_result=partial,
        )
        assert e.type == "tool_execution_update"

    def test_tool_execution_end(self) -> None:
        result = AgentToolResult(content=[TextContent(text="done")], details=None)
        e = ToolExecutionEndEvent(tool_call_id="id1", tool_name="bash", result=result)
        assert e.type == "tool_execution_end"
        assert e.is_error is False


class TestProxyEvents:
    def test_proxy_start_event(self) -> None:
        e = ProxyStartEvent()
        assert e.type == "start"

    def test_proxy_text_start(self) -> None:
        e = ProxyTextStartEvent(content_index=0)
        assert e.type == "text_start"

    def test_proxy_text_delta(self) -> None:
        e = ProxyTextDeltaEvent(content_index=0, delta="hello")
        assert e.delta == "hello"

    def test_proxy_text_end(self) -> None:
        e = ProxyTextEndEvent(content_index=0, content_signature="sig")
        assert e.content_signature == "sig"

    def test_proxy_thinking_events(self) -> None:
        assert ProxyThinkingStartEvent().type == "thinking_start"
        assert ProxyThinkingDeltaEvent(delta="thinking...").type == "thinking_delta"
        assert ProxyThinkingEndEvent().type == "thinking_end"

    def test_proxy_toolcall_events(self) -> None:
        assert ProxyToolCallStartEvent(id="tc1", tool_name="bash").type == "toolcall_start"
        assert ProxyToolCallDeltaEvent(delta='{"cmd"').type == "toolcall_delta"
        assert ProxyToolCallEndEvent().type == "toolcall_end"

    def test_proxy_done_event(self) -> None:
        e = ProxyDoneEvent(reason="stop", usage=Usage())
        assert e.type == "done"
        assert e.reason == "stop"

    def test_proxy_error_event(self) -> None:
        e = ProxyErrorEvent(reason="error", error_message="oops")
        assert e.type == "error"
        assert e.error_message == "oops"

    def test_proxy_stream_options(self) -> None:
        opts = ProxyStreamOptions(auth_token="tok", proxy_url="http://localhost:8080")
        assert opts.auth_token == "tok"
        assert opts.proxy_url == "http://localhost:8080"
