"""Slack bot implementation — port of packages/mom/src/slack.ts."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

import pi_mom.log as log
from pi_mom.store import Attachment, ChannelStore

if TYPE_CHECKING:
    pass

# ============================================================================
# Types
# ============================================================================


@dataclass
class SlackEvent:
    """A Slack event (mention or DM) that triggers the agent."""

    type: Literal["mention", "dm"]
    channel: str
    ts: str
    user: str
    text: str
    files: list[dict[str, Any]] | None = None
    attachments: list[Attachment] | None = None


@dataclass
class SlackUser:
    """A Slack workspace user."""

    id: str
    user_name: str
    display_name: str


@dataclass
class SlackChannel:
    """A Slack workspace channel or DM."""

    id: str
    name: str


@dataclass
class ChannelInfo:
    """Lightweight channel info for agent context."""

    id: str
    name: str


@dataclass
class UserInfo:
    """Lightweight user info for agent context."""

    id: str
    user_name: str
    display_name: str


@dataclass
class SlackMessage:
    """A message as seen by the agent."""

    text: str
    raw_text: str
    user: str
    channel: str
    ts: str
    attachments: list[dict[str, str]]
    user_name: str | None = None


class SlackContext(Protocol):
    """Protocol for the Slack context passed to the agent runner."""

    message: SlackMessage
    channel_name: str | None
    channels: list[ChannelInfo]
    users: list[UserInfo]

    async def respond(self, text: str, should_log: bool = True) -> None: ...

    async def replace_message(self, text: str) -> None: ...

    async def respond_in_thread(self, text: str) -> None: ...

    async def set_typing(self, is_typing: bool) -> None: ...

    async def upload_file(self, file_path: str, title: str | None = None) -> None: ...

    async def set_working(self, working: bool) -> None: ...

    async def delete_message(self) -> None: ...


class MomHandler(Protocol):
    """Protocol for the handler that processes Slack events."""

    def is_running(self, channel_id: str) -> bool: ...

    async def handle_event(self, event: SlackEvent, slack: SlackBot, is_event: bool = False) -> None: ...

    async def handle_stop(self, channel_id: str, slack: SlackBot) -> None: ...


# ============================================================================
# Per-channel queue for sequential processing
# ============================================================================


class ChannelQueue:
    """An asyncio-based queue that processes work items sequentially per channel."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Callable[[], Awaitable[None]]] = asyncio.Queue()
        self._processing = False
        self._tasks: set[asyncio.Task[None]] = set()

    def enqueue(self, work: Callable[[], Awaitable[None]]) -> None:
        self._queue.put_nowait(work)
        if not self._processing:
            task = asyncio.create_task(self._process())
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    def size(self) -> int:
        return self._queue.qsize()

    async def _process(self) -> None:
        self._processing = True
        while not self._queue.empty():
            work = await self._queue.get()
            try:
                await work()
            except Exception as exc:
                log.log_warning("Queue error", str(exc))
        self._processing = False


# ============================================================================
# SlackBot
# ============================================================================


