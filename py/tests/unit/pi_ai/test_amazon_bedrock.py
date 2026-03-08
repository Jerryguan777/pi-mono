"""Tests for pi_ai.providers.amazon_bedrock — Amazon Bedrock Converse streaming provider."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pi_ai.providers.amazon_bedrock import (
    BedrockOptions,
    _build_additional_model_request_fields,
    _build_system_prompt,
    _convert_messages,
    _convert_tool_config,
    _create_image_block,
    _map_stop_reason,
    _map_thinking_level_to_effort,
    _normalize_tool_call_id,
    _resolve_cache_retention,
    _supports_adaptive_thinking,
    _supports_prompt_caching,
    _supports_thinking_signature,
    stream_bedrock,
)
from pi_ai.types import (
    AssistantMessage,
    Context,
    DoneEvent,
    ErrorEvent,
    Model,
    ModelCost,
    TextContent,
    ThinkingBudgets,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


def _model(**kwargs: Any) -> Model:
    defaults: dict[str, Any] = {
        "id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "provider": "amazon-bedrock",
        "api": "bedrock-converse-stream",
        "input": ["text", "image"],
        "reasoning": True,
        "cost": ModelCost(input=3.0, output=15.0, cache_read=0.3, cache_write=3.75),
        "max_tokens": 8192,
    }
    defaults.update(kwargs)
    return Model(**defaults)


# ---------------------------------------------------------------------------
# _map_stop_reason
# ---------------------------------------------------------------------------


class TestMapStopReason:
    def test_end_turn(self) -> None:
        assert _map_stop_reason("end_turn") == "stop"

    def test_stop_sequence(self) -> None:
        assert _map_stop_reason("stop_sequence") == "stop"

    def test_max_tokens(self) -> None:
        assert _map_stop_reason("max_tokens") == "length"

    def test_model_context_window_exceeded(self) -> None:
        assert _map_stop_reason("model_context_window_exceeded") == "length"

    def test_tool_use(self) -> None:
        assert _map_stop_reason("tool_use") == "toolUse"

    def test_unknown(self) -> None:
        assert _map_stop_reason("something_else") == "error"

    def test_none(self) -> None:
        assert _map_stop_reason(None) == "error"


# ---------------------------------------------------------------------------
# _normalize_tool_call_id
# ---------------------------------------------------------------------------


class TestNormalizeToolCallId:
    def test_valid_id_unchanged(self) -> None:
        assert _normalize_tool_call_id("tc_abc-123") == "tc_abc-123"

    def test_special_chars_replaced(self) -> None:
        assert _normalize_tool_call_id("tc:abc.123") == "tc_abc_123"

    def test_truncated_to_64(self) -> None:
        long_id = "a" * 100
        assert len(_normalize_tool_call_id(long_id)) == 64


# ---------------------------------------------------------------------------
# _resolve_cache_retention
# ---------------------------------------------------------------------------


class TestResolveCacheRetention:
    def test_explicit_value(self) -> None:
        assert _resolve_cache_retention("long") == "long"
        assert _resolve_cache_retention("none") == "none"

    def test_default_is_short(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PI_CACHE_RETENTION", raising=False)
        assert _resolve_cache_retention(None) == "short"

    def test_env_long(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PI_CACHE_RETENTION", "long")
        assert _resolve_cache_retention(None) == "long"


# ---------------------------------------------------------------------------
# _supports_* helpers
# ---------------------------------------------------------------------------


class TestSupportsHelpers:
    def test_supports_prompt_caching_by_cost(self) -> None:
        model = _model()
        assert _supports_prompt_caching(model) is True

    def test_supports_prompt_caching_claude_4(self) -> None:
        model = _model(id="anthropic.claude-4-sonnet", cost=ModelCost())
        assert _supports_prompt_caching(model) is True

    def test_supports_prompt_caching_false(self) -> None:
        model = _model(id="amazon.titan-text-express", cost=ModelCost())
        assert _supports_prompt_caching(model) is False

    def test_supports_thinking_signature_claude(self) -> None:
        assert _supports_thinking_signature(_model()) is True

    def test_supports_thinking_signature_non_claude(self) -> None:
        assert _supports_thinking_signature(_model(id="amazon.titan-text")) is False

    def test_supports_adaptive_thinking(self) -> None:
        assert _supports_adaptive_thinking("anthropic.claude-opus-4-6") is True
        assert _supports_adaptive_thinking("anthropic.claude-opus-4.6") is True
        assert _supports_adaptive_thinking("anthropic.claude-3-5-sonnet") is False


# ---------------------------------------------------------------------------
# _map_thinking_level_to_effort
# ---------------------------------------------------------------------------


class TestMapThinkingLevelToEffort:
    def test_minimal(self) -> None:
        assert _map_thinking_level_to_effort("minimal") == "low"

    def test_low(self) -> None:
        assert _map_thinking_level_to_effort("low") == "low"

    def test_medium(self) -> None:
        assert _map_thinking_level_to_effort("medium") == "medium"

    def test_high(self) -> None:
        assert _map_thinking_level_to_effort("high") == "high"

    def test_xhigh(self) -> None:
        assert _map_thinking_level_to_effort("xhigh") == "max"

    def test_none(self) -> None:
        assert _map_thinking_level_to_effort(None) == "high"


# ---------------------------------------------------------------------------
# _create_image_block
# ---------------------------------------------------------------------------


class TestCreateImageBlock:
    def test_jpeg(self) -> None:
        result = _create_image_block("image/jpeg", "AAAA")
        assert result["format"] == "jpeg"
        assert "bytes" in result["source"]

    def test_png(self) -> None:
        result = _create_image_block("image/png", "AAAA")
        assert result["format"] == "png"

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown image type"):
            _create_image_block("image/bmp", "AAAA")


# ---------------------------------------------------------------------------
# _convert_tool_config
# ---------------------------------------------------------------------------


class TestConvertToolConfig:
    def test_none_tools(self) -> None:
        assert _convert_tool_config(None, None) is None

    def test_empty_tools(self) -> None:
        assert _convert_tool_config([], None) is None

    def test_none_tool_choice(self) -> None:
        assert _convert_tool_config([Tool(name="bash")], "none") is None

    def test_auto_choice(self) -> None:
        result = _convert_tool_config(
            [Tool(name="bash", description="Run bash", parameters={"type": "object"})],
            "auto",
        )
        assert result is not None
        assert len(result["tools"]) == 1
        assert result["toolChoice"] == {"auto": {}}

    def test_any_choice(self) -> None:
        result = _convert_tool_config([Tool(name="bash")], "any")
        assert result is not None
        assert result["toolChoice"] == {"any": {}}

    def test_tool_specific_choice(self) -> None:
        result = _convert_tool_config(
            [Tool(name="bash")],
            {"type": "tool", "name": "bash"},
        )
        assert result is not None
        assert result["toolChoice"] == {"tool": {"name": "bash"}}


# ---------------------------------------------------------------------------
# _build_system_prompt
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_none_prompt(self) -> None:
        assert _build_system_prompt(None, _model(), "short") is None

    def test_empty_prompt(self) -> None:
        assert _build_system_prompt("", _model(), "short") is None

    def test_basic_prompt(self) -> None:
        result = _build_system_prompt("You are helpful", _model(), "none")
        assert result is not None
        assert result[0]["text"] == "You are helpful"
        assert len(result) == 1  # No cache point for "none"

    def test_with_cache_short(self) -> None:
        result = _build_system_prompt("Be helpful", _model(), "short")
        assert result is not None
        assert len(result) == 2  # Text + cache point
        assert "cachePoint" in result[1]

    def test_with_cache_long(self) -> None:
        result = _build_system_prompt("Be helpful", _model(), "long")
        assert result is not None
        cache_point = result[1]["cachePoint"]
        assert cache_point.get("ttl", {}).get("unit") == "HOURS"


# ---------------------------------------------------------------------------
# _build_additional_model_request_fields
# ---------------------------------------------------------------------------


class TestBuildAdditionalFields:
    def test_no_reasoning(self) -> None:
        model = _model()
        opts = BedrockOptions()
        assert _build_additional_model_request_fields(model, opts) is None

    def test_non_reasoning_model(self) -> None:
        model = _model(reasoning=False)
        opts = BedrockOptions(reasoning="high")
        assert _build_additional_model_request_fields(model, opts) is None

    def test_claude_adaptive(self) -> None:
        model = _model(id="anthropic.claude-opus-4-6")
        opts = BedrockOptions(reasoning="high")
        result = _build_additional_model_request_fields(model, opts)
        assert result is not None
        assert result["thinking"]["type"] == "adaptive"

    def test_claude_non_adaptive(self) -> None:
        model = _model()
        opts = BedrockOptions(reasoning="high")
        result = _build_additional_model_request_fields(model, opts)
        assert result is not None
        assert result["thinking"]["type"] == "enabled"
        assert "budget_tokens" in result["thinking"]
        assert "anthropic_beta" in result

    def test_claude_custom_budget(self) -> None:
        model = _model()
        opts = BedrockOptions(reasoning="high", thinking_budgets=ThinkingBudgets(high=50000))
        result = _build_additional_model_request_fields(model, opts)
        assert result is not None
        assert result["thinking"]["budget_tokens"] == 50000

    def test_non_claude_model(self) -> None:
        model = _model(id="amazon.titan-text")
        opts = BedrockOptions(reasoning="high")
        assert _build_additional_model_request_fields(model, opts) is None


# ---------------------------------------------------------------------------
# _convert_messages
# ---------------------------------------------------------------------------


class TestConvertMessages:
    def test_user_text(self) -> None:
        ctx = Context(messages=[UserMessage(content="hello")])
        result = _convert_messages(ctx, _model(), "none")
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"][0]["text"] == "hello"

    def test_assistant_text(self) -> None:
        ctx = Context(
            messages=[
                UserMessage(content="hi"),
                AssistantMessage(
                    content=[TextContent(text="hello back")],
                    provider="amazon-bedrock",
                    api="bedrock-converse-stream",
                    model="anthropic.claude-3-5-sonnet-20241022-v2:0",
                ),
            ]
        )
        result = _convert_messages(ctx, _model(), "none")
        assert len(result) == 2
        assert result[1]["role"] == "assistant"
        assert result[1]["content"][0]["text"] == "hello back"

    def test_tool_call_and_result(self) -> None:
        ctx = Context(
            messages=[
                UserMessage(content="hi"),
                AssistantMessage(
                    content=[ToolCall(id="tc_1", name="bash", arguments={"cmd": "ls"})],
                    provider="amazon-bedrock",
                    api="bedrock-converse-stream",
                    model="anthropic.claude-3-5-sonnet-20241022-v2:0",
                ),
                ToolResultMessage(
                    tool_call_id="tc_1",
                    tool_name="bash",
                    content=[TextContent(text="output")],
                ),
            ]
        )
        result = _convert_messages(ctx, _model(), "none")
        assert len(result) == 3
        assert result[1]["content"][0]["toolUse"]["name"] == "bash"
        # Tool result goes into a user message
        assert result[2]["role"] == "user"
        tr = result[2]["content"][0]["toolResult"]
        assert tr["toolUseId"] == "tc_1"

    def test_consecutive_tool_results_grouped(self) -> None:
        ctx = Context(
            messages=[
                UserMessage(content="hi"),
                AssistantMessage(
                    content=[
                        ToolCall(id="tc_1", name="bash", arguments={}),
                        ToolCall(id="tc_2", name="read", arguments={}),
                    ],
                    provider="amazon-bedrock",
                    api="bedrock-converse-stream",
                    model="anthropic.claude-3-5-sonnet-20241022-v2:0",
                ),
                ToolResultMessage(tool_call_id="tc_1", tool_name="bash", content=[TextContent(text="out1")]),
                ToolResultMessage(tool_call_id="tc_2", tool_name="read", content=[TextContent(text="out2")]),
            ]
        )
        result = _convert_messages(ctx, _model(), "none")
        # User, assistant, then both tool results in one user message
        assert len(result) == 3
        assert len(result[2]["content"]) == 2

    def test_thinking_content_with_signature(self) -> None:
        model = _model()
        ctx = Context(
            messages=[
                UserMessage(content="think"),
                AssistantMessage(
                    content=[ThinkingContent(thinking="deep thought", thinking_signature="sig123")],
                    provider="amazon-bedrock",
                    api="bedrock-converse-stream",
                    model=model.id,
                ),
            ]
        )
        result = _convert_messages(ctx, model, "none")
        reasoning = result[1]["content"][0]["reasoningContent"]
        assert reasoning["reasoningText"]["text"] == "deep thought"
        assert reasoning["reasoningText"]["signature"] == "sig123"


# ---------------------------------------------------------------------------
# stream_bedrock
# ---------------------------------------------------------------------------


class TestStreamBedrock:
    """Tests for stream_bedrock with mocked boto3."""

    @staticmethod
    def _make_mock_client(
        converse_stream_return: Any = None,
        converse_stream_side_effect: Any = None,
    ) -> MagicMock:
        mock_client = MagicMock()
        if converse_stream_side_effect is not None:
            mock_client.converse_stream.side_effect = converse_stream_side_effect
        elif converse_stream_return is not None:
            mock_client.converse_stream.return_value = converse_stream_return
        return mock_client

    @patch("pi_ai.providers.amazon_bedrock.boto3")
    async def test_text_stream(self, mock_boto3: MagicMock) -> None:
        events_list: list[dict[str, Any]] = [
            {"messageStart": {"role": "assistant"}},
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Hello "}}},
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "world!"}}},
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}}},
        ]
        mock_boto3.client.return_value = self._make_mock_client(converse_stream_return={"stream": events_list})
        stream = stream_bedrock(_model(), Context(messages=[UserMessage(content="hello")]), BedrockOptions())
        events = []
        async for event in stream:
            events.append(event)
        types = [e.type for e in events]
        assert types[0] == "start"
        assert "text_start" in types
        assert "text_delta" in types
        assert "text_end" in types
        assert types[-1] == "done"
        done = events[-1]
        assert isinstance(done, DoneEvent)
        assert done.reason == "stop"
        text_blocks = [b for b in done.message.content if isinstance(b, TextContent)]
        assert text_blocks[0].text == "Hello world!"
        assert done.message.usage.input == 10
        assert done.message.usage.output == 5

    @patch("pi_ai.providers.amazon_bedrock.boto3")
    async def test_tool_call_stream(self, mock_boto3: MagicMock) -> None:
        events_list: list[dict[str, Any]] = [
            {"messageStart": {"role": "assistant"}},
            {
                "contentBlockStart": {
                    "contentBlockIndex": 0,
                    "start": {"toolUse": {"toolUseId": "tc_1", "name": "bash"}},
                }
            },
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"toolUse": {"input": '{"cmd": "ls"}'}}}},
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "tool_use"}},
            {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5}}},
        ]
        mock_boto3.client.return_value = self._make_mock_client(converse_stream_return={"stream": events_list})
        stream = stream_bedrock(_model(), Context(messages=[UserMessage(content="run ls")]), BedrockOptions())
        events = []
        async for event in stream:
            events.append(event)
        types = [e.type for e in events]
        assert "toolcall_start" in types
        assert "toolcall_delta" in types
        assert "toolcall_end" in types
        assert types[-1] == "done"
        done = events[-1]
        assert isinstance(done, DoneEvent)
        assert done.reason == "toolUse"

    @patch("pi_ai.providers.amazon_bedrock.boto3")
    async def test_thinking_stream(self, mock_boto3: MagicMock) -> None:
        events_list: list[dict[str, Any]] = [
            {"messageStart": {"role": "assistant"}},
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"reasoningContent": {"text": "Let me think..."}}}},
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"reasoningContent": {"signature": "sig123"}}}},
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"contentBlockDelta": {"contentBlockIndex": 1, "delta": {"text": "Here is my answer"}}},
            {"contentBlockStop": {"contentBlockIndex": 1}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 20}}},
        ]
        mock_boto3.client.return_value = self._make_mock_client(converse_stream_return={"stream": events_list})
        stream = stream_bedrock(
            _model(), Context(messages=[UserMessage(content="think")]), BedrockOptions(reasoning="high")
        )
        events = []
        async for event in stream:
            events.append(event)
        types = [e.type for e in events]
        assert "thinking_start" in types
        assert "thinking_delta" in types
        assert "thinking_end" in types
        assert "text_start" in types
        assert "text_end" in types
        assert types[-1] == "done"

    @patch("pi_ai.providers.amazon_bedrock.boto3")
    async def test_error_events(self, mock_boto3: MagicMock) -> None:
        events_list: list[dict[str, Any]] = [
            {"internalServerException": {"message": "Something broke"}},
        ]
        mock_boto3.client.return_value = self._make_mock_client(converse_stream_return={"stream": events_list})
        stream = stream_bedrock(_model(), Context(messages=[UserMessage(content="hi")]), BedrockOptions())
        events = []
        async for event in stream:
            events.append(event)
        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert len(error_events) == 1
        assert error_events[0].error.error_message is not None
        assert "Something broke" in error_events[0].error.error_message

    @patch("pi_ai.providers.amazon_bedrock.boto3")
    async def test_boto3_exception(self, mock_boto3: MagicMock) -> None:
        mock_boto3.client.return_value = self._make_mock_client(
            converse_stream_side_effect=Exception("Connection refused")
        )
        stream = stream_bedrock(_model(), Context(messages=[UserMessage(content="hi")]), BedrockOptions())
        events = []
        async for event in stream:
            events.append(event)
        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert len(error_events) == 1
        assert error_events[0].error.error_message is not None
        assert "Connection refused" in error_events[0].error.error_message
