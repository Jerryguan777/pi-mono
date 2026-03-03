"""Tests for the session layer — SessionManager, compaction, AgentSession."""

import asyncio
import json
import os
import tempfile

import pytest

from pi_ai.api_registry import register_provider
from pi_ai.types import (
    AssistantMessage,
    DoneEvent,
    ImageContent,
    Model,
    ModelCost,
    StartEvent,
    StreamOptions,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)
from pi_agent.agent import Agent
from pi_agent.types import (
    AgentEndEvent,
    AgentLoopConfig,
    AgentStartEvent,
    AgentTool,
    AgentToolResult,
    MessageEndEvent,
    TurnEndEvent,
)

from pi_session.agent_session import (
    AgentSession,
    AgentSessionConfig,
    AutoCompactionEndEvent,
    AutoCompactionStartEvent,
    AutoRetryEndEvent,
    AutoRetryStartEvent,
    RetrySettings,
    SessionStats,
    _is_retryable_error,
)
from pi_session.compaction import (
    CompactionSettings,
    CutPointResult,
    estimate_tokens,
    find_cut_point,
    prepare_compaction,
    should_compact,
)
from pi_session.session_manager import SessionManager
from pi_session.types import (
    CompactionEntry,
    ModelChangeEntry,
    SessionContext,
    SessionHeader,
    SessionMessageEntry,
    ThinkingLevelChangeEntry,
    deserialize_message,
    serialize_message,
)


MOCK_MODEL = Model(
    id="mock-model",
    name="Mock",
    api="mock-api",
    provider="mock",
    base_url="",
    reasoning=False,
    input=["text"],
    cost=ModelCost(),
    context_window=128000,
    max_tokens=4096,
)


# --- Message serialization tests ---


def test_serialize_deserialize_user_message():
    """User message round-trips through serialization."""
    msg = UserMessage(content="hello world", timestamp=12345)
    d = serialize_message(msg)
    assert d["role"] == "user"
    assert d["content"] == "hello world"

    restored = deserialize_message(d)
    assert isinstance(restored, UserMessage)
    assert restored.content == "hello world"
    assert restored.timestamp == 12345


def test_serialize_deserialize_assistant_message():
    """Assistant message with text + tool call round-trips."""
    msg = AssistantMessage(
        content=[
            TextContent(text="Let me help"),
            ToolCall(id="tc1", name="read", arguments={"path": "/tmp/test"}),
        ],
        api="mock-api",
        provider="mock",
        model="mock-model",
        usage=Usage(input=100, output=50, total_tokens=150),
        stop_reason="toolUse",
        timestamp=12345,
    )
    d = serialize_message(msg)
    restored = deserialize_message(d)

    assert isinstance(restored, AssistantMessage)
    assert len(restored.content) == 2
    assert isinstance(restored.content[0], TextContent)
    assert restored.content[0].text == "Let me help"
    assert isinstance(restored.content[1], ToolCall)
    assert restored.content[1].name == "read"
    assert restored.usage.input == 100
    assert restored.stop_reason == "toolUse"


def test_serialize_deserialize_tool_result():
    """Tool result message round-trips."""
    msg = ToolResultMessage(
        tool_call_id="tc1",
        tool_name="read",
        content=[TextContent(text="file contents here")],
        is_error=False,
        timestamp=12345,
    )
    d = serialize_message(msg)
    restored = deserialize_message(d)

    assert isinstance(restored, ToolResultMessage)
    assert restored.tool_call_id == "tc1"
    assert restored.tool_name == "read"
    assert len(restored.content) == 1
    assert restored.content[0].text == "file contents here"


# --- SessionManager tests ---


