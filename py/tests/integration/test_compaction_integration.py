"""Integration test: AgentSession.compact() × compaction module × SessionManager.

Verifies the full compaction chain:
  AgentSession.compact()
    → prepare_compaction(session entries)
    → compact(preparation, model, api_key) [calls LLM via fake provider]
    → session_manager.append_compaction(summary, ...)
    → agent.replace_messages(new context)

Also verifies _check_compaction() triggers auto-compaction when context is large.

This test catches the "stub not wired" failure mode — if compact() raises
NotImplementedError or _check_compaction() is a no-op, these tests fail.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pi_ai.types import (
    AssistantMessage,
    TextContent,
    Usage,
    UserMessage,
)
from pi_coding_agent.core.agent_session import (
    AgentSession,
    AgentSessionConfig,
)
from pi_coding_agent.core.session_manager import (
    SessionManager,
    get_latest_compaction_entry,
)
from tests.helpers.fake_llm import (
    FAKE_API,
    FAKE_MODEL_ID,
    FAKE_PROVIDER,
    FakeLLM,
    make_fake_model,
    make_text_response,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_with_messages(messages: list[Any]) -> MagicMock:
    """Create a mock Agent whose state.messages returns the given list."""
    agent = MagicMock()
    agent.subscribe.return_value = MagicMock()
    model = make_fake_model()
    agent.state.model = model
    agent.state.thinking_level = "off"
    agent.state.is_streaming = False
    agent.state.messages = messages
    agent.wait_for_idle = AsyncMock()
    agent.prompt = AsyncMock()
    agent.follow_up = MagicMock()
    agent.steer = MagicMock()
    agent.set_model = MagicMock()
    agent.replace_messages = MagicMock()
    agent.abort = AsyncMock()
    agent.has_queued_messages = MagicMock(return_value=False)
    return agent


def _make_user_msg(text: str) -> UserMessage:
    return UserMessage(content=[TextContent(text=text)])


def _make_assistant_msg(
    text: str,
    *,
    input_tokens: int = 500,
    output_tokens: int = 200,
    stop_reason: str = "stop",
) -> AssistantMessage:
    return AssistantMessage(
        content=[TextContent(text=text)],
        api=FAKE_API,
        provider=FAKE_PROVIDER,
        model=FAKE_MODEL_ID,
        stop_reason=stop_reason,
        usage=Usage(input=input_tokens, output=output_tokens),
    )


def _populate_session_with_conversation(
    sm: SessionManager,
    turn_count: int = 20,
    chars_per_msg: int = 2000,
) -> None:
    """Add many turns to session manager to create a large context."""
    for i in range(turn_count):
        user_text = f"User message {i}: " + "x" * chars_per_msg
        sm.append_message(_make_user_msg(user_text))
        assistant_text = f"Assistant response {i}: " + "y" * chars_per_msg
        sm.append_message(
            _make_assistant_msg(assistant_text, input_tokens=5000 * (i + 1), output_tokens=1000)
        )


def _make_session_with_history(
    turn_count: int = 20,
    chars_per_msg: int = 2000,
) -> tuple[AgentSession, SessionManager, MagicMock]:
    """Create AgentSession with a pre-populated session (many turns)."""
    sm = SessionManager.in_memory("/tmp")
    _populate_session_with_conversation(sm, turn_count, chars_per_msg)

    # Rebuild messages from session context
    ctx = sm.build_session_context()
    agent = _make_agent_with_messages(list(ctx.messages))

    # Mock model_registry.get_api_key
    model_registry = MagicMock()
    model_registry.get_api_key = AsyncMock(return_value="fake-key")

    # Mock settings_manager.get_compaction_settings
    settings_manager = MagicMock()
    from pi_coding_agent.core.compaction.compaction import CompactionSettings

    settings_manager.get_compaction_settings.return_value = CompactionSettings(
        enabled=True, reserve_tokens=4096, keep_recent_tokens=5000
    )

    config = AgentSessionConfig(
        agent=agent,
        session_manager=sm,
        cwd="/tmp",
        model_registry=model_registry,
        settings_manager=settings_manager,
    )
    session = AgentSession(config)
    return session, sm, agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompactWiring:
    """Test that AgentSession.compact() actually calls the compaction module
    and persists the result via SessionManager."""

    @pytest.mark.anyio
    async def test_compact_produces_compaction_entry(self) -> None:
        """compact() must call the compaction module's compact() function,
        persist via session_manager.append_compaction(), and update agent messages.

        If compact() is a stub (raises NotImplementedError), this test fails.
        """
        session, sm, agent = _make_session_with_history()

        # Register fake LLM to handle the summarization call
        summary_response = make_text_response("## Goal\nTest compaction summary")
        fake_llm = FakeLLM([summary_response])
        fake_llm.register()

        try:
            result = await session.compact()
        except NotImplementedError:
            pytest.fail(
                "AgentSession.compact() raised NotImplementedError — "
                "compaction module is not wired into AgentSession"
            )

        # Verify: compaction entry was appended to session
        compaction_entry = get_latest_compaction_entry(sm.get_branch())
        assert compaction_entry is not None, (
            "No compaction entry in session after compact() — "
            "session_manager.append_compaction() was not called"
        )
        assert "compaction summary" in compaction_entry.summary.lower() or len(compaction_entry.summary) > 0

        # Verify: result contains expected fields
        assert result is not None
        assert hasattr(result, "summary")
        assert hasattr(result, "first_kept_entry_id")
        assert hasattr(result, "tokens_before")
        assert result.tokens_before > 0

        # Verify: agent.replace_messages was called (context was refreshed)
        assert agent.replace_messages.called, (
            "agent.replace_messages() was not called after compaction — "
            "agent context was not refreshed"
        )

class TestCheckCompactionWiring:
    """Test that _check_compaction() actually evaluates context size
    and triggers auto-compaction when needed."""

    @pytest.mark.anyio
    async def test_check_compaction_is_not_noop(self) -> None:
        """_check_compaction() must inspect context tokens and potentially
        trigger compaction — not just 'pass'.

        We verify by giving it an assistant message with huge usage numbers
        and a tiny context window model, then check that auto-compaction events
        are emitted.
        """
        session, sm, agent = _make_session_with_history()

        # Register fake LLM for summarization
        fake_llm = FakeLLM([make_text_response("Auto-compaction summary")])
        fake_llm.register()

        # Collect emitted events
        events: list[Any] = []
        session.subscribe(lambda ev: events.append(ev))

        # Create an assistant message with huge usage (simulates near-full context)
        big_assistant = _make_assistant_msg(
            "response",
            input_tokens=200000,  # huge — should exceed any reasonable threshold
            output_tokens=5000,
            stop_reason="stop",
        )
        big_assistant.provider = FAKE_PROVIDER
        big_assistant.model = FAKE_MODEL_ID

        # Give the model a small context window so threshold is easily exceeded
        model = make_fake_model()
        model.context_window = 50000  # Much smaller than the 200k usage
        agent.state.model = model

        # Call _check_compaction directly
        await session._check_compaction(big_assistant)

        # If _check_compaction is a no-op (just 'pass'), no events will be emitted
        compaction_events = [
            ev for ev in events
            if getattr(ev, "type", None) in ("auto_compaction_start", "auto_compaction_end")
        ]

        assert len(compaction_events) > 0, (
            "_check_compaction() did not emit any auto_compaction events despite "
            "context tokens (200k) exceeding context window (50k). "
            "The method is likely a no-op stub."
        )
