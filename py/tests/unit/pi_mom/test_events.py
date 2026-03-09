"""Tests for pi_mom.events."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from pi_mom.events import (
    EventsWatcher,
    ImmediateEvent,
    OneShotEvent,
    PeriodicEvent,
    _parse_event,
    create_events_watcher,
)


class TestParseEvent:
    def test_parse_immediate(self) -> None:
        content = json.dumps({"type": "immediate", "channelId": "C123", "text": "Hello"})
        event = _parse_event(content, "test.json")
        assert isinstance(event, ImmediateEvent)
        assert event.channel_id == "C123"
        assert event.text == "Hello"

    def test_parse_one_shot(self) -> None:
        content = json.dumps(
            {"type": "one-shot", "channelId": "C123", "text": "Remind me", "at": "2025-12-01T09:00:00+01:00"}
        )
        event = _parse_event(content, "test.json")
        assert isinstance(event, OneShotEvent)
        assert event.at == "2025-12-01T09:00:00+01:00"

    def test_parse_periodic(self) -> None:
        content = json.dumps(
            {
                "type": "periodic",
                "channelId": "C123",
                "text": "Check inbox",
                "schedule": "0 9 * * *",
                "timezone": "Europe/Vienna",
            }
        )
        event = _parse_event(content, "test.json")
        assert isinstance(event, PeriodicEvent)
        assert event.schedule == "0 9 * * *"
        assert event.timezone == "Europe/Vienna"

    def test_parse_missing_fields(self) -> None:
        content = json.dumps({"type": "immediate"})
        with pytest.raises(ValueError, match="Missing required fields"):
            _parse_event(content, "test.json")

    def test_parse_unknown_type(self) -> None:
        content = json.dumps({"type": "unknown", "channelId": "C123", "text": "Hi"})
        with pytest.raises(ValueError, match="Unknown event type"):
            _parse_event(content, "test.json")

    def test_parse_one_shot_missing_at(self) -> None:
        content = json.dumps({"type": "one-shot", "channelId": "C123", "text": "Hi"})
        with pytest.raises(ValueError, match="Missing 'at'"):
            _parse_event(content, "test.json")

    def test_parse_periodic_missing_schedule(self) -> None:
        content = json.dumps({"type": "periodic", "channelId": "C123", "text": "Hi", "timezone": "UTC"})
        with pytest.raises(ValueError, match="Missing 'schedule'"):
            _parse_event(content, "test.json")

    def test_parse_invalid_json(self) -> None:
        with pytest.raises((ValueError, KeyError)):
            _parse_event("NOT JSON", "bad.json")


class TestCreateEventsWatcher:
    def test_creates_watcher(self, tmp_path: Any) -> None:
        slack_mock = MagicMock()
        watcher = create_events_watcher(str(tmp_path), slack_mock)
        assert isinstance(watcher, EventsWatcher)
        assert watcher._events_dir == os.path.join(str(tmp_path), "events")

    @pytest.mark.asyncio
    async def test_start_stop(self, tmp_path: Any) -> None:
        slack_mock = MagicMock()
        events_dir = os.path.join(str(tmp_path), "events")
        watcher = EventsWatcher(events_dir, slack_mock)
        watcher.start()
        assert os.path.isdir(events_dir)
        watcher.stop()
        assert watcher._stopped

    @pytest.mark.asyncio
    async def test_immediate_event_triggers(self, tmp_path: Any) -> None:
        """A new immediate event file should be detected and enqueued."""
        events_dir = os.path.join(str(tmp_path), "events")
        os.makedirs(events_dir)

        enqueued_events: list[Any] = []
        slack_mock = MagicMock()

        def _enqueue(e: Any) -> bool:
            enqueued_events.append(e)
            return True

        slack_mock.enqueue_event = MagicMock(side_effect=_enqueue)

        watcher = EventsWatcher(events_dir, slack_mock)
        watcher.start()

        # Write an immediate event file (after start so it's not stale)
        await asyncio.sleep(0.05)  # Let watcher start
        event_file = os.path.join(events_dir, "test_event.json")
        with open(event_file, "w") as f:
            json.dump({"type": "immediate", "channelId": "C123", "text": "Hello from event"}, f)

        # Wait for polling to detect the file
        await asyncio.sleep(1.0)

        watcher.stop()

        # The event should have been enqueued
        assert len(enqueued_events) >= 1

    @pytest.mark.asyncio
    async def test_past_one_shot_deleted(self, tmp_path: Any) -> None:
        """A one-shot event in the past should be deleted without executing."""
        events_dir = os.path.join(str(tmp_path), "events")
        os.makedirs(events_dir)

        slack_mock = MagicMock()
        slack_mock.enqueue_event = MagicMock(return_value=True)

        watcher = EventsWatcher(events_dir, slack_mock)
        watcher.start()

        event_file = os.path.join(events_dir, "past_event.json")
        with open(event_file, "w") as f:
            json.dump(
                {"type": "one-shot", "channelId": "C123", "text": "Past event", "at": "2020-01-01T00:00:00+00:00"},
                f,
            )

        await asyncio.sleep(1.0)
        watcher.stop()

        # File should be deleted (past events are deleted, not executed)
        assert not os.path.exists(event_file)
        slack_mock.enqueue_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_event_file_deleted(self, tmp_path: Any) -> None:
        """An invalid event file should be deleted."""
        events_dir = os.path.join(str(tmp_path), "events")
        os.makedirs(events_dir)

        slack_mock = MagicMock()
        watcher = EventsWatcher(events_dir, slack_mock)
        watcher.start()

        event_file = os.path.join(events_dir, "bad_event.json")
        with open(event_file, "w") as f:
            f.write('{"type": "unknown_type", "channelId": "C123", "text": "bad"}')

        await asyncio.sleep(1.0)
        watcher.stop()

        # Invalid event files should be deleted
        assert not os.path.exists(event_file)

    @pytest.mark.asyncio
    async def test_stale_immediate_event_deleted(self, tmp_path: Any) -> None:
        """A stale immediate event (older than startup) should be deleted."""
        events_dir = os.path.join(str(tmp_path), "events")
        os.makedirs(events_dir)

        # Create a file BEFORE creating the watcher
        event_file = os.path.join(events_dir, "stale.json")
        with open(event_file, "w") as f:
            json.dump({"type": "immediate", "channelId": "C123", "text": "Stale"}, f)

        await asyncio.sleep(0.05)  # Ensure mtime is in the past relative to watcher

        slack_mock = MagicMock()
        slack_mock.enqueue_event = MagicMock(return_value=True)

        watcher = EventsWatcher(events_dir, slack_mock)
        watcher.start()

        await asyncio.sleep(0.8)
        watcher.stop()

        # Stale file should be deleted and NOT enqueued
        assert not os.path.exists(event_file)
        slack_mock.enqueue_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_directory_handles_deleted_file(self, tmp_path: Any) -> None:
        """EventsWatcher handles files deleted mid-scan gracefully."""
        events_dir = os.path.join(str(tmp_path), "events")
        os.makedirs(events_dir)

        slack_mock = MagicMock()
        watcher = EventsWatcher(events_dir, slack_mock)
        watcher.start()

        # No files — just make sure it doesn't crash
        await asyncio.sleep(0.6)
        watcher.stop()
        assert watcher._stopped


class TestEventHandling:
    """Tests for direct event handling methods."""

    def _make_watcher(self, tmp_path: Any) -> tuple[Any, Any]:
        from pi_mom.events import EventsWatcher

        events_dir = os.path.join(str(tmp_path), "events")
        os.makedirs(events_dir)
        slack_mock = MagicMock()
        slack_mock.enqueue_event = MagicMock(return_value=True)
        watcher = EventsWatcher(events_dir, slack_mock)
        return watcher, slack_mock

    @pytest.mark.asyncio
    async def test_handle_file_parses_immediate(self, tmp_path: Any) -> None:
        watcher, slack_mock = self._make_watcher(tmp_path)
        event_file = os.path.join(watcher._events_dir, "test.json")
        with open(event_file, "w") as f:
            json.dump({"type": "immediate", "channelId": "C123", "text": "Go"}, f)

        # Set start time in the past so the file is not stale
        watcher._start_time = time.time() - 10.0
        await watcher._handle_file("test.json")

        # Should enqueue and delete
        slack_mock.enqueue_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_file_missing_file(self, tmp_path: Any) -> None:
        watcher, _ = self._make_watcher(tmp_path)
        # Should not raise
        await watcher._handle_file("nonexistent.json")

    @pytest.mark.asyncio
    async def test_handle_delete(self, tmp_path: Any) -> None:
        watcher, _ = self._make_watcher(tmp_path)
        watcher._known_files["foo.json"] = time.time()
        watcher._handle_delete("foo.json")
        assert "foo.json" not in watcher._known_files

    @pytest.mark.asyncio
    async def test_cancel_scheduled(self, tmp_path: Any) -> None:
        watcher, _ = self._make_watcher(tmp_path)
        loop = asyncio.get_event_loop()
        handle = loop.call_later(100, lambda: None)
        watcher._timers["foo.json"] = handle
        watcher._cancel_scheduled("foo.json")
        assert "foo.json" not in watcher._timers

    @pytest.mark.asyncio
    async def test_handle_one_shot_in_the_past(self, tmp_path: Any) -> None:
        """A one-shot event with an at time in the past should be deleted."""
        watcher, _ = self._make_watcher(tmp_path)
        import datetime

        past = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
        event = OneShotEvent(type="one-shot", channel_id="C123", text="Hello", at=past)
        event_file = os.path.join(watcher._events_dir, "past.json")
        open(event_file, "w").close()
        watcher._known_files["past.json"] = time.time()

        watcher._handle_one_shot("past.json", event)
        assert not os.path.exists(event_file)

    @pytest.mark.asyncio
    async def test_handle_one_shot_invalid_at(self, tmp_path: Any) -> None:
        """A one-shot event with an invalid 'at' should be deleted."""
        watcher, _ = self._make_watcher(tmp_path)
        event = OneShotEvent(type="one-shot", channel_id="C123", text="Hello", at="not-a-date")
        event_file = os.path.join(watcher._events_dir, "bad.json")
        open(event_file, "w").close()
        watcher._known_files["bad.json"] = time.time()

        watcher._handle_one_shot("bad.json", event)
        assert not os.path.exists(event_file)

    @pytest.mark.asyncio
    async def test_handle_one_shot_future(self, tmp_path: Any) -> None:
        """A one-shot event in the future should register a timer."""
        watcher, _ = self._make_watcher(tmp_path)
        import datetime

        future = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
        event = OneShotEvent(type="one-shot", channel_id="C123", text="Hello", at=future)
        event_file = os.path.join(watcher._events_dir, "future.json")
        open(event_file, "w").close()
        watcher._known_files["future.json"] = time.time()

        watcher._handle_one_shot("future.json", event)
        assert "future.json" in watcher._timers
        # Clean up timer
        watcher._timers["future.json"].cancel()
        del watcher._timers["future.json"]

    @pytest.mark.asyncio
    async def test_handle_periodic_valid(self, tmp_path: Any) -> None:
        """A periodic event with valid cron should create a cron task."""
        watcher, _ = self._make_watcher(tmp_path)
        event = PeriodicEvent(
            type="periodic",
            channel_id="C123",
            text="Check",
            schedule="* * * * *",
            timezone="UTC",
        )
        event_file = os.path.join(watcher._events_dir, "cron.json")
        open(event_file, "w").close()
        watcher._known_files["cron.json"] = time.time()

        watcher._handle_periodic("cron.json", event)
        assert "cron.json" in watcher._cron_tasks
        watcher._cron_tasks["cron.json"].cancel()
        del watcher._cron_tasks["cron.json"]

    @pytest.mark.asyncio
    async def test_handle_periodic_invalid_cron(self, tmp_path: Any) -> None:
        """A periodic event with invalid cron should delete the file."""
        watcher, _ = self._make_watcher(tmp_path)
        event = PeriodicEvent(
            type="periodic",
            channel_id="C123",
            text="Check",
            schedule="not-a-cron",
            timezone="UTC",
        )
        event_file = os.path.join(watcher._events_dir, "badcron.json")
        open(event_file, "w").close()
        watcher._known_files["badcron.json"] = time.time()

        watcher._handle_periodic("badcron.json", event)
        assert not os.path.exists(event_file)

    @pytest.mark.asyncio
    async def test_execute_enqueues_event(self, tmp_path: Any) -> None:
        """_execute should build a SlackEvent and enqueue it via slack."""
        watcher, slack_mock = self._make_watcher(tmp_path)
        event = ImmediateEvent(type="immediate", channel_id="C999", text="Run me")

        watcher._execute("run.json", event, delete_after=False)

        slack_mock.enqueue_event.assert_called_once()
        call_arg = slack_mock.enqueue_event.call_args[0][0]
        assert call_arg.channel == "C999"
        assert "Run me" in call_arg.text

    @pytest.mark.asyncio
    async def test_execute_delete_after_true(self, tmp_path: Any) -> None:
        """_execute with delete_after=True should remove file after enqueueing."""
        watcher, slack_mock = self._make_watcher(tmp_path)
        slack_mock.enqueue_event.return_value = True
        event = ImmediateEvent(type="immediate", channel_id="C888", text="Do it")
        event_file = os.path.join(watcher._events_dir, "del.json")
        open(event_file, "w").close()
        watcher._known_files["del.json"] = time.time()

        watcher._execute("del.json", event, delete_after=True)

        assert not os.path.exists(event_file)

    @pytest.mark.asyncio
    async def test_execute_queue_full_deletes_file(self, tmp_path: Any) -> None:
        """When enqueue_event returns False, file should be deleted."""
        watcher, slack_mock = self._make_watcher(tmp_path)
        slack_mock.enqueue_event.return_value = False
        event = ImmediateEvent(type="immediate", channel_id="C777", text="Full")
        event_file = os.path.join(watcher._events_dir, "full.json")
        open(event_file, "w").close()
        watcher._known_files["full.json"] = time.time()

        watcher._execute("full.json", event, delete_after=True)

        assert not os.path.exists(event_file)

    @pytest.mark.asyncio
    async def test_handle_file_one_shot_type(self, tmp_path: Any) -> None:
        """_handle_file for a one-shot event in the future registers a timer."""
        watcher, _ = self._make_watcher(tmp_path)
        import datetime

        future = (datetime.datetime.now() + datetime.timedelta(hours=2)).isoformat()
        event_data = {"type": "one-shot", "channelId": "C123", "text": "Remind", "at": future}
        event_file = os.path.join(watcher._events_dir, "oneshot.json")
        with open(event_file, "w") as f:
            json.dump(event_data, f)

        watcher._start_time = time.time() - 10.0
        await watcher._handle_file("oneshot.json")

        assert "oneshot.json" in watcher._timers
        watcher._timers["oneshot.json"].cancel()

    @pytest.mark.asyncio
    async def test_handle_file_periodic_type(self, tmp_path: Any) -> None:
        """_handle_file for a periodic event registers a cron task."""
        watcher, _ = self._make_watcher(tmp_path)
        event_data = {
            "type": "periodic",
            "channelId": "C123",
            "text": "Tick",
            "schedule": "* * * * *",
            "timezone": "UTC",
        }
        event_file = os.path.join(watcher._events_dir, "periodic.json")
        with open(event_file, "w") as f:
            json.dump(event_data, f)

        watcher._start_time = time.time() - 10.0
        await watcher._handle_file("periodic.json")

        assert "periodic.json" in watcher._cron_tasks
        watcher._cron_tasks["periodic.json"].cancel()

    @pytest.mark.asyncio
    async def test_delete_file_removes_from_tracking(self, tmp_path: Any) -> None:
        """_delete_file removes file and known_files entry."""
        watcher, _ = self._make_watcher(tmp_path)
        event_file = os.path.join(watcher._events_dir, "tracked.json")
        open(event_file, "w").close()
        watcher._known_files["tracked.json"] = time.time()

        watcher._delete_file("tracked.json")

        assert not os.path.exists(event_file)
        assert "tracked.json" not in watcher._known_files

    @pytest.mark.asyncio
    async def test_stop_cancels_timers_and_cron_tasks(self, tmp_path: Any) -> None:
        """stop() should cancel all debounce_tasks, timers, and cron_tasks."""
        watcher, _ = self._make_watcher(tmp_path)

        loop = asyncio.get_event_loop()

        # Register a timer
        handle = loop.call_later(100, lambda: None)
        watcher._timers["timer.json"] = handle

        # Register a cron task
        async def _dummy() -> None:
            await asyncio.sleep(100)

        cron_task = asyncio.create_task(_dummy())
        watcher._cron_tasks["cron.json"] = cron_task

        # Register a debounce task
        debounce_task = asyncio.create_task(_dummy())
        watcher._debounce_tasks["debounce.json"] = debounce_task

        # Register a poll task so stop() can cancel it
        watcher._poll_task = asyncio.create_task(_dummy())
        watcher.stop()

        assert len(watcher._timers) == 0
        assert len(watcher._cron_tasks) == 0
        assert len(watcher._debounce_tasks) == 0
        assert watcher._stopped is True

    @pytest.mark.asyncio
    async def test_check_directory_detects_new_file(self, tmp_path: Any) -> None:
        """_check_directory should detect new .json files and trigger debouncing."""
        watcher, _ = self._make_watcher(tmp_path)

        event_file = os.path.join(watcher._events_dir, "new.json")
        with open(event_file, "w") as f:
            json.dump({"type": "immediate", "channelId": "C123", "text": "Hi"}, f)

        await watcher._check_directory()

        # A debounce task should be created for the new file
        assert "new.json" in watcher._debounce_tasks
        watcher._debounce_tasks["new.json"].cancel()

    @pytest.mark.asyncio
    async def test_check_directory_detects_deleted_file(self, tmp_path: Any) -> None:
        """_check_directory should call _handle_delete for files that disappeared."""
        watcher, _ = self._make_watcher(tmp_path)
        watcher._known_files["gone.json"] = time.time()

        # Don't create the file — so it should be detected as deleted
        await watcher._check_directory()

        assert "gone.json" not in watcher._known_files

    @pytest.mark.asyncio
    async def test_check_directory_no_events_dir(self, tmp_path: Any) -> None:
        """_check_directory should handle missing events directory gracefully."""
        watcher, _ = self._make_watcher(tmp_path)
        # Remove the events directory
        import shutil

        shutil.rmtree(watcher._events_dir)

        # Should not raise
        await watcher._check_directory()

    @pytest.mark.asyncio
    async def test_handle_file_deleted_during_retry(self, tmp_path: Any) -> None:
        """_handle_file returns gracefully when file is deleted while retrying."""
        watcher, _ = self._make_watcher(tmp_path)
        # Don't create the file — triggers FileNotFoundError immediately
        await watcher._handle_file("nonexistent.json")  # Should not raise

    @pytest.mark.asyncio
    async def test_cancel_scheduled_cancels_cron_task(self, tmp_path: Any) -> None:
        """_cancel_scheduled should also cancel cron tasks."""
        watcher, _ = self._make_watcher(tmp_path)

        async def _dummy() -> None:
            await asyncio.sleep(100)

        cron_task = asyncio.create_task(_dummy())
        watcher._cron_tasks["cron.json"] = cron_task

        watcher._cancel_scheduled("cron.json")
        assert "cron.json" not in watcher._cron_tasks

    @pytest.mark.asyncio
    async def test_handle_immediate_stale_event_deleted(self, tmp_path: Any) -> None:
        """An immediate event older than start_time should be deleted as stale."""
        watcher, slack_mock = self._make_watcher(tmp_path)

        # Write event file
        event_file = os.path.join(watcher._events_dir, "stale.json")
        with open(event_file, "w") as f:
            json.dump({"type": "immediate", "channelId": "C123", "text": "Old"}, f)

        # Set start_time in the future so the file appears stale
        watcher._start_time = time.time() + 1000
        await watcher._handle_file("stale.json")

        # File should be deleted as stale
        assert not os.path.exists(event_file)
        slack_mock.enqueue_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_cron_loop_executes_and_stops(self, tmp_path: Any) -> None:
        """_cron_loop should fire at least once and stop when _stopped is True."""
        watcher, _ = self._make_watcher(tmp_path)

        event = PeriodicEvent(
            type="periodic",
            channel_id="C123",
            text="Tick",
            schedule="* * * * *",
            timezone="UTC",
        )

        # Set _stopped to True immediately after 1 second so the loop terminates
        import contextlib

        async def stop_soon() -> None:
            await asyncio.sleep(0.1)
            watcher._stopped = True

        stop_task = asyncio.create_task(stop_soon())
        watcher._cron_tasks["cron.json"] = asyncio.create_task(watcher._cron_loop("cron.json", event))

        with contextlib.suppress(TimeoutError, Exception):
            await asyncio.wait_for(
                asyncio.gather(
                    watcher._cron_tasks["cron.json"],
                    stop_task,
                    return_exceptions=True,
                ),
                timeout=2.0,
            )
