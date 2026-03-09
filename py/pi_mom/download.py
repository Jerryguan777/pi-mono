"""Channel download utility — port of packages/mom/src/download.ts."""

from __future__ import annotations

import sys
from datetime import UTC, datetime


def _format_ts(ts: str) -> str:
    """Format a Slack timestamp as a readable date string."""
    date = datetime.fromtimestamp(float(ts), tz=UTC)
    return date.strftime("%Y-%m-%d %H:%M:%S")


def _format_message(ts: str, user: str, text: str, indent: str = "") -> str:
    prefix = f"[{_format_ts(ts)}] {user}: "
    lines = text.split("\n")
    first_line = f"{indent}{prefix}{lines[0]}"
    if len(lines) == 1:
        return first_line
    content_indent = indent + " " * len(prefix)
    continuation = [content_indent + line for line in lines[1:]]
    return "\n".join([first_line, *continuation])


async def download_channel(channel_id: str, bot_token: str) -> None:
    """Download and print the full message history of a Slack channel."""
    from slack_sdk.web.async_client import AsyncWebClient

    client = AsyncWebClient(token=bot_token)

    print(f"Fetching channel info for {channel_id}...", file=sys.stderr)

    # Get channel info
    channel_name = channel_id
    try:
        info = await client.conversations_info(channel=channel_id)
        channel_data = info.get("channel") or {}
        channel_name = channel_data.get("name") or channel_id
    except Exception:
        pass  # DM channels don't have names

    print(f"Downloading history for #{channel_name} ({channel_id})...", file=sys.stderr)

    # Fetch all messages
    all_messages: list[dict[str, object]] = []
    cursor: str | None = None

    while True:
        kwargs: dict[str, object] = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        response = await client.conversations_history(**kwargs)  # type: ignore[arg-type]
        messages = response.get("messages") or []
        all_messages.extend(messages)
        cursor = (response.get("response_metadata") or {}).get("next_cursor")
        print(f"  Fetched {len(all_messages)} messages...", file=sys.stderr)
        if not cursor:
            break

    # Reverse to chronological order
    all_messages.reverse()

    # Fetch thread replies for messages that have them
    thread_replies: dict[str, list[dict[str, object]]] = {}
    threads_to_fetch = [m for m in all_messages if m.get("reply_count")]
    print(f"Fetching {len(threads_to_fetch)} threads...", file=sys.stderr)

    for i, parent in enumerate(threads_to_fetch):
        parent_ts = str(parent.get("ts", ""))
        reply_count = parent.get("reply_count", 0)
        print(f"  Thread {i + 1}/{len(threads_to_fetch)} ({reply_count} replies)...", file=sys.stderr)

        replies: list[dict[str, object]] = []
        thread_cursor: str | None = None

        while True:
            kwargs2: dict[str, object] = {"channel": channel_id, "ts": parent_ts, "limit": 200}
            if thread_cursor:
                kwargs2["cursor"] = thread_cursor
            resp = await client.conversations_replies(**kwargs2)  # type: ignore[arg-type]
            reply_messages = resp.get("messages") or []
            # Skip the first message (it's the parent)
            replies.extend(reply_messages[1:])
            thread_cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not thread_cursor:
                break

        thread_replies[parent_ts] = replies

    # Output messages with thread replies interleaved
    total_replies = 0
    for msg in all_messages:
        msg_ts = str(msg.get("ts", ""))
        user_id = str(msg.get("user") or "unknown")
        text = str(msg.get("text") or "")
        print(_format_message(msg_ts, user_id, text))

        replies = thread_replies.get(msg_ts, [])
        for reply in replies:
            r_ts = str(reply.get("ts", ""))
            r_user = str(reply.get("user") or "unknown")
            r_text = str(reply.get("text") or "")
            print(_format_message(r_ts, r_user, r_text, indent="  "))
            total_replies += 1

    print(f"Done! {len(all_messages)} messages, {total_replies} thread replies", file=sys.stderr)
