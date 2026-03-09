"""Tests for pi_ai.providers.anthropic — uses mocked anthropic SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pi_ai.providers.anthropic import (
    _build_messages,
    _build_params,
    _convert_content_blocks,
    _convert_tools,
    _get_cache_control,
    _is_oauth_token,
    _map_stop_reason,
    _map_thinking_level_to_effort,
    _merge_headers,
    _normalize_tool_call_id,
    _resolve_cache_retention,
    _supports_adaptive_thinking,
    _to_claude_code_name,
    stream_anthropic,
    stream_simple_anthropic,
)
from pi_ai.types import (
    AssistantMessage,
    Context,
    DoneEvent,
    ErrorEvent,
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


def _make_model(model_id: str = "claude-3-5-sonnet-20241022") -> Model:
    return Model(
        id=model_id,
        name="Claude",
        api="anthropic-messages",
        provider="anthropic",
        base_url="https://api.anthropic.com",
        max_tokens=8192,
        cost=ModelCost(input=3.0, output=15.0),
    )


def _make_context(text: str = "Hello") -> Context:
    return Context(messages=[UserMessage(content=text)])


def _make_event(type_: str, **kwargs: Any) -> Any:
    """Create a fake Anthropic streaming event."""
    obj = MagicMock()
    obj.type = type_
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


async def _fake_stream(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


class _FakeStreamContextManager:
    """Mimics async context manager returned by client.messages.stream()."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events

    async def __aenter__(self) -> _FakeStreamContextManager:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    def __aiter__(self) -> AsyncIterator[Any]:
        return _fake_stream(self._events)


def _build_anthropic_stream_events(text: str = "Hello!") -> list[Any]:
    """Build a minimal sequence of fake Anthropic streaming events."""
    start = _make_event("message_start")
    start.message = MagicMock()
    start.message.usage = MagicMock(
        input_tokens=10, output_tokens=0, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )

    cb_start = _make_event("content_block_start", index=0)
    cb_start.content_block = MagicMock(type="text")

    cb_delta = _make_event("content_block_delta", index=0)
    cb_delta.delta = MagicMock(type="text_delta", text=text)

    cb_stop = _make_event("content_block_stop", index=0)

    msg_delta = _make_event("message_delta")
    msg_delta.delta = MagicMock(stop_reason="end_turn")
    msg_delta.usage = MagicMock(
        input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )

    return [start, cb_start, cb_delta, cb_stop, msg_delta]


@pytest.mark.asyncio
async def test_stream_anthropic_basic() -> None:
    model = _make_model()
    context = _make_context("Hello")

    events = _build_anthropic_stream_events("Hello!")

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _FakeStreamContextManager(events)

    with (
        patch("pi_ai.providers.anthropic.get_env_api_key", return_value="sk-ant-test"),
        patch("pi_ai.providers.anthropic._create_client", return_value=(mock_client, False)),
    ):
        collected = []
        async for event in stream_anthropic(model, context):
            collected.append(event)

    types = [e.type for e in collected]
    assert "start" in types
    assert "text_start" in types
    assert "text_delta" in types
    assert "text_end" in types
    assert "done" in types

    done_event = next(e for e in collected if e.type == "done")
    assert isinstance(done_event, DoneEvent)
    assert done_event.reason == "stop"


@pytest.mark.asyncio
async def test_stream_anthropic_error_on_exception() -> None:
    model = _make_model()
    context = _make_context("Hello")

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _FakeStreamContextManager([])

    async def _bad_stream() -> AsyncIterator[Any]:
        raise RuntimeError("API error")
        yield

    class _ErrorContextManager:
        async def __aenter__(self) -> _ErrorContextManager:
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        def __aiter__(self) -> AsyncIterator[Any]:
            return _bad_stream()

    mock_client.messages.stream.return_value = _ErrorContextManager()

    with (
        patch("pi_ai.providers.anthropic.get_env_api_key", return_value="sk-ant-test"),
        patch("pi_ai.providers.anthropic._create_client", return_value=(mock_client, False)),
    ):
        collected = []
        async for event in stream_anthropic(model, context):
            collected.append(event)

    error_events = [e for e in collected if e.type == "error"]
    assert len(error_events) == 1
    assert isinstance(error_events[0], ErrorEvent)
    assert error_events[0].reason == "error"


