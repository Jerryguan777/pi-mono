"""Integration test: Mom event -> agent call chain.

Verifies the end-to-end path: event JSON file -> EventsWatcher picks it up ->
synthetic SlackEvent is enqueued -> fake Slack client receives it.

Uses an in-memory fake SlackBot that implements the real enqueue_event interface.
No network calls, no real Slack API.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from collections.abc import Generator

import pytest

from pi_mom.events import EventsWatcher, ImmediateEvent, _parse_event
from pi_mom.slack import SlackEvent


class FakeSlackBot:
    """In-memory SlackBot that collects enqueued events for verification.

    Implements the interface expected by EventsWatcher: enqueue_event(SlackEvent) -> bool.
    """

    def __init__(self) -> None:
        self.enqueued: list[SlackEvent] = []

    def enqueue_event(self, event: SlackEvent) -> bool:
        self.enqueued.append(event)
        return True


@pytest.fixture()
def events_dir() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as d:
        yield d


async def test_immediate_event_triggers_enqueue(events_dir: str) -> None:
    """Writing an immediate event JSON to the events dir should trigger
    EventsWatcher to enqueue a synthetic SlackEvent."""
    fake_slack = FakeSlackBot()

    # Type-ignore because FakeSlackBot is a duck-type match, not a real SlackBot
    watcher = EventsWatcher(events_dir, fake_slack)  # type: ignore[arg-type]

    # Write event file AFTER starting the watcher so it's not stale
    watcher.start()

    # Small delay to let the poll loop start
    await asyncio.sleep(0.05)

    event_data = {
        "type": "immediate",
        "channelId": "C12345",
        "text": "Hello from integration test",
    }
    event_file = os.path.join(events_dir, "test_event.json")
    with open(event_file, "w") as f:
        json.dump(event_data, f)

    # Wait for the watcher to detect and process the file
    # Poll interval is 0.5s + debounce 0.1s, so wait ~1s
    for _ in range(20):
        await asyncio.sleep(0.1)
        if fake_slack.enqueued:
            break

    watcher.stop()

    # Verify the event was enqueued
    assert len(fake_slack.enqueued) >= 1
    enqueued = fake_slack.enqueued[0]
    assert enqueued.channel == "C12345"
    assert "Hello from integration test" in enqueued.text
    assert enqueued.type == "mention"
    assert enqueued.user == "EVENT"


async def test_event_file_deleted_after_processing(events_dir: str) -> None:
    """Immediate event files should be deleted after processing."""
    fake_slack = FakeSlackBot()
    watcher = EventsWatcher(events_dir, fake_slack)  # type: ignore[arg-type]
    watcher.start()

    await asyncio.sleep(0.05)

    event_data = {
        "type": "immediate",
        "channelId": "C99999",
        "text": "Delete me after processing",
    }
    event_file = os.path.join(events_dir, "deletable.json")
    with open(event_file, "w") as f:
        json.dump(event_data, f)

    for _ in range(20):
        await asyncio.sleep(0.1)
        if fake_slack.enqueued:
            break

    watcher.stop()

    # The event file should have been deleted
    assert not os.path.exists(event_file)


async def test_stale_event_is_ignored(events_dir: str) -> None:
    """Event files created before the watcher started should be treated as stale."""
    # Write event file BEFORE starting watcher
    event_data = {
        "type": "immediate",
        "channelId": "C11111",
        "text": "Stale event",
    }
    event_file = os.path.join(events_dir, "stale.json")
    with open(event_file, "w") as f:
        json.dump(event_data, f)

    # Set file mtime to the past
    past_time = time.time() - 60
    os.utime(event_file, (past_time, past_time))

    fake_slack = FakeSlackBot()
    watcher = EventsWatcher(events_dir, fake_slack)  # type: ignore[arg-type]

    # Small delay so start_time is definitely after the file mtime
    await asyncio.sleep(0.05)
    watcher.start()

    # Wait for processing
    await asyncio.sleep(1.5)
    watcher.stop()

    # Stale immediate events should be deleted and NOT enqueued
    stale_events = [e for e in fake_slack.enqueued if "Stale event" in e.text]
    assert len(stale_events) == 0


def test_parse_event_immediate() -> None:
    """Verify _parse_event correctly parses an immediate event JSON."""
    content = json.dumps({"type": "immediate", "channelId": "C123", "text": "hello"})
    event = _parse_event(content, "test.json")
    assert isinstance(event, ImmediateEvent)
    assert event.channel_id == "C123"
    assert event.text == "hello"


def test_parse_event_missing_fields() -> None:
    """_parse_event should raise on missing required fields."""
    content = json.dumps({"type": "immediate", "text": "no channel"})
    with pytest.raises(ValueError, match="Missing required fields"):
        _parse_event(content, "bad.json")


async def test_multiple_events_processed(events_dir: str) -> None:
    """Multiple event files should all be processed."""
    fake_slack = FakeSlackBot()
    watcher = EventsWatcher(events_dir, fake_slack)  # type: ignore[arg-type]
    watcher.start()
    await asyncio.sleep(0.05)

    for i in range(3):
        event_data = {
            "type": "immediate",
            "channelId": f"C{i:05d}",
            "text": f"Event {i}",
        }
        with open(os.path.join(events_dir, f"event_{i}.json"), "w") as f:
            json.dump(event_data, f)

    # Wait for all to be processed
    for _ in range(30):
        await asyncio.sleep(0.1)
        if len(fake_slack.enqueued) >= 3:
            break

    watcher.stop()

    assert len(fake_slack.enqueued) >= 3
    channels = {e.channel for e in fake_slack.enqueued}
    assert "C00000" in channels
    assert "C00001" in channels
    assert "C00002" in channels
