"""Tests for pi_ai.types — core dataclass types."""

from __future__ import annotations

import asyncio

from pi_ai.types import (
    AssistantMessage,
    Context,
    DoneEvent,
    ErrorEvent,
    ImageContent,
    Model,
    ModelCost,
    SimpleStreamOptions,
    StartEvent,
    StreamOptions,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ThinkingBudgets,
    ThinkingContent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    Tool,
    ToolCall,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultMessage,
    Usage,
    UsageCost,
    UserMessage,
)

# ---------------------------------------------------------------------------
# TextContent
# ---------------------------------------------------------------------------


class TestTextContent:
    def test_defaults(self) -> None:
        tc = TextContent()
        assert tc.type == "text"
        assert tc.text == ""
        assert tc.text_signature is None

    def test_custom_values(self) -> None:
        tc = TextContent(text="hello", text_signature="sig123")
        assert tc.text == "hello"
        assert tc.text_signature == "sig123"


# ---------------------------------------------------------------------------
# ThinkingContent
# ---------------------------------------------------------------------------


class TestThinkingContent:
    def test_defaults(self) -> None:
        tc = ThinkingContent()
        assert tc.type == "thinking"
        assert tc.thinking == ""
        assert tc.thinking_signature is None

    def test_custom_values(self) -> None:
        tc = ThinkingContent(thinking="deep thought", thinking_signature="sig456")
        assert tc.thinking == "deep thought"
        assert tc.thinking_signature == "sig456"


# ---------------------------------------------------------------------------
# ImageContent
# ---------------------------------------------------------------------------


class TestImageContent:
    def test_defaults(self) -> None:
        ic = ImageContent()
        assert ic.type == "image"
        assert ic.data == ""
        assert ic.mime_type == ""

    def test_custom_values(self) -> None:
        ic = ImageContent(data="base64data", mime_type="image/png")
        assert ic.data == "base64data"
        assert ic.mime_type == "image/png"


# ---------------------------------------------------------------------------
# ToolCall
# ---------------------------------------------------------------------------


class TestToolCall:
    def test_defaults(self) -> None:
        tc = ToolCall()
        assert tc.type == "toolCall"
        assert tc.id == ""
        assert tc.name == ""
        assert tc.arguments == {}
        assert tc.thought_signature is None

    def test_custom_values(self) -> None:
        tc = ToolCall(id="tc_1", name="read_file", arguments={"path": "/tmp"})
        assert tc.id == "tc_1"
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "/tmp"}

    def test_arguments_default_is_not_shared(self) -> None:
        a = ToolCall()
        b = ToolCall()
        a.arguments["key"] = "val"
        assert "key" not in b.arguments


# ---------------------------------------------------------------------------
# Usage / UsageCost
# ---------------------------------------------------------------------------


class TestUsageCost:
    def test_defaults(self) -> None:
        uc = UsageCost()
        assert uc.input == 0.0
        assert uc.output == 0.0
        assert uc.total == 0.0

    def test_custom(self) -> None:
        uc = UsageCost(input=1.5, output=2.5, total=4.0)
        assert uc.total == 4.0


class TestUsage:
    def test_defaults(self) -> None:
        u = Usage()
        assert u.input == 0
        assert u.output == 0
        assert u.total_tokens == 0
        assert isinstance(u.cost, UsageCost)

    def test_cost_factory(self) -> None:
        a = Usage()
        b = Usage()
        a.cost.total = 5.0
        assert b.cost.total == 0.0


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


class TestUserMessage:
    def test_defaults(self) -> None:
        m = UserMessage()
        assert m.role == "user"
        assert m.content == ""
        assert m.timestamp == 0

    def test_string_content(self) -> None:
        m = UserMessage(content="hello")
        assert m.content == "hello"

    def test_list_content(self) -> None:
        m = UserMessage(content=[TextContent(text="hi"), ImageContent(data="abc", mime_type="image/png")])
        assert len(m.content) == 2


class TestAssistantMessage:
    def test_defaults(self) -> None:
        m = AssistantMessage()
        assert m.role == "assistant"
        assert m.content == []
        assert m.api == ""
        assert m.provider == ""
        assert m.model == ""
        assert m.stop_reason == "stop"
        assert m.error_message is None

    def test_content_list_not_shared(self) -> None:
        a = AssistantMessage()
        b = AssistantMessage()
        a.content.append(TextContent(text="x"))
        assert len(b.content) == 0


class TestToolResultMessage:
    def test_defaults(self) -> None:
        m = ToolResultMessage()
        assert m.role == "toolResult"
        assert m.tool_call_id == ""
        assert m.is_error is False

    def test_custom(self) -> None:
        m = ToolResultMessage(
            tool_call_id="tc_1",
            tool_name="bash",
            content=[TextContent(text="output")],
            is_error=True,
        )
        assert m.is_error is True
        assert m.tool_name == "bash"


