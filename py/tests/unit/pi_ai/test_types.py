"""Tests for pi_ai.types — dataclass creation and basic properties."""

from __future__ import annotations

from pi_ai.types import (
    AssistantMessage,
    Context,
    CostBreakdown,
    DoneEvent,
    ErrorEvent,
    ImageContent,
    Model,
    ModelCost,
    StartEvent,
    TextContent,
    TextDeltaEvent,
    ThinkingBudgets,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)


def test_text_content_defaults() -> None:
    tc = TextContent()
    assert tc.type == "text"
    assert tc.text == ""
    assert tc.text_signature is None


def test_text_content_with_values() -> None:
    tc = TextContent(text="hello", text_signature="sig123")
    assert tc.text == "hello"
    assert tc.text_signature == "sig123"


def test_thinking_content_defaults() -> None:
    tc = ThinkingContent()
    assert tc.type == "thinking"
    assert tc.thinking == ""
    assert tc.thinking_signature is None


def test_image_content() -> None:
    ic = ImageContent(data="abc123", mime_type="image/png")
    assert ic.type == "image"
    assert ic.data == "abc123"
    assert ic.mime_type == "image/png"


def test_tool_call() -> None:
    tc = ToolCall(id="call1", name="bash", arguments={"cmd": "ls"})
    assert tc.type == "toolCall"
    assert tc.id == "call1"
    assert tc.arguments == {"cmd": "ls"}
    assert tc.thought_signature is None


def test_cost_breakdown() -> None:
    cb = CostBreakdown(input=0.01, output=0.02, total=0.03)
    assert cb.cache_read == 0.0
    assert cb.cache_write == 0.0


def test_usage_defaults() -> None:
    u = Usage()
    assert u.input == 0
    assert u.output == 0
    assert u.total_tokens == 0
    assert isinstance(u.cost, CostBreakdown)


def test_user_message() -> None:
    um = UserMessage(content="hello", timestamp=1000)
    assert um.role == "user"
    assert um.content == "hello"


def test_user_message_with_content_blocks() -> None:
    um = UserMessage(content=[TextContent(text="hi"), ImageContent(data="x", mime_type="image/jpeg")])
    assert isinstance(um.content, list)
    assert len(um.content) == 2


def test_assistant_message_defaults() -> None:
    am = AssistantMessage()
    assert am.role == "assistant"
    assert am.content == []
    assert am.stop_reason == "stop"
    assert am.error_message is None


def test_tool_result_message() -> None:
    tr = ToolResultMessage(
        tool_call_id="call1",
        tool_name="bash",
        content=[TextContent(text="output")],
        is_error=False,
        timestamp=2000,
    )
    assert tr.role == "toolResult"
    assert tr.tool_call_id == "call1"
    assert not tr.is_error


def test_tool() -> None:
    t = Tool(name="read", description="Read a file", parameters={"type": "object"})
    assert t.name == "read"


def test_context_defaults() -> None:
    ctx = Context()
    assert ctx.messages == []
    assert ctx.system_prompt is None
    assert ctx.tools is None


def test_model_cost() -> None:
    mc = ModelCost(input=3.0, output=15.0)
    assert mc.cache_read == 0.0


def test_model_defaults() -> None:
    m = Model(id="gpt-4", name="GPT-4", api="openai-completions", provider="openai")
    assert m.base_url == ""
    assert not m.reasoning
    assert m.input == ["text"]
    assert m.compat is None


def test_thinking_budgets() -> None:
    tb = ThinkingBudgets(minimal=512, low=1024)
    assert tb.minimal == 512
    assert tb.medium is None


def test_start_event() -> None:
    msg = AssistantMessage()
    ev = StartEvent(partial=msg)
    assert ev.type == "start"
    assert ev.partial is msg


def test_done_event() -> None:
    msg = AssistantMessage()
    ev = DoneEvent(reason="stop", message=msg)
    assert ev.type == "done"


def test_error_event() -> None:
    msg = AssistantMessage(stop_reason="error")
    ev = ErrorEvent(reason="error", error=msg)
    assert ev.type == "error"
    assert ev.reason == "error"


def test_text_delta_event() -> None:
    msg = AssistantMessage()
    ev = TextDeltaEvent(content_index=0, delta="hello", partial=msg)
    assert ev.type == "text_delta"
    assert ev.delta == "hello"


def test_event_stream_module_reexports() -> None:
    from pi_ai.utils.event_stream import (
        AssistantMessageEvent,
        AssistantMessageEventStream,
    )

    assert AssistantMessageEvent is not None
    assert AssistantMessageEventStream is not None