def test_session_manager_create_and_append():
    """Create session, append messages, verify JSONL persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SessionManager.create(tmpdir, session_dir=tmpdir)
        assert mgr.path is not None
        assert os.path.exists(mgr.path)

        # Append messages
        id1 = mgr.append_message(UserMessage(content="hello"))
        id2 = mgr.append_message(AssistantMessage(content=[TextContent(text="hi")]))

        assert len(mgr.entries) == 2
        assert mgr.leaf_id == id2

        # Verify JSONL file
        with open(mgr.path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        assert len(lines) == 3  # header + 2 entries
        header = json.loads(lines[0])
        assert header["type"] == "session"

        entry1 = json.loads(lines[1])
        assert entry1["type"] == "message"
        assert entry1["message"]["role"] == "user"

        entry2 = json.loads(lines[2])
        assert entry2["type"] == "message"
        assert entry2["parent_id"] == entry1["id"]


def test_session_manager_build_context():
    """Build context reconstructs messages from session."""
    mgr = SessionManager.in_memory()

    user_msg = UserMessage(content="What is 2+2?")
    asst_msg = AssistantMessage(
        content=[TextContent(text="4")],
        usage=Usage(input=10, output=5),
    )

    mgr.append_message(user_msg)
    mgr.append_message(asst_msg)

    ctx = mgr.build_session_context()
    assert len(ctx.messages) == 2
    assert ctx.summary is None
    assert isinstance(ctx.messages[0], UserMessage)
    assert isinstance(ctx.messages[1], AssistantMessage)
    assert ctx.messages[1].content[0].text == "4"


def test_session_manager_in_memory():
    """In-memory mode works without file I/O."""
    mgr = SessionManager.in_memory()
    assert mgr.path is None

    mgr.append_message(UserMessage(content="test"))
    assert len(mgr.entries) == 1


def test_session_manager_open():
    """Open an existing session file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr1 = SessionManager.create(tmpdir, session_dir=tmpdir)
        mgr1.append_message(UserMessage(content="hello"))
        mgr1.append_message(AssistantMessage(content=[TextContent(text="hi")]))

        # Re-open
        mgr2 = SessionManager.open(mgr1.path)
        assert len(mgr2.entries) == 2
        assert mgr2.header.id == mgr1.header.id

        ctx = mgr2.build_session_context()
        assert len(ctx.messages) == 2


