"""Tests for pi_coding_agent.cli.session_picker."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from pi_coding_agent.cli.session_picker import select_session


@dataclass
class FakeSession:
    id: str
    path: str


@pytest.mark.asyncio
async def test_select_session_no_sessions(capsys: pytest.CaptureFixture[str]) -> None:
    current_loader = AsyncMock(return_value=[])
    all_loader = AsyncMock(return_value=[])

    result = await select_session(current_loader, all_loader)

    assert result is None
    captured = capsys.readouterr()
    assert "No sessions found" in captured.out


@pytest.mark.asyncio
async def test_select_session_chooses_current(capsys: pytest.CaptureFixture[str]) -> None:
    sessions = [FakeSession(id="abc123", path="/tmp/sessions/abc123")]
    current_loader = AsyncMock(return_value=sessions)
    all_loader = AsyncMock(return_value=[])

    with patch("builtins.input", return_value="1"):
        result = await select_session(current_loader, all_loader)

    assert result == "/tmp/sessions/abc123"


@pytest.mark.asyncio
async def test_select_session_cancel_empty_input(capsys: pytest.CaptureFixture[str]) -> None:
    sessions = [FakeSession(id="abc123", path="/tmp/sessions/abc123")]
    current_loader = AsyncMock(return_value=sessions)
    all_loader = AsyncMock(return_value=[])

    with patch("builtins.input", return_value=""):
        result = await select_session(current_loader, all_loader)

    assert result is None


@pytest.mark.asyncio
async def test_select_session_invalid_number(capsys: pytest.CaptureFixture[str]) -> None:
    sessions = [FakeSession(id="abc123", path="/tmp/sessions/abc123")]
    current_loader = AsyncMock(return_value=sessions)
    all_loader = AsyncMock(return_value=[])

    with patch("builtins.input", return_value="abc"):
        result = await select_session(current_loader, all_loader)

    assert result is None


@pytest.mark.asyncio
async def test_select_session_out_of_range(capsys: pytest.CaptureFixture[str]) -> None:
    sessions = [FakeSession(id="abc123", path="/tmp/sessions/abc123")]
    current_loader = AsyncMock(return_value=sessions)
    all_loader = AsyncMock(return_value=[])

    with patch("builtins.input", return_value="99"):
        result = await select_session(current_loader, all_loader)

    assert result is None


@pytest.mark.asyncio
async def test_select_session_falls_back_to_all(capsys: pytest.CaptureFixture[str]) -> None:
    sessions = [FakeSession(id="xyz789", path="/tmp/sessions/xyz789")]
    current_loader = AsyncMock(return_value=[])  # empty current
    all_loader = AsyncMock(return_value=sessions)

    with patch("builtins.input", return_value="1"):
        result = await select_session(current_loader, all_loader)

    assert result == "/tmp/sessions/xyz789"


@pytest.mark.asyncio
async def test_select_session_eof(capsys: pytest.CaptureFixture[str]) -> None:
    sessions = [FakeSession(id="abc123", path="/tmp/sessions/abc123")]
    current_loader = AsyncMock(return_value=sessions)
    all_loader = AsyncMock(return_value=[])

    with patch("builtins.input", side_effect=EOFError):
        result = await select_session(current_loader, all_loader)

    assert result is None


@pytest.mark.asyncio
async def test_select_session_keyboard_interrupt(capsys: pytest.CaptureFixture[str]) -> None:
    sessions = [FakeSession(id="abc123", path="/tmp/sessions/abc123")]
    current_loader = AsyncMock(return_value=sessions)
    all_loader = AsyncMock(return_value=[])

    with patch("builtins.input", side_effect=KeyboardInterrupt):
        result = await select_session(current_loader, all_loader)

    assert result is None


@pytest.mark.asyncio
async def test_select_session_loader_exception(capsys: pytest.CaptureFixture[str]) -> None:
    current_loader = AsyncMock(side_effect=RuntimeError("connection error"))
    all_loader = AsyncMock(side_effect=RuntimeError("connection error"))

    result = await select_session(current_loader, all_loader)

    assert result is None
    captured = capsys.readouterr()
    assert "No sessions found" in captured.out


@pytest.mark.asyncio
async def test_select_session_displays_sessions(capsys: pytest.CaptureFixture[str]) -> None:
    sessions = [
        FakeSession(id="abc123", path="/tmp/sessions/abc123"),
        FakeSession(id="def456", path="/tmp/sessions/def456"),
    ]
    current_loader = AsyncMock(return_value=sessions)
    all_loader = AsyncMock(return_value=[])

    with patch("builtins.input", return_value=""):
        await select_session(current_loader, all_loader)

    captured = capsys.readouterr()
    assert "abc123" in captured.out
    assert "def456" in captured.out
    assert "1." in captured.out
    assert "2." in captured.out
