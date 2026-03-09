"""Tests for pi_mom.main (argument parsing and state management)."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestParseArgs:
    def test_working_dir(self, tmp_path: Any) -> None:
        from pi_mom.main import _parse_args

        with patch.object(sys, "argv", ["mom", str(tmp_path)]):
            working_dir, _sandbox, download = _parse_args()
        import os

        assert working_dir == os.path.realpath(str(tmp_path))
        assert download is None

    def test_sandbox_host(self, tmp_path: Any) -> None:
        from pi_mom.main import _parse_args
        from pi_mom.sandbox import HostSandboxConfig

        with patch.object(sys, "argv", ["mom", "--sandbox=host", str(tmp_path)]):
            _, sandbox, _ = _parse_args()
        assert isinstance(sandbox, HostSandboxConfig)

    def test_sandbox_docker(self, tmp_path: Any) -> None:
        from pi_mom.main import _parse_args
        from pi_mom.sandbox import DockerSandboxConfig

        with patch.object(sys, "argv", ["mom", "--sandbox=docker:my-box", str(tmp_path)]):
            _, sandbox, _ = _parse_args()
        assert isinstance(sandbox, DockerSandboxConfig)

    def test_download_mode_equals(self) -> None:
        from pi_mom.main import _parse_args

        with patch.object(sys, "argv", ["mom", "--download=C123"]):
            _, _, download = _parse_args()
        assert download == "C123"

    def test_download_mode_space(self) -> None:
        from pi_mom.main import _parse_args

        with patch.object(sys, "argv", ["mom", "--download", "C456"]):
            _, _, download = _parse_args()
        assert download == "C456"

    def test_sandbox_as_separate_arg(self, tmp_path: Any) -> None:
        from pi_mom.main import _parse_args
        from pi_mom.sandbox import HostSandboxConfig

        with patch.object(sys, "argv", ["mom", "--sandbox", "host", str(tmp_path)]):
            _, sandbox, _ = _parse_args()
        assert isinstance(sandbox, HostSandboxConfig)

    def test_default_sandbox_is_host(self) -> None:
        from pi_mom.main import _parse_args
        from pi_mom.sandbox import HostSandboxConfig

        with patch.object(sys, "argv", ["mom"]):
            _, sandbox, _ = _parse_args()
        assert isinstance(sandbox, HostSandboxConfig)


class TestChannelState:
    def test_creation(self) -> None:
        from unittest.mock import MagicMock

        from pi_mom.main import _ChannelState

        runner = MagicMock()
        store = MagicMock()
        state = _ChannelState(runner=runner, store=store)
        assert state.running is False
        assert state.stop_requested is False
        assert state.stop_message_ts is None

    def test_state_fields(self) -> None:
        from pi_mom.main import _ChannelState

        runner = MagicMock()
        store = MagicMock()
        state = _ChannelState(runner=runner, store=store)
        state.running = True
        state.stop_requested = True
        state.stop_message_ts = "1234567890.0"
        assert state.running
        assert state.stop_requested
        assert state.stop_message_ts == "1234567890.0"


class TestGetState:
    def test_creates_new_state(self, tmp_path: Any) -> None:
        from pi_mom.main import _channel_states, _get_state
        from pi_mom.sandbox import HostSandboxConfig

        # Clear global state
        _channel_states.clear()

        channel_id = "C_TEST_NEW_UNIQUE_123"
        with (
            patch("pi_mom.main.get_or_create_runner") as mock_runner_fn,
            patch("pi_mom.main.ChannelStore") as mock_store_cls,
        ):
            mock_runner_fn.return_value = MagicMock()
            mock_store_cls.return_value = MagicMock()
            state = _get_state(
                channel_id=channel_id,
                working_dir=str(tmp_path),
                sandbox=HostSandboxConfig(),
                bot_token="xoxb-test",
            )

        assert channel_id in _channel_states
        assert state is _channel_states[channel_id]

    def test_returns_existing_state(self, tmp_path: Any) -> None:
        from pi_mom.main import _channel_states, _ChannelState, _get_state
        from pi_mom.sandbox import HostSandboxConfig

        channel_id = "C_TEST_EXISTING_456"
        existing = _ChannelState(runner=MagicMock(), store=MagicMock())
        _channel_states[channel_id] = existing

        state = _get_state(
            channel_id=channel_id,
            working_dir=str(tmp_path),
            sandbox=HostSandboxConfig(),
            bot_token="xoxb-test",
        )
        assert state is existing


class TestCreateSlackContext:
    """Tests for _create_slack_context."""

    def _make_event(self) -> Any:
        from pi_mom.slack import SlackEvent

        return SlackEvent(
            type="mention",
            channel="C123",
            ts="1234567890.0",
            user="U456",
            text="Hello bot",
        )

    def _make_slack_mock(self) -> Any:
        from unittest.mock import MagicMock

        from pi_mom.slack import SlackChannel, SlackUser

        slack = MagicMock()
        slack.get_user.return_value = SlackUser(id="U456", user_name="mario", display_name="Mario")
        slack.get_channel.return_value = SlackChannel(id="C123", name="general")
        slack.get_all_channels.return_value = []
        slack.get_all_users.return_value = []
        return slack

    def test_creates_context_object(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        assert ctx is not None

    def test_context_message(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        assert ctx.message is not None  # type: ignore[attr-defined]
        assert ctx.message.user == "U456"  # type: ignore[attr-defined]
        assert ctx.message.user_name == "mario"  # type: ignore[attr-defined]
        assert ctx.channel_name == "general"  # type: ignore[attr-defined]

    def test_context_event_filename(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context
        from pi_mom.slack import SlackEvent

        event = SlackEvent(
            type="mention",
            channel="C123",
            ts="1234567890.0",
            user="U456",
            text="[EVENT:foo.json:immediate:immediate] Do something",
        )
        slack = self._make_slack_mock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state, is_event=True)
        assert ctx is not None

    @pytest.mark.asyncio
    async def test_context_set_typing_creates_message(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.post_message = AsyncMock(return_value="1234567890.1")
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        await ctx.set_typing(True)  # type: ignore[attr-defined]

        slack.post_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_set_typing_already_has_message(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.post_message = AsyncMock(return_value="1234567890.1")
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        await ctx.set_typing(True)  # type: ignore[attr-defined]
        await ctx.set_typing(True)  # type: ignore[attr-defined]  # Already has a ts

        # Should only post once
        slack.post_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_respond(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.post_message = AsyncMock(return_value="1234567890.1")
        slack.update_message = AsyncMock()
        slack.log_bot_response = AsyncMock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        await ctx.respond("Hello!")  # type: ignore[attr-defined]

        slack.post_message.assert_called_once()
        assert "Hello!" in slack.post_message.call_args[0][1]

    @pytest.mark.asyncio
    async def test_context_respond_accumulates(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.post_message = AsyncMock(return_value="1234567890.1")
        slack.update_message = AsyncMock()
        slack.log_bot_response = AsyncMock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        await ctx.respond("Part 1")  # type: ignore[attr-defined]
        await ctx.respond("Part 2")  # type: ignore[attr-defined]

        # Second call should update, not post
        slack.update_message.assert_called()
        # Accumulated text should contain both parts
        update_text = slack.update_message.call_args[0][2]
        assert "Part 1" in update_text
        assert "Part 2" in update_text

    @pytest.mark.asyncio
    async def test_context_set_working(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.post_message = AsyncMock(return_value="1234567890.1")
        slack.update_message = AsyncMock()
        slack.log_bot_response = AsyncMock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        # Post a message first
        await ctx.respond("Working...")  # type: ignore[attr-defined]
        await ctx.set_working(False)  # type: ignore[attr-defined]

        # Update should be called without " ..."
        update_text = slack.update_message.call_args[0][2]
        assert " ..." not in update_text

    @pytest.mark.asyncio
    async def test_context_upload_file(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.upload_file = AsyncMock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        await ctx.upload_file("/tmp/test.png", "Test file")  # type: ignore[attr-defined]

        slack.upload_file.assert_called_once_with("C123", "/tmp/test.png", "Test file")

    @pytest.mark.asyncio
    async def test_context_delete_message(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.post_message = AsyncMock(return_value="1234567890.1")
        slack.delete_message = AsyncMock()
        slack.log_bot_response = AsyncMock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        await ctx.respond("Hello")  # type: ignore[attr-defined]
        await ctx.delete_message()  # type: ignore[attr-defined]

        slack.delete_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_replace_message(self) -> None:
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.post_message = AsyncMock(return_value="1234567890.1")
        slack.update_message = AsyncMock()
        slack.log_bot_response = AsyncMock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        await ctx.respond("Old text")  # type: ignore[attr-defined]
        await ctx.replace_message("New text")  # type: ignore[attr-defined]

        update_args = slack.update_message.call_args[0][2]
        assert "New text" in update_args
        assert "Old text" not in update_args

    @pytest.mark.asyncio
    async def test_context_replace_message_no_existing(self) -> None:
        """replace_message when no message yet should post a new message."""
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.post_message = AsyncMock(return_value="1234567890.1")
        slack.update_message = AsyncMock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        await ctx.replace_message("Fresh text")  # type: ignore[attr-defined]

        slack.post_message.assert_called_once()
        assert "Fresh text" in slack.post_message.call_args[0][1]

    @pytest.mark.asyncio
    async def test_context_respond_in_thread(self) -> None:
        """respond_in_thread posts a reply to the thread."""
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.post_message = AsyncMock(return_value="1234567890.1")
        slack.post_in_thread = AsyncMock(return_value="1234567890.2")
        slack.log_bot_response = AsyncMock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        # First post a message to get the ts
        await ctx.respond("Main message")  # type: ignore[attr-defined]
        await ctx.respond_in_thread("Thread reply")  # type: ignore[attr-defined]

        slack.post_in_thread.assert_called_once()
        assert "Thread reply" in slack.post_in_thread.call_args[0][2]

    @pytest.mark.asyncio
    async def test_context_delete_message_with_thread(self) -> None:
        """delete_message should also delete thread messages."""
        from pi_mom.main import _ChannelState, _create_slack_context

        event = self._make_event()
        slack = self._make_slack_mock()
        slack.post_message = AsyncMock(return_value="1234567890.1")
        slack.post_in_thread = AsyncMock(return_value="1234567890.2")
        slack.delete_message = AsyncMock()
        slack.log_bot_response = AsyncMock()
        state = _ChannelState(runner=MagicMock(), store=MagicMock())

        ctx = _create_slack_context(event, slack, state)
        await ctx.respond("Main")  # type: ignore[attr-defined]
        await ctx.respond_in_thread("Thread reply")  # type: ignore[attr-defined]
        await ctx.delete_message()  # type: ignore[attr-defined]

        # Should delete both thread message and main message
        assert slack.delete_message.call_count == 2


class TestBuildHandler:
    @pytest.mark.asyncio
    async def test_is_running_returns_false_for_unknown_channel(self, tmp_path: Any) -> None:
        from pi_mom.main import _build_handler, _channel_states
        from pi_mom.sandbox import HostSandboxConfig

        _channel_states.clear()
        handler = _build_handler(str(tmp_path), HostSandboxConfig(), "xoxb-test")
        assert not handler.is_running("C_UNKNOWN")

    @pytest.mark.asyncio
    async def test_handle_stop_when_not_running(self, tmp_path: Any) -> None:
        from unittest.mock import AsyncMock

        from pi_mom.main import _build_handler, _channel_states
        from pi_mom.sandbox import HostSandboxConfig

        _channel_states.clear()
        handler = _build_handler(str(tmp_path), HostSandboxConfig(), "xoxb-test")

        slack_mock = MagicMock()
        slack_mock.post_message = AsyncMock(return_value="1234")

        await handler.handle_stop("C_NOTRUNNING", slack_mock)
        slack_mock.post_message.assert_called_once()
        assert "Nothing running" in slack_mock.post_message.call_args[0][1]

    @pytest.mark.asyncio
    async def test_handle_stop_when_running(self, tmp_path: Any) -> None:
        from pi_mom.main import _build_handler, _channel_states, _ChannelState
        from pi_mom.sandbox import HostSandboxConfig

        _channel_states.clear()
        handler = _build_handler(str(tmp_path), HostSandboxConfig(), "xoxb-test")

        runner = MagicMock()
        runner.abort = MagicMock()
        store = MagicMock()
        state = _ChannelState(runner=runner, store=store)
        state.running = True
        _channel_states["C_RUNNING"] = state

        slack_mock = MagicMock()
        slack_mock.post_message = AsyncMock(return_value="ts-stop-123")

        await handler.handle_stop("C_RUNNING", slack_mock)

        runner.abort.assert_called_once()
        slack_mock.post_message.assert_called_once()
        assert "Stopping" in slack_mock.post_message.call_args[0][1]
        assert state.stop_requested is True
        assert state.stop_message_ts == "ts-stop-123"

    @pytest.mark.asyncio
    async def test_handle_event_runs_and_clears_state(self, tmp_path: Any) -> None:
        from pi_mom.main import _build_handler, _channel_states, _ChannelState
        from pi_mom.sandbox import HostSandboxConfig
        from pi_mom.slack import SlackEvent

        _channel_states.clear()
        handler = _build_handler(str(tmp_path), HostSandboxConfig(), "xoxb-test")

        runner = MagicMock()
        runner.run = AsyncMock(return_value={"stopReason": "done"})
        runner.abort = MagicMock()
        store = MagicMock()
        state = _ChannelState(runner=runner, store=store)
        _channel_states["C_EVENT"] = state

        slack_mock = MagicMock()
        slack_mock.post_message = AsyncMock(return_value="ts-event")
        slack_mock.update_message = AsyncMock()
        slack_mock.log_bot_response = AsyncMock()
        slack_mock.get_user = MagicMock(return_value=None)
        slack_mock.get_channel = MagicMock(return_value=None)
        slack_mock.get_all_channels = MagicMock(return_value=[])
        slack_mock.get_all_users = MagicMock(return_value=[])

        event = SlackEvent(
            type="mention",
            channel="C_EVENT",
            ts="1234567890.0",
            user="U001",
            text="Do something",
        )

        with (
            patch("pi_mom.main.get_or_create_runner", return_value=runner),
            patch("pi_mom.main.ChannelStore", return_value=store),
        ):
            await handler.handle_event(event, slack_mock)

        assert state.running is False
        runner.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_event_aborted_with_stop_request(self, tmp_path: Any) -> None:
        from pi_mom.main import _build_handler, _channel_states, _ChannelState
        from pi_mom.sandbox import HostSandboxConfig
        from pi_mom.slack import SlackEvent

        _channel_states.clear()
        handler = _build_handler(str(tmp_path), HostSandboxConfig(), "xoxb-test")

        runner = MagicMock()
        store = MagicMock()
        state = _ChannelState(runner=runner, store=store)
        _channel_states["C_ABORT"] = state

        # Simulate runner.run setting stop_requested=True during execution
        async def run_and_set_stop(ctx: Any, s: Any) -> dict[str, Any]:
            state.stop_requested = True
            state.stop_message_ts = "ts-stop-msg"
            return {"stopReason": "aborted"}

        runner.run = run_and_set_stop

        slack_mock = MagicMock()
        slack_mock.post_message = AsyncMock(return_value="ts-event")
        slack_mock.update_message = AsyncMock()
        slack_mock.log_bot_response = AsyncMock()
        slack_mock.get_user = MagicMock(return_value=None)
        slack_mock.get_channel = MagicMock(return_value=None)
        slack_mock.get_all_channels = MagicMock(return_value=[])
        slack_mock.get_all_users = MagicMock(return_value=[])

        event = SlackEvent(
            type="mention",
            channel="C_ABORT",
            ts="1234567890.0",
            user="U001",
            text="Stop this",
        )

        with (
            patch("pi_mom.main.get_or_create_runner", return_value=runner),
            patch("pi_mom.main.ChannelStore", return_value=store),
        ):
            await handler.handle_event(event, slack_mock)

        # Should have called update_message with "_Stopped_"
        update_calls = [args[0] for args in slack_mock.update_message.call_args_list]
        stopped_calls = [a for a in update_calls if "_Stopped_" in a[2]]
        assert len(stopped_calls) > 0
        assert state.running is False

    @pytest.mark.asyncio
    async def test_handle_event_aborted_no_stop_message_ts(self, tmp_path: Any) -> None:
        from pi_mom.main import _build_handler, _channel_states, _ChannelState
        from pi_mom.sandbox import HostSandboxConfig
        from pi_mom.slack import SlackEvent

        _channel_states.clear()
        handler = _build_handler(str(tmp_path), HostSandboxConfig(), "xoxb-test")

        runner = MagicMock()
        store = MagicMock()
        state = _ChannelState(runner=runner, store=store)
        _channel_states["C_ABORT2"] = state

        # Simulate runner.run setting stop_requested=True but no stop_message_ts
        async def run_and_set_stop(ctx: Any, s: Any) -> dict[str, Any]:
            state.stop_requested = True
            state.stop_message_ts = None
            return {"stopReason": "aborted"}

        runner.run = run_and_set_stop

        slack_mock = MagicMock()
        slack_mock.post_message = AsyncMock(return_value="ts-event")
        slack_mock.update_message = AsyncMock()
        slack_mock.log_bot_response = AsyncMock()
        slack_mock.get_user = MagicMock(return_value=None)
        slack_mock.get_channel = MagicMock(return_value=None)
        slack_mock.get_all_channels = MagicMock(return_value=[])
        slack_mock.get_all_users = MagicMock(return_value=[])

        event = SlackEvent(
            type="mention",
            channel="C_ABORT2",
            ts="1234567890.0",
            user="U001",
            text="Stop",
        )

        with (
            patch("pi_mom.main.get_or_create_runner", return_value=runner),
            patch("pi_mom.main.ChannelStore", return_value=store),
        ):
            await handler.handle_event(event, slack_mock)

        # Should post a new "Stopped" message (since no stop_message_ts)
        posted_texts = [args[0][1] for args in slack_mock.post_message.call_args_list]
        assert any("Stopped" in t for t in posted_texts)

    @pytest.mark.asyncio
    async def test_handle_event_exception_clears_running(self, tmp_path: Any) -> None:
        from pi_mom.main import _build_handler, _channel_states, _ChannelState
        from pi_mom.sandbox import HostSandboxConfig
        from pi_mom.slack import SlackEvent

        _channel_states.clear()
        handler = _build_handler(str(tmp_path), HostSandboxConfig(), "xoxb-test")

        runner = MagicMock()
        runner.run = AsyncMock(side_effect=RuntimeError("agent crashed"))
        store = MagicMock()
        state = _ChannelState(runner=runner, store=store)
        _channel_states["C_ERR"] = state

        slack_mock = MagicMock()
        slack_mock.post_message = AsyncMock(return_value="ts-event")
        slack_mock.get_user = MagicMock(return_value=None)
        slack_mock.get_channel = MagicMock(return_value=None)
        slack_mock.get_all_channels = MagicMock(return_value=[])
        slack_mock.get_all_users = MagicMock(return_value=[])

        event = SlackEvent(
            type="mention",
            channel="C_ERR",
            ts="1234567890.0",
            user="U001",
            text="Crash me",
        )

        with (
            patch("pi_mom.main.get_or_create_runner", return_value=runner),
            patch("pi_mom.main.ChannelStore", return_value=store),
        ):
            await handler.handle_event(event, slack_mock)

        # Should clear running even when exception occurs
        assert state.running is False

    @pytest.mark.asyncio
    async def test_is_running_returns_true_for_running_channel(self, tmp_path: Any) -> None:
        from pi_mom.main import _build_handler, _channel_states, _ChannelState
        from pi_mom.sandbox import HostSandboxConfig

        _channel_states.clear()
        handler = _build_handler(str(tmp_path), HostSandboxConfig(), "xoxb-test")

        state = _ChannelState(runner=MagicMock(), store=MagicMock())
        state.running = True
        _channel_states["C_ISRUNNING"] = state

        assert handler.is_running("C_ISRUNNING") is True
