"""Tests for pi_coding_agent.core.event_bus."""

from __future__ import annotations

from pi_coding_agent.core.event_bus import create_event_bus


class TestEventBus:
    def test_emit_calls_handler(self) -> None:
        bus = create_event_bus()
        received: list[object] = []
        bus.on("test", lambda data: received.append(data))
        bus.emit("test", "hello")
        assert received == ["hello"]

    def test_emit_no_handler(self) -> None:
        bus = create_event_bus()
        # Should not raise
        bus.emit("no-handler", 42)

    def test_on_returns_unsubscribe(self) -> None:
        bus = create_event_bus()
        received: list[object] = []
        unsub = bus.on("ch", lambda data: received.append(data))
        bus.emit("ch", 1)
        unsub()
        bus.emit("ch", 2)
        assert received == [1]

    def test_multiple_handlers(self) -> None:
        bus = create_event_bus()
        received_a: list[object] = []
        received_b: list[object] = []
        bus.on("x", lambda d: received_a.append(d))
        bus.on("x", lambda d: received_b.append(d))
        bus.emit("x", "v")
        assert received_a == ["v"]
        assert received_b == ["v"]

    def test_clear_removes_all_handlers(self) -> None:
        bus = create_event_bus()
        received: list[object] = []
        bus.on("c", lambda d: received.append(d))
        bus.clear()
        bus.emit("c", "ignored")
        assert received == []

    def test_handler_error_does_not_propagate(self) -> None:
        bus = create_event_bus()

        def bad_handler(data: object) -> None:
            raise RuntimeError("boom")

        bus.on("err", bad_handler)
        # Should not raise
        bus.emit("err", None)

    def test_multiple_channels_isolated(self) -> None:
        bus = create_event_bus()
        a: list[object] = []
        b: list[object] = []
        bus.on("a", lambda d: a.append(d))
        bus.on("b", lambda d: b.append(d))
        bus.emit("a", 1)
        bus.emit("b", 2)
        assert a == [1]
        assert b == [2]

    def test_double_unsubscribe_is_safe(self) -> None:
        bus = create_event_bus()
        unsub = bus.on("x", lambda d: None)
        unsub()
        unsub()  # Should not raise
