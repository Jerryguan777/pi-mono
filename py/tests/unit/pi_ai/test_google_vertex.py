"""Tests for pi_ai.providers.google_vertex — Google Vertex AI streaming provider."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pi_ai.providers.google_vertex import (
    GoogleVertexOptions,
    _get_gemini_3_thinking_level,
    _get_google_budget,
    _is_gemini_3_flash_model,
    _is_gemini_3_pro_model,
    _resolve_location,
    _resolve_project,
    stream_google_vertex,
)
from pi_ai.types import (
    Context,
    DoneEvent,
    ErrorEvent,
    Model,
    ModelCost,
    TextContent,
    UserMessage,
)


def _model(**kwargs: Any) -> Model:
    defaults: dict[str, Any] = {
        "id": "gemini-2.0-flash",
        "provider": "google-vertex",
        "api": "google-vertex",
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
) -> SimpleNamespace:
    parts = []
    if text is not None:
        part = SimpleNamespace(text=text, function_call=None, thought_signature=None)
        if thought is not None:
            part.thought = thought
        parts.append(part)
    if function_call is not None:
        part = SimpleNamespace(text=None, function_call=function_call, thought_signature=None)
        parts.append(part)

    content = SimpleNamespace(parts=parts) if parts else None
    candidate = SimpleNamespace(content=content, finish_reason=finish_reason)
    return SimpleNamespace(candidates=[candidate], usage_metadata=usage_metadata)


# ---------------------------------------------------------------------------
# _resolve_project / _resolve_location
# ---------------------------------------------------------------------------


class TestResolveProject:
    def test_from_options(self) -> None:
        opts = GoogleVertexOptions(project="my-project")
        assert _resolve_project(opts) == "my-project"

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        assert _resolve_project(None) == "env-project"

    def test_from_gcloud_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.setenv("GCLOUD_PROJECT", "gcloud-project")
        assert _resolve_project(None) == "gcloud-project"

    def test_missing_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GCLOUD_PROJECT", raising=False)
        with pytest.raises(ValueError, match="project ID"):
            _resolve_project(None)


class TestResolveLocation:
    def test_from_options(self) -> None:
        opts = GoogleVertexOptions(location="us-central1")
        assert _resolve_location(opts) == "us-central1"

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
        assert _resolve_location(None) == "europe-west1"

    def test_missing_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        with pytest.raises(ValueError, match="location"):
            _resolve_location(None)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_is_gemini_3_pro_model(self) -> None:
        assert _is_gemini_3_pro_model(_model(id="gemini-3-pro")) is True
        assert _is_gemini_3_pro_model(_model(id="gemini-2.0-flash")) is False

    def test_is_gemini_3_flash_model(self) -> None:
        assert _is_gemini_3_flash_model(_model(id="gemini-3-flash")) is True
        assert _is_gemini_3_flash_model(_model(id="gemini-2.0-flash")) is False

    def test_get_gemini_3_thinking_level_pro(self) -> None:
        model = _model(id="gemini-3-pro")
        assert _get_gemini_3_thinking_level("minimal", model) == "LOW"
        assert _get_gemini_3_thinking_level("high", model) == "HIGH"

    def test_get_gemini_3_thinking_level_flash(self) -> None:
        model = _model(id="gemini-3-flash")
        assert _get_gemini_3_thinking_level("minimal", model) == "MINIMAL"
        assert _get_gemini_3_thinking_level("medium", model) == "MEDIUM"

    def test_get_google_budget(self) -> None:
        model = _model(id="gemini-2.5-pro")
        assert _get_google_budget(model, "minimal") == 128
        assert _get_google_budget(model, "high") == 32768


# ---------------------------------------------------------------------------
# stream_google_vertex
# ---------------------------------------------------------------------------


class TestStreamGoogleVertex:
    @patch("pi_ai.providers.google_vertex.genai")
    @patch("pi_ai.providers.google_vertex.asyncio.to_thread")
    async def test_text_stream(self, mock_to_thread: MagicMock, mock_genai: MagicMock) -> None:
        model = _model()
        ctx = Context(messages=[UserMessage(content="hello")])
        options = GoogleVertexOptions(project="test-proj", location="us-central1")

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

        mock_to_thread.return_value = chunks
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        stream = stream_google_vertex(model, ctx, options)
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
        text_blocks = [b for b in done.message.content if isinstance(b, TextContent)]
        assert text_blocks[0].text == "Hello world!"

    @patch("pi_ai.providers.google_vertex.genai")
    @patch("pi_ai.providers.google_vertex.asyncio.to_thread")
    async def test_missing_project_error(
        self,
        mock_to_thread: MagicMock,
        mock_genai: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GCLOUD_PROJECT", raising=False)

        model = _model()
        ctx = Context(messages=[UserMessage(content="hello")])
        options = GoogleVertexOptions(location="us-central1")  # No project

        stream = stream_google_vertex(model, ctx, options)
        events = []
        async for event in stream:
            events.append(event)

        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert len(error_events) == 1
        assert error_events[0].error.error_message is not None
        assert "project ID" in error_events[0].error.error_message

    @patch("pi_ai.providers.google_vertex.genai")
    @patch("pi_ai.providers.google_vertex.asyncio.to_thread")
    async def test_tool_call_stream(self, mock_to_thread: MagicMock, mock_genai: MagicMock) -> None:
        model = _model()
        ctx = Context(messages=[UserMessage(content="run command")])
        options = GoogleVertexOptions(project="test-proj", location="us-central1")

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

        mock_to_thread.return_value = chunks
        mock_genai.Client.return_value = MagicMock()

        stream = stream_google_vertex(model, ctx, options)
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
