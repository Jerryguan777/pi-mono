"""Integration test: Session persistence x cross-instance recovery.

Verifies that conversation history persisted by one SessionManager instance
can be loaded by a second instance, and that new messages can be appended.
Also verifies the JSONL file format is valid for third-party parsers.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from pi_agent.agent_loop import agent_loop
from pi_agent.types import (
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    MessageEndEvent,
)
from pi_ai.api_registry import clear_api_providers
from pi_ai.types import AssistantMessage, TextContent, UserMessage
from pi_coding_agent.core.session_manager import (
    SessionManager,
    SessionMessageEntry,
    load_entries_from_file,
)
from tests.helpers.fake_llm import (
    FakeLLM,
    make_fake_model,
    make_text_response,
)


@pytest.fixture(autouse=True)
def _clean_registry() -> Generator[None, None, None]:
    clear_api_providers()
    yield
    clear_api_providers()


@pytest.fixture()
def session_dir() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as d:
        yield d


async def _run_agent_loop_and_persist(
    sm: SessionManager,
    user_text: str,
    fake: FakeLLM,
) -> list[AgentEvent]:
    """Run one round of agent loop with the given SessionManager and persist messages."""
    model = make_fake_model()
    fake.register()

    user_msg = UserMessage(content=user_text)
    sm.append_message(user_msg)

    context = AgentContext(
        system_prompt="Test system prompt",
        messages=[user_msg],
        tools=[],
    )
    config = AgentLoopConfig(model=model, max_turns=5)

    events: list[AgentEvent] = []
    async for event in agent_loop([user_msg], context, config):
        events.append(event)
        # Persist assistant messages to session
        if isinstance(event, MessageEndEvent) and isinstance(event.message, AssistantMessage):
            sm.append_message(event.message)

    return events


async def test_instance_a_writes_instance_b_reads(session_dir: str) -> None:
    """Instance A creates a session and writes messages.
    Instance B loads the same file and sees the full history."""
    # Instance A: create session and run one round
    sm_a = SessionManager(
        cwd=session_dir,
        session_dir=session_dir,
        session_file=None,
        persist=True,
    )
    session_file = sm_a.get_session_file()
    assert session_file is not None

    fake_a = FakeLLM([make_text_response("Hello from A!")])
    await _run_agent_loop_and_persist(sm_a, "User message 1", fake_a)

    # Instance B: load the same session file
    sm_b = SessionManager(
        cwd=session_dir,
        session_dir=session_dir,
        session_file=session_file,
        persist=True,
    )

    # B should see the messages written by A
    ctx_b = sm_b.build_session_context()
    assert len(ctx_b.messages) >= 2  # at least user + assistant

    # Find the user message
    user_msgs = [m for m in ctx_b.messages if hasattr(m, "role") and m.role == "user"]
    assert any("User message 1" in (getattr(m, "content", "") or "") for m in user_msgs)

    # Find the assistant message
    assistant_msgs = [m for m in ctx_b.messages if hasattr(m, "role") and m.role == "assistant"]
    assert len(assistant_msgs) >= 1


async def test_instance_b_appends_to_same_file(session_dir: str) -> None:
    """Instance A writes, Instance B loads and appends more messages to the same file."""
    # Instance A
    sm_a = SessionManager(
        cwd=session_dir,
        session_dir=session_dir,
        session_file=None,
        persist=True,
    )
    session_file = sm_a.get_session_file()
    assert session_file is not None

    fake_a = FakeLLM([make_text_response("Response from round 1")])
    await _run_agent_loop_and_persist(sm_a, "Round 1 prompt", fake_a)

    # Count entries after A
    entries_after_a = load_entries_from_file(session_file)
    msg_count_a = sum(1 for e in entries_after_a if isinstance(e, SessionMessageEntry))

    # Instance B: load and append
    sm_b = SessionManager(
        cwd=session_dir,
        session_dir=session_dir,
        session_file=session_file,
        persist=True,
    )

    clear_api_providers()
    fake_b = FakeLLM([make_text_response("Response from round 2")])
    await _run_agent_loop_and_persist(sm_b, "Round 2 prompt", fake_b)

    # Verify the file now has more message entries
    entries_after_b = load_entries_from_file(session_file)
    msg_count_b = sum(1 for e in entries_after_b if isinstance(e, SessionMessageEntry))
    assert msg_count_b > msg_count_a


async def test_jsonl_format_is_valid(session_dir: str) -> None:
    """The JSONL session file must be parseable line-by-line by a standard JSON parser."""
    sm = SessionManager(
        cwd=session_dir,
        session_dir=session_dir,
        session_file=None,
        persist=True,
    )
    session_file = sm.get_session_file()
    assert session_file is not None

    fake = FakeLLM([make_text_response("Verifying JSONL format")])
    await _run_agent_loop_and_persist(sm, "Test JSONL", fake)

    # Read and parse each line independently
    content = Path(session_file).read_text(encoding="utf-8")
    lines = [line for line in content.strip().split("\n") if line.strip()]

    assert len(lines) >= 1  # at least the header

    for i, line in enumerate(lines):
        parsed = json.loads(line)
        assert isinstance(parsed, dict), f"Line {i} is not a JSON object"
        assert "type" in parsed, f"Line {i} missing 'type' field"

    # First line must be session header
    header = json.loads(lines[0])
    assert header["type"] == "session"
    assert "id" in header
    assert "timestamp" in header


async def test_session_context_preserves_message_order(session_dir: str) -> None:
    """Messages loaded from a session file must maintain chronological order."""
    sm = SessionManager(
        cwd=session_dir,
        session_dir=session_dir,
        session_file=None,
        persist=True,
    )
    session_file = sm.get_session_file()
    assert session_file is not None

    # Write multiple rounds
    for i in range(3):
        clear_api_providers()
        fake = FakeLLM([make_text_response(f"Response {i}")])
        user_msg = UserMessage(content=f"Prompt {i}")
        sm.append_message(user_msg)

        model = make_fake_model()
        fake.register()

        context = AgentContext(system_prompt="test", messages=[user_msg], tools=[])
        config = AgentLoopConfig(model=model, max_turns=2)

        async for event in agent_loop([user_msg], context, config):
            if isinstance(event, MessageEndEvent) and isinstance(event.message, AssistantMessage):
                sm.append_message(event.message)

    # Reload from file and verify order
    sm_reload = SessionManager(
        cwd=session_dir,
        session_dir=session_dir,
        session_file=session_file,
        persist=True,
    )
    ctx = sm_reload.build_session_context()

    # Extract text from messages in order
    texts: list[str] = []
    for msg in ctx.messages:
        if hasattr(msg, "content"):
            content = msg.content
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, TextContent):
                        texts.append(block.text)

    # User prompts should appear in order
    prompt_texts = [t for t in texts if t.startswith("Prompt")]
    assert prompt_texts == ["Prompt 0", "Prompt 1", "Prompt 2"]
