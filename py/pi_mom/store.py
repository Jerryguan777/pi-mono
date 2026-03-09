"""Channel message store — port of packages/mom/src/store.ts."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import httpx

import pi_mom.log as log


@dataclass
class ChannelStoreConfig:
    """Configuration for creating a ChannelStore."""

    working_dir: str
    bot_token: str  # needed for authenticated file downloads


@dataclass
class Attachment:
    """A file attached to a Slack message."""

    original: str  # original filename from uploader
    local: str  # path relative to working dir (e.g., "C12345/attachments/1732531234567_file.png")


@dataclass
class LoggedMessage:
    """A message entry stored in log.jsonl."""

    date: str
    ts: str
    user: str
    text: str
    attachments: list[Attachment]
    is_bot: bool
    user_name: str | None = None
    display_name: str | None = None


@dataclass
class _PendingDownload:
    channel_id: str
    local_path: str
    url: str


class ChannelStore:
    """Manages per-channel message logs and attachment downloads."""

    def __init__(self, working_dir: str, bot_token: str) -> None:
        self._working_dir = working_dir
        self._bot_token = bot_token
        self._pending_downloads: deque[_PendingDownload] = deque()
        self._is_downloading = False
        # Track recently logged message timestamps to prevent duplicates
        # Key: "channelId:ts", value: epoch time when logged
        self._recently_logged: dict[str, float] = {}
        # Scheduled cleanup tasks
        self._cleanup_tasks: list[asyncio.TimerHandle] = []
        # Keep references to background tasks to prevent GC
        self._bg_tasks: set[asyncio.Task[None]] = set()

        os.makedirs(self._working_dir, exist_ok=True)

    def get_channel_dir(self, channel_id: str) -> str:
        """Get or create the directory for a channel/DM."""
        d = os.path.join(self._working_dir, channel_id)
        os.makedirs(d, exist_ok=True)
        return d

    def generate_local_filename(self, original_name: str, timestamp: str) -> str:
        """Generate a unique local filename for an attachment."""
        ts = int(float(timestamp) * 1000)
        sanitized = re.sub(r"[^a-zA-Z0-9._\-]", "_", original_name)
        return f"{ts}_{sanitized}"

    def process_attachments(
        self,
        channel_id: str,
        files: list[dict[str, Any]],
        timestamp: str,
    ) -> list[Attachment]:
        """Process attachments from a Slack message event.

        Returns attachment metadata and queues downloads in the background.
        """
        attachments: list[Attachment] = []

        for file_info in files:
            url: str | None = file_info.get("url_private_download") or file_info.get("url_private")
            if not url:
                continue
            name: str | None = file_info.get("name")
            if not name:
                log.log_warning("Attachment missing name, skipping", url)
                continue

            filename = self.generate_local_filename(name, timestamp)
            local_path = f"{channel_id}/attachments/{filename}"

            attachments.append(Attachment(original=name, local=local_path))
            self._pending_downloads.append(_PendingDownload(channel_id=channel_id, local_path=local_path, url=url))

        # Trigger background download (non-blocking) only if we have pending items
        if attachments and not self._is_downloading:
            try:
                task = asyncio.create_task(self._process_download_queue())
                self._bg_tasks.add(task)
                task.add_done_callback(self._bg_tasks.discard)
            except RuntimeError:
                # No event loop running (e.g., in tests) — will be processed later
                pass

        return attachments

    async def log_message(self, channel_id: str, message: LoggedMessage) -> bool:
        """Log a message to the channel's log.jsonl.

        Returns False if the message was already logged (duplicate).
        """
        dedupe_key = f"{channel_id}:{message.ts}"
        if dedupe_key in self._recently_logged:
            return False

        self._recently_logged[dedupe_key] = time.time()
        # Schedule cleanup after 60 seconds
        asyncio.get_running_loop().call_later(60.0, lambda: self._recently_logged.pop(dedupe_key, None))

        log_path = os.path.join(self.get_channel_dir(channel_id), "log.jsonl")

        # Ensure message has a date field
        if not message.date:
            ts_epoch = float(message.ts) * 1000 if "." in message.ts else float(message.ts)
            import datetime

            message.date = datetime.datetime.fromtimestamp(ts_epoch / 1000, tz=datetime.UTC).isoformat()

        entry = {
            "date": message.date,
            "ts": message.ts,
            "user": message.user,
            "userName": message.user_name,
            "displayName": message.display_name,
            "text": message.text,
            "attachments": [{"original": a.original, "local": a.local} for a in message.attachments],
            "isBot": message.is_bot,
        }
        line = json.dumps(entry) + "\n"

        await asyncio.to_thread(_append_file, log_path, line)
        return True

    async def log_bot_response(self, channel_id: str, text: str, ts: str) -> None:
        """Log a bot response to the channel's log.jsonl."""
        import datetime

        now = datetime.datetime.now(tz=datetime.UTC).isoformat()
        msg = LoggedMessage(date=now, ts=ts, user="bot", text=text, attachments=[], is_bot=True)
        await self.log_message(channel_id, msg)

    def get_last_timestamp(self, channel_id: str) -> str | None:
        """Get the timestamp of the last logged message for a channel."""
        log_path = os.path.join(self._working_dir, channel_id, "log.jsonl")
        if not os.path.exists(log_path):
            return None

        try:
            with open(log_path, encoding="utf-8") as f:
                content = f.read()
            lines = [ln for ln in content.strip().split("\n") if ln]
            if not lines:
                return None
            last_line = lines[-1]
            parsed = json.loads(last_line)
            return str(parsed.get("ts")) if parsed.get("ts") else None
        except Exception:
            return None

    async def _process_download_queue(self) -> None:
        """Process the download queue in the background."""
        if self._is_downloading or not self._pending_downloads:
            return

        self._is_downloading = True

        while self._pending_downloads:
            item = self._pending_downloads.popleft()
            try:
                await self._download_attachment(item.local_path, item.url)
            except Exception as exc:
                log.log_warning("Failed to download attachment", f"{item.local_path}: {exc}")

        self._is_downloading = False

    async def _download_attachment(self, local_path: str, url: str) -> None:
        """Download a single attachment from Slack."""
        file_path = os.path.join(self._working_dir, local_path)
        dir_path = os.path.dirname(file_path)
        os.makedirs(dir_path, exist_ok=True)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {self._bot_token}"},
                follow_redirects=True,
            )
            if not response.is_success:
                raise RuntimeError(f"HTTP {response.status_code}: {response.reason_phrase}")

            content = response.content

        await asyncio.to_thread(_write_bytes, file_path, content)


def _append_file(path: str, line: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def _write_bytes(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)
