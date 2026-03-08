"""Tests for pi_ai.event_stream — EventStream and AssistantMessageEventStream."""

from __future__ import annotations

import asyncio

import pytest

from pi_ai.event_stream import AssistantMessageEventStream, EventStream
from pi_ai.types import (
    AssistantMessage,
    DoneEvent,
    ErrorEvent,
    StartEvent,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
)

# ---------------------------------------------------------------------------
# AssistantMessageEventStream — basic push / iterate / result
# ---------------------------------------------------------------------------


class TestAssistantMessageEventStream:
    async def test_push_and_iterate(self) -> None:
        stream = AssistantMessageEventStream()
        msg = AssistantMessage(content=[TextContent(text="hello")])

        stream.push(StartEvent(partial=msg))
        stream.push(TextStartEvent(content_index=0, partial=msg))
        stream.push(TextDeltaEvent(content_index=0, delta="hello", partial=msg))
        stream.push(TextEndEvent(content_index=0, content="hello", partial=msg))
        stream.push(DoneEvent(reason="stop", message=msg))
        stream.end()

        events = []
        async for event in stream:
            events.append(event)

        assert len(events) == 5
        assert events[0].type == "start"
        assert events[1].type == "text_start"
        assert events[2].type == "text_delta"
        assert events[3].type == "text_end"
        assert events[4].type == "done"

    async def test_result_from_done_event(self) -> None:
        stream = AssistantMessageEventStream()
        msg = AssistantMessage(
            content=[TextContent(text="result text")],
            stop_reason="stop",
        )

        stream.push(DoneEvent(reason="stop", message=msg))
        stream.end()

        result = await stream.result()
        assert result is msg
        assert result.stop_reason == "stop"

    async def test_result_from_error_event(self) -> None:
        stream = AssistantMessageEventStream()
        err_msg = AssistantMessage(
            stop_reason="error",
            error_message="Something went wrong",
        )

        stream.push(ErrorEvent(reason="error", error=err_msg))
        stream.end()

        result = await stream.result()
        assert result is err_msg
        assert result.error_message == "Something went wrong"

    async def test_end_without_done_uses_explicit_result(self) -> None:
        stream = AssistantMessageEventStream()
        msg = AssistantMessage(content=[TextContent(text="ok")])

        stream.push(StartEvent(partial=msg))
        stream.end(msg)

        events = []
        async for event in stream:
            events.append(event)

        assert len(events) == 1
        assert events[0].type == "start"

        result = await stream.result()
        assert result is msg

    async def test_push_after_done_is_ignored(self) -> None:
        stream = AssistantMessageEventStream()
        msg = AssistantMessage()

        stream.push(DoneEvent(reason="stop", message=msg))
        # This push should be silently ignored because stream is done
        stream.push(TextDeltaEvent(content_index=0, delta="late", partial=msg))
        stream.end()

        events = []
        async for event in stream:
            events.append(event)

        # Only the DoneEvent should be yielded
        assert len(events) == 1
        assert events[0].type == "done"

    async def test_empty_stream(self) -> None:
        stream = AssistantMessageEventStream()
        stream.end()

        events = []
        async for event in stream:
            events.append(event)

        assert len(events) == 0

    async def test_is_complete_for_done(self) -> None:
        stream = AssistantMessageEventStream()
        msg = AssistantMessage()
        done = DoneEvent(reason="stop", message=msg)
        assert stream._is_complete(done) is True

    async def test_is_complete_for_error(self) -> None:
        stream = AssistantMessageEventStream()
        msg = AssistantMessage()
        err = ErrorEvent(reason="error", error=msg)
        assert stream._is_complete(err) is True

    async def test_is_complete_for_other_events(self) -> None:
        stream = AssistantMessageEventStream()
        msg = AssistantMessage()
        start = StartEvent(partial=msg)
        assert stream._is_complete(start) is False

    async def test_extract_result_done(self) -> None:
        stream = AssistantMessageEventStream()
        msg = AssistantMessage(model="test-model")
        done = DoneEvent(reason="stop", message=msg)
        result = stream._extract_result(done)
        assert result.model == "test-model"

    async def test_extract_result_error(self) -> None:
        stream = AssistantMessageEventStream()
        msg = AssistantMessage(error_message="err")
        err = ErrorEvent(reason="error", error=msg)
        result = stream._extract_result(err)
        assert result.error_message == "err"

    async def test_extract_result_unexpected_raises(self) -> None:
        stream = AssistantMessageEventStream()
        msg = AssistantMessage()
        with pytest.raises(ValueError, match="Unexpected event type"):
            stream._extract_result(StartEvent(partial=msg))

    async def test_concurrent_push_and_iterate(self) -> None:
        """Test that push from a separate task works with async iteration."""
        stream = AssistantMessageEventStream()
        msg = AssistantMessage()

        async def producer() -> None:
            await asyncio.sleep(0.01)
            stream.push(StartEvent(partial=msg))
            await asyncio.sleep(0.01)
            stream.push(DoneEvent(reason="stop", message=msg))
            stream.end()

        _task = asyncio.create_task(producer())  # noqa: RUF006

        events = []
        async for event in stream:
            events.append(event)

        assert len(events) == 2
        assert events[0].type == "start"
        assert events[1].type == "done"


# ---------------------------------------------------------------------------
# Base EventStream
# ---------------------------------------------------------------------------


class TestEventStreamBase:
    def test_is_complete_not_implemented(self) -> None:
        stream: EventStream[str, str] = EventStream()
        with pytest.raises(NotImplementedError):
            stream._is_complete("test")

    def test_extract_result_not_implemented(self) -> None:
        stream: EventStream[str, str] = EventStream()
        with pytest.raises(NotImplementedError):
            stream._extract_result("test")
