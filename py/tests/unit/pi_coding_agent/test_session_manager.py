"""Tests for pi_coding_agent.core.session_manager."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pi_ai.types import AssistantMessage, UserMessage
from pi_coding_agent.core.messages import BashExecutionMessage
from pi_coding_agent.core.session_manager import (
    BranchSummaryEntry,
    CompactionEntry,
    CustomEntry,
    CustomMessageEntry,
    LabelEntry,
    ModelChangeEntry,
    NewSessionOptions,
    SessionHeader,
    SessionInfoEntry,
    SessionManager,
    SessionMessageEntry,
    ThinkingLevelChangeEntry,
    _deserialize_entry,
    _serialize_entry,
    build_session_context,
    find_most_recent_session,
    get_latest_compaction_entry,
    load_entries_from_file,
    parse_session_entries,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_in_memory_sm() -> SessionManager:
    return SessionManager.in_memory("/tmp")


def make_temp_sm(tmp_path: Path) -> SessionManager:
    return SessionManager.create(str(tmp_path), str(tmp_path / "sessions"))


# ---------------------------------------------------------------------------
# Test new session
# ---------------------------------------------------------------------------


class TestNewSession:
    def test_new_session_creates_fresh_id(self) -> None:
        sm = make_in_memory_sm()
        original_id = sm.get_session_id()
        sm.new_session()
        assert sm.get_session_id() != original_id

    def test_new_session_clears_entries(self) -> None:
        sm = make_in_memory_sm()
        sm.append_message(UserMessage(content="hi"))
        sm.new_session()
        assert sm.get_entries() == []

    def test_new_session_with_parent(self) -> None:
        sm = make_in_memory_sm()
        sm.new_session(NewSessionOptions(parent_session="/old/session.jsonl"))
        header = sm.get_header()
        assert header is not None
        assert header.parent_session == "/old/session.jsonl"


# ---------------------------------------------------------------------------
# Test append methods
# ---------------------------------------------------------------------------


class TestAppendMethods:
    def test_append_message_returns_id(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_message(UserMessage(content="hello"))
        assert isinstance(entry_id, str)
        assert len(entry_id) == 8  # short UUID

    def test_append_message_becomes_leaf(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_message(UserMessage(content="a"))
        assert sm.get_leaf_id() == entry_id

    def test_append_thinking_level_change(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_thinking_level_change("medium")
        entry = sm.get_entry(entry_id)
        assert isinstance(entry, ThinkingLevelChangeEntry)
        assert entry.thinking_level == "medium"

    def test_append_model_change(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_model_change("anthropic", "claude-3-5-sonnet")
        entry = sm.get_entry(entry_id)
        assert isinstance(entry, ModelChangeEntry)
        assert entry.provider == "anthropic"
        assert entry.model_id == "claude-3-5-sonnet"

    def test_append_compaction(self) -> None:
        sm = make_in_memory_sm()
        first_id = sm.append_message(UserMessage(content="hi"))
        comp_id = sm.append_compaction("summary text", first_id, 1000)
        entry = sm.get_entry(comp_id)
        assert isinstance(entry, CompactionEntry)
        assert entry.summary == "summary text"
        assert entry.first_kept_entry_id == first_id
        assert entry.tokens_before == 1000

    def test_append_session_info(self) -> None:
        sm = make_in_memory_sm()
        sm.append_session_info("  My Session  ")
        assert sm.get_session_name() == "My Session"

    def test_append_custom_entry(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_custom_entry("my-type", {"key": "value"})
        entry = sm.get_entry(entry_id)
        assert entry is not None
        assert getattr(entry, "custom_type", None) == "my-type"

    def test_append_custom_message_entry(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_custom_message_entry("ext", "content", True, None)
        entry = sm.get_entry(entry_id)
        assert entry is not None
        assert getattr(entry, "content", None) == "content"

    def test_append_label_change_sets_label(self) -> None:
        sm = make_in_memory_sm()
        msg_id = sm.append_message(UserMessage(content="a"))
        sm.append_label_change(msg_id, "important")
        assert sm.get_label(msg_id) == "important"

    def test_append_label_change_unknown_entry_raises(self) -> None:
        sm = make_in_memory_sm()
        with pytest.raises(ValueError):
            sm.append_label_change("nonexistent", "label")

    def test_clear_label(self) -> None:
        sm = make_in_memory_sm()
        msg_id = sm.append_message(UserMessage(content="a"))
        sm.append_label_change(msg_id, "test")
        sm.append_label_change(msg_id, None)
        assert sm.get_label(msg_id) is None


# ---------------------------------------------------------------------------
# Test tree traversal
# ---------------------------------------------------------------------------


class TestTreeTraversal:
    def test_get_branch_returns_path(self) -> None:
        sm = make_in_memory_sm()
        id1 = sm.append_message(UserMessage(content="a"))
        id2 = sm.append_message(UserMessage(content="b"))
        id3 = sm.append_message(UserMessage(content="c"))
        branch = sm.get_branch()
        ids = [e.id for e in branch]
        assert ids == [id1, id2, id3]

    def test_get_branch_from_id(self) -> None:
        sm = make_in_memory_sm()
        id1 = sm.append_message(UserMessage(content="a"))
        id2 = sm.append_message(UserMessage(content="b"))
        sm.append_message(UserMessage(content="c"))
        branch = sm.get_branch(id2)
        ids = [e.id for e in branch]
        assert ids == [id1, id2]

    def test_get_children(self) -> None:
        sm = make_in_memory_sm()
        id1 = sm.append_message(UserMessage(content="a"))
        sm.branch(id1)
        sm.append_message(UserMessage(content="b1"))
        sm.branch(id1)
        sm.append_message(UserMessage(content="b2"))
        children = sm.get_children(id1)
        assert len(children) == 2

    def test_get_entries_excludes_header(self) -> None:
        sm = make_in_memory_sm()
        sm.append_message(UserMessage(content="a"))
        entries = sm.get_entries()
        assert all(not isinstance(e, SessionHeader) for e in entries)

    def test_get_tree_returns_roots(self) -> None:
        sm = make_in_memory_sm()
        sm.append_message(UserMessage(content="root"))
        tree = sm.get_tree()
        assert len(tree) == 1


# ---------------------------------------------------------------------------
# Test branching
# ---------------------------------------------------------------------------


class TestBranching:
    def test_branch_sets_leaf(self) -> None:
        sm = make_in_memory_sm()
        id1 = sm.append_message(UserMessage(content="a"))
        sm.append_message(UserMessage(content="b"))
        sm.branch(id1)
        assert sm.get_leaf_id() == id1

    def test_branch_unknown_raises(self) -> None:
        sm = make_in_memory_sm()
        with pytest.raises(ValueError):
            sm.branch("nonexistent")

    def test_reset_leaf(self) -> None:
        sm = make_in_memory_sm()
        sm.append_message(UserMessage(content="a"))
        sm.reset_leaf()
        assert sm.get_leaf_id() is None

    def test_branch_with_summary(self) -> None:
        sm = make_in_memory_sm()
        id1 = sm.append_message(UserMessage(content="a"))
        sm.append_message(UserMessage(content="b"))
        summary_id = sm.branch_with_summary(id1, "branch summary")
        entry = sm.get_entry(summary_id)
        assert isinstance(entry, BranchSummaryEntry)
        assert entry.summary == "branch summary"


# ---------------------------------------------------------------------------
# Test build_session_context
# ---------------------------------------------------------------------------


class TestBuildSessionContext:
    def test_empty_entries_returns_empty_context(self) -> None:
        ctx = build_session_context([])
        assert ctx.messages == []
        assert ctx.thinking_level == "off"
        assert ctx.model is None

    def test_messages_are_in_path(self) -> None:
        sm = make_in_memory_sm()
        sm.append_message(UserMessage(content="hello"))
        sm.append_thinking_level_change("medium")
        sm.append_message(AssistantMessage())
        ctx = sm.build_session_context()
        assert ctx.thinking_level == "medium"
        # user + assistant messages
        assert len(ctx.messages) == 2

    def test_compaction_inserts_summary(self) -> None:
        sm = make_in_memory_sm()
        sm.append_message(UserMessage(content="a"))
        id2 = sm.append_message(UserMessage(content="b"))
        sm.append_compaction("compact summary", id2, 500)
        sm.append_message(UserMessage(content="after"))

        ctx = sm.build_session_context()
        # Should have: summary, b, after
        assert any(hasattr(m, "role") and m.role == "compaction_summary" for m in ctx.messages)

    def test_model_tracked_from_model_change_entry(self) -> None:
        sm = make_in_memory_sm()
        sm.append_model_change("openai", "gpt-4o")
        ctx = sm.build_session_context()
        assert ctx.model == {"provider": "openai", "model_id": "gpt-4o"}


# ---------------------------------------------------------------------------
# Test get_latest_compaction_entry
# ---------------------------------------------------------------------------


class TestGetLatestCompactionEntry:
    def test_returns_none_when_no_compaction(self) -> None:
        sm = make_in_memory_sm()
        sm.append_message(UserMessage(content="a"))
        result = get_latest_compaction_entry(sm.get_entries())
        assert result is None

    def test_returns_last_compaction(self) -> None:
        sm = make_in_memory_sm()
        id1 = sm.append_message(UserMessage(content="a"))
        sm.append_compaction("first", id1, 100)
        id2 = sm.append_message(UserMessage(content="b"))
        sm.append_compaction("second", id2, 200)
        result = get_latest_compaction_entry(sm.get_entries())
        assert result is not None
        assert result.summary == "second"


# ---------------------------------------------------------------------------
# Test file I/O
# ---------------------------------------------------------------------------


class TestFileIO:
    def test_persist_and_reload(self, tmp_path: Path) -> None:
        sm = make_temp_sm(tmp_path)
        msg = UserMessage(content="hello world")
        sm.append_message(msg)
        # Trigger flush by adding assistant message
        sm.append_message(AssistantMessage())

        session_file = sm.get_session_file()
        assert session_file is not None
        assert Path(session_file).exists()

        # Reload
        sm2 = SessionManager.open(session_file)
        entries = sm2.get_entries()
        # Should have user + assistant entries
        assert any(isinstance(e, SessionMessageEntry) and getattr(e.message, "role", "") == "user" for e in entries)

    def test_load_entries_from_nonexistent_file(self) -> None:
        result = load_entries_from_file("/nonexistent/path/session.jsonl")
        assert result == []

    def test_parse_session_entries(self) -> None:
        header = {"type": "session", "id": "abc123", "timestamp": "2024-01-01T00:00:00Z", "cwd": "/tmp"}
        level_change = {
            "type": "thinking_level_change",
            "id": "def456",
            "parentId": None,
            "timestamp": "2024-01-01T00:00:00Z",
            "thinkingLevel": "medium",
        }
        content = json.dumps(header) + "\n" + json.dumps(level_change)
        entries = parse_session_entries(content)
        assert len(entries) == 2

    def test_parse_session_entries_skips_malformed(self) -> None:
        content = '{"type": "session", "id": "x", "timestamp": "t", "cwd": "/"}\nnot-json\n'
        entries = parse_session_entries(content)
        assert len(entries) == 1

    def test_in_memory_does_not_create_file(self) -> None:
        sm = SessionManager.in_memory("/tmp")
        sm.append_message(UserMessage(content="test"))
        sm.append_message(AssistantMessage())
        assert sm.get_session_file() is None

    def test_create_branched_session(self, tmp_path: Path) -> None:
        sm = make_temp_sm(tmp_path)
        sm.append_message(UserMessage(content="a"))
        sm.append_message(AssistantMessage())
        id2 = sm.append_message(UserMessage(content="b"))
        sm.append_message(AssistantMessage())

        new_file = sm.create_branched_session(id2)
        assert new_file is not None
        assert Path(new_file).exists()

    def test_find_most_recent_session(self, tmp_path: Path) -> None:
        sm1 = SessionManager.create(str(tmp_path), str(tmp_path / "sessions"))
        sm1.append_message(UserMessage(content="a"))
        sm1.append_message(AssistantMessage())
        sm1.get_session_file()

        sm2 = SessionManager.create(str(tmp_path), str(tmp_path / "sessions"))
        sm2.append_message(UserMessage(content="b"))
        sm2.append_message(AssistantMessage())

        most_recent = find_most_recent_session(str(tmp_path / "sessions"))
        # Most recent should be one of the two files
        assert most_recent is not None


# ---------------------------------------------------------------------------
# Test factory methods
# ---------------------------------------------------------------------------


class TestFactoryMethods:
    def test_in_memory(self) -> None:
        sm = SessionManager.in_memory()
        assert not sm.is_persisted()

    def test_continue_recent_creates_new_when_no_sessions(self, tmp_path: Path) -> None:
        session_dir = str(tmp_path / "sessions")
        sm = SessionManager.continue_recent("/tmp", session_dir)
        assert sm.get_session_id() != ""

    def test_fork_from(self, tmp_path: Path) -> None:
        # Create source session
        source_sm = SessionManager.create(str(tmp_path), str(tmp_path / "sessions"))
        source_sm.append_message(UserMessage(content="source message"))
        source_sm.append_message(AssistantMessage())
        source_file = source_sm.get_session_file()
        assert source_file is not None

        target_dir = str(tmp_path / "target")
        os.makedirs(target_dir, exist_ok=True)

        forked = SessionManager.fork_from(source_file, target_dir, target_dir)
        assert forked.get_session_id() != source_sm.get_session_id()
        entries = forked.get_entries()
        assert len(entries) > 0


# ---------------------------------------------------------------------------
# Test bash execution message serialization
# ---------------------------------------------------------------------------


class TestBashMessageSerialization:
    def test_bash_execution_stored_and_retrieved(self, tmp_path: Path) -> None:
        sm = make_temp_sm(tmp_path)
        bash_msg = BashExecutionMessage(command="echo hi", stdout="hi\n", exit_code=0)
        sm.append_message(bash_msg)
        # Add assistant to trigger flush
        sm.append_message(AssistantMessage())
        session_file = sm.get_session_file()
        assert session_file is not None

        sm2 = SessionManager.open(session_file)
        entries = sm2.get_entries()
        bash_entries = [
            e for e in entries if isinstance(e, SessionMessageEntry) and isinstance(e.message, BashExecutionMessage)
        ]
        assert len(bash_entries) == 1
        assert bash_entries[0].message.command == "echo hi"


# ---------------------------------------------------------------------------
# Test serialize/deserialize entry round-trips
# ---------------------------------------------------------------------------


class TestSerializeEntry:
    """Test _serialize_entry for all entry types."""

    def test_serialize_thinking_level_change(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_thinking_level_change("high")
        entry = sm.get_entry(entry_id)
        assert entry is not None
        d = _serialize_entry(entry)
        assert d["type"] == "thinking_level_change"
        assert d["thinkingLevel"] == "high"

    def test_serialize_model_change(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_model_change("openai", "gpt-4o")
        entry = sm.get_entry(entry_id)
        assert entry is not None
        d = _serialize_entry(entry)
        assert d["type"] == "model_change"
        assert d["provider"] == "openai"
        assert d["modelId"] == "gpt-4o"

    def test_serialize_compaction(self) -> None:
        sm = make_in_memory_sm()
        id1 = sm.append_message(UserMessage(content="a"))
        comp_id = sm.append_compaction("summary text", id1, 500)
        entry = sm.get_entry(comp_id)
        assert entry is not None
        d = _serialize_entry(entry)
        assert d["type"] == "compaction"
        assert d["summary"] == "summary text"
        assert d["tokensBefore"] == 500

    def test_serialize_branch_summary(self) -> None:
        sm = make_in_memory_sm()
        id1 = sm.append_message(UserMessage(content="a"))
        sm.append_message(UserMessage(content="b"))
        summary_id = sm.branch_with_summary(id1, "my summary")
        entry = sm.get_entry(summary_id)
        assert entry is not None
        d = _serialize_entry(entry)
        assert d["type"] == "branch_summary"
        assert d["summary"] == "my summary"

    def test_serialize_custom_entry(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_custom_entry("my-type", {"key": "val"})
        entry = sm.get_entry(entry_id)
        assert entry is not None
        d = _serialize_entry(entry)
        assert d["type"] == "custom"
        assert d["customType"] == "my-type"

    def test_serialize_custom_message_entry(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_custom_message_entry("ext", "hello", True, None)
        entry = sm.get_entry(entry_id)
        assert entry is not None
        d = _serialize_entry(entry)
        assert d["type"] == "custom_message"
        assert d["content"] == "hello"

    def test_serialize_label_entry(self) -> None:
        sm = make_in_memory_sm()
        msg_id = sm.append_message(UserMessage(content="a"))
        sm.append_label_change(msg_id, "important")
        # Label entry is appended; find it
        label_entries = [e for e in sm.get_entries() if isinstance(e, LabelEntry)]
        assert len(label_entries) == 1
        d = _serialize_entry(label_entries[0])
        assert d["type"] == "label"
        assert d["label"] == "important"

    def test_serialize_session_info_entry(self) -> None:
        sm = make_in_memory_sm()
        sm.append_session_info("My Session")
        info_entries = [e for e in sm.get_entries() if isinstance(e, SessionInfoEntry)]
        assert len(info_entries) == 1
        d = _serialize_entry(info_entries[0])
        assert d["type"] == "session_info"
        assert d["name"] == "My Session"

    def test_serialize_bash_execution_message(self) -> None:
        sm = make_in_memory_sm()
        bash_msg = BashExecutionMessage(command="ls", stdout="file.txt\n", exit_code=0)
        sm.append_message(bash_msg)
        msg_entries = [e for e in sm.get_entries() if isinstance(e, SessionMessageEntry)]
        assert len(msg_entries) == 1
        d = _serialize_entry(msg_entries[0])
        assert d["type"] == "message"
        assert d["message"]["role"] == "bashExecution"
        assert d["message"]["output"] == "file.txt\n"

    def test_serialize_bash_message_with_optional_fields(self) -> None:
        sm = make_in_memory_sm()
        bash_msg = BashExecutionMessage(
            command="ls",
            stdout="file.txt\n",
            exit_code=0,
            full_output_path="/tmp/out.log",
            exclude_from_context=True,
        )
        sm.append_message(bash_msg)
        msg_entries = [e for e in sm.get_entries() if isinstance(e, SessionMessageEntry)]
        d = _serialize_entry(msg_entries[0])
        assert d["message"]["fullOutputPath"] == "/tmp/out.log"
        assert d["message"]["excludeFromContext"] is True

    def test_serialize_compaction_with_details(self) -> None:
        sm = make_in_memory_sm()
        id1 = sm.append_message(UserMessage(content="a"))
        comp_id = sm.append_compaction("summary", id1, 200)
        # Manually set details on the entry
        entry = sm.get_entry(comp_id)
        assert isinstance(entry, CompactionEntry)
        entry.details = {"extra": "data"}
        entry.from_hook = True
        d = _serialize_entry(entry)
        assert d["details"] == {"extra": "data"}
        assert d["fromHook"] is True

    def test_serialize_branch_summary_with_details(self) -> None:
        sm = make_in_memory_sm()
        id1 = sm.append_message(UserMessage(content="a"))
        sm.append_message(UserMessage(content="b"))
        summary_id = sm.branch_with_summary(id1, "summary")
        entry = sm.get_entry(summary_id)
        assert isinstance(entry, BranchSummaryEntry)
        entry.details = {"info": "here"}
        entry.from_hook = True
        d = _serialize_entry(entry)
        assert d["details"] == {"info": "here"}
        assert d["fromHook"] is True

    def test_serialize_custom_message_entry_with_details(self) -> None:
        sm = make_in_memory_sm()
        entry_id = sm.append_custom_message_entry("ext", "content", True, {"detail_key": "val"})
        entry = sm.get_entry(entry_id)
        assert entry is not None
        d = _serialize_entry(entry)
        assert d["details"] == {"detail_key": "val"}

    def test_serialize_custom_message_entry_with_list_content(self) -> None:
        from pi_ai.types import TextContent

        sm = make_in_memory_sm()
        list_content = [TextContent(text="hello"), TextContent(text="world")]
        entry_id = sm.append_custom_message_entry("ext", list_content, True, None)  # type: ignore[arg-type]
        entry = sm.get_entry(entry_id)
        assert entry is not None
        d = _serialize_entry(entry)
        assert d["type"] == "custom_message"
        assert isinstance(d["content"], list)


class TestDeserializeCustomRole:
    """Test deserialization of custom-role messages."""

    _TS = "2024-01-01T00:00:00Z"

    def test_deserialize_custom_role_with_string_content(self) -> None:
        data = {
            "type": "message",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "message": {
                "role": "custom",
                "customType": "ext",
                "content": "plain text",
                "display": True,
                "timestamp": 0.0,
            },
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, SessionMessageEntry)
        from pi_coding_agent.core.messages import CustomMessage

        assert isinstance(entry.message, CustomMessage)
        assert entry.message.content == "plain text"

    def test_deserialize_custom_message_entry_with_list_content(self) -> None:
        data = {
            "type": "custom_message",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "customType": "ext",
            "content": [{"type": "text", "text": "hello"}],
            "display": True,
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, CustomMessageEntry)
        # Content is a list (deserialized from blocks)
        assert isinstance(entry.content, list)


class TestDeserializeEntry:
    """Test _deserialize_entry for all entry types."""

    _TS = "2024-01-01T00:00:00Z"

    def test_deserialize_thinking_level_change(self) -> None:
        data = {
            "type": "thinking_level_change",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "thinkingLevel": "medium",
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, ThinkingLevelChangeEntry)
        assert entry.thinking_level == "medium"

    def test_deserialize_model_change(self) -> None:
        data = {
            "type": "model_change",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "provider": "google",
            "modelId": "gemini-pro",
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, ModelChangeEntry)
        assert entry.provider == "google"
        assert entry.model_id == "gemini-pro"

    def test_deserialize_compaction(self) -> None:
        data = {
            "type": "compaction",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "summary": "compact",
            "firstKeptEntryId": "first",
            "tokensBefore": 999,
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, CompactionEntry)
        assert entry.summary == "compact"
        assert entry.tokens_before == 999

    def test_deserialize_branch_summary(self) -> None:
        data = {
            "type": "branch_summary",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "fromId": "parent",
            "summary": "branch sum",
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, BranchSummaryEntry)
        assert entry.summary == "branch sum"

    def test_deserialize_custom_entry(self) -> None:
        data = {
            "type": "custom",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "customType": "hook",
            "data": {"foo": "bar"},
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, CustomEntry)
        assert entry.custom_type == "hook"

    def test_deserialize_custom_message_entry(self) -> None:
        data = {
            "type": "custom_message",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "customType": "ext",
            "content": "hello",
            "display": True,
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, CustomMessageEntry)
        assert entry.content == "hello"

    def test_deserialize_label_entry(self) -> None:
        data = {
            "type": "label",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "targetId": "tgt",
            "label": "flagged",
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, LabelEntry)
        assert entry.label == "flagged"

    def test_deserialize_session_info_entry(self) -> None:
        data = {
            "type": "session_info",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "name": "cool session",
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, SessionInfoEntry)
        assert entry.name == "cool session"

    def test_deserialize_bash_execution_message(self) -> None:
        data = {
            "type": "message",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
            "message": {
                "role": "bashExecution",
                "command": "ls",
                "output": "file.txt\n",
                "exitCode": 0,
                "cancelled": False,
                "truncated": False,
            },
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, SessionMessageEntry)
        assert isinstance(entry.message, BashExecutionMessage)
        assert entry.message.stdout == "file.txt\n"

    def test_deserialize_unknown_type_returns_none(self) -> None:
        data = {
            "type": "totally_unknown_type",
            "id": "abc",
            "parentId": None,
            "timestamp": self._TS,
        }
        result = _deserialize_entry(data)
        assert result is None

    def test_deserialize_session_header(self) -> None:
        data = {
            "type": "session",
            "id": "s1",
            "timestamp": self._TS,
            "cwd": "/tmp",
        }
        entry = _deserialize_entry(data)
        assert isinstance(entry, SessionHeader)
        assert entry.id == "s1"


# ---------------------------------------------------------------------------
# Test additional session manager methods
# ---------------------------------------------------------------------------


class TestSessionManagerAdditional:
    def test_get_label_returns_none_for_unlabeled(self) -> None:
        sm = make_in_memory_sm()
        msg_id = sm.append_message(UserMessage(content="a"))
        assert sm.get_label(msg_id) is None

    def test_get_session_name_returns_none_when_not_set(self) -> None:
        sm = make_in_memory_sm()
        assert sm.get_session_name() is None

    def test_get_session_name_returns_set_name(self) -> None:
        sm = make_in_memory_sm()
        sm.append_session_info("My Session")
        assert sm.get_session_name() == "My Session"

    def test_is_persisted_true_for_file_sm(self, tmp_path: Path) -> None:
        sm = make_temp_sm(tmp_path)
        sm.append_message(UserMessage(content="a"))
        sm.append_message(AssistantMessage())
        assert sm.is_persisted()

    def test_in_memory_is_not_persisted(self) -> None:
        sm = make_in_memory_sm()
        assert not sm.is_persisted()

    def test_get_children_empty_for_leaf(self) -> None:
        sm = make_in_memory_sm()
        msg_id = sm.append_message(UserMessage(content="only"))
        children = sm.get_children(msg_id)
        assert children == []

    def test_get_entry_returns_none_for_unknown(self) -> None:
        sm = make_in_memory_sm()
        result = sm.get_entry("nonexistent-id")
        assert result is None
