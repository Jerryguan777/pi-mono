"""Tests for stream event types — verifies event dataclass contracts.

Ported from python-superpowers. Since the rewrite uses dataclasses
(not Pydantic), we test construction and field access directly.
"""

from __future__ import annotations

from pi_ai.types import (
    DoneEvent,
    ErrorEvent,
    StartEvent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)

# ── Construction & defaults ───────────────────────────────────────────


class TestStartEvent:
    def test_default(self) -> None:
        e = StartEvent()
        assert e.type == "start"


class TestTextStartEvent:
    def test_default(self) -> None:
        e = TextStartEvent()
        assert e.type == "text_start"


class TestTextDeltaEvent:
    def test_with_text(self) -> None:
        e = TextDeltaEvent(delta="hello")
        assert e.type == "text_delta"
        assert e.delta == "hello"

    def test_default_empty(self) -> None:
        e = TextDeltaEvent()
        assert e.delta == ""


class TestTextEndEvent:
    def test_default(self) -> None:
        e = TextEndEvent()
        assert e.type == "text_end"


class TestThinkingStartEvent:
    def test_default(self) -> None:
        e = ThinkingStartEvent()
        assert e.type == "thinking_start"


class TestThinkingDeltaEvent:
    def test_with_thinking(self) -> None:
        e = ThinkingDeltaEvent(delta="hmm")
        assert e.type == "thinking_delta"
        assert e.delta == "hmm"

    def test_default_empty(self) -> None:
        e = ThinkingDeltaEvent()
        assert e.delta == ""


class TestThinkingEndEvent:
    def test_default(self) -> None:
        e = ThinkingEndEvent()
        assert e.type == "thinking_end"


class TestToolCallStartEvent:
    def test_default(self) -> None:
        e = ToolCallStartEvent()
        assert e.type == "toolcall_start"


class TestToolCallDeltaEvent:
    def test_default_empty(self) -> None:
        e = ToolCallDeltaEvent()
        assert e.type == "toolcall_delta"
        assert e.delta == ""

    def test_with_delta(self) -> None:
        e = ToolCallDeltaEvent(delta='{"cmd":')
        assert e.delta == '{"cmd":'


class TestToolCallEndEvent:
    def test_default(self) -> None:
        e = ToolCallEndEvent()
        assert e.type == "toolcall_end"


class TestDoneEvent:
    def test_stop(self) -> None:
        e = DoneEvent(reason="stop")
        assert e.type == "done"
        assert e.reason == "stop"

    def test_length(self) -> None:
        e = DoneEvent(reason="length")
        assert e.reason == "length"

    def test_tool_use(self) -> None:
        e = DoneEvent(reason="toolUse")
        assert e.reason == "toolUse"


class TestErrorEvent:
    def test_aborted(self) -> None:
        e = ErrorEvent(reason="aborted")
        assert e.type == "error"
        assert e.reason == "aborted"

    def test_error(self) -> None:
        e = ErrorEvent(reason="error")
        assert e.reason == "error"
