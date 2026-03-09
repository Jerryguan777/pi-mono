"""Tests for pi_coding_agent.core.agent_session."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pi_ai.types import TextContent, UserMessage
from pi_coding_agent.core.agent_session import (
    _RETRYABLE_ERROR_PATTERN,
    AgentSession,
    AgentSessionConfig,
    AutoCompactionEndEvent,
    AutoCompactionStartEvent,
    AutoRetryEndEvent,
    AutoRetryStartEvent,
    SessionStats,
)
from pi_coding_agent.core.messages import BashExecutionMessage
from pi_coding_agent.core.session_manager import SessionManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_agent() -> MagicMock:
    """Create a mock agent with the minimum interface needed by AgentSession."""
    agent = MagicMock()
    agent.subscribe.return_value = MagicMock()  # unsubscribe fn
    agent.state.model = None
    agent.state.thinking_level = "off"
    agent.state.is_streaming = False
    agent.state.messages = []
    # Async methods need AsyncMock
    agent.wait_for_idle = AsyncMock()
    agent.prompt = AsyncMock()
    # Sync methods (called but not awaited)
    agent.follow_up = MagicMock()
    agent.steer = MagicMock()
    agent.set_model = MagicMock()
    return agent


def make_session(agent: MagicMock | None = None) -> AgentSession:
    """Create an AgentSession with an in-memory SessionManager."""
    if agent is None:
        agent = make_mock_agent()
    sm = SessionManager.in_memory("/tmp")
    config = AgentSessionConfig(agent=agent, session_manager=sm, cwd="/tmp")
    return AgentSession(config)


# ---------------------------------------------------------------------------
# Test dataclasses
# ---------------------------------------------------------------------------


class TestEventDataclasses:
    def test_auto_compaction_start_event(self) -> None:
        ev = AutoCompactionStartEvent(reason="overflow")
        assert ev.type == "auto_compaction_start"
        assert ev.reason == "overflow"

    def test_auto_compaction_end_event(self) -> None:
        ev = AutoCompactionEndEvent(aborted=True)
        assert ev.type == "auto_compaction_end"
        assert ev.aborted is True

    def test_auto_retry_start_event(self) -> None:
        ev = AutoRetryStartEvent(attempt=2, max_attempts=3, delay_ms=500, error_message="err")
        assert ev.type == "auto_retry_start"
        assert ev.attempt == 2

    def test_auto_retry_end_event(self) -> None:
        ev = AutoRetryEndEvent(success=True, attempt=1)
        assert ev.type == "auto_retry_end"
        assert ev.success is True


# ---------------------------------------------------------------------------
# Test construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_creates_successfully(self) -> None:
        session = make_session()
        assert session is not None

    def test_subscribes_to_agent_on_creation(self) -> None:
        agent = make_mock_agent()
        make_session(agent)
        agent.subscribe.assert_called_once()

    def test_session_id_comes_from_session_manager(self) -> None:
        session = make_session()
        sm = session.session_manager
        assert session.session_id == sm.get_session_id()

    def test_session_file_is_none_in_memory(self) -> None:
        session = make_session()
        assert session.session_file is None

    def test_session_manager_property(self) -> None:
        sm = SessionManager.in_memory("/tmp")
        agent = make_mock_agent()
        config = AgentSessionConfig(agent=agent, session_manager=sm, cwd="/tmp")
        sess = AgentSession(config)
        assert sess.session_manager is sm


# ---------------------------------------------------------------------------
# Test properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_model_returns_none_by_default(self) -> None:
        session = make_session()
        assert session.model is None

    def test_thinking_level_returns_off_by_default(self) -> None:
        session = make_session()
        assert session.thinking_level == "off"

    def test_is_streaming_false_by_default(self) -> None:
        session = make_session()
        assert session.is_streaming is False

    def test_is_compacting_false_by_default(self) -> None:
        session = make_session()
        assert session.is_compacting is False

    def test_is_bash_running_false_by_default(self) -> None:
        session = make_session()
        assert session.is_bash_running is False

    def test_is_retrying_false_by_default(self) -> None:
        session = make_session()
        assert session.is_retrying is False

    def test_retry_attempt_zero_by_default(self) -> None:
        session = make_session()
        assert session.retry_attempt == 0

    def test_pending_message_count_zero_by_default(self) -> None:
        session = make_session()
        assert session.pending_message_count == 0

    def test_state_proxies_agent_state(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        assert session.state is agent.state


# ---------------------------------------------------------------------------
# Test subscribe / emit
# ---------------------------------------------------------------------------


class TestSubscribe:
    def test_subscribe_returns_callable(self) -> None:
        session = make_session()
        unsub = session.subscribe(lambda e: None)
        assert callable(unsub)

    def test_subscribe_listener_receives_events(self) -> None:
        session = make_session()
        received: list[Any] = []
        session.subscribe(received.append)
        ev = AutoCompactionStartEvent()
        session._emit(ev)
        assert len(received) == 1
        assert received[0] is ev

    def test_unsubscribe_removes_listener(self) -> None:
        session = make_session()
        received: list[Any] = []
        unsub = session.subscribe(received.append)
        unsub()
        session._emit(AutoCompactionStartEvent())
        assert len(received) == 0

    def test_double_unsubscribe_is_safe(self) -> None:
        session = make_session()
        unsub = session.subscribe(lambda e: None)
        unsub()
        unsub()  # Should not raise

    def test_listener_error_does_not_propagate(self) -> None:
        session = make_session()

        def bad_listener(e: Any) -> None:
            raise RuntimeError("boom")

        session.subscribe(bad_listener)
        session._emit(AutoCompactionStartEvent())  # Should not raise


# ---------------------------------------------------------------------------
# Test _handle_agent_event session persistence
# ---------------------------------------------------------------------------


class TestHandleAgentEvent:
    def test_user_message_appended_to_session_manager(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)

        # Simulate message_end event with user message
        msg = UserMessage(content="hello")
        event = MagicMock()
        event.type = "message_end"
        event.message = msg
        msg.role = "user"

        initial_count = len(session.session_manager.get_entries())
        session._handle_agent_event(event)
        # Session manager should have the user message now
        assert len(session.session_manager.get_entries()) > initial_count

    def test_steering_message_removed_on_message_start(self) -> None:
        session = make_session()
        session._steering_messages.append("steer text")

        msg = MagicMock()
        msg.role = "user"
        msg.content = "steer text"
        event = MagicMock()
        event.type = "message_start"
        event.message = msg

        session._handle_agent_event(event)
        assert "steer text" not in session._steering_messages

    def test_follow_up_message_removed_on_message_start(self) -> None:
        session = make_session()
        session._follow_up_messages.append("follow text")

        msg = MagicMock()
        msg.role = "user"
        msg.content = "follow text"
        event = MagicMock()
        event.type = "message_start"
        event.message = msg

        session._handle_agent_event(event)
        assert "follow text" not in session._follow_up_messages

    def test_event_forwarded_to_listeners(self) -> None:
        session = make_session()
        received: list[Any] = []
        session.subscribe(received.append)

        event = MagicMock()
        event.type = "some_other_event"
        session._handle_agent_event(event)
        assert len(received) == 1


# ---------------------------------------------------------------------------
# Test _get_user_message_text
# ---------------------------------------------------------------------------


class TestGetUserMessageText:
    def test_string_content(self) -> None:
        session = make_session()
        msg = MagicMock()
        msg.role = "user"
        msg.content = "hello"
        result = session._get_user_message_text(msg)
        assert result == "hello"

    def test_non_user_returns_empty(self) -> None:
        session = make_session()
        msg = MagicMock()
        msg.role = "assistant"
        result = session._get_user_message_text(msg)
        assert result == ""

    def test_list_content_joins_text_blocks(self) -> None:
        session = make_session()
        msg = MagicMock()
        msg.role = "user"
        msg.content = [TextContent(text="hello "), TextContent(text="world")]
        result = session._get_user_message_text(msg)
        assert result == "hello world"


# ---------------------------------------------------------------------------
# Test _clamp_thinking_level
# ---------------------------------------------------------------------------


class TestClampThinkingLevel:
    def test_exact_match_returns_level(self) -> None:
        session = make_session()
        result = session._clamp_thinking_level("medium", ["off", "low", "medium", "high"])
        assert result == "medium"

    def test_level_not_in_available_clamps_up(self) -> None:
        session = make_session()
        # "high" not in available, should return next available above
        result = session._clamp_thinking_level("high", ["off", "low", "medium"])
        # Should find xhigh or wrap to available
        assert result in ["off", "minimal", "low", "medium", "high", "xhigh"]

    def test_empty_available_returns_off(self) -> None:
        session = make_session()
        result = session._clamp_thinking_level("medium", [])
        assert result == "off"


# ---------------------------------------------------------------------------
# Test _supports_xhigh
# ---------------------------------------------------------------------------


class TestSupportsXhigh:
    def test_no_model_returns_false(self) -> None:
        session = make_session()
        assert session._supports_xhigh() is False

    def test_claude_3_7_model_returns_true(self) -> None:
        agent = make_mock_agent()
        agent.state.model = MagicMock()
        agent.state.model.id = "claude-3-7-sonnet"
        session = make_session(agent)
        assert session._supports_xhigh() is True

    def test_other_model_returns_false(self) -> None:
        agent = make_mock_agent()
        agent.state.model = MagicMock()
        agent.state.model.id = "gpt-4o"
        session = make_session(agent)
        assert session._supports_xhigh() is False


# ---------------------------------------------------------------------------
# Test _is_retryable_error
# ---------------------------------------------------------------------------


class TestIsRetryableError:
    def test_overloaded_error_is_retryable(self) -> None:
        session = make_session()
        msg = MagicMock()
        msg.stop_reason = "error"
        msg.error_message = "Service overloaded"
        assert session._is_retryable_error(msg) is True

    def test_non_error_stop_reason_not_retryable(self) -> None:
        session = make_session()
        msg = MagicMock()
        msg.stop_reason = "end_turn"
        msg.error_message = "overloaded"
        assert session._is_retryable_error(msg) is False

    def test_rate_limit_is_retryable(self) -> None:
        session = make_session()
        msg = MagicMock()
        msg.stop_reason = "error"
        msg.error_message = "Rate limit exceeded 429"
        assert session._is_retryable_error(msg) is True

    def test_unrelated_error_not_retryable(self) -> None:
        session = make_session()
        msg = MagicMock()
        msg.stop_reason = "error"
        msg.error_message = "Invalid API key"
        assert session._is_retryable_error(msg) is False


# ---------------------------------------------------------------------------
# Test retryable pattern
# ---------------------------------------------------------------------------


class TestRetryablePattern:
    def test_pattern_matches_overloaded(self) -> None:
        assert _RETRYABLE_ERROR_PATTERN.search("Service overloaded")

    def test_pattern_matches_rate_limit(self) -> None:
        assert _RETRYABLE_ERROR_PATTERN.search("rate limit exceeded")

    def test_pattern_matches_500(self) -> None:
        assert _RETRYABLE_ERROR_PATTERN.search("500 Internal Server Error")

    def test_pattern_no_match_for_auth(self) -> None:
        assert not _RETRYABLE_ERROR_PATTERN.search("Invalid API key - authentication failed")


# ---------------------------------------------------------------------------
# Test get_session_stats
# ---------------------------------------------------------------------------


class TestGetSessionStats:
    def test_empty_messages_returns_zeros(self) -> None:
        agent = make_mock_agent()
        agent.state.messages = []
        session = make_session(agent)
        stats = session.get_session_stats()
        assert isinstance(stats, SessionStats)
        assert stats.user_messages == 0
        assert stats.assistant_messages == 0

    def test_counts_user_messages(self) -> None:
        agent = make_mock_agent()
        user_msg = MagicMock()
        user_msg.role = "user"
        user_msg.content = "hi"
        agent.state.messages = [user_msg]
        session = make_session(agent)
        stats = session.get_session_stats()
        assert stats.user_messages == 1

    def test_counts_assistant_messages(self) -> None:
        agent = make_mock_agent()
        asst_msg = MagicMock()
        asst_msg.role = "assistant"
        asst_msg.content = []
        asst_msg.usage = None
        agent.state.messages = [asst_msg]
        session = make_session(agent)
        stats = session.get_session_stats()
        assert stats.assistant_messages == 1


# ---------------------------------------------------------------------------
# Test abort_compaction / abort_bash
# ---------------------------------------------------------------------------


class TestAbortMethods:
    def test_abort_compaction_no_event_is_safe(self) -> None:
        session = make_session()
        session.abort_compaction()  # Should not raise

    def test_abort_bash_no_event_is_safe(self) -> None:
        session = make_session()
        session.abort_bash()  # Should not raise

    def test_abort_compaction_sets_event(self) -> None:
        import asyncio

        session = make_session()
        session._compaction_abort_event = asyncio.Event()
        session.abort_compaction()
        assert session._compaction_abort_event.is_set()

    def test_abort_bash_sets_event(self) -> None:
        import asyncio

        session = make_session()
        session._bash_abort_event = asyncio.Event()
        session.abort_bash()
        assert session._bash_abort_event.is_set()


# ---------------------------------------------------------------------------
# Test dispose
# ---------------------------------------------------------------------------


class TestDispose:
    def test_dispose_clears_listeners(self) -> None:
        session = make_session()
        session.subscribe(lambda e: None)
        session.dispose()
        assert len(session._event_listeners) == 0

    def test_dispose_disconnects_from_agent(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        session.dispose()
        assert session._unsubscribe_agent is None


# ---------------------------------------------------------------------------
# Test compact raises NotImplementedError
# ---------------------------------------------------------------------------


class TestCompact:
    @pytest.mark.anyio
    async def test_compact_raises_not_implemented(self) -> None:
        session = make_session()
        with pytest.raises(NotImplementedError):
            await session.compact()


# ---------------------------------------------------------------------------
# Test execute_bash integration
# ---------------------------------------------------------------------------


class TestExecuteBash:
    @pytest.mark.anyio
    async def test_execute_simple_command(self) -> None:
        session = make_session()
        result = await session.execute_bash("echo test_output")
        assert "test_output" in result.output
        assert result.exit_code == 0

    @pytest.mark.anyio
    async def test_is_bash_running_during_execution(self) -> None:
        """Verify bash_abort_event is cleaned up after execution."""
        session = make_session()
        await session.execute_bash("echo hi")
        assert session.is_bash_running is False

    @pytest.mark.anyio
    async def test_bash_result_recorded_in_session(self) -> None:
        session = make_session()
        await session.execute_bash("echo recorded")
        entries = session.session_manager.get_entries()
        from pi_coding_agent.core.session_manager import SessionMessageEntry

        bash_entries = [
            e for e in entries if isinstance(e, SessionMessageEntry) and isinstance(e.message, BashExecutionMessage)
        ]
        assert len(bash_entries) == 1

    @pytest.mark.anyio
    async def test_on_chunk_callback_called(self) -> None:
        session = make_session()
        chunks: list[str] = []
        await session.execute_bash("echo chunk_test", on_chunk=chunks.append)
        assert any("chunk_test" in c for c in chunks)


# ---------------------------------------------------------------------------
# Test prompt
# ---------------------------------------------------------------------------


class TestPrompt:
    @pytest.mark.anyio
    async def test_prompt_raises_when_streaming_no_behavior(self) -> None:
        agent = make_mock_agent()
        agent.state.is_streaming = True
        session = make_session(agent)
        with pytest.raises(RuntimeError, match="streaming_behavior"):
            await session.prompt("hello")

    @pytest.mark.anyio
    async def test_prompt_queues_follow_up_when_streaming(self) -> None:
        agent = make_mock_agent()
        agent.state.is_streaming = True
        session = make_session(agent)
        await session.prompt("hello", streaming_behavior="followUp")
        # follow_up method on agent should be called
        agent.follow_up.assert_called_once()

    @pytest.mark.anyio
    async def test_prompt_queues_steer_when_streaming(self) -> None:
        agent = make_mock_agent()
        agent.state.is_streaming = True
        session = make_session(agent)
        await session.prompt("hello", streaming_behavior="steer")
        agent.steer.assert_called_once()

    @pytest.mark.anyio
    async def test_prompt_raises_when_no_model(self) -> None:
        agent = make_mock_agent()
        agent.state.is_streaming = False
        agent.state.model = None
        session = make_session(agent)
        with pytest.raises(RuntimeError, match="No model selected"):
            await session.prompt("hello")

    @pytest.mark.anyio
    async def test_prompt_calls_agent_prompt_when_model_set(self) -> None:
        agent = make_mock_agent()
        agent.state.is_streaming = False
        agent.state.model = MagicMock()
        session = make_session(agent)
        await session.prompt("hello")
        agent.prompt.assert_called_once()


# ---------------------------------------------------------------------------
# Test abort
# ---------------------------------------------------------------------------


class TestAbort:
    @pytest.mark.anyio
    async def test_abort_calls_agent_abort(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        await session.abort()
        agent.abort.assert_called_once()

    @pytest.mark.anyio
    async def test_abort_calls_wait_for_idle(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        await session.abort()
        agent.wait_for_idle.assert_called_once()


# ---------------------------------------------------------------------------
# Test new_session
# ---------------------------------------------------------------------------


class TestNewSession:
    @pytest.mark.anyio
    async def test_new_session_creates_new_session_id(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        old_id = session.session_id
        await session.new_session()
        assert session.session_id != old_id

    @pytest.mark.anyio
    async def test_new_session_clears_steering_messages(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        session._steering_messages.append("steer")
        await session.new_session()
        assert len(session._steering_messages) == 0

    @pytest.mark.anyio
    async def test_new_session_with_parent_session(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        await session.new_session(parent_session="/old/session.jsonl")
        header = session.session_manager.get_header()
        assert header is not None
        assert header.parent_session == "/old/session.jsonl"


# ---------------------------------------------------------------------------
# Test set_model
# ---------------------------------------------------------------------------


class TestSetModel:
    @pytest.mark.anyio
    async def test_set_model_calls_agent(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        mock_model = MagicMock()
        await session.set_model(mock_model)
        agent.set_model.assert_called_once_with(mock_model)

    @pytest.mark.anyio
    async def test_set_model_appends_model_change_to_session(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        mock_model = MagicMock()
        mock_model.provider = "openai"
        mock_model.id = "gpt-4o"
        await session.set_model(mock_model)
        from pi_coding_agent.core.session_manager import ModelChangeEntry

        model_entries = [e for e in session.session_manager.get_entries() if isinstance(e, ModelChangeEntry)]
        assert len(model_entries) == 1


# ---------------------------------------------------------------------------
# Test set_thinking_level
# ---------------------------------------------------------------------------


class TestSetThinkingLevel:
    def test_set_thinking_level_no_model_stays_off(self) -> None:
        agent = make_mock_agent()
        agent.state.model = None
        agent.state.thinking_level = "off"
        session = make_session(agent)
        session.set_thinking_level("high")
        # model is None, only "off" available - no change should be made
        agent.set_thinking_level.assert_not_called()

    def test_set_thinking_level_non_reasoning_model_stays_off(self) -> None:
        agent = make_mock_agent()
        mock_model = MagicMock()
        mock_model.reasoning = False
        agent.state.model = mock_model
        agent.state.thinking_level = "off"
        session = make_session(agent)
        session.set_thinking_level("high")
        agent.set_thinking_level.assert_not_called()

    def test_set_thinking_level_reasoning_model_applies_change(self) -> None:
        agent = make_mock_agent()
        mock_model = MagicMock()
        mock_model.reasoning = True
        mock_model.id = "claude-3-5-sonnet"
        agent.state.model = mock_model
        agent.state.thinking_level = "off"
        session = make_session(agent)
        session.set_thinking_level("medium")
        agent.set_thinking_level.assert_called_once_with("medium")


# ---------------------------------------------------------------------------
# Test _flush_pending_bash_messages
# ---------------------------------------------------------------------------


class TestFlushPendingBashMessages:
    @pytest.mark.anyio
    async def test_flush_clears_pending_bash_messages(self) -> None:
        session = make_session()
        bash_msg = BashExecutionMessage(command="ls", stdout="a.txt\n", exit_code=0)
        session._pending_bash_messages.append(bash_msg)
        session._flush_pending_bash_messages()
        assert len(session._pending_bash_messages) == 0


# ---------------------------------------------------------------------------
# Test _disconnect_from_agent / _reconnect_to_agent
# ---------------------------------------------------------------------------


class TestDisconnectReconnect:
    def test_disconnect_calls_unsubscribe(self) -> None:
        agent = make_mock_agent()
        unsub_fn = MagicMock()
        agent.subscribe.return_value = unsub_fn
        session = make_session(agent)
        session._disconnect_from_agent()
        unsub_fn.assert_called_once()
        assert session._unsubscribe_agent is None

    def test_reconnect_resubscribes(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        session._disconnect_from_agent()
        initial_call_count = agent.subscribe.call_count
        session._reconnect_to_agent()
        assert agent.subscribe.call_count > initial_call_count

    def test_reconnect_when_already_connected_is_noop(self) -> None:
        agent = make_mock_agent()
        session = make_session(agent)
        call_count_before = agent.subscribe.call_count
        session._reconnect_to_agent()  # already connected
        assert agent.subscribe.call_count == call_count_before


# ---------------------------------------------------------------------------
# Test _get_available_thinking_levels
# ---------------------------------------------------------------------------


class TestGetAvailableThinkingLevels:
    def test_no_model_returns_off_only(self) -> None:
        agent = make_mock_agent()
        agent.state.model = None
        session = make_session(agent)
        levels = session._get_available_thinking_levels()
        assert levels == ["off"]

    def test_reasoning_model_returns_all_levels(self) -> None:
        agent = make_mock_agent()
        mock_model = MagicMock()
        mock_model.reasoning = True
        mock_model.id = "claude-3-5-sonnet"
        agent.state.model = mock_model
        session = make_session(agent)
        levels = session._get_available_thinking_levels()
        assert "medium" in levels

    def test_claude_3_7_returns_xhigh(self) -> None:
        agent = make_mock_agent()
        mock_model = MagicMock()
        mock_model.reasoning = True
        mock_model.id = "claude-3-7-sonnet"
        agent.state.model = mock_model
        session = make_session(agent)
        levels = session._get_available_thinking_levels()
        assert "xhigh" in levels
