"""Tests for pi_coding_agent.modes.print_mode."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pi_coding_agent.modes.print_mode import PrintModeOptions, run_print_mode

# ---------------------------------------------------------------------------
# Helpers / Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeContentItem:
    type: str
    text: str = ""


@dataclass
class FakeMessage:
    role: str
    stop_reason: str | None = None
    error_message: str | None = None
    content: list[FakeContentItem] = field(default_factory=list)


@dataclass
class FakeState:
    messages: list[FakeMessage] = field(default_factory=list)


def make_session(
    state: FakeState | None = None,
    session_manager: Any = None,
) -> Any:
    session = MagicMock()
    session.bind_extensions = AsyncMock()
    session.subscribe = MagicMock()
    session.prompt = AsyncMock()
    session.state = state or FakeState()
    session.session_manager = session_manager
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_print_mode_options_defaults() -> None:
    opts = PrintModeOptions(mode="text")
    assert opts.mode == "text"
    assert opts.messages == []
    assert opts.initial_message is None
    assert opts.initial_images is None


@pytest.mark.asyncio
async def test_run_print_mode_text_no_messages() -> None:
    state = FakeState(messages=[])
    session = make_session(state=state)
    opts = PrintModeOptions(mode="text")

    await run_print_mode(session, opts)

    session.bind_extensions.assert_called_once()
    session.subscribe.assert_called_once()
    session.prompt.assert_not_called()


@pytest.mark.asyncio
async def test_run_print_mode_text_with_initial(capsys: pytest.CaptureFixture[str]) -> None:
    content = FakeContentItem(type="text", text="Hello from AI")
    msg = FakeMessage(role="assistant", stop_reason="stop", content=[content])
    state = FakeState(messages=[msg])
    session = make_session(state=state)
    opts = PrintModeOptions(mode="text", initial_message="Hello!")

    await run_print_mode(session, opts)

    session.prompt.assert_called_once_with("Hello!", images=None)
    captured = capsys.readouterr()
    assert "Hello from AI" in captured.out


@pytest.mark.asyncio
async def test_run_print_mode_text_multiple_messages(capsys: pytest.CaptureFixture[str]) -> None:
    content = FakeContentItem(type="text", text="Response")
    msg = FakeMessage(role="assistant", stop_reason="stop", content=[content])
    state = FakeState(messages=[msg])
    session = make_session(state=state)
    opts = PrintModeOptions(mode="text", messages=["second", "third"])

    await run_print_mode(session, opts)

    assert session.prompt.call_count == 2


@pytest.mark.asyncio
async def test_run_print_mode_text_error_exits(capsys: pytest.CaptureFixture[str]) -> None:
    msg = FakeMessage(role="assistant", stop_reason="error", error_message="Something broke")
    state = FakeState(messages=[msg])
    session = make_session(state=state)
    opts = PrintModeOptions(mode="text")

    with pytest.raises(SystemExit) as exc_info:
        await run_print_mode(session, opts)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Something broke" in captured.err


@pytest.mark.asyncio
async def test_run_print_mode_text_aborted_exits(capsys: pytest.CaptureFixture[str]) -> None:
    msg = FakeMessage(role="assistant", stop_reason="aborted")
    state = FakeState(messages=[msg])
    session = make_session(state=state)
    opts = PrintModeOptions(mode="text")

    with pytest.raises(SystemExit) as exc_info:
        await run_print_mode(session, opts)

    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_run_print_mode_json_header(capsys: pytest.CaptureFixture[str]) -> None:
    header = {"type": "session", "id": "123"}
    session_manager = MagicMock()
    session_manager.get_header.return_value = header
    session = make_session(session_manager=session_manager)
    opts = PrintModeOptions(mode="json")

    await run_print_mode(session, opts)

    captured = capsys.readouterr()
    first_line = captured.out.strip().splitlines()[0] if captured.out.strip() else ""
    parsed = json.loads(first_line)
    assert parsed == header


@pytest.mark.asyncio
async def test_run_print_mode_json_events(capsys: pytest.CaptureFixture[str]) -> None:
    session = make_session()
    opts = PrintModeOptions(mode="json", initial_message="Hi")

    # The subscribe callback should be called with events
    captured_callback: list[Any] = []

    def capture_subscribe(cb: Any) -> None:
        captured_callback.append(cb)

    session.subscribe = capture_subscribe

    await run_print_mode(session, opts)

    assert len(captured_callback) == 1
    cb = captured_callback[0]

    # Simulate an event being emitted
    event = {"type": "text", "content": "hello"}
    cb(event)

    captured = capsys.readouterr()
    assert json.dumps(event) in captured.out


@pytest.mark.asyncio
async def test_run_print_mode_text_no_event_output_in_text_mode(capsys: pytest.CaptureFixture[str]) -> None:
    session = make_session()
    opts = PrintModeOptions(mode="text", initial_message="Hi")

    captured_callback: list[Any] = []

    def capture_subscribe(cb: Any) -> None:
        captured_callback.append(cb)

    session.subscribe = capture_subscribe

    await run_print_mode(session, opts)

    cb = captured_callback[0]
    event = {"type": "text", "content": "hello"}
    cb(event)

    captured = capsys.readouterr()
    # In text mode, events should NOT be printed
    assert json.dumps(event) not in captured.out


@pytest.mark.asyncio
async def test_run_print_mode_text_non_text_content_skipped(capsys: pytest.CaptureFixture[str]) -> None:
    tool_call = FakeContentItem(type="tool_call", text="")
    text_content = FakeContentItem(type="text", text="Final answer")
    msg = FakeMessage(role="assistant", stop_reason="stop", content=[tool_call, text_content])
    state = FakeState(messages=[msg])
    session = make_session(state=state)
    opts = PrintModeOptions(mode="text")

    await run_print_mode(session, opts)

    captured = capsys.readouterr()
    assert "Final answer" in captured.out


@pytest.mark.asyncio
async def test_run_print_mode_last_message_not_assistant(capsys: pytest.CaptureFixture[str]) -> None:
    # If the last message is from the user, don't crash
    user_msg = FakeMessage(role="user")
    state = FakeState(messages=[user_msg])
    session = make_session(state=state)
    opts = PrintModeOptions(mode="text")

    await run_print_mode(session, opts)

    captured = capsys.readouterr()
    assert captured.out.strip() == ""