@pytest.mark.asyncio
async def test_stream_simple_anthropic_no_reasoning() -> None:
    model = _make_model()
    context = _make_context("Hello")

    events = _build_anthropic_stream_events("Hi!")

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _FakeStreamContextManager(events)

    with (
        patch("pi_ai.providers.anthropic.get_env_api_key", return_value="sk-ant-test"),
        patch("pi_ai.providers.anthropic._create_client", return_value=(mock_client, False)),
    ):
        collected = []
        async for event in stream_simple_anthropic(model, context):
            collected.append(event)

    done_events = [e for e in collected if e.type == "done"]
    assert len(done_events) == 1


@pytest.mark.asyncio
async def test_stream_simple_anthropic_missing_api_key_raises() -> None:
    model = _make_model()
    context = _make_context()

    with (
        patch("pi_ai.providers.anthropic.get_env_api_key", return_value=None),
        pytest.raises(ValueError, match="No API key"),
    ):
        async for _ in stream_simple_anthropic(model, context):
            pass


@pytest.mark.asyncio
async def test_stream_anthropic_tool_call() -> None:
    """Test that tool_use blocks are yielded as toolcall events."""
    model = _make_model()
    context = _make_context("Run ls")

    start = _make_event("message_start")
    start.message = MagicMock()
    start.message.usage = MagicMock(
        input_tokens=10, output_tokens=0, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )

    cb_start = _make_event("content_block_start", index=0)
    cb_start.content_block = MagicMock(type="tool_use", id="toolu_123", name="bash")
    cb_start.content_block.input = {}

    cb_delta = _make_event("content_block_delta", index=0)
    cb_delta.delta = MagicMock(type="input_json_delta", partial_json='{"cmd"')

    cb_stop = _make_event("content_block_stop", index=0)

    msg_delta = _make_event("message_delta")
    msg_delta.delta = MagicMock(stop_reason="tool_use")
    msg_delta.usage = MagicMock(
        input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )

    events = [start, cb_start, cb_delta, cb_stop, msg_delta]

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _FakeStreamContextManager(events)

    with (
        patch("pi_ai.providers.anthropic.get_env_api_key", return_value="sk-ant-test"),
        patch("pi_ai.providers.anthropic._create_client", return_value=(mock_client, False)),
    ):
        collected = []
        async for event in stream_anthropic(model, context):
            collected.append(event)

    types = [e.type for e in collected]
    assert "toolcall_start" in types
    assert "toolcall_delta" in types
    assert "toolcall_end" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_stream_anthropic_thinking_block() -> None:
    """Test that thinking blocks are yielded as thinking events."""
    model = _make_model()
    context = _make_context("Solve this")

    start = _make_event("message_start")
    start.message = MagicMock()
    start.message.usage = MagicMock(
        input_tokens=5, output_tokens=0, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )

    # Thinking block
    cb_think_start = _make_event("content_block_start", index=0)
    cb_think_start.content_block = MagicMock(type="thinking")

    cb_think_delta = _make_event("content_block_delta", index=0)
    cb_think_delta.delta = MagicMock(type="thinking_delta", thinking="Let me think...")

    cb_think_sig = _make_event("content_block_delta", index=0)
    cb_think_sig.delta = MagicMock(type="signature_delta", signature="sig123")

    cb_think_stop = _make_event("content_block_stop", index=0)

    # Text block
    cb_text_start = _make_event("content_block_start", index=1)
    cb_text_start.content_block = MagicMock(type="text")

    cb_text_delta = _make_event("content_block_delta", index=1)
    cb_text_delta.delta = MagicMock(type="text_delta", text="The answer is 42.")

    cb_text_stop = _make_event("content_block_stop", index=1)

    msg_delta = _make_event("message_delta")
    msg_delta.delta = MagicMock(stop_reason="end_turn")
    msg_delta.usage = MagicMock(
        input_tokens=5, output_tokens=10, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )

    events = [
        start,
        cb_think_start,
        cb_think_delta,
        cb_think_sig,
        cb_think_stop,
        cb_text_start,
        cb_text_delta,
        cb_text_stop,
        msg_delta,
    ]

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _FakeStreamContextManager(events)

    with (
        patch("pi_ai.providers.anthropic.get_env_api_key", return_value="sk-ant-test"),
        patch("pi_ai.providers.anthropic._create_client", return_value=(mock_client, False)),
    ):
        collected = []
        async for event in stream_anthropic(model, context):
            collected.append(event)

    types = [e.type for e in collected]
    assert "thinking_start" in types
    assert "thinking_delta" in types
    assert "text_start" in types
    assert "text_delta" in types
    assert "done" in types


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