# ---------------------------------------------------------------------------
# Tool / Context
# ---------------------------------------------------------------------------


class TestTool:
    def test_defaults(self) -> None:
        t = Tool()
        assert t.name == ""
        assert t.description == ""
        assert t.parameters == {}


class TestContext:
    def test_defaults(self) -> None:
        c = Context()
        assert c.system_prompt is None
        assert c.messages == []
        assert c.tools is None

    def test_custom(self) -> None:
        c = Context(
            system_prompt="You are helpful",
            messages=[UserMessage(content="hi")],
            tools=[Tool(name="bash")],
        )
        assert c.system_prompt == "You are helpful"
        assert len(c.messages) == 1


# ---------------------------------------------------------------------------
# Model / ModelCost
# ---------------------------------------------------------------------------


class TestModelCost:
    def test_defaults(self) -> None:
        mc = ModelCost()
        assert mc.input == 0.0
        assert mc.output == 0.0


class TestModel:
    def test_defaults(self) -> None:
        m = Model()
        assert m.id == ""
        assert m.reasoning is False
        assert m.input == ["text"]

    def test_input_default_not_shared(self) -> None:
        a = Model()
        b = Model()
        a.input.append("image")
        assert "image" not in b.input


# ---------------------------------------------------------------------------
# StreamOptions / SimpleStreamOptions / ThinkingBudgets
# ---------------------------------------------------------------------------


class TestStreamOptions:
    def test_defaults(self) -> None:
        so = StreamOptions()
        assert so.temperature is None
        assert so.max_tokens is None
        assert so.signal is None
        assert so.api_key is None
        assert so.headers is None

    def test_signal_is_event(self) -> None:
        evt = asyncio.Event()
        so = StreamOptions(signal=evt)
        assert so.signal is evt


class TestSimpleStreamOptions:
    def test_inherits_stream_options(self) -> None:
        sso = SimpleStreamOptions(temperature=0.5, reasoning="high")
        assert sso.temperature == 0.5
        assert sso.reasoning == "high"

    def test_thinking_budgets(self) -> None:
        sso = SimpleStreamOptions(thinking_budgets=ThinkingBudgets(low=512))
        assert sso.thinking_budgets is not None
        assert sso.thinking_budgets.low == 512


class TestThinkingBudgets:
    def test_defaults(self) -> None:
        tb = ThinkingBudgets()
        assert tb.minimal is None
        assert tb.low is None
        assert tb.medium is None
        assert tb.high is None


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class TestStartEvent:
    def test_defaults(self) -> None:
        e = StartEvent()
        assert e.type == "start"
        assert isinstance(e.partial, AssistantMessage)


class TestTextEvents:
    def test_text_start(self) -> None:
        e = TextStartEvent(content_index=0)
        assert e.type == "text_start"
        assert e.content_index == 0

    def test_text_delta(self) -> None:
        e = TextDeltaEvent(content_index=1, delta="hello")
        assert e.type == "text_delta"
        assert e.delta == "hello"

    def test_text_end(self) -> None:
        e = TextEndEvent(content_index=2, content="full text")
        assert e.type == "text_end"
        assert e.content == "full text"


class TestThinkingEvents:
    def test_thinking_start(self) -> None:
        e = ThinkingStartEvent(content_index=0)
        assert e.type == "thinking_start"

    def test_thinking_delta(self) -> None:
        e = ThinkingDeltaEvent(content_index=0, delta="thought")
        assert e.delta == "thought"

    def test_thinking_end(self) -> None:
        e = ThinkingEndEvent(content_index=0, content="full thought")
        assert e.content == "full thought"


class TestToolCallEvents:
    def test_toolcall_start(self) -> None:
        e = ToolCallStartEvent(content_index=0)
        assert e.type == "toolcall_start"

    def test_toolcall_delta(self) -> None:
        e = ToolCallDeltaEvent(content_index=0, delta='{"path":')
        assert e.delta == '{"path":'

    def test_toolcall_end(self) -> None:
        tc = ToolCall(id="tc_1", name="bash", arguments={"cmd": "ls"})
        e = ToolCallEndEvent(content_index=0, tool_call=tc)
        assert e.tool_call.name == "bash"


class TestDoneEvent:
    def test_defaults(self) -> None:
        e = DoneEvent()
        assert e.type == "done"
        assert e.reason == "stop"

    def test_custom_reason(self) -> None:
        msg = AssistantMessage(stop_reason="toolUse")
        e = DoneEvent(reason="toolUse", message=msg)
        assert e.reason == "toolUse"


class TestErrorEvent:
    def test_defaults(self) -> None:
        e = ErrorEvent()
        assert e.type == "error"
        assert e.reason == "error"
