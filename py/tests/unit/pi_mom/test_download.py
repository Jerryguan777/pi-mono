"""Tests for pi_mom.download."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


class TestDownloadFormatHelpers:
    """Test the helper functions in download.py."""

    def test_format_ts(self) -> None:
        from pi_mom.download import _format_ts

        result = _format_ts("1609459200.0")
        assert "2021" in result

    def test_format_message_single_line(self) -> None:
        from pi_mom.download import _format_message

        result = _format_message("1609459200.0", "mario", "Hello")
        assert "mario" in result
        assert "Hello" in result

    def test_format_message_multiline(self) -> None:
        from pi_mom.download import _format_message

        result = _format_message("1609459200.0", "mario", "Line 1\nLine 2\nLine 3")
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_format_message_with_indent(self) -> None:
        from pi_mom.download import _format_message

        result = _format_message("1609459200.0", "bot", "Reply", indent="  ")
        assert result.startswith("  ")


class TestDownloadChannel:
    """Test download_channel with mocked Slack API."""

    @pytest.mark.asyncio
    async def test_download_channel_basic(self, capsys: Any) -> None:
        from pi_mom.download import download_channel

        mock_client = AsyncMock()
        mock_client.conversations_info.return_value = {"channel": {"name": "test-channel"}}
        mock_client.conversations_history.return_value = {
            "messages": [{"ts": "1609459200.0", "user": "U123", "text": "Hello", "reply_count": 0}],
            "response_metadata": {"next_cursor": ""},
        }

        with patch("slack_sdk.web.async_client.AsyncWebClient", return_value=mock_client):
            await download_channel("C123", "xoxb-test")

        captured = capsys.readouterr()
        assert "Hello" in captured.out or "test-channel" in captured.err

    @pytest.mark.asyncio
    async def test_download_channel_with_threads(self, capsys: Any) -> None:
        from pi_mom.download import download_channel

        mock_client = AsyncMock()
        mock_client.conversations_info.return_value = {"channel": {"name": "dev"}}
        mock_client.conversations_history.return_value = {
            "messages": [{"ts": "1609459200.0", "user": "U1", "text": "Main msg", "reply_count": 1}],
            "response_metadata": {"next_cursor": ""},
        }
        mock_client.conversations_replies.return_value = {
            "messages": [
                {"ts": "1609459200.0", "user": "U1", "text": "Main msg"},
                {"ts": "1609459201.0", "user": "U2", "text": "Reply!"},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        with patch("slack_sdk.web.async_client.AsyncWebClient", return_value=mock_client):
            await download_channel("C456", "xoxb-test")

        captured = capsys.readouterr()
        assert "Reply!" in captured.out or "dev" in captured.err

    @pytest.mark.asyncio
    async def test_download_channel_info_fails(self, capsys: Any) -> None:
        """Should still work if conversations_info fails (e.g., DMs)."""
        from pi_mom.download import download_channel

        mock_client = AsyncMock()
        mock_client.conversations_info.side_effect = Exception("not a channel")
        mock_client.conversations_history.return_value = {
            "messages": [],
            "response_metadata": {"next_cursor": ""},
        }

        with patch("slack_sdk.web.async_client.AsyncWebClient", return_value=mock_client):
            await download_channel("D123", "xoxb-test")

        # Should not raise
        captured = capsys.readouterr()
        assert "D123" in captured.err