def test_resolve_cache_retention_explicit() -> None:
    assert _resolve_cache_retention("long") == "long"
    assert _resolve_cache_retention("short") == "short"
    assert _resolve_cache_retention(None) == "short"


def test_resolve_cache_retention_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("PI_CACHE_RETENTION", "long")
    assert _resolve_cache_retention(None) == "long"


def test_get_cache_control_none_for_none_retention() -> None:
    result = _get_cache_control("https://api.anthropic.com", "none")
    assert result is None


def test_get_cache_control_ephemeral() -> None:
    result = _get_cache_control("https://api.anthropic.com", "short")
    assert result is not None
    assert result["type"] == "ephemeral"
    assert "ttl" not in result


def test_get_cache_control_long_ttl() -> None:
    result = _get_cache_control("https://api.anthropic.com", "long")
    assert result is not None
    assert result.get("ttl") == "1h"


def test_merge_headers() -> None:
    result = _merge_headers({"a": "1"}, {"b": "2"}, None, {"a": "overridden"})
    assert result == {"a": "overridden", "b": "2"}


def test_is_oauth_token() -> None:
    assert _is_oauth_token("sk-ant-oat-abc123") is True
    assert _is_oauth_token("sk-ant-api03-xxx") is False


def test_supports_adaptive_thinking() -> None:
    assert _supports_adaptive_thinking("claude-opus-4-6-20250514") is True
    assert _supports_adaptive_thinking("claude-sonnet-4-5-20250512") is False


def test_map_thinking_level_to_effort() -> None:
    assert _map_thinking_level_to_effort("minimal") == "low"
    assert _map_thinking_level_to_effort("xhigh") == "max"
    assert _map_thinking_level_to_effort("high") == "high"
    assert _map_thinking_level_to_effort(None) == "high"


def test_normalize_tool_call_id() -> None:
    result = _normalize_tool_call_id("call|extra_info")
    assert "|" not in result
    # Special chars replaced with _
    assert "call_extra_info" in result or result.startswith("call")


def test_to_claude_code_name() -> None:
    assert _to_claude_code_name("bash") == "Bash"
    assert _to_claude_code_name("read") == "Read"
    assert _to_claude_code_name("unknown_tool") == "unknown_tool"


def test_convert_content_blocks_text_only() -> None:
    blocks: list[TextContent | ImageContent] = [TextContent(text="hello"), TextContent(text="world")]
    result = _convert_content_blocks(blocks)
    assert isinstance(result, str)
    assert "hello" in result
    assert "world" in result


def test_convert_content_blocks_with_image() -> None:
    blocks: list[TextContent | ImageContent] = [
        TextContent(text="look at this"),
        ImageContent(data="abc123", mime_type="image/png"),
    ]
    result = _convert_content_blocks(blocks)
    assert isinstance(result, list)
    assert any(b.get("type") == "image" for b in result)


def test_convert_content_blocks_image_only() -> None:
    blocks: list[TextContent | ImageContent] = [
        ImageContent(data="abc123", mime_type="image/png"),
    ]
    result = _convert_content_blocks(blocks)
    assert isinstance(result, list)
    # Placeholder text is added for image-only
    assert any(b.get("type") == "text" for b in result)


