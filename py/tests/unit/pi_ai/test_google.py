"""Tests for pi_ai.providers.google — Google Generative AI streaming provider."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from pi_ai.providers.google import (
    GoogleOptions,
    GoogleThinkingConfig,
    _get_gemini3_thinking_level,
    _get_google_budget,
    _is_gemini_3_flash_model,
    _is_gemini_3_pro_model,
    stream_google,
)
from pi_ai.types import (
    Context,
    DoneEvent,
    ErrorEvent,
    Model,
    ModelCost,
    TextContent,
    ThinkingBudgets,
    Tool,
    UserMessage,
)


def _model(**kwargs: Any) -> Model:
    defaults: dict[str, Any] = {
        "id": "gemini-2.0-flash",
        "provider": "google",
        "api": "google-generative-ai",
        "input": ["text"],
        "reasoning": False,
        "cost": ModelCost(),
        "max_tokens": 8192,
    }
    defaults.update(kwargs)
    return Model(**defaults)


def _make_chunk(
    text: str | None = None,
    thought: bool | None = None,
    function_call: Any = None,
    finish_reason: str | None = None,
    usage_metadata: Any = None,
    thought_signature: str | None = None,
) -> SimpleNamespace:
    """Create a mock chunk as returned by google-genai SDK."""
    parts = []
    if text is not None:
        part = SimpleNamespace(text=text, function_call=None)
        if thought is not None:
            part.thought = thought
        if thought_signature is not None:
            part.thought_signature = thought_signature
        parts.append(part)
    if function_call is not None:
        part = SimpleNamespace(text=None, function_call=function_call, thought_signature=None)
        parts.append(part)

    content = SimpleNamespace(parts=parts) if parts else None
    candidate = SimpleNamespace(
        content=content,
        finish_reason=finish_reason,
    )
    chunk = SimpleNamespace(
        candidates=[candidate],
        usage_metadata=usage_metadata,
    )
    return chunk


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_is_gemini_3_pro_model(self) -> None:
        assert _is_gemini_3_pro_model(_model(id="gemini-3-pro")) is True
        assert _is_gemini_3_pro_model(_model(id="gemini-2.0-flash")) is False

    def test_is_gemini_3_flash_model(self) -> None:
        assert _is_gemini_3_flash_model(_model(id="gemini-3-flash")) is True
        assert _is_gemini_3_flash_model(_model(id="gemini-2.0-flash")) is False

    def test_get_gemini3_thinking_level_pro(self) -> None:
        model = _model(id="gemini-3-pro")
        assert _get_gemini3_thinking_level("minimal", model) == "LOW"
        assert _get_gemini3_thinking_level("low", model) == "LOW"
        assert _get_gemini3_thinking_level("medium", model) == "HIGH"
        assert _get_gemini3_thinking_level("high", model) == "HIGH"

    def test_get_gemini3_thinking_level_flash(self) -> None:
        model = _model(id="gemini-3-flash")
        assert _get_gemini3_thinking_level("minimal", model) == "MINIMAL"
        assert _get_gemini3_thinking_level("low", model) == "LOW"
        assert _get_gemini3_thinking_level("medium", model) == "MEDIUM"
        assert _get_gemini3_thinking_level("high", model) == "HIGH"

    def test_get_google_budget_25_pro(self) -> None:
        model = _model(id="gemini-2.5-pro-latest")
        assert _get_google_budget(model, "minimal") == 128
        assert _get_google_budget(model, "low") == 2048
        assert _get_google_budget(model, "medium") == 8192
        assert _get_google_budget(model, "high") == 32768

    def test_get_google_budget_25_flash(self) -> None:
        model = _model(id="gemini-2.5-flash")
        assert _get_google_budget(model, "high") == 24576

    def test_get_google_budget_unknown_model(self) -> None:
        model = _model(id="gemini-3.0-flash")
        assert _get_google_budget(model, "high") == -1

    def test_get_google_budget_custom_budgets(self) -> None:
        model = _model(id="gemini-2.5-pro")
        budgets = ThinkingBudgets(high=99999)
        assert _get_google_budget(model, "high", budgets) == 99999


# ---------------------------------------------------------------------------
# stream_google — text response
# ---------------------------------------------------------------------------


class TestStreamGoogle:
    @patch("pi_ai.providers.google.genai")
    async def test_text_stream(self, mock_genai: MagicMock) -> None:
        """Test basic text streaming: start -> text_start -> text_delta -> text_end -> done."""
        model = _model()
        ctx = Context(messages=[UserMessage(content="hello")])
        options = GoogleOptions(api_key="test-key")

        chunks = [
            _make_chunk(text="Hello "),
            _make_chunk(text="world!"),
            _make_chunk(
                finish_reason="STOP",
                usage_metadata=SimpleNamespace(
                    prompt_token_count=10,
                    candidates_token_count=5,
                    thoughts_token_count=0,
                    cached_content_token_count=0,
                    total_token_count=15,
                ),
            ),
        ]

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = chunks
        mock_genai.Client.return_value = mock_client

        stream = stream_google(model, ctx, options)
        events = []
        async for event in stream:
            events.append(event)

        types = [e.type for e in events]
        assert types[0] == "start"
        assert "text_start" in types
        assert "text_delta" in types
        assert "text_end" in types
        assert types[-1] == "done"

        # Verify the final message
        done = events[-1]
        assert isinstance(done, DoneEvent)
        assert done.reason == "stop"
        text_blocks = [b for b in done.message.content if isinstance(b, TextContent)]
        assert len(text_blocks) == 1
        assert text_blocks[0].text == "Hello world!"

    @patch("pi_ai.providers.google.genai")
    async def test_tool_call_stream(self, mock_genai: MagicMock) -> None:
        """Test streaming with function call."""
        model = _model()
        ctx = Context(
            messages=[UserMessage(content="list files")],
            tools=[Tool(name="bash", description="Run bash", parameters={})],
        )
        options = GoogleOptions(api_key="test-key")

        fc = SimpleNamespace(name="bash", args={"cmd": "ls"}, id=None)
        chunks = [
            _make_chunk(function_call=fc),
            _make_chunk(
                finish_reason="STOP",
                usage_metadata=SimpleNamespace(
                    prompt_token_count=10,
                    candidates_token_count=5,
                    thoughts_token_count=0,
                    cached_content_token_count=0,
                    total_token_count=15,
                ),
            ),
        ]

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = chunks
        mock_genai.Client.return_value = mock_client

        stream = stream_google(model, ctx, options)
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

    @patch("pi_ai.providers.google.genai")
    async def test_no_api_key_error(self, mock_genai: MagicMock) -> None:
        """Test that missing API key produces an error event."""
        model = _model()
        ctx = Context(messages=[UserMessage(content="hi")])
        options = GoogleOptions()  # No api_key

        stream = stream_google(model, ctx, options)
        events = []
        async for event in stream:
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)
        assert events[0].error.error_message is not None
        assert "No API key" in events[0].error.error_message

    @patch("pi_ai.providers.google.genai")
    async def test_exception_during_stream(self, mock_genai: MagicMock) -> None:
        """Test error handling when SDK raises exception."""
        model = _model()
        ctx = Context(messages=[UserMessage(content="hi")])
        options = GoogleOptions(api_key="test-key")

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.side_effect = RuntimeError("SDK error")
        mock_genai.Client.return_value = mock_client

        stream = stream_google(model, ctx, options)
        events = []
        async for event in stream:
            events.append(event)

        # Should get start + error, or just error
        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert len(error_events) == 1
        assert error_events[0].error.error_message is not None
        assert "SDK error" in error_events[0].error.error_message

    @patch("pi_ai.providers.google.genai")
    async def test_thinking_then_text(self, mock_genai: MagicMock) -> None:
        """Test thinking block followed by text block."""
        model = _model(reasoning=True)
        ctx = Context(messages=[UserMessage(content="think about this")])
        options = GoogleOptions(
            api_key="test-key",
            thinking=GoogleThinkingConfig(enabled=True, level="HIGH"),
        )

        chunks = [
            _make_chunk(text="thinking...", thought=True),
            _make_chunk(text="Here is my answer"),
            _make_chunk(
                finish_reason="STOP",
                usage_metadata=SimpleNamespace(
                    prompt_token_count=10,
                    candidates_token_count=20,
                    thoughts_token_count=5,
                    cached_content_token_count=0,
                    total_token_count=35,
                ),
            ),
        ]

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = chunks
        mock_genai.Client.return_value = mock_client

        stream = stream_google(model, ctx, options)
        events = []
        async for event in stream:
            events.append(event)

        types = [e.type for e in events]
        assert "thinking_start" in types
        assert "thinking_delta" in types
        assert "thinking_end" in types
        assert "text_start" in types
        assert "text_delta" in types
        assert "text_end" in types
        assert types[-1] == "done"
