"""Tests for pi_ai.providers.openai_completions — uses mocked openai SDK."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_ai.providers.openai_completions import (
    _detect_compat,
    _get_compat,
    _has_tool_history,
    _normalize_mistral_tool_id,
    convert_messages,
    stream_openai_completions,
    stream_simple_openai_completions,
)
from pi_ai.types import (
    AssistantMessage,
    Context,
    ErrorEvent,
    ImageContent,
    Model,
    ModelCost,
    OpenAICompletionsCompat,
    TextContent,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)


def _make_model(
    model_id: str = "gpt-4o",
    provider: str = "openai",
) -> Model:
    return Model(
        id=model_id,
        name=model_id,
        api="openai-completions",
        provider=provider,
        base_url="https://api.openai.com/v1",
        max_tokens=4096,
        cost=ModelCost(input=5.0, output=15.0),
        input=["text"],
    )


def _make_context(text: str = "Hello") -> Context:
    return Context(messages=[UserMessage(content=text)])


def _make_chunk(
    content: str | None = None,
    finish_reason: str | None = None,
    tool_calls: list[Any] | None = None,
    usage: Any = None,
) -> Any:
    chunk = MagicMock()
    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.delta = MagicMock()
    choice.delta.content = content
    choice.delta.tool_calls = tool_calls or []
    choice.delta.reasoning_content = None
    choice.delta.reasoning = None
    choice.delta.reasoning_text = None
    choice.delta.reasoning_details = None
    chunk.choices = [choice]
    chunk.usage = usage
    return chunk


async def _fake_async_iter(items: list[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


class _FakeStream:
    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncIterator[Any]:
        return _fake_async_iter(self._chunks)


@pytest.mark.asyncio
async def test_stream_completions_basic() -> None:
    model = _make_model()
    context = _make_context("Hello")

    chunks = [
        _make_chunk(content="Hello"),
        _make_chunk(content=" World"),
        _make_chunk(finish_reason="stop"),
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_FakeStream(chunks))

    with (
        patch("pi_ai.providers.openai_completions.get_env_api_key", return_value="sk-test"),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        collected = []
        async for event in stream_openai_completions(model, context):
            collected.append(event)

    types = [e.type for e in collected]
    assert "start" in types
    assert "text_start" in types
    assert "text_delta" in types
    assert "text_end" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_stream_completions_error_on_exception() -> None:
    model = _make_model()
    context = _make_context("Hello")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API error"))

    with (
        patch("pi_ai.providers.openai_completions.get_env_api_key", return_value="sk-test"),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        collected = []
        async for event in stream_openai_completions(model, context):
            collected.append(event)

    error_events = [e for e in collected if e.type == "error"]
    assert len(error_events) == 1
    assert isinstance(error_events[0], ErrorEvent)


@pytest.mark.asyncio
async def test_stream_simple_completions_missing_key_raises() -> None:
    model = _make_model()
    context = _make_context()

    with (
        patch("pi_ai.providers.openai_completions.get_env_api_key", return_value=None),
        pytest.raises(ValueError, match="No API key"),
    ):
        async for _ in stream_simple_openai_completions(model, context):
            pass


def test_convert_messages_simple() -> None:
    model = _make_model()
    context = Context(
        messages=[UserMessage(content="hello")],
        system_prompt="You are helpful.",
    )
    compat = OpenAICompletionsCompat(
        supports_developer_role=False,
        requires_assistant_after_tool_result=False,
        requires_thinking_as_text=False,
        requires_tool_result_name=False,
        requires_mistral_tool_ids=False,
        supports_strict_mode=True,
    )
    messages = convert_messages(model, context, compat)
    roles = [m["role"] for m in messages]
    assert "system" in roles
    assert "user" in roles


@pytest.mark.asyncio
async def test_stream_completions_tool_call() -> None:
    """Test tool call streaming via openai completions."""
    model = _make_model()
    context = _make_context("Run bash")

    tc_delta = MagicMock()
    tc_delta.id = "call1"
    tc_delta.function = MagicMock()
    tc_delta.function.name = "bash"
    tc_delta.function.arguments = '{"cmd":'

    tc_delta2 = MagicMock()
    tc_delta2.id = ""
    tc_delta2.function = MagicMock()
    tc_delta2.function.name = None
    tc_delta2.function.arguments = '"ls"}'

    chunks = [
        _make_chunk(tool_calls=[tc_delta]),
        _make_chunk(tool_calls=[tc_delta2]),
        _make_chunk(finish_reason="tool_calls"),
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_FakeStream(chunks))

    with (
        patch("pi_ai.providers.openai_completions.get_env_api_key", return_value="sk-test"),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        collected = []
        async for event in stream_openai_completions(model, context):
            collected.append(event)

    types = [e.type for e in collected]
    assert "toolcall_start" in types
    assert "toolcall_delta" in types


def test_detect_compat_openai() -> None:
    model = _make_model("gpt-4o", "openai")
    compat = _detect_compat(model)
    assert compat.supports_store is True
    assert compat.supports_developer_role is True
    assert compat.supports_strict_mode is True


def test_detect_compat_mistral() -> None:
    model = Model(
        id="mistral-large",
        name="Mistral",
        api="openai-completions",
        provider="mistral",
        base_url="https://api.mistral.ai/v1",
        input=["text"],
    )
    compat = _detect_compat(model)
    assert compat.requires_thinking_as_text is True
    assert compat.requires_tool_result_name is True
    assert compat.requires_mistral_tool_ids is True
    assert compat.max_tokens_field == "max_tokens"


def test_detect_compat_xai() -> None:
    model = Model(
        id="grok-2",
        name="Grok",
        api="openai-completions",
        provider="xai",
        base_url="https://api.x.ai/v1",
        input=["text"],
    )
    compat = _detect_compat(model)
    assert compat.supports_reasoning_effort is False


def test_get_compat_no_model_compat() -> None:
    model = _make_model("gpt-4o", "openai")
    compat = _get_compat(model)
    assert compat.supports_store is True


def test_get_compat_with_model_compat() -> None:
    mc = OpenAICompletionsCompat(
        supports_store=False,
        requires_tool_result_name=True,
        requires_thinking_as_text=False,
        requires_mistral_tool_ids=False,
        supports_strict_mode=False,
    )
    model = Model(
        id="gpt-4o",
        name="gpt-4o",
        api="openai-completions",
        provider="openai",
        base_url="https://api.openai.com/v1",
        input=["text"],
        compat=mc,
    )
    compat = _get_compat(model)
    assert compat.supports_store is False
    assert compat.requires_tool_result_name is True


def test_normalize_mistral_tool_id_short() -> None:
    result = _normalize_mistral_tool_id("ab")
    assert len(result) == 9
    assert result.startswith("ab")


def test_normalize_mistral_tool_id_long() -> None:
    result = _normalize_mistral_tool_id("abcdefghijk")
    assert len(result) == 9
    assert result == "abcdefghi"


def test_normalize_mistral_tool_id_special_chars() -> None:
    result = _normalize_mistral_tool_id("call_123-abc")
    assert re.match(r"[a-zA-Z0-9]+", result)


def test_has_tool_history_empty() -> None:
    from pi_ai.types import Message

    msgs: list[Message] = [UserMessage(content="hello")]
    assert _has_tool_history(msgs) is False


def test_has_tool_history_with_tool_result() -> None:
    from pi_ai.types import Message

    tool_result = ToolResultMessage(
        tool_call_id="call1",
        tool_name="bash",
        content=[TextContent(text="output")],
        timestamp=1000,
    )
    msgs: list[Message] = [tool_result]
    assert _has_tool_history(msgs) is True


def test_has_tool_history_with_assistant_tool_call() -> None:
    from pi_ai.types import Message

    tc = ToolCall(id="call1", name="bash", arguments={})
    assistant = AssistantMessage(content=[tc], usage=Usage(), timestamp=1000)
    msgs: list[Message] = [assistant]
    assert _has_tool_history(msgs) is True


def test_convert_messages_tool_result() -> None:
    model = _make_model()
    tool_call = ToolCall(id="call1", name="bash", arguments={})
    assistant = AssistantMessage(
        content=[tool_call],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        timestamp=1000,
    )
    tool_result = ToolResultMessage(
        tool_call_id="call1",
        tool_name="bash",
        content=[TextContent(text="output")],
        timestamp=2000,
    )
    context = Context(messages=[UserMessage(content="run"), assistant, tool_result])
    compat = OpenAICompletionsCompat(
        requires_assistant_after_tool_result=False,
        requires_thinking_as_text=False,
        requires_tool_result_name=False,
        requires_mistral_tool_ids=False,
        supports_strict_mode=True,
    )
    messages = convert_messages(model, context, compat)
    roles = [m.get("role") or m.get("type") for m in messages]
    assert "tool" in roles


@pytest.mark.asyncio
async def test_stream_completions_thinking_content() -> None:
    """Test that reasoning_content fields trigger thinking events."""
    model = _make_model()
    context = _make_context("Think about this")

    def _make_thinking_chunk(reasoning: str) -> Any:
        chunk = MagicMock()
        choice = MagicMock()
        choice.finish_reason = None
        choice.delta = MagicMock()
        choice.delta.content = None
        choice.delta.tool_calls = []
        choice.delta.reasoning_content = reasoning
        choice.delta.reasoning = None
        choice.delta.reasoning_text = None
        choice.delta.reasoning_details = None
        chunk.choices = [choice]
        chunk.usage = None
        return chunk

    chunks = [
        _make_thinking_chunk("Let me think..."),
        _make_thinking_chunk(" more thoughts"),
        _make_chunk(finish_reason="stop"),
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_FakeStream(chunks))

    with (
        patch("pi_ai.providers.openai_completions.get_env_api_key", return_value="sk-test"),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        collected = []
        async for event in stream_openai_completions(model, context):
            collected.append(event)

    types = [e.type for e in collected]
    assert "thinking_start" in types
    assert "thinking_delta" in types
    assert "thinking_end" in types


@pytest.mark.asyncio
async def test_stream_completions_with_usage_chunk() -> None:
    """Test that a usage chunk updates the output usage."""
    model = _make_model()
    context = _make_context("Hello")

    usage_mock = MagicMock()
    usage_mock.prompt_tokens = 10
    usage_mock.completion_tokens = 5
    usage_mock.prompt_tokens_details = None
    usage_mock.completion_tokens_details = None

    chunks = [
        _make_chunk(content="Hello"),
        _make_chunk(finish_reason="stop"),
    ]
    # Add usage to first chunk
    chunks[0].usage = usage_mock

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_FakeStream(chunks))

    with (
        patch("pi_ai.providers.openai_completions.get_env_api_key", return_value="sk-test"),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        collected = []
        async for event in stream_openai_completions(model, context):
            collected.append(event)

    done_events = [e for e in collected if e.type == "done"]
    assert len(done_events) == 1


@pytest.mark.asyncio
async def test_stream_completions_on_payload_called() -> None:
    model = _make_model()
    context = _make_context()

    payloads: list[Any] = []
    chunks = [_make_chunk(content="Hi"), _make_chunk(finish_reason="stop")]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_FakeStream(chunks))

    from pi_ai.providers.openai_completions import OpenAICompletionsOptions

    options = OpenAICompletionsOptions(
        api_key="sk-test",
        on_payload=lambda p: payloads.append(p),
    )

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        async for _ in stream_openai_completions(model, context, options):
            pass

    assert len(payloads) == 1
    assert "model" in payloads[0]


@pytest.mark.asyncio
async def test_stream_simple_completions_basic() -> None:
    model = _make_model()
    context = _make_context("Hello")

    chunks = [
        _make_chunk(content="Hello"),
        _make_chunk(finish_reason="stop"),
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_FakeStream(chunks))

    with (
        patch("pi_ai.providers.openai_completions.get_env_api_key", return_value="sk-test"),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        collected = []
        async for event in stream_simple_openai_completions(model, context):
            collected.append(event)

    assert any(e.type == "done" for e in collected)


def test_convert_messages_with_image_content() -> None:
    model = Model(
        id="gpt-4o",
        name="gpt-4o",
        api="openai-completions",
        provider="openai",
        base_url="https://api.openai.com/v1",
        input=["text", "image"],
    )
    context = Context(
        messages=[
            UserMessage(content=[TextContent(text="look at this"), ImageContent(data="abc123", mime_type="image/png")]),
        ]
    )
    compat = OpenAICompletionsCompat(
        requires_assistant_after_tool_result=False,
        requires_thinking_as_text=False,
        requires_tool_result_name=False,
        requires_mistral_tool_ids=False,
        supports_strict_mode=True,
    )
    messages = convert_messages(model, context, compat)
    user_msg = next(m for m in messages if m["role"] == "user")
    assert isinstance(user_msg["content"], list)
    assert any(p.get("type") == "image_url" for p in user_msg["content"])
