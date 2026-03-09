"""Events watcher for scheduled Slack messages — port of packages/mom/src/events.ts."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import pi_mom.log as log

if TYPE_CHECKING:
    from pi_mom.slack import SlackBot

# ============================================================================
# Event types
# ============================================================================

DEBOUNCE_SECS = 0.1
MAX_RETRIES = 3
RETRY_BASE_SECS = 0.1
POLL_INTERVAL_SECS = 0.5


@dataclass
class ImmediateEvent:
    """Event that triggers as soon as the harness sees the file."""

    channel_id: str
    text: str
    type: Literal["immediate"] = "immediate"


@dataclass
class OneShotEvent:
    """Event that triggers once at a specific time."""

    channel_id: str
    text: str
    at: str  # ISO 8601 with timezone offset
    type: Literal["one-shot"] = "one-shot"


@dataclass
class PeriodicEvent:
    """Event that triggers on a cron schedule."""

    channel_id: str
    text: str
    schedule: str  # cron syntax
    timezone: str  # IANA timezone name
    type: Literal["periodic"] = "periodic"


MomEvent = ImmediateEvent | OneShotEvent | PeriodicEvent


# ============================================================================
# EventsWatcher
# ============================================================================


class EventsWatcher:
    """Watches an events directory and dispatches events to SlackBot."""

    def __init__(self, events_dir: str, slack: SlackBot) -> None:
        self._events_dir = events_dir
        self._slack = slack
        self._start_time = time.time()

        # filename -> mtime for known files
        self._known_files: dict[str, float] = {}

        # Scheduled timers: filename -> asyncio.TimerHandle
        self._timers: dict[str, asyncio.TimerHandle] = {}

        # Cron tasks: filename -> asyncio.Task
        self._cron_tasks: dict[str, asyncio.Task[None]] = {}

        # Debounce tasks: filename -> asyncio.Task
        self._debounce_tasks: dict[str, asyncio.Task[None]] = {}

        # Poll task
        self._poll_task: asyncio.Task[None] | None = None

        # Background scan tasks — kept to prevent GC
        self._scan_tasks: set[asyncio.Task[None]] = set()

        self._stopped = False

    def start(self) -> None:
        """Start watching for events. Call this after SlackBot is ready."""
        os.makedirs(self._events_dir, exist_ok=True)
        log.log_info(f"Events watcher starting, dir: {self._events_dir}")

        # Scan existing files immediately
        self._scan_existing()

        # Start polling loop
        self._poll_task = asyncio.create_task(self._poll_loop())

        log.log_info(f"Events watcher started, tracking {len(self._known_files)} files")

    def stop(self) -> None:
        """Stop watching and cancel all scheduled events."""
        self._stopped = True

        if self._poll_task is not None:
            self._poll_task.cancel()
            self._poll_task = None

        for task in self._debounce_tasks.values():
            task.cancel()
        self._debounce_tasks.clear()

        for handle in self._timers.values():
            handle.cancel()
        self._timers.clear()

        for task in self._cron_tasks.values():
            task.cancel()
        self._cron_tasks.clear()

        self._known_files.clear()
        log.log_info("Events watcher stopped")

    async def _poll_loop(self) -> None:
        """Poll the events directory periodically for file changes."""
        while not self._stopped:
            try:
                await self._check_directory()
            except Exception as exc:
                log.log_warning("Events watcher poll error", str(exc))
            await asyncio.sleep(POLL_INTERVAL_SECS)

    async def _check_directory(self) -> None:
        """Check the events directory for added/removed/modified files."""
        try:
            entries = os.listdir(self._events_dir)
        except FileNotFoundError:
            return

        current_files: dict[str, float] = {}
        for fname in entries:
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self._events_dir, fname)
            try:
                mtime = os.path.getmtime(fpath)
                current_files[fname] = mtime
            except FileNotFoundError:
                continue

        # Detect deleted files
        for fname in list(self._known_files.keys()):
            if fname not in current_files:
                self._handle_delete(fname)

        # Detect new or modified files
        for fname, mtime in current_files.items():
            prev_mtime = self._known_files.get(fname)
            if prev_mtime is None:
                # New file
                self._debounce(fname)
            elif abs(mtime - prev_mtime) > 0.001:
                # Modified file
                self._cancel_scheduled(fname)
                self._debounce(fname)

    def _scan_existing(self) -> None:
        """Scan existing files and handle them."""
        try:
            files = [f for f in os.listdir(self._events_dir) if f.endswith(".json")]
        except FileNotFoundError:
            return
        except Exception as exc:
            log.log_warning("Failed to read events directory", str(exc))
            return

        for fname in files:
            task = asyncio.create_task(self._handle_file(fname))
            self._scan_tasks.add(task)
            task.add_done_callback(self._scan_tasks.discard)

    def _debounce(self, filename: str) -> None:
        """Debounce file handling to avoid rapid re-processing."""
        existing = self._debounce_tasks.get(filename)
        if existing is not None:
            existing.cancel()

        async def _delayed() -> None:
            await asyncio.sleep(DEBOUNCE_SECS)
            self._debounce_tasks.pop(filename, None)
            await self._handle_file(filename)

        self._debounce_tasks[filename] = asyncio.create_task(_delayed())

    def _handle_delete(self, filename: str) -> None:
        """Handle a deleted event file."""
        if filename not in self._known_files:
            return
        log.log_info(f"Event file deleted: {filename}")
        self._cancel_scheduled(filename)
        self._known_files.pop(filename, None)

    def _cancel_scheduled(self, filename: str) -> None:
        """Cancel any scheduled timer or cron task for the file."""
        handle = self._timers.pop(filename, None)
        if handle is not None:
            handle.cancel()

        task = self._cron_tasks.pop(filename, None)
        if task is not None:
            task.cancel()

    async def _handle_file(self, filename: str) -> None:
        """Parse and schedule an event file, with retries."""
        file_path = os.path.join(self._events_dir, filename)

        event: MomEvent | None = None
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                event = _parse_event(content, filename)
                break
            except FileNotFoundError:
                return  # File was deleted while we were retrying
            except Exception as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BASE_SECS * (2**attempt))

        if event is None:
            log.log_warning(
                f"Failed to parse event file after {MAX_RETRIES} retries: {filename}",
                str(last_error),
            )
            self._delete_file(filename)
            return

        # Record known file with mtime
        try:
            self._known_files[filename] = os.path.getmtime(file_path)
        except FileNotFoundError:
            return

        if event.type == "immediate":
            self._handle_immediate(filename, event)
        elif event.type == "one-shot":
            self._handle_one_shot(filename, event)
        elif event.type == "periodic":
            self._handle_periodic(filename, event)

    def _handle_immediate(self, filename: str, event: ImmediateEvent) -> None:
        """Handle an immediate event — execute now if not stale."""
        file_path = os.path.join(self._events_dir, filename)
        try:
            mtime = os.path.getmtime(file_path)
            if mtime < self._start_time:
                log.log_info(f"Stale immediate event, deleting: {filename}")
                self._delete_file(filename)
                return
        except FileNotFoundError:
            return

        log.log_info(f"Executing immediate event: {filename}")
        self._execute(filename, event)

    def _handle_one_shot(self, filename: str, event: OneShotEvent) -> None:
        """Handle a one-shot event — schedule for future execution."""
        import datetime

        try:
            at_time = datetime.datetime.fromisoformat(event.at)
            at_ts = at_time.timestamp()
        except ValueError as exc:
            log.log_warning(f"Invalid 'at' timestamp for {filename}: {event.at}", str(exc))
            self._delete_file(filename)
            return

        now = time.time()
        if at_ts <= now:
            log.log_info(f"One-shot event in the past, deleting: {filename}")
            self._delete_file(filename)
            return

        delay = at_ts - now
        log.log_info(f"Scheduling one-shot event: {filename} in {round(delay)}s")

        loop = asyncio.get_running_loop()

        def _fire() -> None:
            self._timers.pop(filename, None)
            log.log_info(f"Executing one-shot event: {filename}")
            self._execute(filename, event)

        handle = loop.call_later(delay, _fire)
        self._timers[filename] = handle

    def _handle_periodic(self, filename: str, event: PeriodicEvent) -> None:
        """Handle a periodic event — start a cron task."""
        try:
            from croniter import croniter
        except ImportError:
            log.log_warning(f"croniter not installed, cannot schedule periodic event: {filename}")
            self._delete_file(filename)
            return

        try:
            import datetime
            from zoneinfo import ZoneInfo

            # Validate cron expression using the event's timezone
            tz: datetime.tzinfo
            try:
                tz = ZoneInfo(event.timezone)
            except Exception:
                tz = datetime.UTC
            now_dt = datetime.datetime.now(tz=tz)
            cron = croniter(event.schedule, now_dt)
            next_run = cron.get_next(datetime.datetime)
        except Exception as exc:
            log.log_warning(f"Invalid cron schedule for {filename}: {event.schedule}", str(exc))
            self._delete_file(filename)
            return

        log.log_info(f"Scheduled periodic event: {filename}, next run: {next_run.isoformat()}")

        task = asyncio.create_task(self._cron_loop(filename, event))
        self._cron_tasks[filename] = task

    async def _cron_loop(self, filename: str, event: PeriodicEvent) -> None:
        """Run a cron task that fires on the given schedule."""
        try:
            from croniter import croniter
        except ImportError:
            return

        import datetime
        from zoneinfo import ZoneInfo

        while not self._stopped:
            tz: datetime.tzinfo
            try:
                tz = ZoneInfo(event.timezone)
            except Exception:
                tz = datetime.UTC
            now_dt = datetime.datetime.now(tz=tz)
            try:
                cron = croniter(event.schedule, now_dt)
                next_dt = cron.get_next(datetime.datetime)
            except Exception:
                return

            delay = (next_dt - now_dt).total_seconds()
            if delay > 0:
                await asyncio.sleep(delay)

            if self._stopped or filename not in self._cron_tasks:
                return

            log.log_info(f"Executing periodic event: {filename}")
            self._execute(filename, event, delete_after=False)

    def _execute(self, filename: str, event: MomEvent, delete_after: bool = True) -> None:
        """Build a synthetic SlackEvent and enqueue it."""
        from pi_mom.slack import SlackEvent

        if event.type == "immediate":
            schedule_info = "immediate"
        elif event.type == "one-shot":
            schedule_info = event.at
        else:
            schedule_info = event.schedule

        message = f"[EVENT:{filename}:{event.type}:{schedule_info}] {event.text}"

        synthetic: SlackEvent = SlackEvent(
            type="mention",
            channel=event.channel_id,
            user="EVENT",
            text=message,
            ts=str(int(time.time() * 1000)),
        )

        enqueued = self._slack.enqueue_event(synthetic)

        if enqueued and delete_after:
            self._delete_file(filename)
        elif not enqueued:
            log.log_warning(f"Event queue full, discarded: {filename}")
            if delete_after:
                self._delete_file(filename)

    def _delete_file(self, filename: str) -> None:
        """Delete an event file and remove it from tracking."""
        file_path = os.path.join(self._events_dir, filename)
        try:
            os.unlink(file_path)
        except FileNotFoundError:
            pass
        except Exception as exc:
            log.log_warning(f"Failed to delete event file: {filename}", str(exc))
        self._known_files.pop(filename, None)


def _parse_event(content: str, filename: str) -> MomEvent:
    """Parse a JSON event file into a MomEvent."""
    data: dict[str, Any] = json.loads(content)

    if not data.get("type") or not data.get("channelId") or not data.get("text"):
        raise ValueError(f"Missing required fields (type, channelId, text) in {filename}")

    event_type: str = data["type"]
    channel_id: str = data["channelId"]
    text: str = data["text"]

    if event_type == "immediate":
        return ImmediateEvent(channel_id=channel_id, text=text)
    elif event_type == "one-shot":
        if not data.get("at"):
            raise ValueError(f"Missing 'at' field for one-shot event in {filename}")
        return OneShotEvent(channel_id=channel_id, text=text, at=data["at"])
    elif event_type == "periodic":
        if not data.get("schedule"):
            raise ValueError(f"Missing 'schedule' field for periodic event in {filename}")
        if not data.get("timezone"):
            raise ValueError(f"Missing 'timezone' field for periodic event in {filename}")
        return PeriodicEvent(
            channel_id=channel_id,
            text=text,
            schedule=data["schedule"],
            timezone=data["timezone"],
        )
    else:
        raise ValueError(f"Unknown event type '{event_type}' in {filename}")


def create_events_watcher(workspace_dir: str, slack: SlackBot) -> EventsWatcher:
    """Create an EventsWatcher for the workspace."""
    events_dir = os.path.join(workspace_dir, "events")
    return EventsWatcher(events_dir, slack)
