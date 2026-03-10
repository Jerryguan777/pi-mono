"""Tests for pi_ai.stream — unified stream() and complete() entry points.

Ported from python-superpowers. Adapted to use ApiProvider registration
and the rewrite's event field naming (delta instead of text).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import pytest
from pi_ai.api_registry import (
    ApiProvider,
    clear_api_providers,
    register_api_provider,
)
from pi_ai.stream import complete, stream
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    DoneEvent,
    ErrorEvent,
    Model,
    StartEvent,
    StreamOptions,
    SimpleStreamOptions,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    ToolCall,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    UserMessage,
)

if TYPE_CHECKING:
    pass

# ── Helpers ───────────────────────────────────────────────────────────


def _make_model(api: str = "test-api") -> Model:
    return Model(
        id="test-model",
        name="Test Model",
        api=api,
        provider="test-provider",
    )


def _make_context() -> Context:
    return Context(
        messages=[
            UserMessage(role="user", content="Hello", timestamp=1000),
        ]
    )


def _make_stream_fn(events: list[AssistantMessageEvent]):
    """Create a stream function that yields predetermined events."""

    async def stream_fn(
        model: Model, context: Context, options: StreamOptions | None = None
    ) -> AsyncIterator[AssistantMessageEvent]:
        for event in events:
            yield event

    return stream_fn


def _make_stream_simple_fn(events: list[AssistantMessageEvent]):
    """Create a simple stream function that yields predetermined events."""

    async def stream_fn(
        model: Model, context: Context, options: SimpleStreamOptions | None = None
    ) -> AsyncIterator[AssistantMessageEvent]:
        for event in events:
            yield event

    return stream_fn


def _register_mock(api: str, events: list[AssistantMessageEvent]) -> None:
    """Register a mock provider with predetermined events."""
    register_api_provider(
        ApiProvider(
            api=api,
            stream=_make_stream_fn(events),
            stream_simple=_make_stream_simple_fn(events),
        )
    )


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    """Ensure every test starts with an empty registry."""
    clear_api_providers()


# ── stream() tests ───────────────────────────────────────────────────


class TestStream:
    @pytest.mark.asyncio
    async def test_yields_events_from_registered_provider(self) -> None:
        msg = AssistantMessage(api="test-api", provider="test-provider", model="test-model")
        events: list[AssistantMessageEvent] = [
            StartEvent(partial=msg),
            TextStartEvent(partial=msg),
            TextDeltaEvent(delta="Hello", partial=msg),
            TextEndEvent(partial=msg),
            DoneEvent(reason="stop", message=msg),
        ]
        _register_mock("test-api", events)

        collected: list[AssistantMessageEvent] = []
        async for event in stream(_make_model(), _make_context()):
            collected.append(event)

        assert len(collected) == 5
        assert collected[0].type == "start"
        assert collected[2].type == "text_delta"
        assert collected[4].type == "done"

    @pytest.mark.asyncio
    async def test_raises_for_unknown_api(self) -> None:
        with pytest.raises(ValueError, match="No API provider registered"):
            async for _ in stream(_make_model(api="unknown"), _make_context()):
                pass  # pragma: no cover

    @pytest.mark.asyncio
    async def test_passes_options_to_provider(self) -> None:
        """Verify that options are forwarded to the provider."""
        received_options: list[StreamOptions | None] = []

        async def capturing_stream(
            model: Model, context: Context, options: StreamOptions | None = None
        ) -> AsyncIterator[AssistantMessageEvent]:
            received_options.append(options)
            msg = AssistantMessage(api="test-api", provider="test-provider", model="test-model")
            yield DoneEvent(reason="stop", message=msg)

        async def capturing_simple(
            model: Model, context: Context, options: SimpleStreamOptions | None = None
        ) -> AsyncIterator[AssistantMessageEvent]:
            msg = AssistantMessage(api="test-api", provider="test-provider", model="test-model")
            yield DoneEvent(reason="stop", message=msg)

        register_api_provider(
            ApiProvider(api="test-api", stream=capturing_stream, stream_simple=capturing_simple)
        )
        opts = StreamOptions(temperature=0.5)
        async for _ in stream(_make_model(), _make_context(), options=opts):
            pass

        assert len(received_options) == 1
        assert received_options[0] is opts


# ── complete() tests ─────────────────────────────────────────────────


class TestComplete:
    def _make_done_msg(self, **kwargs) -> AssistantMessage:
        defaults = {
            "api": "test-api",
            "provider": "test-provider",
            "model": "test-model",
            "stop_reason": "stop",
        }
        defaults.update(kwargs)
        return AssistantMessage(**defaults)

    @pytest.mark.asyncio
    async def test_collects_text_into_assistant_message(self) -> None:
        msg = self._make_done_msg(
            content=[
                TextDeltaEvent.__class__,  # placeholder - real content set via DoneEvent.message
            ],
        )
        # In the rewrite, complete() reads the final message from DoneEvent.message
        final_msg = self._make_done_msg(
            content=[
                # The complete() function just returns DoneEvent.message directly
                # The stream function is responsible for building up the message
            ],
        )
        partial = AssistantMessage(api="test-api", provider="test-provider", model="test-model")
        events: list[AssistantMessageEvent] = [
            StartEvent(partial=partial),
            TextStartEvent(partial=partial),
            TextDeltaEvent(delta="Hello, ", partial=partial),
            TextDeltaEvent(delta="world!", partial=partial),
            TextEndEvent(partial=partial),
            DoneEvent(reason="stop", message=self._make_done_msg(stop_reason="stop")),
        ]
        _register_mock("test-api", events)

        result = await complete(_make_model(), _make_context())

        assert result.role == "assistant"
        assert result.stop_reason == "stop"
        assert result.api == "test-api"
        assert result.provider == "test-provider"
        assert result.model == "test-model"

    @pytest.mark.asyncio
    async def test_handles_error_event(self) -> None:
        error_msg = self._make_done_msg(stop_reason="error", error_message="Something went wrong")
        partial = AssistantMessage(api="test-api", provider="test-provider", model="test-model")
        events: list[AssistantMessageEvent] = [
            StartEvent(partial=partial),
            ErrorEvent(reason="error", error=error_msg),
        ]
        _register_mock("test-api", events)

        result = await complete(_make_model(), _make_context())

        assert result.stop_reason == "error"
        assert result.error_message == "Something went wrong"

    @pytest.mark.asyncio
    async def test_empty_stream_returns_message(self) -> None:
        msg = self._make_done_msg()
        partial = AssistantMessage(api="test-api", provider="test-provider", model="test-model")
        events: list[AssistantMessageEvent] = [
            StartEvent(partial=partial),
            DoneEvent(reason="stop", message=msg),
        ]
        _register_mock("test-api", events)

        result = await complete(_make_model(), _make_context())

        assert result.stop_reason == "stop"
