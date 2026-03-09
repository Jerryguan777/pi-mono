"""Tests for pi_agent.proxy — proxy event parsing and stream reconstruction."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_agent.proxy import (
    _make_partial,
    _parse_proxy_event,
    _parse_usage,
    _process_proxy_event,
    _process_sse_line,
    _serialize_content_block,
    _serialize_context,
    _serialize_message,
    stream_proxy,
)
from pi_agent.types import (
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
)
from pi_ai.types import (
    AssistantMessage,
    Context,
    DoneEvent,
    ErrorEvent,
    ImageContent,
    Model,
    StartEvent,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ThinkingContent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    ToolCall,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultMessage,
    Usage,
    UserMessage,
)


def make_model() -> Model:
    return Model(id="claude-3", api="anthropic-messages", provider="anthropic")


def make_partial(model: Model | None = None) -> AssistantMessage:
    return _make_partial(model or make_model())


class TestMakePartial:
    def test_creates_assistant_message(self) -> None:
        model = make_model()
        partial = _make_partial(model)
        assert isinstance(partial, AssistantMessage)
        assert partial.api == model.api
        assert partial.provider == model.provider
        assert partial.model == model.id

    def test_default_stop_reason(self) -> None:
        partial = _make_partial(make_model())
        assert partial.stop_reason == "stop"


class TestParseUsage:
    def test_none_returns_empty_usage(self) -> None:
        usage = _parse_usage(None)
        assert isinstance(usage, Usage)
        assert usage.input == 0

    def test_dict_parsing(self) -> None:
        data = {
            "input": 100,
            "output": 200,
            "cacheRead": 50,
            "cacheWrite": 25,
            "totalTokens": 375,
            "cost": {
                "input": 0.001,
                "output": 0.002,
                "cacheRead": 0.0,
                "cacheWrite": 0.0,
                "total": 0.003,
            },
        }
        usage = _parse_usage(data)
        assert usage.input == 100
        assert usage.output == 200
        assert usage.cache_read == 50
        assert usage.cache_write == 25
        assert usage.total_tokens == 375
        assert usage.cost.total == 0.003

    def test_non_dict_returns_empty_usage(self) -> None:
        usage = _parse_usage("not a dict")
        assert isinstance(usage, Usage)


class TestParseProxyEvent:
    def test_parse_start(self) -> None:
        event = _parse_proxy_event({"type": "start"})
        assert isinstance(event, ProxyStartEvent)

    def test_parse_text_start(self) -> None:
        event = _parse_proxy_event({"type": "text_start", "contentIndex": 1})
        assert isinstance(event, ProxyTextStartEvent)
        assert event.content_index == 1

    def test_parse_text_delta(self) -> None:
        event = _parse_proxy_event({"type": "text_delta", "contentIndex": 0, "delta": "hello"})
        assert isinstance(event, ProxyTextDeltaEvent)
        assert event.delta == "hello"

    def test_parse_text_end(self) -> None:
        event = _parse_proxy_event({"type": "text_end", "contentIndex": 0, "contentSignature": "sig"})
        assert isinstance(event, ProxyTextEndEvent)
        assert event.content_signature == "sig"

    def test_parse_thinking_start(self) -> None:
        event = _parse_proxy_event({"type": "thinking_start", "contentIndex": 0})
        assert isinstance(event, ProxyThinkingStartEvent)

    def test_parse_thinking_delta(self) -> None:
        event = _parse_proxy_event({"type": "thinking_delta", "contentIndex": 0, "delta": "I think"})
        assert isinstance(event, ProxyThinkingDeltaEvent)
        assert event.delta == "I think"

    def test_parse_thinking_end(self) -> None:
        event = _parse_proxy_event({"type": "thinking_end", "contentIndex": 0})
        assert isinstance(event, ProxyThinkingEndEvent)

    def test_parse_toolcall_start(self) -> None:
        event = _parse_proxy_event({"type": "toolcall_start", "contentIndex": 0, "id": "tc1", "toolName": "bash"})
        assert isinstance(event, ProxyToolCallStartEvent)
        assert event.id == "tc1"
        assert event.tool_name == "bash"

    def test_parse_toolcall_delta(self) -> None:
        event = _parse_proxy_event({"type": "toolcall_delta", "contentIndex": 0, "delta": '{"cmd"'})
        assert isinstance(event, ProxyToolCallDeltaEvent)
        assert event.delta == '{"cmd"'

    def test_parse_toolcall_end(self) -> None:
        event = _parse_proxy_event({"type": "toolcall_end", "contentIndex": 0})
        assert isinstance(event, ProxyToolCallEndEvent)

    def test_parse_done(self) -> None:
        event = _parse_proxy_event({"type": "done", "reason": "stop", "usage": None})
        assert isinstance(event, ProxyDoneEvent)
        assert event.reason == "stop"

    def test_parse_error(self) -> None:
        event = _parse_proxy_event({"type": "error", "reason": "error", "errorMessage": "oops"})
        assert isinstance(event, ProxyErrorEvent)
        assert event.error_message == "oops"

    def test_parse_unknown_returns_none(self) -> None:
        result = _parse_proxy_event({"type": "unknown_event"})
        assert result is None


class TestProcessProxyEvent:
    def test_start_event(self) -> None:
        partial = make_partial()
        partial_json: dict[int, str] = {}
        result = _process_proxy_event(ProxyStartEvent(), partial, partial_json)
        assert isinstance(result, StartEvent)

    def test_text_flow(self) -> None:
        partial = make_partial()
        partial_json: dict[int, str] = {}

        # text_start
        result = _process_proxy_event(ProxyTextStartEvent(content_index=0), partial, partial_json)
        assert isinstance(result, TextStartEvent)
        assert isinstance(partial.content[0], TextContent)
        assert partial.content[0].text == ""

        # text_delta
        result = _process_proxy_event(ProxyTextDeltaEvent(content_index=0, delta="hello "), partial, partial_json)
        assert isinstance(result, TextDeltaEvent)
        assert isinstance(partial.content[0], TextContent) and partial.content[0].text == "hello "

        # text_delta again
        result = _process_proxy_event(ProxyTextDeltaEvent(content_index=0, delta="world"), partial, partial_json)
        assert isinstance(result, TextDeltaEvent)
        assert isinstance(partial.content[0], TextContent) and partial.content[0].text == "hello world"

        # text_end
        result = _process_proxy_event(
            ProxyTextEndEvent(content_index=0, content_signature="sig"), partial, partial_json
        )
        assert isinstance(result, TextEndEvent)
        assert isinstance(partial.content[0], TextContent) and partial.content[0].text_signature == "sig"

    def test_thinking_flow(self) -> None:
        partial = make_partial()
        partial_json: dict[int, str] = {}

        result = _process_proxy_event(ProxyThinkingStartEvent(content_index=0), partial, partial_json)
        assert isinstance(result, ThinkingStartEvent)
        assert isinstance(partial.content[0], ThinkingContent)

        result = _process_proxy_event(
            ProxyThinkingDeltaEvent(content_index=0, delta="let me think"), partial, partial_json
        )
        assert isinstance(result, ThinkingDeltaEvent)
        assert isinstance(partial.content[0], ThinkingContent) and partial.content[0].thinking == "let me think"

        result = _process_proxy_event(ProxyThinkingEndEvent(content_index=0), partial, partial_json)
        assert isinstance(result, ThinkingEndEvent)

    def test_toolcall_flow(self) -> None:
        partial = make_partial()
        partial_json: dict[int, str] = {}

        result = _process_proxy_event(
            ProxyToolCallStartEvent(content_index=0, id="tc1", tool_name="bash"), partial, partial_json
        )
        assert isinstance(result, ToolCallStartEvent)
        assert isinstance(partial.content[0], ToolCall)
        assert partial.content[0].name == "bash"

        result = _process_proxy_event(
            ProxyToolCallDeltaEvent(content_index=0, delta='{"cmd": "ls"}'), partial, partial_json
        )
        assert isinstance(result, ToolCallDeltaEvent)
        assert isinstance(partial.content[0], ToolCall) and partial.content[0].arguments.get("cmd") == "ls"

        result = _process_proxy_event(ProxyToolCallEndEvent(content_index=0), partial, partial_json)
        assert isinstance(result, ToolCallEndEvent)

    def test_done_event(self) -> None:
        partial = make_partial()
        partial_json: dict[int, str] = {}
        usage = Usage(input=10, output=20)
        result = _process_proxy_event(ProxyDoneEvent(reason="stop", usage=usage), partial, partial_json)
        assert isinstance(result, DoneEvent)
        assert result.reason == "stop"
        assert partial.usage.input == 10

    def test_error_event(self) -> None:
        partial = make_partial()
        partial_json: dict[int, str] = {}
        result = _process_proxy_event(
            ProxyErrorEvent(reason="error", error_message="test error"), partial, partial_json
        )
        assert isinstance(result, ErrorEvent)
        assert partial.error_message == "test error"

    def test_text_delta_on_wrong_type_raises(self) -> None:
        partial = make_partial()
        partial.content = [ThinkingContent(thinking="")]
        partial_json: dict[int, str] = {}
        with pytest.raises(ValueError, match="non-text"):
            _process_proxy_event(ProxyTextDeltaEvent(content_index=0, delta="oops"), partial, partial_json)

    def test_thinking_delta_on_wrong_type_raises(self) -> None:
        partial = make_partial()
        partial.content = [TextContent(text="")]
        partial_json: dict[int, str] = {}
        with pytest.raises(ValueError, match="non-thinking"):
            _process_proxy_event(ProxyThinkingDeltaEvent(content_index=0, delta="oops"), partial, partial_json)

    def test_multiple_content_blocks(self) -> None:
        """Multiple content blocks at different indices."""
        partial = make_partial()
        partial_json: dict[int, str] = {}

        # First block at index 0
        _process_proxy_event(ProxyTextStartEvent(content_index=0), partial, partial_json)
        # Second block at index 1
        _process_proxy_event(ProxyThinkingStartEvent(content_index=1), partial, partial_json)

        assert isinstance(partial.content[0], TextContent)
        assert isinstance(partial.content[1], ThinkingContent)


class TestStreamProxy:
    @pytest.mark.asyncio
    async def test_successful_stream(self) -> None:
        """stream_proxy should reconstruct LLM events from SSE lines."""
        model = make_model()
        ctx = Context(system_prompt="sys")
        opts = ProxyStreamOptions(auth_token="test-token", proxy_url="http://localhost:8080")

        # Build fake SSE lines
        sse_lines = [
            'data: {"type": "start"}\n\n',
            'data: {"type": "text_start", "contentIndex": 0}\n\n',
            'data: {"type": "text_delta", "contentIndex": 0, "delta": "Hello!"}\n\n',
            'data: {"type": "text_end", "contentIndex": 0}\n\n',
            'data: {"type": "done", "reason": "stop", "usage": {"input": 10, "output": 5, "totalTokens": 15}}\n\n',
        ]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"

        async def mock_aiter_text() -> Any:
            for line in sse_lines:
                yield line

        mock_response.aiter_text = mock_aiter_text
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        events = []
        with patch("pi_agent.proxy.httpx.AsyncClient", return_value=mock_client):
            async for event in stream_proxy(model, ctx, opts):
                events.append(event)

        event_types = [type(e).__name__ for e in events]
        assert "StartEvent" in event_types
        assert "TextStartEvent" in event_types
        assert "TextDeltaEvent" in event_types
        assert "DoneEvent" in event_types
        done_event = next(e for e in events if isinstance(e, DoneEvent))
        assert done_event.reason == "stop"

    @pytest.mark.asyncio
    async def test_http_error_response(self) -> None:
        """Non-200 response should yield an error event."""
        model = make_model()
        ctx = Context(system_prompt="sys")
        opts = ProxyStreamOptions(auth_token="tok", proxy_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.reason_phrase = "Unauthorized"
        mock_response.aread = AsyncMock(return_value=b'{"error": "Invalid token"}')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        events = []
        with patch("pi_agent.proxy.httpx.AsyncClient", return_value=mock_client):
            async for event in stream_proxy(model, ctx, opts):
                events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)


class TestSerializeContentBlock:
    def test_text_content(self) -> None:
        block = TextContent(text="hello")
        result = _serialize_content_block(block)
        assert result == {"type": "text", "text": "hello"}

    def test_text_content_with_signature(self) -> None:
        block = TextContent(text="hello", text_signature="sig123")
        result = _serialize_content_block(block)
        assert result["textSignature"] == "sig123"

    def test_thinking_content(self) -> None:
        block = ThinkingContent(thinking="I think")
        result = _serialize_content_block(block)
        assert result == {"type": "thinking", "thinking": "I think"}

    def test_thinking_content_with_signature(self) -> None:
        block = ThinkingContent(thinking="I think", thinking_signature="sig")
        result = _serialize_content_block(block)
        assert result["thinkingSignature"] == "sig"

    def test_image_content(self) -> None:
        block = ImageContent(data="base64data", mime_type="image/png")
        result = _serialize_content_block(block)
        assert result == {"type": "image", "data": "base64data", "mimeType": "image/png"}

    def test_tool_call(self) -> None:
        block = ToolCall(id="tc1", name="bash", arguments={"cmd": "ls"})
        result = _serialize_content_block(block)
        assert result == {"type": "toolCall", "id": "tc1", "name": "bash", "arguments": {"cmd": "ls"}}

    def test_tool_call_with_thought_signature(self) -> None:
        block = ToolCall(id="tc1", name="bash", arguments={}, thought_signature="sig")
        result = _serialize_content_block(block)
        assert result["thoughtSignature"] == "sig"

    def test_unknown_type_returns_empty(self) -> None:
        result = _serialize_content_block("not a block")
        assert result == {}


class TestSerializeMessage:
    def test_user_message_string_content(self) -> None:
        msg = UserMessage(content="hello", timestamp=1000.0)
        result = _serialize_message(msg)
        assert result["role"] == "user"
        assert result["content"] == "hello"
        assert result["timestamp"] == 1000.0

    def test_user_message_list_content(self) -> None:
        msg = UserMessage(content=[TextContent(text="hi")], timestamp=2000.0)
        result = _serialize_message(msg)
        assert result["role"] == "user"
        assert isinstance(result["content"], list)
        assert result["content"][0] == {"type": "text", "text": "hi"}

    def test_assistant_message(self) -> None:
        msg = AssistantMessage(
            api="anthropic-messages",
            provider="anthropic",
            model="claude-3",
            stop_reason="stop",
            timestamp=3000.0,
            content=[TextContent(text="answer")],
        )
        result = _serialize_message(msg)
        assert result["role"] == "assistant"
        assert result["stopReason"] == "stop"
        assert result["content"][0]["text"] == "answer"

    def test_assistant_message_with_error(self) -> None:
        msg = AssistantMessage(
            api="anthropic-messages",
            provider="anthropic",
            model="claude-3",
            stop_reason="error",
            timestamp=4000.0,
            error_message="oops",
        )
        result = _serialize_message(msg)
        assert result["errorMessage"] == "oops"

    def test_tool_result_message(self) -> None:
        msg = ToolResultMessage(
            tool_call_id="tc1",
            tool_name="bash",
            content=[TextContent(text="result")],
            is_error=False,
            timestamp=5000.0,
        )
        result = _serialize_message(msg)
        assert result["role"] == "toolResult"
        assert result["toolCallId"] == "tc1"
        assert result["toolName"] == "bash"
        assert result["isError"] is False

    def test_unknown_message_returns_empty(self) -> None:
        result = _serialize_message("not a message")  # type: ignore[arg-type]
        assert result == {}


class TestSerializeContext:
    def test_minimal_context(self) -> None:
        ctx = Context(messages=[])
        result = _serialize_context(ctx)
        assert result["messages"] == []
        assert "systemPrompt" not in result
        assert "tools" not in result

    def test_context_with_system_prompt(self) -> None:
        ctx = Context(messages=[], system_prompt="You are helpful")
        result = _serialize_context(ctx)
        assert result["systemPrompt"] == "You are helpful"

    def test_context_with_messages(self) -> None:
        ctx = Context(messages=[UserMessage(content="hi", timestamp=1.0)])
        result = _serialize_context(ctx)
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"


class TestProcessSseLine:
    def test_non_data_line_returns_none(self) -> None:
        partial = _make_partial(make_model())
        result = _process_sse_line("event: message", partial, {})
        assert result is None

    def test_empty_data_returns_none(self) -> None:
        partial = _make_partial(make_model())
        result = _process_sse_line("data: ", partial, {})
        assert result is None

    def test_invalid_json_returns_none(self) -> None:
        partial = _make_partial(make_model())
        result = _process_sse_line("data: {bad json}", partial, {})
        assert result is None

    def test_valid_start_event(self) -> None:
        partial = _make_partial(make_model())
        result = _process_sse_line('data: {"type": "start"}', partial, {})
        assert isinstance(result, StartEvent)

    def test_unknown_event_type_returns_none(self) -> None:
        partial = _make_partial(make_model())
        result = _process_sse_line('data: {"type": "unknown"}', partial, {})
        assert result is None

    @pytest.mark.asyncio
    async def test_abort_signal_stops_streaming(self) -> None:
        """Setting abort signal should stop streaming and yield error."""
        import asyncio

        model = make_model()
        ctx = Context(system_prompt="sys")
        signal = asyncio.Event()
        signal.set()  # Pre-set to abort immediately
        opts = ProxyStreamOptions(auth_token="tok", proxy_url="http://localhost:8080", signal=signal)

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"

        async def mock_aiter_text() -> Any:
            yield 'data: {"type": "start"}\n\n'

        mock_response.aiter_text = mock_aiter_text
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        events = []
        with patch("pi_agent.proxy.httpx.AsyncClient", return_value=mock_client):
            async for event in stream_proxy(model, ctx, opts):
                events.append(event)

        # Should have ended with error event due to abort
        assert any(isinstance(e, ErrorEvent) for e in events)

    @pytest.mark.asyncio
    async def test_network_error_yields_error_event(self) -> None:
        """Network error during streaming should yield ErrorEvent."""
        import httpx

        model = make_model()
        ctx = Context(system_prompt="sys")
        opts = ProxyStreamOptions(auth_token="tok", proxy_url="http://localhost:8080")

        mock_client = MagicMock()
        mock_client.stream = MagicMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        events = []
        with patch("pi_agent.proxy.httpx.AsyncClient", return_value=mock_client):
            async for event in stream_proxy(model, ctx, opts):
                events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)
