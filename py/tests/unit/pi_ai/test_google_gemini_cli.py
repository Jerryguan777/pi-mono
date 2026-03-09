"""Tests for pi_ai.providers.google_gemini_cli — Gemini CLI / Antigravity provider."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pi_ai.providers.google_gemini_cli import (
    ANTIGRAVITY_SYSTEM_INSTRUCTION,
    GoogleGeminiCliOptions,
    _extract_error_message,
    _get_gemini_cli_thinking_level,
    _is_claude_thinking_model,
    _is_retryable_error,
    _ThinkingConfig,
    build_request,
    extract_retry_delay,
    stream_google_gemini_cli,
)
from pi_ai.types import (
    Context,
    DoneEvent,
    ErrorEvent,
    Model,
    ModelCost,
    TextContent,
    Tool,
    UserMessage,
)


def _model(**kwargs: Any) -> Model:
    defaults: dict[str, Any] = {
        "id": "gemini-2.0-flash",
        "provider": "google-gemini-cli",
        "api": "google-gemini-cli",
        "input": ["text"],
        "reasoning": False,
        "cost": ModelCost(),
        "max_tokens": 8192,
        "base_url": "",
    }
    defaults.update(kwargs)
    return Model(**defaults)


# ---------------------------------------------------------------------------
# extract_retry_delay
# ---------------------------------------------------------------------------


class TestExtractRetryDelay:
    def test_retry_after_header_seconds(self) -> None:
        delay = extract_retry_delay("", headers={"retry-after": "5"})
        assert delay is not None
        # 5000ms + 1000ms buffer = 6000
        assert delay == 6000

    def test_retry_after_header_fractional(self) -> None:
        delay = extract_retry_delay("", headers={"retry-after": "2.5"})
        assert delay is not None
        # ceil(2500 + 1000) = 3500
        assert delay == 3500

    def test_x_ratelimit_reset_after_header(self) -> None:
        delay = extract_retry_delay("", headers={"x-ratelimit-reset-after": "10"})
        assert delay is not None
        assert delay == 11000

    def test_body_quota_reset_seconds(self) -> None:
        delay = extract_retry_delay("Your quota will reset after 39s")
        assert delay is not None
        assert delay == 40000

    def test_body_quota_reset_hms(self) -> None:
        delay = extract_retry_delay("Your quota will reset after 1h2m3s")
        assert delay is not None
        expected_ms = ((1 * 60 + 2) * 60 + 3) * 1000
        assert delay == expected_ms + 1000

    def test_body_quota_reset_minutes_seconds(self) -> None:
        delay = extract_retry_delay("Your quota will reset after 10m15s")
        assert delay is not None
        expected_ms = (10 * 60 + 15) * 1000
        assert delay == expected_ms + 1000

    def test_body_please_retry_seconds(self) -> None:
        delay = extract_retry_delay("Please retry in 5s")
        assert delay is not None
        assert delay == 6000

    def test_body_please_retry_ms(self) -> None:
        delay = extract_retry_delay("Please retry in 500ms")
        assert delay is not None
        assert delay == 1500  # ceil(500 + 1000) = 1500

    def test_body_retry_delay_json_field(self) -> None:
        body = '{"error": {"details": [{"retryDelay": "34.074824224s"}]}}'
        delay = extract_retry_delay(body)
        assert delay is not None
        # ceil(34074.824224 + 1000) = 35075
        assert delay == 35075

    def test_no_delay_found(self) -> None:
        assert extract_retry_delay("Some other error") is None

    def test_none_headers(self) -> None:
        assert extract_retry_delay("no info", headers=None) is None

    def test_empty_string(self) -> None:
        assert extract_retry_delay("") is None


# ---------------------------------------------------------------------------
# _is_retryable_error
# ---------------------------------------------------------------------------


class TestIsRetryableError:
    def test_rate_limit_status(self) -> None:
        assert _is_retryable_error(429, "") is True

    def test_server_error_statuses(self) -> None:
        assert _is_retryable_error(500, "") is True
        assert _is_retryable_error(502, "") is True
        assert _is_retryable_error(503, "") is True
        assert _is_retryable_error(504, "") is True

    def test_non_retryable_status(self) -> None:
        assert _is_retryable_error(400, "") is False
        assert _is_retryable_error(401, "") is False
        assert _is_retryable_error(403, "") is False
        assert _is_retryable_error(404, "") is False

    def test_retryable_by_body_pattern(self) -> None:
        assert _is_retryable_error(200, "resource exhausted") is True
        assert _is_retryable_error(200, "rate limit exceeded") is True
        assert _is_retryable_error(200, "service unavailable") is True

    def test_not_retryable_body(self) -> None:
        assert _is_retryable_error(200, "invalid request") is False


# ---------------------------------------------------------------------------
# _extract_error_message
# ---------------------------------------------------------------------------


class TestExtractErrorMessage:
    def test_json_error_message(self) -> None:
        body = json.dumps({"error": {"message": "Model not found"}})
        assert _extract_error_message(body) == "Model not found"

    def test_plain_text_fallback(self) -> None:
        assert _extract_error_message("something went wrong") == "something went wrong"

    def test_malformed_json(self) -> None:
        assert _extract_error_message("{bad json") == "{bad json"

    def test_json_without_error_key(self) -> None:
        body = json.dumps({"status": "error"})
        assert _extract_error_message(body) == body


# ---------------------------------------------------------------------------
# _is_claude_thinking_model
# ---------------------------------------------------------------------------


class TestIsClaudeThinkingModel:
    def test_claude_thinking(self) -> None:
        assert _is_claude_thinking_model("claude-3.5-sonnet-thinking") is True

    def test_claude_non_thinking(self) -> None:
        assert _is_claude_thinking_model("claude-3.5-sonnet") is False

    def test_non_claude(self) -> None:
        assert _is_claude_thinking_model("gemini-2.0-flash") is False


# ---------------------------------------------------------------------------
# _get_gemini_cli_thinking_level
# ---------------------------------------------------------------------------


class TestGetGeminiCliThinkingLevel:
    def test_3pro_minimal(self) -> None:
        assert _get_gemini_cli_thinking_level("minimal", "gemini-3-pro") == "LOW"

    def test_3pro_high(self) -> None:
        assert _get_gemini_cli_thinking_level("high", "gemini-3-pro") == "HIGH"

    def test_other_model_mapping(self) -> None:
        assert _get_gemini_cli_thinking_level("minimal", "gemini-2.5-flash") == "MINIMAL"
        assert _get_gemini_cli_thinking_level("low", "gemini-2.5-flash") == "LOW"
        assert _get_gemini_cli_thinking_level("medium", "gemini-2.5-flash") == "MEDIUM"
        assert _get_gemini_cli_thinking_level("high", "gemini-2.5-flash") == "HIGH"


# ---------------------------------------------------------------------------
# build_request
# ---------------------------------------------------------------------------


class TestBuildRequest:
    def test_basic_request(self) -> None:
        model = _model()
        ctx = Context(
            system_prompt="You are helpful",
            messages=[UserMessage(content="hello")],
        )
        result = build_request(model, ctx, "project-123")

        assert result["project"] == "project-123"
        assert result["model"] == "gemini-2.0-flash"
        assert result["userAgent"] == "pi-coding-agent"
        assert "requestId" in result
        assert "request" in result
        req = result["request"]
        assert "systemInstruction" in req
        assert req["systemInstruction"]["parts"][0]["text"] == "You are helpful"

    def test_antigravity_request(self) -> None:
        model = _model(provider="google-antigravity")
        ctx = Context(messages=[UserMessage(content="hi")])
        result = build_request(model, ctx, "proj-1", is_antigravity=True)

        assert result["userAgent"] == "antigravity"
        assert result.get("requestType") == "agent"
        req = result["request"]
        sys_parts = req["systemInstruction"]["parts"]
        assert any(ANTIGRAVITY_SYSTEM_INSTRUCTION in p.get("text", "") for p in sys_parts)

    def test_with_tools(self) -> None:
        model = _model()
        ctx = Context(
            messages=[UserMessage(content="hi")],
            tools=[Tool(name="bash", description="Run bash", parameters={"type": "object"})],
        )
        options = GoogleGeminiCliOptions(tool_choice="auto")
        result = build_request(model, ctx, "proj-1", options)
        req = result["request"]
        assert "tools" in req
        assert "toolConfig" in req

    def test_with_thinking_config(self) -> None:
        model = _model(reasoning=True)
        ctx = Context(messages=[UserMessage(content="think")])
        options = GoogleGeminiCliOptions(
            thinking=_ThinkingConfig(enabled=True, level="HIGH"),
        )
        result = build_request(model, ctx, "proj-1", options)
        gen_config = result["request"]["generationConfig"]
        assert "thinkingConfig" in gen_config
        assert gen_config["thinkingConfig"]["includeThoughts"] is True
        assert gen_config["thinkingConfig"]["thinkingLevel"] == "HIGH"

    def test_with_thinking_budget(self) -> None:
        model = _model(reasoning=True)
        ctx = Context(messages=[UserMessage(content="think")])
        options = GoogleGeminiCliOptions(
            thinking=_ThinkingConfig(enabled=True, budget_tokens=4096),
        )
        result = build_request(model, ctx, "proj-1", options)
        gen_config = result["request"]["generationConfig"]
        assert gen_config["thinkingConfig"]["thinkingBudget"] == 4096

    def test_session_id(self) -> None:
        model = _model()
        ctx = Context(messages=[UserMessage(content="hi")])
        options = GoogleGeminiCliOptions(session_id="sess-123")
        result = build_request(model, ctx, "proj-1", options)
        assert result["request"]["sessionId"] == "sess-123"

    def test_temperature_and_max_tokens(self) -> None:
        model = _model()
        ctx = Context(messages=[UserMessage(content="hi")])
        options = GoogleGeminiCliOptions(temperature=0.7, max_tokens=1024)
        result = build_request(model, ctx, "proj-1", options)
        gen_config = result["request"]["generationConfig"]
        assert gen_config["temperature"] == 0.7
        assert gen_config["maxOutputTokens"] == 1024

    def test_claude_model_uses_parameters(self) -> None:
        model = _model(id="claude-3.5-sonnet")
        ctx = Context(
            messages=[UserMessage(content="hi")],
            tools=[Tool(name="bash", description="Run bash", parameters={"type": "object"})],
        )
        result = build_request(model, ctx, "proj-1")
        req = result["request"]
        decls = req["tools"][0]["functionDeclarations"]
        assert "parameters" in decls[0]
        assert "parametersJsonSchema" not in decls[0]


# ---------------------------------------------------------------------------
# stream_google_gemini_cli
# ---------------------------------------------------------------------------


def _make_sse_bytes(data: dict[str, Any]) -> bytes:
    """Create SSE-formatted bytes for a single data event."""
    return f"data: {json.dumps(data)}\n\n".encode()


def _make_response_chunk(
    text: str | None = None,
    thought: bool | None = None,
    function_call: dict[str, Any] | None = None,
    finish_reason: str | None = None,
    usage_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a Gemini CLI SSE response dict."""
    parts = []
    if text is not None:
        part: dict[str, Any] = {"text": text}
        if thought is not None:
            part["thought"] = thought
        parts.append(part)
    if function_call is not None:
        parts.append({"functionCall": function_call})

    candidate: dict[str, Any] = {
        "content": {"parts": parts} if parts else {},
    }
    if finish_reason:
        candidate["finishReason"] = finish_reason

    response: dict[str, Any] = {"candidates": [candidate]}
    if usage_metadata:
        response["usageMetadata"] = usage_metadata

    return {"response": response}


