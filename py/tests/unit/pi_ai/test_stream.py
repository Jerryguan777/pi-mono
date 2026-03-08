"""Tests for pi_ai.stream."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from pi_ai.api_registry import ApiProvider, clear_api_providers, register_api_provider
from pi_ai.stream import complete, stream
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    DoneEvent,
    Model,
    ModelCost,
    SimpleStreamOptions,
    StartEvent,
    StreamOptions,
    TextContent,
    TextDeltaEvent,
)


def _make_model(api: str = "test-api") -> Model:
    return Model(id="test", name="Test", api=api, provider="test", cost=ModelCost())


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    clear_api_providers()


class TestStream:
    def test_no_provider_raises(self) -> None:
        model = _make_model("unregistered")
        with pytest.raises(ValueError, match="No API provider registered"):
            stream(model, Context())

    async def test_stream_yields_events(self) -> None:
        final_msg = AssistantMessage(content=[TextContent(text="hi")], stop_reason="stop")

        async def fake_stream(
            model: Model, context: Context, options: StreamOptions | None = None
        ) -> AsyncIterator[AssistantMessageEvent]:
            yield StartEvent()
            yield TextDeltaEvent(delta="hi")
            yield DoneEvent(message=final_msg)

        async def fake_simple(
            model: Model, context: Context, options: SimpleStreamOptions | None = None
        ) -> AsyncIterator[AssistantMessageEvent]:
            yield DoneEvent(message=final_msg)

        register_api_provider(ApiProvider(api="test-api", stream=fake_stream, stream_simple=fake_simple))

        events = []
        async for event in stream(_make_model(), Context()):
            events.append(event)

        assert len(events) == 3
        assert isinstance(events[0], StartEvent)
        assert isinstance(events[2], DoneEvent)


class TestComplete:
    async def test_complete_returns_message(self) -> None:
        final_msg = AssistantMessage(content=[TextContent(text="answer")], stop_reason="stop")

        async def fake_stream(
            model: Model, context: Context, options: StreamOptions | None = None
        ) -> AsyncIterator[AssistantMessageEvent]:
            yield StartEvent()
            yield DoneEvent(message=final_msg)

        async def fake_simple(
            model: Model, context: Context, options: SimpleStreamOptions | None = None
        ) -> AsyncIterator[AssistantMessageEvent]:
            yield DoneEvent(message=final_msg)

        register_api_provider(ApiProvider(api="test-api", stream=fake_stream, stream_simple=fake_simple))

        result = await complete(_make_model(), Context())
        assert result.content[0].text == "answer"  # type: ignore[union-attr]