def test_session_manager_continue_recent():
    """Continue from most recent session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr1 = SessionManager.create(tmpdir, session_dir=tmpdir)
        mgr1.append_message(UserMessage(content="session 1"))

        # Create a second (more recent) session
        mgr2 = SessionManager.create(tmpdir, session_dir=tmpdir)
        mgr2.append_message(UserMessage(content="session 2"))

        # Continue should pick up the most recent
        mgr3 = SessionManager.continue_recent(tmpdir, session_dir=tmpdir)
        ctx = mgr3.build_session_context()
        assert len(ctx.messages) == 1
        assert ctx.messages[0].content == "session 2"


def test_session_manager_tree_navigation():
    """Branch and navigate the session tree."""
    mgr = SessionManager.in_memory()

    id1 = mgr.append_message(UserMessage(content="message 1"))
    id2 = mgr.append_message(AssistantMessage(content=[TextContent(text="response 1")]))
    id3 = mgr.append_message(UserMessage(content="message 2"))

    # Branch from id2 (fork after first response)
    mgr.branch(id2)
    id4 = mgr.append_message(UserMessage(content="alternate message 2"))

    # Get current branch (should be id1 -> id2 -> id4)
    branch = mgr.get_branch()
    assert len(branch) == 3
    assert branch[0].id == id1
    assert branch[1].id == id2
    assert branch[2].id == id4

    # Original branch (id1 -> id2 -> id3)
    orig_branch = mgr.get_branch(id3)
    assert len(orig_branch) == 3
    assert orig_branch[2].id == id3

    # Tree should have branching structure
    tree = mgr.get_tree()
    assert len(tree) == 1  # One root
    assert len(tree[0].children) == 1  # id2
    assert len(tree[0].children[0].children) == 2  # id3 and id4


def test_session_manager_append_model_change():
    """Append model change entry."""
    mgr = SessionManager.in_memory()
    entry_id = mgr.append_model_change("anthropic", "claude-opus-4-6")
    assert len(mgr.entries) == 1
    assert isinstance(mgr.entries[0], ModelChangeEntry)
    assert mgr.entries[0].provider == "anthropic"


def test_session_manager_append_compaction():
    """Append compaction entry and verify context reconstruction."""
    mgr = SessionManager.in_memory()

    # Add some messages
    id1 = mgr.append_message(UserMessage(content="old message 1"))
    id2 = mgr.append_message(AssistantMessage(content=[TextContent(text="old response")]))
    id3 = mgr.append_message(UserMessage(content="new message"))
    id4 = mgr.append_message(AssistantMessage(content=[TextContent(text="new response")]))

    # Add compaction that keeps from id3 onwards
    mgr.append_compaction(
        summary="User asked a question, assistant answered.",
        first_kept_id=id3,
        tokens_before=500,
    )

    # Build context should only include kept messages
    ctx = mgr.build_session_context()
    assert ctx.summary == "User asked a question, assistant answered."
    assert len(ctx.messages) == 2
    assert isinstance(ctx.messages[0], UserMessage)
    assert ctx.messages[0].content == "new message"


# --- Compaction tests ---


def test_compaction_estimate_tokens():
    """Token estimation uses chars/4 heuristic."""
    msg = UserMessage(content="Hello world!")  # 12 chars
    tokens = estimate_tokens(msg)
    assert tokens == 3  # 12 // 4

    # Empty message should return at least 1
    empty = UserMessage(content="")
    assert estimate_tokens(empty) >= 1


def test_compaction_estimate_tokens_assistant():
    """Token estimation for assistant messages with various content."""
    msg = AssistantMessage(
        content=[
            TextContent(text="x" * 400),  # 100 tokens
            ToolCall(id="tc1", name="read", arguments={"path": "/tmp/test"}),
        ],
    )
    tokens = estimate_tokens(msg)
    assert tokens > 100  # text + tool call overhead


def test_compaction_should_compact():
    """Threshold detection triggers at 80% of available window."""
    settings = CompactionSettings(reserve_tokens=16384)

    # 128000 - 16384 = 111616, 80% = 89293
    assert not should_compact(80000, 128000, settings)
    assert should_compact(100000, 128000, settings)


def test_compaction_should_compact_disabled():
    """No compaction when disabled."""
    settings = CompactionSettings(enabled=False)
    assert not should_compact(200000, 128000, settings)


def test_compaction_find_cut_point():
    """Cut-point algorithm keeps recent messages."""
    messages: list = [
        UserMessage(content="x" * 400),      # ~100 tokens
        AssistantMessage(content=[TextContent(text="y" * 400)]),  # ~100 tokens
        UserMessage(content="a" * 400),       # ~100 tokens
        AssistantMessage(content=[TextContent(text="b" * 400)]),  # ~100 tokens
        UserMessage(content="c" * 400),       # ~100 tokens
        AssistantMessage(content=[TextContent(text="d" * 400)]),  # ~100 tokens
    ]

    result = find_cut_point(messages, keep_recent_tokens=250)
    assert result is not None
    assert result.cut_index >= 2
    assert len(result.compacted_messages) > 0
    assert len(result.kept_messages) > 0
    assert result.compacted_tokens > 0


def test_compaction_find_cut_point_too_few_messages():
    """No cut point when fewer than 4 messages."""
    messages: list = [
        UserMessage(content="hello"),
        AssistantMessage(content=[TextContent(text="hi")]),
    ]
    result = find_cut_point(messages, keep_recent_tokens=100)
    assert result is None


def test_compaction_prepare():
    """prepare_compaction finds cut point and extracts file ops."""
    messages: list = [
        UserMessage(content="Read /tmp/test.py"),
        AssistantMessage(content=[
            TextContent(text="Let me read that"),
            ToolCall(id="tc1", name="read", arguments={"path": "/tmp/test.py"}),
        ]),
        ToolResultMessage(
            tool_call_id="tc1", tool_name="read",
            content=[TextContent(text="file contents " * 100)],
        ),
        AssistantMessage(content=[
            ToolCall(id="tc2", name="edit", arguments={"path": "/tmp/test.py", "oldText": "a", "newText": "b"}),
        ]),
        ToolResultMessage(
            tool_call_id="tc2", tool_name="edit",
            content=[TextContent(text="done")],
        ),
        AssistantMessage(content=[TextContent(text="x" * 400)]),
        UserMessage(content="What next?"),
        AssistantMessage(content=[TextContent(text="All done!")]),
    ]

    settings = CompactionSettings(keep_recent_tokens=50)
    prep = prepare_compaction(messages, settings)
    assert prep is not None
    assert "/tmp/test.py" in prep.read_files
    assert "/tmp/test.py" in prep.modified_files


# --- Retryable error detection ---


def test_is_retryable_error():
    """Retryable error patterns are detected."""
    msg = AssistantMessage(stop_reason="error", error_message="Rate limit exceeded (429)")
    assert _is_retryable_error(msg)

    msg2 = AssistantMessage(stop_reason="error", error_message="Server overloaded")
    assert _is_retryable_error(msg2)

    msg3 = AssistantMessage(stop_reason="error", error_message="connection error")
    assert _is_retryable_error(msg3)

    # Non-retryable
    msg4 = AssistantMessage(stop_reason="error", error_message="Invalid API key")
    assert not _is_retryable_error(msg4)

    # Not an error
    msg5 = AssistantMessage(stop_reason="stop")
    assert not _is_retryable_error(msg5)


# --- Mock stream helpers ---


async def mock_text_stream(model, context, options=None):
    """Mock stream returning a text response."""
    output = AssistantMessage(
        api="mock-api", provider="mock", model="mock-model",
        content=[TextContent(text="Hello from mock!")],
        usage=Usage(input=100, output=50, total_tokens=150),
        stop_reason="stop",
    )
    yield StartEvent(partial=output)
    yield TextStartEvent(content_index=0, partial=output)
    yield TextDeltaEvent(content_index=0, delta="Hello from mock!", partial=output)
    yield TextEndEvent(content_index=0, content="Hello from mock!", partial=output)
    yield DoneEvent(reason="stop", message=output)


from pi_ai.types import TextStartEvent


_retry_call_count = 0


async def mock_retry_stream(model, context, options=None):
    """First call returns retryable error, second succeeds."""
    global _retry_call_count
    _retry_call_count += 1

    if _retry_call_count == 1:
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[],
            usage=Usage(),
            stop_reason="error",
            error_message="Rate limit exceeded (429)",
        )
        yield StartEvent(partial=output)
        yield DoneEvent(reason="error", message=output)
    else:
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[TextContent(text="Success after retry!")],
            usage=Usage(input=100, output=50, total_tokens=150),
            stop_reason="stop",
        )
        yield StartEvent(partial=output)
        yield DoneEvent(reason="stop", message=output)


_overflow_call_count = 0


async def mock_overflow_stream(model, context, options=None):
    """First call returns context overflow error, second succeeds."""
    global _overflow_call_count
    _overflow_call_count += 1

    if _overflow_call_count == 1:
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[],
            usage=Usage(),
            stop_reason="error",
            error_message="prompt is too long: 200000 tokens > 128000 maximum",
        )
        yield StartEvent(partial=output)
        yield DoneEvent(reason="error", message=output)
    else:
        output = AssistantMessage(
            api="mock-api", provider="mock", model="mock-model",
            content=[TextContent(text="Success after compaction!")],
            usage=Usage(input=50, output=20, total_tokens=70),
            stop_reason="stop",
        )
        yield StartEvent(partial=output)
        yield DoneEvent(reason="stop", message=output)


# --- AgentSession tests ---


@pytest.mark.asyncio
async def test_agent_session_prompt():
    """AgentSession.prompt persists messages to session."""
    register_provider("mock-api", mock_text_stream)

    agent = Agent(model=MOCK_MODEL, system_prompt="test")
    mgr = SessionManager.in_memory()
    session = AgentSession(AgentSessionConfig(agent=agent, session_manager=mgr))

    events: list = []
    session.subscribe(lambda e: events.append(e))

    await session.prompt("hello")

    # Session manager should have entries (user prompt + agent events)
    assert len(mgr.entries) > 0

    # Should have received events
    event_types = [type(e).__name__ for e in events]
    assert "AgentStartEvent" in event_types
    assert "AgentEndEvent" in event_types


@pytest.mark.asyncio
async def test_agent_session_auto_retry():
    """AgentSession auto-retries on retryable error with backoff."""
    global _retry_call_count
    _retry_call_count = 0

    register_provider("mock-api", mock_retry_stream)

    agent = Agent(model=MOCK_MODEL, system_prompt="test")
    mgr = SessionManager.in_memory()
    session = AgentSession(AgentSessionConfig(
        agent=agent,
        session_manager=mgr,
        retry_settings=RetrySettings(base_delay=0.01, max_delay=0.1),
    ))

    events: list = []
    session.subscribe(lambda e: events.append(e))

    await session.prompt("hello")

    # Wait for auto-retry to complete
    await asyncio.sleep(0.2)

    # Should have retry events
    retry_starts = [e for e in events if isinstance(e, AutoRetryStartEvent)]
    assert len(retry_starts) >= 1
    assert retry_starts[0].attempt == 1


@pytest.mark.asyncio
async def test_agent_session_stats():
    """AgentSession.get_stats returns correct statistics."""
    register_provider("mock-api", mock_text_stream)

    agent = Agent(model=MOCK_MODEL, system_prompt="test")
    mgr = SessionManager.in_memory()
    session = AgentSession(AgentSessionConfig(agent=agent, session_manager=mgr))

    await session.prompt("hello")

    stats = session.get_stats()
    assert isinstance(stats, SessionStats)
    assert stats.total_messages > 0


@pytest.mark.asyncio
async def test_agent_session_set_model():
    """set_model persists model change to session."""
    agent = Agent(model=MOCK_MODEL, system_prompt="test")
    mgr = SessionManager.in_memory()
    session = AgentSession(AgentSessionConfig(agent=agent, session_manager=mgr))

    new_model = Model(id="new-model", name="New", api="new-api", provider="new", context_window=200000)
    session.set_model(new_model, "high")

    # Model change should be in entries
    model_changes = [e for e in mgr.entries if isinstance(e, ModelChangeEntry)]
    assert len(model_changes) == 1
    assert model_changes[0].model_id == "new-model"

    # Thinking level change too
    thinking_changes = [e for e in mgr.entries if isinstance(e, ThinkingLevelChangeEntry)]
    assert len(thinking_changes) == 1
    assert thinking_changes[0].thinking_level == "high"


@pytest.mark.asyncio
async def test_agent_session_abort():
    """Abort stops the agent."""
    register_provider("mock-api", mock_text_stream)

    agent = Agent(model=MOCK_MODEL, system_prompt="test")
    mgr = SessionManager.in_memory()
    session = AgentSession(AgentSessionConfig(agent=agent, session_manager=mgr))

    # Abort before running should be safe
    session.abort()