class TestStreamGoogleGeminiCli:
    def _api_key_json(self, token: str = "test-token", project_id: str = "proj-1") -> str:
        return json.dumps({"token": token, "projectId": project_id})

    @patch("pi_ai.providers.google_gemini_cli.httpx.AsyncClient")
    async def test_text_stream(self, mock_client_cls: MagicMock) -> None:
        """Test basic text streaming via SSE."""
        model = _model()
        ctx = Context(messages=[UserMessage(content="hello")])
        options = GoogleGeminiCliOptions(api_key=self._api_key_json())

        # Build mock SSE response
        sse_data = (
            _make_sse_bytes(_make_response_chunk(text="Hello "))
            + _make_sse_bytes(_make_response_chunk(text="world!"))
            + _make_sse_bytes(
                _make_response_chunk(
                    finish_reason="STOP",
                    usage_metadata={
                        "promptTokenCount": 10,
                        "candidatesTokenCount": 5,
                        "totalTokenCount": 15,
                    },
                )
            )
        )

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = _async_bytes_iter(sse_data)
        mock_response.aclose = AsyncMock()

        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.build_request.return_value = MagicMock()
        mock_instance.send = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_instance

        stream = stream_google_gemini_cli(model, ctx, options)
        events = []
        async for event in stream:
            events.append(event)

        types = [e.type for e in events]
        assert "start" in types
        assert "text_start" in types
        assert "text_delta" in types
        assert "text_end" in types
        assert types[-1] == "done"

        done = events[-1]
        assert isinstance(done, DoneEvent)
        text_blocks = [b for b in done.message.content if isinstance(b, TextContent)]
        assert text_blocks[0].text == "Hello world!"

    @patch("pi_ai.providers.google_gemini_cli.httpx.AsyncClient")
    async def test_tool_call_stream(self, mock_client_cls: MagicMock) -> None:
        model = _model()
        ctx = Context(
            messages=[UserMessage(content="run ls")],
            tools=[Tool(name="bash", description="Run bash", parameters={})],
        )
        options = GoogleGeminiCliOptions(api_key=self._api_key_json())

        sse_data = _make_sse_bytes(
            _make_response_chunk(function_call={"name": "bash", "args": {"cmd": "ls"}})
        ) + _make_sse_bytes(
            _make_response_chunk(
                finish_reason="STOP",
                usage_metadata={"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
            )
        )

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = _async_bytes_iter(sse_data)
        mock_response.aclose = AsyncMock()

        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.build_request.return_value = MagicMock()
        mock_instance.send = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_instance

        stream = stream_google_gemini_cli(model, ctx, options)
        events = []
        async for event in stream:
            events.append(event)

        types = [e.type for e in events]
        assert "toolcall_start" in types
        assert "toolcall_end" in types
        assert types[-1] == "done"
        done = events[-1]
        assert isinstance(done, DoneEvent)
        assert done.reason == "toolUse"

    async def test_no_api_key_error(self) -> None:
        model = _model()
        ctx = Context(messages=[UserMessage(content="hi")])
        options = GoogleGeminiCliOptions()  # No api_key

        stream = stream_google_gemini_cli(model, ctx, options)
        events = []
        async for event in stream:
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)
        assert events[0].error.error_message is not None
        assert "OAuth" in events[0].error.error_message

    async def test_invalid_api_key_json(self) -> None:
        model = _model()
        ctx = Context(messages=[UserMessage(content="hi")])
        options = GoogleGeminiCliOptions(api_key="not-json")

        stream = stream_google_gemini_cli(model, ctx, options)
        events = []
        async for event in stream:
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)
        assert events[0].error.error_message is not None
        assert "Invalid" in events[0].error.error_message


def _async_bytes_iter(data: bytes) -> Any:
    """Create a callable that returns an async iterator over bytes chunks."""

    async def _iter() -> Any:
        yield data

    return _iter
