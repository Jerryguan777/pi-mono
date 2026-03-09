"""Tests for pi_mom.store."""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_mom.store import ChannelStore, LoggedMessage


class TestChannelStore:
    def test_creates_working_dir(self, tmp_path: Any) -> None:
        working_dir = str(tmp_path / "workspace")
        ChannelStore(working_dir=working_dir, bot_token="xoxb-test")
        assert os.path.isdir(working_dir)

    def test_get_channel_dir(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        channel_dir = store.get_channel_dir("C12345")
        assert os.path.isdir(channel_dir)
        assert channel_dir.endswith("C12345")

    def test_generate_local_filename(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        filename = store.generate_local_filename("test file.png", "1234567890.123456")
        assert "test_file.png" in filename
        assert not filename.startswith("_")

    def test_generate_local_filename_sanitizes(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        filename = store.generate_local_filename("weird!@#file.txt", "1234567890.0")
        # Special chars replaced with underscore
        assert "!" not in filename
        assert "@" not in filename

    @pytest.mark.asyncio
    async def test_log_message(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        msg = LoggedMessage(
            date="2025-01-01T00:00:00Z",
            ts="1234567890.123456",
            user="U123",
            text="Hello",
            attachments=[],
            is_bot=False,
            user_name="mario",
        )
        result = await store.log_message("C123", msg)
        assert result is True

        log_path = os.path.join(str(tmp_path), "C123", "log.jsonl")
        assert os.path.exists(log_path)
        with open(log_path) as f:
            entry = json.loads(f.read().strip())
        assert entry["text"] == "Hello"
        assert entry["user"] == "U123"

    @pytest.mark.asyncio
    async def test_log_message_deduplication(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        msg = LoggedMessage(
            date="2025-01-01T00:00:00Z",
            ts="1234567890.123456",
            user="U123",
            text="Hello",
            attachments=[],
            is_bot=False,
        )
        result1 = await store.log_message("C123", msg)
        result2 = await store.log_message("C123", msg)
        assert result1 is True
        assert result2 is False  # duplicate

    @pytest.mark.asyncio
    async def test_log_bot_response(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        await store.log_bot_response("C123", "I am the bot", "1234567890.654321")

        log_path = os.path.join(str(tmp_path), "C123", "log.jsonl")
        with open(log_path) as f:
            entry = json.loads(f.read().strip())
        assert entry["user"] == "bot"
        assert entry["isBot"] is True

    def test_get_last_timestamp_no_log(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        result = store.get_last_timestamp("C999")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_last_timestamp(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        msg = LoggedMessage(
            date="2025-01-01T00:00:00Z",
            ts="9876543210.000001",
            user="U123",
            text="Latest",
            attachments=[],
            is_bot=False,
        )
        await store.log_message("C123", msg)
        ts = store.get_last_timestamp("C123")
        assert ts == "9876543210.000001"

    def test_process_attachments_no_url(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        # File without URL
        files = [{"name": "test.png"}]
        result = store.process_attachments("C123", files, "1234567890.0")
        assert result == []

    def test_process_attachments_no_name(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        files = [{"url_private": "https://example.com/file"}]
        result = store.process_attachments("C123", files, "1234567890.0")
        assert result == []

    def test_process_attachments_with_url(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        files = [{"name": "photo.jpg", "url_private_download": "https://files.slack.com/photo.jpg"}]
        result = store.process_attachments("C123", files, "1234567890.0")
        assert len(result) == 1
        assert result[0].original == "photo.jpg"
        assert "photo.jpg" in result[0].local


class TestChannelStoreLogMessage:
    @pytest.mark.asyncio
    async def test_log_message_no_date_sets_date(self, tmp_path: Any) -> None:
        """When message.date is empty, it should be computed from ts."""
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        msg = LoggedMessage(
            date="",
            ts="1609459200.0",
            user="U001",
            text="Hello",
            attachments=[],
            is_bot=False,
        )
        result = await store.log_message("C001", msg)
        assert result is True
        assert msg.date  # date was set

    @pytest.mark.asyncio
    async def test_log_bot_response_creates_entry(self, tmp_path: Any) -> None:
        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        await store.log_bot_response("C001", "Hello world", "1609459200.0")

        log_path = os.path.join(str(tmp_path), "C001", "log.jsonl")
        assert os.path.exists(log_path)
        with open(log_path) as f:
            entry = json.loads(f.read().strip())
        assert entry["text"] == "Hello world"
        assert entry["isBot"] is True

    @pytest.mark.asyncio
    async def test_process_download_queue_downloads(self, tmp_path: Any) -> None:
        """_process_download_queue should download pending items."""
        from unittest.mock import patch

        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")

        # Add a fake pending download
        from pi_mom.store import _PendingDownload

        store._pending_downloads.append(
            _PendingDownload(channel_id="C001", local_path="C001/attachments/test.txt", url="https://example.com/file")
        )

        # Mock _download_attachment to avoid actual HTTP
        with patch.object(store, "_download_attachment", new=AsyncMock()) as mock_dl:
            await store._process_download_queue()
            mock_dl.assert_called_once()

        assert store._is_downloading is False

    @pytest.mark.asyncio
    async def test_process_download_queue_idempotent_when_downloading(self, tmp_path: Any) -> None:
        """If _is_downloading is already True, queue should not run again."""
        from unittest.mock import patch

        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")
        store._is_downloading = True

        with patch.object(store, "_download_attachment", new=AsyncMock()) as mock_dl:
            await store._process_download_queue()
            mock_dl.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_attachment_success(self, tmp_path: Any) -> None:
        """_download_attachment should write file to disk."""

        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = b"file content"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("pi_mom.store.httpx.AsyncClient", return_value=mock_client):
            await store._download_attachment("C001/attachments/test.txt", "https://example.com/file")

        out_path = os.path.join(str(tmp_path), "C001", "attachments", "test.txt")
        assert os.path.exists(out_path)
        with open(out_path, "rb") as f:
            assert f.read() == b"file content"

    @pytest.mark.asyncio
    async def test_download_attachment_http_error(self, tmp_path: Any) -> None:
        """_download_attachment should raise RuntimeError on HTTP error."""

        store = ChannelStore(working_dir=str(tmp_path), bot_token="xoxb-test")

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 403
        mock_response.reason_phrase = "Forbidden"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch("pi_mom.store.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="403"),
        ):
            await store._download_attachment("C001/attachments/test.txt", "https://example.com/file")
