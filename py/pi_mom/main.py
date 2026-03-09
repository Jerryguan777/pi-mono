"""CLI entry point for pi_mom — port of packages/mom/src/main.ts."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal as os_signal
import sys
from typing import TYPE_CHECKING

import pi_mom.log as log
from pi_mom.agent import get_or_create_runner
from pi_mom.events import create_events_watcher
from pi_mom.sandbox import DockerSandboxConfig, SandboxConfig, parse_sandbox_arg, validate_sandbox
from pi_mom.slack import ChannelInfo, MomHandler, SlackBot, SlackEvent, UserInfo
from pi_mom.store import ChannelStore

if TYPE_CHECKING:
    from pi_mom.agent import AgentRunner


# ============================================================================
# Per-channel state
# ============================================================================


class _ChannelState:
    def __init__(self, runner: AgentRunner, store: ChannelStore) -> None:
        self.running = False
        self.runner = runner
        self.store = store
        self.stop_requested = False
        self.stop_message_ts: str | None = None


_channel_states: dict[str, _ChannelState] = {}


def _get_state(channel_id: str, working_dir: str, sandbox: SandboxConfig, bot_token: str) -> _ChannelState:
    if channel_id not in _channel_states:
        channel_dir = os.path.join(working_dir, channel_id)
        state = _ChannelState(
            runner=get_or_create_runner(sandbox, channel_id, channel_dir),
            store=ChannelStore(working_dir=working_dir, bot_token=bot_token),
        )
        _channel_states[channel_id] = state
    return _channel_states[channel_id]


# ============================================================================
# SlackContext adapter
# ============================================================================


def _create_slack_context(
    event: SlackEvent,
    slack: SlackBot,
    state: _ChannelState,
    is_event: bool = False,
) -> object:
    """Create a SlackContext object for a given event."""

    message_ts_holder: list[str | None] = [None]
    thread_message_ts: list[str] = []
    accumulated_text: list[str] = [""]
    is_working: list[bool] = [True]
    working_indicator = " ..."
    update_lock = asyncio.Lock()

    user = slack.get_user(event.user)

    # Extract event filename for status message
    event_filename: str | None = None
    if is_event:
        import re

        m = re.match(r"^\[EVENT:([^:]+):", event.text)
        if m:
            event_filename = m.group(1)

    from pi_mom.slack import SlackMessage

    message = SlackMessage(
        text=event.text,
        raw_text=event.text,
        user=event.user,
        user_name=user.user_name if user else None,
        channel=event.channel,
        ts=event.ts,
        attachments=[{"local": a.local} for a in (event.attachments or [])],
    )

    _ch = slack.get_channel(event.channel)

    class _SlackContext:
        message = None  # will be set below
        channel_name: str | None = _ch.name if _ch else None
        channels: list[ChannelInfo] = [  # noqa: RUF012
            ChannelInfo(id=c.id, name=c.name) for c in slack.get_all_channels()
        ]
        users: list[UserInfo] = [  # noqa: RUF012
            UserInfo(id=u.id, user_name=u.user_name, display_name=u.display_name) for u in slack.get_all_users()
        ]

        async def respond(self, text: str, should_log: bool = True) -> None:
            async with update_lock:
                if accumulated_text[0]:
                    accumulated_text[0] = accumulated_text[0] + "\n" + text
                else:
                    accumulated_text[0] = text
                display = accumulated_text[0] + working_indicator if is_working[0] else accumulated_text[0]

                if message_ts_holder[0]:
                    await slack.update_message(event.channel, message_ts_holder[0], display)
                else:
                    ts = await slack.post_message(event.channel, display)
                    message_ts_holder[0] = ts

                if should_log and message_ts_holder[0]:
                    await slack.log_bot_response(event.channel, text, message_ts_holder[0])

        async def replace_message(self, text: str) -> None:
            async with update_lock:
                accumulated_text[0] = text
                display = accumulated_text[0] + working_indicator if is_working[0] else accumulated_text[0]
                if message_ts_holder[0]:
                    await slack.update_message(event.channel, message_ts_holder[0], display)
                else:
                    ts = await slack.post_message(event.channel, display)
                    message_ts_holder[0] = ts

        async def respond_in_thread(self, text: str) -> None:
            async with update_lock:
                if message_ts_holder[0]:
                    ts = await slack.post_in_thread(event.channel, message_ts_holder[0], text)
                    thread_message_ts.append(ts)

        async def set_typing(self, is_typing: bool) -> None:
            if is_typing and not message_ts_holder[0]:
                async with update_lock:
                    if not message_ts_holder[0]:
                        initial_text = f"_Starting event: {event_filename}_" if event_filename else "_Thinking_"
                        accumulated_text[0] = initial_text
                        ts = await slack.post_message(event.channel, accumulated_text[0] + working_indicator)
                        message_ts_holder[0] = ts

        async def upload_file(self, file_path: str, title: str | None = None) -> None:
            await slack.upload_file(event.channel, file_path, title)

        async def set_working(self, working: bool) -> None:
            async with update_lock:
                is_working[0] = working
                if message_ts_holder[0]:
                    display = accumulated_text[0] + working_indicator if is_working[0] else accumulated_text[0]
                    await slack.update_message(event.channel, message_ts_holder[0], display)

        async def delete_message(self) -> None:
            async with update_lock:
                for ts in reversed(thread_message_ts):
                    with contextlib.suppress(Exception):
                        await slack.delete_message(event.channel, ts)
                thread_message_ts.clear()
                if message_ts_holder[0]:
                    await slack.delete_message(event.channel, message_ts_holder[0])
                    message_ts_holder[0] = None

    ctx = _SlackContext()
    ctx.message = message  # type: ignore[assignment]
    return ctx


# ============================================================================
# Handler
# ============================================================================


def _build_handler(working_dir: str, sandbox: SandboxConfig, bot_token: str) -> MomHandler:
    class _Handler:
        def is_running(self, channel_id: str) -> bool:
            state = _channel_states.get(channel_id)
            return state.running if state else False

        async def handle_stop(self, channel_id: str, slack: SlackBot) -> None:
            state = _channel_states.get(channel_id)
            if state and state.running:
                state.stop_requested = True
                state.runner.abort()
                ts = await slack.post_message(channel_id, "_Stopping..._")
                state.stop_message_ts = ts
            else:
                await slack.post_message(channel_id, "_Nothing running_")

        async def handle_event(self, event: SlackEvent, slack: SlackBot, is_event: bool = False) -> None:
            state = _get_state(event.channel, working_dir, sandbox, bot_token)

            state.running = True
            state.stop_requested = False
            log.log_info(f"[{event.channel}] Starting run: {event.text[:50]}")

            try:
                ctx = _create_slack_context(event, slack, state, is_event)
                await ctx.set_typing(True)  # type: ignore[attr-defined]
                await ctx.set_working(True)  # type: ignore[attr-defined]
                result = await state.runner.run(ctx, state.store)  # type: ignore[arg-type]
                await ctx.set_working(False)  # type: ignore[attr-defined]

                if result.get("stopReason") == "aborted" and state.stop_requested:
                    if state.stop_message_ts:
                        await slack.update_message(event.channel, state.stop_message_ts, "_Stopped_")
                        state.stop_message_ts = None
                    else:
                        await slack.post_message(event.channel, "_Stopped_")
            except Exception as exc:
                log.log_warning(f"[{event.channel}] Run error", str(exc))
            finally:
                state.running = False

    return _Handler()


# ============================================================================
# Argument parsing
# ============================================================================


def _parse_args() -> tuple[str | None, SandboxConfig, str | None]:
    args = sys.argv[1:]
    sandbox: SandboxConfig = parse_sandbox_arg("host")
    working_dir: str | None = None
    download_channel: str | None = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--sandbox="):
            sandbox = parse_sandbox_arg(arg[len("--sandbox=") :])
        elif arg == "--sandbox":
            i += 1
            sandbox = parse_sandbox_arg(args[i] if i < len(args) else "")
        elif arg.startswith("--download="):
            download_channel = arg[len("--download=") :]
        elif arg == "--download":
            i += 1
            download_channel = args[i] if i < len(args) else None
        elif not arg.startswith("-"):
            working_dir = os.path.realpath(arg)
        i += 1

    return working_dir, sandbox, download_channel


# ============================================================================
# Main
# ============================================================================


async def main() -> None:
    working_dir, sandbox, download_channel_id = _parse_args()

    app_token = os.environ.get("MOM_SLACK_APP_TOKEN")
    bot_token = os.environ.get("MOM_SLACK_BOT_TOKEN")

    # Handle --download mode
    if download_channel_id:
        if not bot_token:
            print("Missing env: MOM_SLACK_BOT_TOKEN", file=sys.stderr)
            sys.exit(1)
        from pi_mom.download import download_channel

        await download_channel(download_channel_id, bot_token)
        return

    # Normal bot mode — require working dir
    if not working_dir:
        print("Usage: mom [--sandbox=host|docker:<name>] <working-directory>", file=sys.stderr)
        print("       mom --download <channel-id>", file=sys.stderr)
        sys.exit(1)

    if not app_token or not bot_token:
        print("Missing env: MOM_SLACK_APP_TOKEN, MOM_SLACK_BOT_TOKEN", file=sys.stderr)
        sys.exit(1)

    await validate_sandbox(sandbox)

    sandbox_label = "host" if not isinstance(sandbox, DockerSandboxConfig) else f"docker:{sandbox.container}"
    log.log_startup(working_dir, sandbox_label)

    shared_store = ChannelStore(working_dir=working_dir, bot_token=bot_token)
    handler = _build_handler(working_dir, sandbox, bot_token)

    bot = SlackBot(
        handler=handler,
        app_token=app_token,
        bot_token=bot_token,
        working_dir=working_dir,
        store=shared_store,
    )

    events_watcher = create_events_watcher(working_dir, bot)
    events_watcher.start()

    loop = asyncio.get_event_loop()

    def _shutdown() -> None:
        log.log_info("Shutting down...")
        events_watcher.stop()
        loop.stop()

    loop.add_signal_handler(os_signal.SIGINT, _shutdown)
    loop.add_signal_handler(os_signal.SIGTERM, _shutdown)

    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
