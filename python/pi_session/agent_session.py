"""AgentSession — orchestrator wrapping Agent + SessionManager with auto-retry and auto-compaction."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Union

from pi_ai.overflow import is_context_overflow
from pi_ai.types import (
    AssistantMessage,
    ImageContent,
    Message,
    Model,
    Usage,
    UserMessage,
)
from pi_agent.agent import Agent
from pi_agent.types import (
    AgentEndEvent,
    AgentEvent,
    AgentStartEvent,
    MessageEndEvent,
    TurnEndEvent,
)

from pi_session.compaction import (
    CompactionResult,
    CompactionSettings,
    calculate_context_tokens,
    compact,
    prepare_compaction,
    should_compact,
)
from pi_session.session_manager import SessionManager


# --- Retry settings ---


@dataclass
class RetrySettings:
    enabled: bool = True
    max_retries: int = 3
    base_delay: float = 2.0
    max_delay: float = 60.0


# --- Session events (extends AgentEvent) ---


@dataclass
class AutoCompactionStartEvent:
    type: Literal["auto_compaction_start"] = "auto_compaction_start"


@dataclass
class AutoCompactionEndEvent:
    type: Literal["auto_compaction_end"] = "auto_compaction_end"
    summary: str = ""
    tokens_before: int = 0


@dataclass
class AutoRetryStartEvent:
    type: Literal["auto_retry_start"] = "auto_retry_start"
    attempt: int = 0
    delay: float = 0.0
    error: str = ""


@dataclass
class AutoRetryEndEvent:
    type: Literal["auto_retry_end"] = "auto_retry_end"
    attempt: int = 0


SessionEvent = Union[
    AgentEvent,
    AutoCompactionStartEvent,
    AutoCompactionEndEvent,
    AutoRetryStartEvent,
    AutoRetryEndEvent,
]


# --- Session stats ---


@dataclass
class SessionStats:
    total_messages: int = 0
    total_turns: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    compactions: int = 0


# --- Retryable error detection ---

RETRYABLE_PATTERN = re.compile(
    r"overloaded|rate.?limit|429|500|502|503|504|"
    r"connection.?error|fetch.?failed|timeout|"
    r"internal.?server.?error|service.?unavailable|"
    r"bad.?gateway|gateway.?timeout|ECONNRESET|ETIMEDOUT",
    re.IGNORECASE,
)


def _is_retryable_error(message: AssistantMessage) -> bool:
    """Check if an assistant message represents a retryable error."""
    if message.stop_reason != "error":
        return False
    if not message.error_message:
        return False
    return bool(RETRYABLE_PATTERN.search(message.error_message))


# --- AgentSession config ---


@dataclass
class AgentSessionConfig:
    agent: Agent
    session_manager: SessionManager
    compaction_settings: CompactionSettings = field(default_factory=CompactionSettings)
    retry_settings: RetrySettings = field(default_factory=RetrySettings)


# --- AgentSession ---


class AgentSession:
    """Orchestrator wrapping Agent + SessionManager with auto-retry and auto-compaction."""

    def __init__(self, config: AgentSessionConfig):
        self._agent = config.agent
        self._session_manager = config.session_manager
        self._compaction_settings = config.compaction_settings
        self._retry_settings = config.retry_settings
        self._listeners: list[Any] = []
        self._abort_signal: asyncio.Event | None = None
        self._retry_count = 0
        self._compaction_count = 0

        # Subscribe to agent events
        self._agent.subscribe(self._handle_agent_event)

    @property
    def agent(self) -> Agent:
        return self._agent

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    # --- Event subscription ---

    def subscribe(self, fn: Any) -> Any:
        """Subscribe to session events. Returns unsubscribe function."""
        self._listeners.append(fn)
        return lambda: self._listeners.remove(fn) if fn in self._listeners else None

    def _emit(self, event: SessionEvent) -> None:
        for listener in self._listeners:
            listener(event)

    # --- Public API ---

    async def prompt(self, text: str, images: list[ImageContent] | None = None) -> None:
        """Send a prompt and process with auto-retry and auto-compaction."""
        self._abort_signal = asyncio.Event()
        self._retry_count = 0

        # Persist user message
        user_msg = UserMessage(content=text)
        if images:
            user_msg = UserMessage(content=[*([__import__("pi_ai.types", fromlist=["TextContent"]).TextContent(text=text)] if text else []), *images])

        self._session_manager.append_message(user_msg)

        await self._agent.prompt(text, images)

    async def steer(self, text: str) -> None:
        """Send a steering message."""
        user_msg = UserMessage(content=text)
        self._session_manager.append_message(user_msg)
        self._agent.steer(user_msg)

    async def follow_up(self, text: str) -> None:
        """Queue a follow-up message."""
        user_msg = UserMessage(content=text)
        self._session_manager.append_message(user_msg)
        self._agent.follow_up(user_msg)

    def abort(self) -> None:
        """Abort the current operation."""
        if self._abort_signal:
            self._abort_signal.set()
        self._agent.abort()

    async def manual_compact(self, custom_instructions: str | None = None) -> None:
        """Manually trigger compaction."""
        await self._run_compaction()

    def set_model(self, model: Model, thinking_level: str | None = None) -> None:
        """Change the model and optionally the thinking level."""
        self._agent.set_model(model)
        if thinking_level is not None:
            self._agent.set_thinking_level(thinking_level)
        self._session_manager.append_model_change(model.provider, model.id)
        if thinking_level:
            self._session_manager.append_thinking_level_change(thinking_level)

    def get_stats(self) -> SessionStats:
        """Get session statistics."""
        entries = self._session_manager.entries
        total_messages = 0
        total_tokens = 0
        total_cost = 0.0
        compactions = 0

        ctx = self._session_manager.build_session_context()
        for msg in ctx.messages:
            total_messages += 1
            if isinstance(msg, AssistantMessage):
                total_tokens += msg.usage.total_tokens
                total_cost += msg.usage.cost.total

        from pi_session.types import CompactionEntry
        for entry in entries:
            if isinstance(entry, CompactionEntry):
                compactions += 1

        return SessionStats(
            total_messages=total_messages,
            total_turns=total_messages,
            total_tokens=total_tokens,
            total_cost=total_cost,
            compactions=compactions,
        )

    # --- Internal event handler ---

    def _handle_agent_event(self, event: AgentEvent) -> None:
        """Handle agent events: persist messages, trigger auto-retry/compaction."""
        # Forward event to session listeners
        self._emit(event)

        # Persist messages
        if isinstance(event, MessageEndEvent):
            self._session_manager.append_message(event.message)

        # Check for retryable errors and context overflow on turn end
        if isinstance(event, TurnEndEvent) and isinstance(event.message, AssistantMessage):
            msg = event.message

            # Schedule auto-retry or auto-compaction (non-blocking)
            if _is_retryable_error(msg):
                asyncio.ensure_future(self._handle_retryable_error(msg))
            elif is_context_overflow(
                msg,
                self._agent.model.context_window if self._agent.model else None,
            ):
                asyncio.ensure_future(self._handle_context_overflow(msg))
            elif self._agent.model and should_compact(
                calculate_context_tokens(msg.usage),
                self._agent.model.context_window,
                self._compaction_settings,
            ):
                asyncio.ensure_future(self._check_compaction_threshold(msg))

    # --- Auto-retry ---

    async def _handle_retryable_error(self, msg: AssistantMessage) -> bool:
        """Handle a retryable error with exponential backoff."""
        if not self._retry_settings.enabled:
            return False
        if self._retry_count >= self._retry_settings.max_retries:
            return False

        self._retry_count += 1
        delay = min(
            self._retry_settings.base_delay * (2 ** (self._retry_count - 1)),
            self._retry_settings.max_delay,
        )

        self._emit(AutoRetryStartEvent(
            attempt=self._retry_count,
            delay=delay,
            error=msg.error_message or "",
        ))

        # Remove the error message from agent's messages
        if self._agent.messages and isinstance(self._agent.messages[-1], AssistantMessage):
            if self._agent.messages[-1].stop_reason == "error":
                self._agent.messages.pop()

        await asyncio.sleep(delay)

        self._emit(AutoRetryEndEvent(attempt=self._retry_count))

        # Continue the agent
        try:
            await self._agent.continue_()
        except RuntimeError:
            # Agent may have been aborted
            pass

        return True

    # --- Auto-compaction ---

    async def _handle_context_overflow(self, msg: AssistantMessage) -> None:
        """Handle context overflow: compact and retry."""
        # Remove the error message
        if self._agent.messages and isinstance(self._agent.messages[-1], AssistantMessage):
            if self._agent.messages[-1].stop_reason == "error":
                self._agent.messages.pop()

        await self._run_compaction()

        # Retry after compaction
        try:
            await self._agent.continue_()
        except RuntimeError:
            pass

    async def _check_compaction_threshold(self, msg: AssistantMessage) -> None:
        """Check if we should compact after a successful response."""
        await self._run_compaction()

    async def _run_compaction(self) -> None:
        """Run the compaction process."""
        if not self._compaction_settings.enabled:
            return

        messages = self._agent.messages
        prep = prepare_compaction(messages, self._compaction_settings)
        if prep is None:
            return

        self._emit(AutoCompactionStartEvent())

        model = self._agent.model
        if not model:
            return

        try:
            result = await compact(
                prep,
                model,
                api_key=self._agent._api_key,
                abort_signal=self._abort_signal,
                stream_fn=self._agent._stream_fn,
            )

            # Find the first kept entry ID in the session
            first_kept_entry_id = ""
            branch = self._session_manager.get_branch()
            kept_count = 0
            for entry in reversed(branch):
                from pi_session.types import SessionMessageEntry
                if isinstance(entry, SessionMessageEntry):
                    kept_count += 1
                    if kept_count >= len(result.kept_messages):
                        first_kept_entry_id = entry.id
                        break

            self._session_manager.append_compaction(
                summary=result.summary,
                first_kept_id=first_kept_entry_id,
                tokens_before=result.compacted_tokens,
            )

            # Rebuild agent context from session
            ctx = self._session_manager.build_session_context()
            self._agent.replace_messages(ctx.messages)

            self._compaction_count += 1

            self._emit(AutoCompactionEndEvent(
                summary=result.summary,
                tokens_before=result.compacted_tokens,
            ))
        except Exception:
            # Compaction failed — continue without it
            pass