class SlackBot:
    """Slack bot that listens for events and dispatches them to MomHandler."""

    def __init__(
        self,
        handler: MomHandler,
        app_token: str,
        bot_token: str,
        working_dir: str,
        store: ChannelStore,
    ) -> None:
        self._handler = handler
        self._app_token = app_token
        self._bot_token = bot_token
        self._working_dir = working_dir
        self._store = store

        self._bot_user_id: str | None = None
        self._startup_ts: str | None = None

        self._users: dict[str, SlackUser] = {}
        self._channels: dict[str, SlackChannel] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._queues: dict[str, ChannelQueue] = {}

    def _spawn(self, coro: Awaitable[Any]) -> None:
        """Create a background task and keep a reference to avoid GC."""
        task: asyncio.Task[Any] = asyncio.create_task(coro)  # type: ignore[arg-type]
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    # ==========================================================================
    # Public API
    # ==========================================================================

    async def start(self) -> None:
        """Fetch users/channels, backfill logs, then connect via Socket Mode."""
        from slack_sdk.socket_mode.aiohttp import SocketModeClient
        from slack_sdk.web.async_client import AsyncWebClient

        self._web_client: AsyncWebClient = AsyncWebClient(token=self._bot_token)
        self._socket_client: SocketModeClient = SocketModeClient(
            app_token=self._app_token,
            web_client=self._web_client,
        )

        auth = await self._web_client.auth_test()
        self._bot_user_id = str(auth.get("user_id", ""))

        await asyncio.gather(self._fetch_users(), self._fetch_channels())
        log.log_info(f"Loaded {len(self._channels)} channels, {len(self._users)} users")

        await self._backfill_all_channels()

        self._setup_event_handlers()
        await self._socket_client.connect()  # type: ignore[no-untyped-call]

        # Record startup time — messages older than this are just logged, not processed
        self._startup_ts = f"{time.time():.6f}"

        log.log_connected()

    def get_user(self, user_id: str) -> SlackUser | None:
        return self._users.get(user_id)

    def get_channel(self, channel_id: str) -> SlackChannel | None:
        return self._channels.get(channel_id)

    def get_all_users(self) -> list[SlackUser]:
        return list(self._users.values())

    def get_all_channels(self) -> list[SlackChannel]:
        return list(self._channels.values())

    async def post_message(self, channel: str, text: str) -> str:
        result = await self._web_client.chat_postMessage(channel=channel, text=text)
        return str(result.get("ts", ""))

    async def update_message(self, channel: str, ts: str, text: str) -> None:
        await self._web_client.chat_update(channel=channel, ts=ts, text=text)

    async def delete_message(self, channel: str, ts: str) -> None:
        await self._web_client.chat_delete(channel=channel, ts=ts)

    async def post_in_thread(self, channel: str, thread_ts: str, text: str) -> str:
        result = await self._web_client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)
        return str(result.get("ts", ""))

    async def upload_file(self, channel: str, file_path: str, title: str | None = None) -> None:
        file_name = title or os.path.basename(file_path)
        with open(file_path, "rb") as f:
            file_content = f.read()
        await self._web_client.files_upload_v2(
            channel_id=channel,
            file=file_content,
            filename=file_name,
            title=file_name,
        )

    async def log_to_file(self, channel: str, entry: dict[str, Any]) -> None:
        """Log a message to log.jsonl."""
        d = os.path.join(self._working_dir, channel)
        os.makedirs(d, exist_ok=True)
        line = json.dumps(entry) + "\n"
        await asyncio.to_thread(_append_log_line, os.path.join(d, "log.jsonl"), line)

    async def log_bot_response(self, channel: str, text: str, ts: str) -> None:
        """Log a bot response to log.jsonl."""
        import datetime

        await self.log_to_file(
            channel,
            {
                "date": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                "ts": ts,
                "user": "bot",
                "text": text,
                "attachments": [],
                "isBot": True,
            },
        )

    def enqueue_event(self, event: SlackEvent) -> bool:
        """Enqueue an event for processing.

        Returns True if enqueued, False if the queue is full (max 5).
        """
        queue = self._get_queue(event.channel)
        if queue.size() >= 5:
            log.log_warning(f"Event queue full for {event.channel}, discarding: {event.text[:50]}")
            return False
        log.log_info(f"Enqueueing event for {event.channel}: {event.text[:50]}")
        _e = event

        async def _dispatch_event() -> None:
            await self._handler.handle_event(_e, self, True)

        queue.enqueue(_dispatch_event)
        return True

    # ==========================================================================
    # Private — Event Handlers
    # ==========================================================================

    def _get_queue(self, channel_id: str) -> ChannelQueue:
        if channel_id not in self._queues:
            self._queues[channel_id] = ChannelQueue()
        return self._queues[channel_id]

    def _setup_event_handlers(self) -> None:
        """Register socket mode event handlers."""
        from slack_sdk.socket_mode.request import SocketModeRequest
        from slack_sdk.socket_mode.response import SocketModeResponse

        async def handle_request(client: Any, req: SocketModeRequest) -> None:
            # Always ack immediately
            await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))

            if req.type != "events_api":
                return

            payload = req.payload
            event = payload.get("event", {})
            event_type: str = event.get("type", "")

            if event_type == "app_mention":
                await self._handle_app_mention(event)
            elif event_type == "message":
                await self._handle_message(event)

        self._socket_client.socket_mode_request_listeners.append(handle_request)

    async def _handle_app_mention(self, event: dict[str, Any]) -> None:
        """Handle an @mention in a channel."""
        channel: str = event.get("channel", "")
        user: str = event.get("user", "")
        ts: str = event.get("ts", "")
        text: str = event.get("text", "")
        files: list[dict[str, Any]] | None = event.get("files")

        # Skip DMs (handled by message event)
        if channel.startswith("D"):
            return

        import re

        clean_text = re.sub(r"<@[A-Z0-9]+>", "", text, flags=re.IGNORECASE).strip()

        slack_event = SlackEvent(
            type="mention",
            channel=channel,
            ts=ts,
            user=user,
            text=clean_text,
            files=files,
        )

        # Log to log.jsonl — always, even for old messages
        slack_event.attachments = await self._log_user_message(slack_event)

        # Only trigger processing for messages AFTER startup
        if self._startup_ts and ts < self._startup_ts:
            log.log_info(f"[{channel}] Logged old message (pre-startup), not triggering: {clean_text[:30]}")
            return

        # Check for stop command
        if clean_text.lower().strip() == "stop":
            if self._handler.is_running(channel):
                self._spawn(self._handler.handle_stop(channel, self))
            else:
                self._spawn(self.post_message(channel, "_Nothing running_"))
            return

        # Check if busy
        if self._handler.is_running(channel):
            self._spawn(self.post_message(channel, "_Already working. Say `@mom stop` to cancel._"))
        else:
            _mention_event = slack_event

            async def _dispatch_mention() -> None:
                await self._handler.handle_event(_mention_event, self)

            self._get_queue(channel).enqueue(_dispatch_mention)

    async def _handle_message(self, event: dict[str, Any]) -> None:
        """Handle a general message event (for logging + DMs)."""
        channel: str = event.get("channel", "")
        user: str | None = event.get("user")
        ts: str = event.get("ts", "")
        text: str = event.get("text") or ""
        channel_type: str = event.get("channel_type", "")
        subtype: str | None = event.get("subtype")
        bot_id: str | None = event.get("bot_id")
        files: list[dict[str, Any]] | None = event.get("files")

        # Skip bot messages, edits, etc.
        if bot_id or not user or user == self._bot_user_id:
            return
        if subtype is not None and subtype != "file_share":
            return
        if not text and not files:
            return

        is_dm = channel_type == "im"
        is_bot_mention = self._bot_user_id and f"<@{self._bot_user_id}>" in text

        # Skip channel @mentions — already handled by app_mention event
        if not is_dm and is_bot_mention:
            return

        import re

        clean_text = re.sub(r"<@[A-Z0-9]+>", "", text, flags=re.IGNORECASE).strip()

        slack_event = SlackEvent(
            type="dm" if is_dm else "mention",
            channel=channel,
            ts=ts,
            user=user,
            text=clean_text,
            files=files,
        )

        # Log to log.jsonl — ALL messages
        slack_event.attachments = await self._log_user_message(slack_event)

        # Only trigger processing for messages AFTER startup
        if self._startup_ts and ts < self._startup_ts:
            log.log_info(f"[{channel}] Skipping old message (pre-startup): {clean_text[:30]}")
            return

        # Only trigger handler for DMs
        if is_dm:
            if clean_text.lower().strip() == "stop":
                if self._handler.is_running(channel):
                    self._spawn(self._handler.handle_stop(channel, self))
                else:
                    self._spawn(self.post_message(channel, "_Nothing running_"))
                return

            if self._handler.is_running(channel):
                self._spawn(self.post_message(channel, "_Already working. Say `stop` to cancel._"))
            else:
                _dm_event = slack_event

                async def _dispatch_dm() -> None:
                    await self._handler.handle_event(_dm_event, self)

                self._get_queue(channel).enqueue(_dispatch_dm)

    async def _log_user_message(self, event: SlackEvent) -> list[Attachment]:
        """Log a user message to log.jsonl."""
        import datetime

        user = self._users.get(event.user)
        attachments = self._store.process_attachments(event.channel, event.files, event.ts) if event.files else []
        date = datetime.datetime.fromtimestamp(float(event.ts), tz=datetime.UTC).isoformat()
        await self.log_to_file(
            event.channel,
            {
                "date": date,
                "ts": event.ts,
                "user": event.user,
                "userName": user.user_name if user else None,
                "displayName": user.display_name if user else None,
                "text": event.text,
                "attachments": [{"original": a.original, "local": a.local} for a in attachments],
                "isBot": False,
            },
        )
        return attachments

    # ==========================================================================
    # Private — Backfill
    # ==========================================================================

    async def _get_existing_timestamps(self, channel_id: str) -> set[str]:
        log_path = os.path.join(self._working_dir, channel_id, "log.jsonl")
        timestamps: set[str] = set()
        if not os.path.exists(log_path):
            return timestamps
        content = await asyncio.to_thread(_read_text_file, log_path)
        for line in content.strip().split("\n"):
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("ts"):
                    timestamps.add(str(entry["ts"]))
            except Exception:
                pass
        return timestamps

    async def _backfill_channel(self, channel_id: str) -> int:
        """Backfill missed messages for a channel. Returns count of new messages."""
        existing_ts = await self._get_existing_timestamps(channel_id)

        # Find the latest timestamp we already have
        latest_ts: str | None = None
        for ts in existing_ts:
            if latest_ts is None or float(ts) > float(latest_ts):
                latest_ts = ts

        all_messages: list[dict[str, Any]] = []
        cursor: str | None = None
        page_count = 0
        max_pages = 3

        while True:
            kwargs: dict[str, Any] = {
                "channel": channel_id,
                "inclusive": False,
                "limit": 1000,
            }
            if latest_ts:
                kwargs["oldest"] = latest_ts
            if cursor:
                kwargs["cursor"] = cursor

            result = await self._web_client.conversations_history(**kwargs)
            messages = result.get("messages") or []
            all_messages.extend(messages)
            cursor = (result.get("response_metadata") or {}).get("next_cursor")
            page_count += 1
            if not cursor or page_count >= max_pages:
                break

        # Filter relevant messages
        import datetime

        relevant = []
        for msg in all_messages:
            msg_ts = msg.get("ts", "")
            if not msg_ts or msg_ts in existing_ts:
                continue
            if msg.get("user") == self._bot_user_id:
                relevant.append(msg)
                continue
            if msg.get("bot_id"):
                continue
            sub = msg.get("subtype")
            if sub is not None and sub != "file_share":
                continue
            if not msg.get("user"):
                continue
            if not msg.get("text") and not msg.get("files"):
                continue
            relevant.append(msg)

        # Sort chronologically
        relevant.reverse()

        for msg in relevant:
            msg_ts = msg.get("ts", "")
            is_mom = msg.get("user") == self._bot_user_id
            user = self._users.get(msg.get("user", ""))

            import re

            text = re.sub(r"<@[A-Z0-9]+>", "", msg.get("text") or "", flags=re.IGNORECASE).strip()
            attachments = self._store.process_attachments(channel_id, msg["files"], msg_ts) if msg.get("files") else []

            date_str = datetime.datetime.fromtimestamp(float(msg_ts), tz=datetime.UTC).isoformat()

            await self.log_to_file(
                channel_id,
                {
                    "date": date_str,
                    "ts": msg_ts,
                    "user": "bot" if is_mom else msg.get("user", ""),
                    "userName": None if is_mom else (user.user_name if user else None),
                    "displayName": None if is_mom else (user.display_name if user else None),
                    "text": text,
                    "attachments": [{"original": a.original, "local": a.local} for a in attachments],
                    "isBot": is_mom,
                },
            )

        return len(relevant)

    async def _backfill_all_channels(self) -> None:
        """Backfill all channels that already have a log.jsonl."""
        start_time = time.time()

        channels_to_backfill = [
            (cid, ch)
            for cid, ch in self._channels.items()
            if os.path.exists(os.path.join(self._working_dir, cid, "log.jsonl"))
        ]

        log.log_backfill_start(len(channels_to_backfill))

        total_messages = 0
        for channel_id, channel in channels_to_backfill:
            try:
                count = await self._backfill_channel(channel_id)
                if count > 0:
                    log.log_backfill_channel(channel.name, count)
                total_messages += count
            except Exception as exc:
                log.log_warning(f"Failed to backfill #{channel.name}", str(exc))

        duration_ms = (time.time() - start_time) * 1000
        log.log_backfill_complete(total_messages, duration_ms)

    # ==========================================================================
    # Private — Fetch Users/Channels
    # ==========================================================================

    async def _fetch_users(self) -> None:
        cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {"limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            result = await self._web_client.users_list(**kwargs)
            members = result.get("members") or []
            for u in members:
                if u.get("id") and u.get("name") and not u.get("deleted"):
                    self._users[u["id"]] = SlackUser(
                        id=u["id"],
                        user_name=u["name"],
                        display_name=u.get("real_name") or u["name"],
                    )
            cursor = (result.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break

    async def _fetch_channels(self) -> None:
        # Public + private channels
        cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "types": "public_channel,private_channel",
                "exclude_archived": True,
                "limit": 200,
            }
            if cursor:
                kwargs["cursor"] = cursor
            result = await self._web_client.conversations_list(**kwargs)
            channels = result.get("channels") or []
            for c in channels:
                if c.get("id") and c.get("name") and c.get("is_member"):
                    self._channels[c["id"]] = SlackChannel(id=c["id"], name=c["name"])
            cursor = (result.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break

        # DM channels (IMs)
        cursor = None
        while True:
            kwargs = {"types": "im", "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            result = await self._web_client.conversations_list(**kwargs)
            ims = result.get("channels") or []
            for im in ims:
                if im.get("id"):
                    im_user = im.get("user")
                    user = self._users.get(im_user) if im_user else None
                    name = f"DM:{user.user_name}" if user else f"DM:{im['id']}"
                    self._channels[im["id"]] = SlackChannel(id=im["id"], name=name)
            cursor = (result.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break


def _append_log_line(path: str, line: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def _read_text_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()
