"""Integration tests for stream() dispatch path."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import cast

import pytest

from pi_ai.api_registry import (
    ApiProvider,
    StreamFunction,
    StreamSimpleFunction,
    clear_api_providers,
    register_api_provider,
)
from pi_ai.stream import complete, complete_simple, stream, stream_simple
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    DoneEvent,
    ErrorEvent,
    Model,
    ModelCost,
    SimpleStreamOptions,
    StartEvent,
    StreamOptions,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    UserMessage,
)


@pytest.fixture(autouse=True)
def clean_registry() -> Generator[None, None, None]:
    """Clear the API provider registry before and after each test."""
    clear_api_providers()
    yield
    clear_api_providers()


def make_model(api: str = "test-api") -> Model:
    """Create a minimal test model."""
    return Model(
        id="test-model",
        name="Test Model",
        api=api,
        provider="test-provider",
        base_url="https://example.com",
        cost=ModelCost(),
    )


def make_context() -> Context:
    """Create a minimal test context."""
    return Context(
        system_prompt=None,
        messages=[UserMessage(content="Hello")],
    )


def make_mock_stream(*events: AssistantMessageEvent) -> StreamFunction:
    """Return a stream function that yields the given events."""

    async def _stream(
        model: Model,
        context: Context,
        options: StreamOptions | None = None,
    ) -> AsyncGenerator[AssistantMessageEvent, None]:
        for event in events:
            yield event

    return cast(StreamFunction, _stream)


def make_mock_stream_simple(*events: AssistantMessageEvent) -> StreamSimpleFunction:
    """Return a stream_simple function that yields the given events."""

    async def _stream_simple(
        model: Model,
        context: Context,
        options: SimpleStreamOptions | None = None,
    ) -> AsyncGenerator[AssistantMessageEvent, None]:
        for event in events:
            yield event

    return cast(StreamSimpleFunction, _stream_simple)


def make_done_event(text: str = "Hello!") -> DoneEvent:
    """Create a DoneEvent with an AssistantMessage containing the given text."""
    from pi_ai.types import TextContent

    msg = AssistantMessage(
        content=[TextContent(text=text)],
        api="test-api",
        provider="test-provider",
        model="test-model",
    )
    return DoneEvent(reason="stop", message=msg)


@pytest.mark.asyncio
async def test_stream_dispatches_to_registered_provider() -> None:
    """stream() should forward events from a registered provider."""
    done = make_done_event("Hi!")
    start = StartEvent()

    register_api_provider(
        ApiProvider(
            api="test-api",
            stream=make_mock_stream(start, done),
            stream_simple=make_mock_stream_simple(),
        )
    )

    model = make_model("test-api")
    context = make_context()

    events = []
    async for event in stream(model, context):
        events.append(event)

    assert len(events) == 2
    assert isinstance(events[0], StartEvent)
    assert isinstance(events[1], DoneEvent)


@pytest.mark.asyncio
async def test_stream_unregistered_raises() -> None:
    """stream() should raise ValueError for an unregistered api."""
    model = make_model("nonexistent-api")
    context = make_context()

    with pytest.raises(ValueError, match="No API provider registered for api: nonexistent-api"):
        async for _ in stream(model, context):
            pass


@pytest.mark.asyncio
async def test_complete_collects_done_event_message() -> None:
    """complete() should return the AssistantMessage from the DoneEvent."""
    done = make_done_event("Result text")

    register_api_provider(
        ApiProvider(
            api="test-api",
            stream=make_mock_stream(StartEvent(), done),
            stream_simple=make_mock_stream_simple(),
        )
    )

    model = make_model("test-api")
    context = make_context()

    msg = await complete(model, context)

    assert isinstance(msg, AssistantMessage)
    from pi_ai.types import TextContent

    assert any(isinstance(c, TextContent) and c.text == "Result text" for c in msg.content)


@pytest.mark.asyncio
async def test_complete_raises_on_empty_stream() -> None:
    """complete() should raise RuntimeError if the stream produces no done/error event."""
    register_api_provider(
        ApiProvider(
            api="test-api",
            stream=make_mock_stream(),
            stream_simple=make_mock_stream_simple(),
        )
    )

    model = make_model("test-api")
    context = make_context()

    with pytest.raises(RuntimeError, match="Stream ended without a done or error event"):
        await complete(model, context)


@pytest.mark.asyncio
async def test_stream_error_event() -> None:
    """stream() should yield ErrorEvent and complete() should return the error message."""
    error_msg = AssistantMessage(
        api="test-api",
        provider="test-provider",
        model="test-model",
        stop_reason="error",
        error_message="Something went wrong",
    )
    error_event = ErrorEvent(reason="error", error=error_msg)

    register_api_provider(
        ApiProvider(
            api="test-api",
            stream=make_mock_stream(error_event),
            stream_simple=make_mock_stream_simple(),
        )
    )

    model = make_model("test-api")
    context = make_context()

    # complete() should return the error message, not raise
    result = await complete(model, context)
    assert isinstance(result, AssistantMessage)
    assert result.error_message == "Something went wrong"


@pytest.mark.asyncio
async def test_stream_simple_dispatch() -> None:
    """stream_simple() should forward events from the stream_simple function."""
    done = make_done_event("Simple result")

    register_api_provider(
        ApiProvider(
            api="test-api",
            stream=make_mock_stream(),
            stream_simple=make_mock_stream_simple(done),
        )
    )

    model = make_model("test-api")
    context = make_context()

    events = []
    async for event in stream_simple(model, context):
        events.append(event)

    assert len(events) == 1
    assert isinstance(events[0], DoneEvent)


@pytest.mark.asyncio
async def test_complete_simple_collects_done_event() -> None:
    """complete_simple() should collect the DoneEvent message."""
    done = make_done_event("Simple complete")

    register_api_provider(
        ApiProvider(
            api="test-api",
            stream=make_mock_stream(),
            stream_simple=make_mock_stream_simple(done),
        )
    )

    model = make_model("test-api")
    context = make_context()

    msg = await complete_simple(model, context)
    assert isinstance(msg, AssistantMessage)


@pytest.mark.asyncio
async def test_multiple_providers_dispatch_correctly() -> None:
    """Registering multiple providers should route to the right one by api."""
    done_a = make_done_event("From A")
    done_b = make_done_event("From B")

    register_api_provider(
        ApiProvider(
            api="api-a",
            stream=make_mock_stream(done_a),
            stream_simple=make_mock_stream_simple(),
        )
    )
    register_api_provider(
        ApiProvider(
            api="api-b",
            stream=make_mock_stream(done_b),
            stream_simple=make_mock_stream_simple(),
        )
    )

    model_a = make_model("api-a")
    model_b = make_model("api-b")
    context = make_context()

    from pi_ai.types import TextContent

    msg_a = await complete(model_a, context)
    msg_b = await complete(model_b, context)

    assert any(isinstance(c, TextContent) and c.text == "From A" for c in msg_a.content)
    assert any(isinstance(c, TextContent) and c.text == "From B" for c in msg_b.content)


@pytest.mark.asyncio
async def test_stream_yields_multiple_event_types() -> None:
    """stream() should yield all event types in order."""
    done = make_done_event("Final")
    text_start = TextStartEvent(content_index=0)
    text_delta = TextDeltaEvent(content_index=0, delta="Hello")
    text_end = TextEndEvent(content_index=0, content="Hello")

    register_api_provider(
        ApiProvider(
            api="test-api",
            stream=make_mock_stream(text_start, text_delta, text_end, done),
            stream_simple=make_mock_stream_simple(),
        )
    )

    model = make_model("test-api")
    context = make_context()

    events = []
    async for event in stream(model, context):
        events.append(event)

    assert isinstance(events[0], TextStartEvent)
    assert isinstance(events[1], TextDeltaEvent)
    assert isinstance(events[2], TextEndEvent)
    assert isinstance(events[3], DoneEvent)
    assert events[1].delta == "Hello"
