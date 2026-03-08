"""Tests for pi_ai.providers.openai_responses_shared."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from pi_ai.providers.openai_responses_shared import (
    ConvertResponsesMessagesOptions,
    ConvertResponsesToolsOptions,
    convert_responses_messages,
    convert_responses_tools,
    process_responses_stream,
)
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    ImageContent,
    Model,
    ModelCost,
    TextContent,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)


async def _collect_events(
    stream: AsyncGenerator[AssistantMessageEvent, None],
) -> list[AssistantMessageEvent]:
    events = []
    async for e in stream:
        events.append(e)
    return events


def _make_output(model: Model) -> AssistantMessage:
    return AssistantMessage(
        role="assistant",
        content=[],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        stop_reason="stop",
        timestamp=int(time.time() * 1000),
    )


async def _dict_stream(events: list[dict[str, Any]]) -> AsyncGenerator[dict[str, Any], None]:
    for e in events:
        yield e


def _make_model(
    model_id: str = "gpt-4o",
    provider: str = "openai",
    api: str = "openai-responses",
    reasoning: bool = False,
) -> Model:
    return Model(
        id=model_id,
        name=model_id,
        api=api,
        provider=provider,
        base_url="https://api.openai.com/v1",
        reasoning=reasoning,
        input=["text", "image"],
        cost=ModelCost(),
    )


def _make_assistant(model: Model, content: list[TextContent | ToolCall] | None = None) -> AssistantMessage:
    return AssistantMessage(
        content=list(content) if content is not None else [],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        timestamp=1000,
    )


def test_convert_messages_user_string() -> None:
    model = _make_model()
    ctx = Context(messages=[UserMessage(content="hello")])
    result = convert_responses_messages(model, ctx, frozenset())
    user_msgs = [m for m in result if m.get("role") == "user"]
    assert len(user_msgs) == 1
    assert user_msgs[0]["content"][0]["type"] == "input_text"
    assert user_msgs[0]["content"][0]["text"] == "hello"


def test_convert_messages_with_system_prompt() -> None:
    model = _make_model()
    ctx = Context(messages=[], system_prompt="Be helpful.")
    result = convert_responses_messages(model, ctx, frozenset())
    system_msgs = [m for m in result if m.get("role") == "system"]
    assert len(system_msgs) == 1
    assert system_msgs[0]["content"] == "Be helpful."


def test_convert_messages_reasoning_model_uses_developer() -> None:
    model = _make_model(reasoning=True)
    ctx = Context(messages=[], system_prompt="You are helpful.")
    result = convert_responses_messages(model, ctx, frozenset())
    dev_msgs = [m for m in result if m.get("role") == "developer"]
    assert len(dev_msgs) == 1


def test_convert_messages_no_system_when_disabled() -> None:
    model = _make_model()
    ctx = Context(messages=[], system_prompt="hidden")
    result = convert_responses_messages(
        model, ctx, frozenset(), ConvertResponsesMessagesOptions(include_system_prompt=False)
    )
    system_msgs = [m for m in result if m.get("role") in ("system", "developer")]
    assert len(system_msgs) == 0


def test_convert_messages_tool_result() -> None:
    model = _make_model()
    tool_call = ToolCall(id="call1|fc_item1", name="bash", arguments={})
    assistant = _make_assistant(model, content=[tool_call])
    tool_result = ToolResultMessage(
        tool_call_id="call1|fc_item1",
        tool_name="bash",
        content=[TextContent(text="output text")],
        timestamp=2000,
    )
    ctx = Context(messages=[UserMessage(content="hi"), assistant, tool_result])
    result = convert_responses_messages(model, ctx, frozenset())
    fc_outputs = [m for m in result if m.get("type") == "function_call_output"]
    assert len(fc_outputs) == 1
    assert fc_outputs[0]["output"] == "output text"
    assert fc_outputs[0]["call_id"] == "call1"


def test_convert_messages_image_in_user() -> None:
    model = _make_model()
    ctx = Context(
        messages=[
            UserMessage(
                content=[
                    TextContent(text="look"),
                    ImageContent(data="base64data", mime_type="image/png"),
                ]
            )
        ]
    )
    result = convert_responses_messages(model, ctx, frozenset())
    user_msg = next(m for m in result if m.get("role") == "user")
    types = [c["type"] for c in user_msg["content"]]
    assert "input_image" in types


def test_convert_tools_basic() -> None:
    tools = [Tool(name="bash", description="Run a bash command", parameters={"type": "object"})]
    result = convert_responses_tools(tools)
    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert result[0]["name"] == "bash"
    assert result[0]["description"] == "Run a bash command"


def test_convert_tools_strict_default_false() -> None:
    tools = [Tool(name="t", description="d", parameters={})]
    result = convert_responses_tools(tools)
    assert result[0]["strict"] is False


def test_convert_tools_strict_none() -> None:
    tools = [Tool(name="t", description="d", parameters={})]
    result = convert_responses_tools(tools, ConvertResponsesToolsOptions(strict=None))
    assert "strict" not in result[0]


def test_convert_tools_empty() -> None:
    result = convert_responses_tools([])
    assert result == []


# --- process_responses_stream tests ---


@pytest.mark.asyncio
async def test_process_stream_text() -> None:
    model = _make_model()
    output = _make_output(model)
    events_in: list[dict[str, Any]] = [
        {"type": "response.output_item.added", "item": {"type": "message", "id": "msg1"}},
        {"type": "response.content_part.added", "part": {"type": "output_text", "text": ""}},
        {"type": "response.output_text.delta", "delta": "Hello"},
        {"type": "response.output_text.delta", "delta": " world"},
        {
            "type": "response.output_item.done",
            "item": {"type": "message", "id": "msg1", "content": [{"type": "output_text", "text": "Hello world"}]},
        },
        {
            "type": "response.completed",
            "response": {
                "status": "completed",
                "usage": {"input_tokens": 10, "output_tokens": 5, "input_tokens_details": {}},
            },
        },
    ]
    events_out = await _collect_events(process_responses_stream(_dict_stream(events_in), output, model))
    types = [type(e).__name__ for e in events_out]
    assert "TextStartEvent" in types
    assert "TextDeltaEvent" in types
    assert "TextEndEvent" in types
    assert output.usage.input == 10
    assert output.usage.output == 5


@pytest.mark.asyncio
async def test_process_stream_tool_call() -> None:
    model = _make_model()
    output = _make_output(model)
    events_in: list[dict[str, Any]] = [
        {
            "type": "response.output_item.added",
            "item": {"type": "function_call", "id": "fc1", "call_id": "call1", "name": "bash", "arguments": ""},
        },
        {"type": "response.function_call_arguments.delta", "delta": '{"cmd": "ls"}'},
        {"type": "response.function_call_arguments.done", "arguments": '{"cmd": "ls"}'},
        {
            "type": "response.output_item.done",
            "item": {
                "type": "function_call",
                "id": "fc1",
                "call_id": "call1",
                "name": "bash",
                "arguments": '{"cmd": "ls"}',
            },
        },
        {
            "type": "response.completed",
            "response": {"status": "completed", "usage": {"input_tokens": 5, "output_tokens": 3}},
        },
    ]
    events_out = await _collect_events(process_responses_stream(_dict_stream(events_in), output, model))
    types = [type(e).__name__ for e in events_out]
    assert "ToolcallStartEvent" in types
    assert "ToolcallDeltaEvent" in types
    assert "ToolcallEndEvent" in types
    tool_calls = [b for b in output.content if isinstance(b, ToolCall)]
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "bash"


@pytest.mark.asyncio
async def test_process_stream_thinking() -> None:
    model = _make_model(reasoning=True)
    output = _make_output(model)
    events_in: list[dict[str, Any]] = [
        {"type": "response.output_item.added", "item": {"type": "reasoning", "id": "r1"}},
        {
            "type": "response.reasoning_summary_part.added",
            "item_id": "r1",
            "part": {"type": "summary_text", "text": ""},
        },
        {"type": "response.reasoning_summary_text.delta", "item_id": "r1", "delta": "I think"},
        {"type": "response.reasoning_summary_part.done", "item_id": "r1", "part": {"text": "I think"}},
        {
            "type": "response.output_item.done",
            "item": {"type": "reasoning", "id": "r1", "summary": [{"text": "I think"}]},
        },
        {
            "type": "response.completed",
            "response": {"status": "completed", "usage": {"input_tokens": 5, "output_tokens": 3}},
        },
    ]
    events_out = await _collect_events(process_responses_stream(_dict_stream(events_in), output, model))
    types = [type(e).__name__ for e in events_out]
    assert "ThinkingStartEvent" in types
    assert "ThinkingDeltaEvent" in types
    thinking_blocks = [b for b in output.content if isinstance(b, ThinkingContent)]
    assert len(thinking_blocks) == 1


@pytest.mark.asyncio
async def test_process_stream_error_event() -> None:
    model = _make_model()
    output = _make_output(model)
    events_in = [
        {"type": "error", "code": "rate_limit", "message": "Rate limited"},
    ]
    with pytest.raises(RuntimeError, match="Rate limited"):
        await _collect_events(process_responses_stream(_dict_stream(events_in), output, model))


@pytest.mark.asyncio
async def test_process_stream_failed_event() -> None:
    model = _make_model()
    output = _make_output(model)
    events_in = [
        {"type": "response.failed"},
    ]
    with pytest.raises(RuntimeError):
        await _collect_events(process_responses_stream(_dict_stream(events_in), output, model))


@pytest.mark.asyncio
async def test_process_stream_none_type_ignored() -> None:
    model = _make_model()
    output = _make_output(model)
    events_in: list[dict[str, Any]] = [
        {"no_type_key": "value"},
        {
            "type": "response.completed",
            "response": {"status": "completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
        },
    ]
    events_out = await _collect_events(process_responses_stream(_dict_stream(events_in), output, model))
    assert events_out == []
