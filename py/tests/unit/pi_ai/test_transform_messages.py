"""Tests for pi_ai.providers.transform_messages."""

from __future__ import annotations

from pi_ai.providers.transform_messages import transform_messages
from pi_ai.types import (
    AssistantMessage,
    Message,
    Model,
    ModelCost,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)


def _make_model(
    model_id: str = "gpt-4o",
    provider: str = "openai",
    api: str = "openai-completions",
) -> Model:
    return Model(
        id=model_id,
        name=model_id,
        api=api,
        provider=provider,
        base_url="https://api.openai.com/v1",
        cost=ModelCost(),
    )


def _make_assistant(
    model: Model,
    content: list[TextContent | ThinkingContent | ToolCall] | None = None,
    stop_reason: str = "stop",
) -> AssistantMessage:
    return AssistantMessage(
        content=list(content) if content is not None else [],
        api=model.api,
        provider=model.provider,
        model=model.id,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        usage=Usage(),
        timestamp=1000,
    )


def test_user_messages_pass_through() -> None:
    model = _make_model()
    msgs = [UserMessage(content="hello")]
    result = transform_messages(msgs, model)
    assert len(result) == 1
    assert result[0].role == "user"


def test_errored_assistant_skipped() -> None:
    model = _make_model()
    msgs: list[Message] = [
        UserMessage(content="hi"),
        _make_assistant(model, stop_reason="error"),
    ]
    result = transform_messages(msgs, model)
    assert len(result) == 1
    assert result[0].role == "user"


def test_aborted_assistant_skipped() -> None:
    model = _make_model()
    msgs: list[Message] = [
        UserMessage(content="hi"),
        _make_assistant(model, stop_reason="aborted"),
    ]
    result = transform_messages(msgs, model)
    assert len(result) == 1


def test_same_model_keeps_thinking_with_signature() -> None:
    model = _make_model()
    thinking = ThinkingContent(thinking="thought", thinking_signature="sig")
    msgs: list[Message] = [
        UserMessage(content="hi"),
        _make_assistant(model, content=[thinking]),
    ]
    result = transform_messages(msgs, model)
    assistant_result = next(m for m in result if m.role == "assistant")
    assert isinstance(assistant_result, AssistantMessage)
    found = [b for b in assistant_result.content if isinstance(b, ThinkingContent)]
    assert len(found) == 1
    assert found[0].thinking_signature == "sig"


def test_cross_model_thinking_converted_to_text() -> None:
    model = _make_model(model_id="gpt-4o")
    other_model = _make_model(model_id="claude-3")
    thinking = ThinkingContent(thinking="thought text", thinking_signature="sig")
    msgs: list[Message] = [
        UserMessage(content="hi"),
        _make_assistant(other_model, content=[thinking]),
    ]
    result = transform_messages(msgs, model)
    assistant_result = next(m for m in result if m.role == "assistant")
    assert isinstance(assistant_result, AssistantMessage)
    # Thinking should be converted to text for cross-model replay
    text_blocks = [b for b in assistant_result.content if isinstance(b, TextContent)]
    assert any("thought text" in b.text for b in text_blocks)


def test_empty_thinking_block_dropped() -> None:
    model = _make_model()
    thinking = ThinkingContent(thinking="", thinking_signature=None)
    msgs: list[Message] = [
        UserMessage(content="hi"),
        _make_assistant(model, content=[thinking]),
    ]
    result = transform_messages(msgs, model)
    assistant_msgs = [m for m in result if m.role == "assistant"]
    # Empty thinking block → assistant with no content → skipped
    assert len(assistant_msgs) == 0


def test_orphaned_tool_call_gets_synthetic_result() -> None:
    model = _make_model()
    tool_call = ToolCall(id="call1", name="bash", arguments={"cmd": "ls"})
    assistant = _make_assistant(model, content=[tool_call])
    # Second assistant without tool result in between
    msgs: list[Message] = [
        UserMessage(content="hi"),
        assistant,
        UserMessage(content="hi again"),
    ]
    result = transform_messages(msgs, model)
    tool_result_msgs = [m for m in result if m.role == "toolResult"]
    assert len(tool_result_msgs) == 1
    assert tool_result_msgs[0].tool_call_id == "call1"
    assert tool_result_msgs[0].is_error


def test_tool_call_with_result_no_synthetic() -> None:
    model = _make_model()
    tool_call = ToolCall(id="call1", name="bash", arguments={})
    assistant = _make_assistant(model, content=[tool_call])
    tool_result = ToolResultMessage(
        tool_call_id="call1",
        tool_name="bash",
        content=[TextContent(text="output")],
        timestamp=2000,
    )
    msgs: list[Message] = [UserMessage(content="hi"), assistant, tool_result]
    result = transform_messages(msgs, model)
    tool_results = [m for m in result if m.role == "toolResult"]
    assert len(tool_results) == 1
    assert tool_results[0].tool_call_id == "call1"
    assert not tool_results[0].is_error


def test_normalize_tool_call_id() -> None:
    model = _make_model()
    tool_call = ToolCall(id="call-original", name="bash", arguments={})
    assistant = _make_assistant(model, content=[tool_call])
    tool_result = ToolResultMessage(
        tool_call_id="call-original",
        tool_name="bash",
        content=[TextContent(text="output")],
        timestamp=2000,
    )

    def normalize(tc_id: str, _m: Model, _a: AssistantMessage) -> str:
        return "normalized-id"

    msgs: list[Message] = [UserMessage(content="hi"), assistant, tool_result]
    result = transform_messages(msgs, model, normalize)
    tool_results = [m for m in result if m.role == "toolResult"]
    assert len(tool_results) == 1
    assert tool_results[0].tool_call_id == "normalized-id"


def test_cross_model_thought_signature_removed() -> None:
    model = _make_model(model_id="gpt-4o")
    other_model = _make_model(model_id="claude-3")
    tool_call = ToolCall(id="call1", name="bash", arguments={}, thought_signature="some-sig")
    assistant = _make_assistant(other_model, content=[tool_call])
    msgs: list[Message] = [UserMessage(content="hi"), assistant]
    result = transform_messages(msgs, model)
    assistant_msgs = [m for m in result if m.role == "assistant"]
    if assistant_msgs:
        assert isinstance(assistant_msgs[0], AssistantMessage)
        tool_calls = [b for b in assistant_msgs[0].content if isinstance(b, ToolCall)]
        if tool_calls:
            # thought_signature should be stripped for cross-model
            assert tool_calls[0].thought_signature is None