def test_convert_tools() -> None:
    tools = [
        Tool(
            name="bash",
            description="Run bash commands",
            parameters={"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]},
        )
    ]
    result = _convert_tools(tools, is_oauth=False)
    assert len(result) == 1
    assert result[0]["name"] == "bash"
    assert result[0]["input_schema"]["properties"] == {"cmd": {"type": "string"}}


def test_convert_tools_oauth() -> None:
    tools = [
        Tool(
            name="bash",
            description="Run bash commands",
            parameters={"type": "object"},
        )
    ]
    result = _convert_tools(tools, is_oauth=True)
    assert result[0]["name"] == "Bash"


def test_map_stop_reason() -> None:
    assert _map_stop_reason("end_turn") == "stop"
    assert _map_stop_reason("max_tokens") == "length"
    assert _map_stop_reason("tool_use") == "toolUse"
    assert _map_stop_reason("unknown") == "stop"


def test_build_messages_user_str() -> None:
    model = _make_model()
    messages = [UserMessage(content="hello")]
    result = _build_messages(messages, model, is_oauth=False, cache_control=None)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "hello"


def test_build_messages_user_content_blocks() -> None:
    model = _make_model()
    messages = [UserMessage(content=[TextContent(text="hello"), TextContent(text="world")])]
    result = _build_messages(messages, model, is_oauth=False, cache_control=None)
    assert len(result) == 1
    content = result[0]["content"]
    assert isinstance(content, list)
    assert any(b.get("text") == "hello" for b in content)


def test_build_messages_assistant_with_text() -> None:
    model = _make_model()
    assistant = AssistantMessage(
        content=[TextContent(text="I am here")],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        timestamp=1000,
    )
    messages: list[Any] = [UserMessage(content="hello"), assistant]
    result = _build_messages(messages, model, is_oauth=False, cache_control=None)
    assert any(m["role"] == "assistant" for m in result)


def test_build_messages_assistant_with_tool_call() -> None:
    model = _make_model()
    tc = ToolCall(id="call1", name="bash", arguments={"cmd": "ls"})
    assistant = AssistantMessage(
        content=[tc],
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
    messages: list[Any] = [UserMessage(content="run"), assistant, tool_result]
    result = _build_messages(messages, model, is_oauth=False, cache_control=None)
    roles = [m["role"] for m in result]
    assert "assistant" in roles
    # Tool results are wrapped in user messages
    assert roles.count("user") >= 2


def test_build_messages_with_thinking_content() -> None:
    model = _make_model()
    thinking = ThinkingContent(thinking="Let me think...", thinking_signature="sig123")
    assistant = AssistantMessage(
        content=[thinking, TextContent(text="The answer is 42")],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        timestamp=1000,
    )
    messages: list[Any] = [UserMessage(content="solve this"), assistant]
    result = _build_messages(messages, model, is_oauth=False, cache_control=None)
    assistant_msg = next(m for m in result if m["role"] == "assistant")
    assert isinstance(assistant_msg["content"], list)
    block_types = [b.get("type") for b in assistant_msg["content"]]
    assert "thinking" in block_types


def test_build_messages_cache_control_applied() -> None:
    model = _make_model()
    messages = [UserMessage(content="hello")]
    cache_ctrl = {"type": "ephemeral"}
    result = _build_messages(messages, model, is_oauth=False, cache_control=cache_ctrl)
    last = result[-1]
    assert last["role"] == "user"
    # String content wrapped in list with cache_control
    assert isinstance(last["content"], list)
    assert last["content"][0].get("cache_control") == cache_ctrl


def test_build_params_basic() -> None:
    model = _make_model()
    context = Context(messages=[UserMessage(content="hello")])
    params = _build_params(model, context, is_oauth=False, options=None)
    assert params["model"] == model.id
    assert "messages" in params
    assert params["stream"] is True


def test_build_params_with_system_prompt() -> None:
    model = _make_model()
    context = Context(
        messages=[UserMessage(content="hello")],
        system_prompt="You are a helpful assistant.",
    )
    params = _build_params(model, context, is_oauth=False, options=None)
    assert "system" in params
    system = params["system"]
    assert any(b.get("text") == "You are a helpful assistant." for b in system)


def test_build_params_oauth_system() -> None:
    model = _make_model()
    context = Context(messages=[UserMessage(content="hello")])
    params = _build_params(model, context, is_oauth=True, options=None)
    system = params["system"]
    assert any("Claude Code" in b.get("text", "") for b in system)
