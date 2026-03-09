"""Tests for compaction utilities."""

from __future__ import annotations

from typing import ClassVar

from pi_coding_agent.core.compaction.compaction import (
    CompactionSettings,
    estimate_tokens,
    find_cut_point,
    should_compact,
)
from pi_coding_agent.core.compaction.utils import (
    compute_file_lists,
    create_file_ops,
    extract_file_ops_from_message,
    format_file_operations,
    serialize_conversation,
)


class TestEstimateTokens:
    def test_user_message_string(self) -> None:
        class Msg:
            role = "user"
            content = "Hello, world!"  # 13 chars -> ceil(13/4) = 4

        tokens = estimate_tokens(Msg())  # type: ignore[arg-type]
        assert tokens == 4

    def test_user_message_text_blocks(self) -> None:
        class Block:
            type = "text"
            text = "Hello"

        class Msg:
            role = "user"
            content: ClassVar[list[object]] = [Block()]

        tokens = estimate_tokens(Msg())  # type: ignore[arg-type]
        assert tokens == 2  # ceil(5/4) = 2

    def test_assistant_message(self) -> None:
        class TextBlock:
            type = "text"
            text = "Hi there"

        class Msg:
            role = "assistant"
            content: ClassVar[list[object]] = [TextBlock()]

        tokens = estimate_tokens(Msg())  # type: ignore[arg-type]
        assert tokens == 2  # ceil(8/4) = 2

    def test_unknown_role_returns_zero(self) -> None:
        class Msg:
            role = "unknown"

        assert estimate_tokens(Msg()) == 0  # type: ignore[arg-type]

    def test_empty_assistant_message(self) -> None:
        class Msg:
            role = "assistant"
            content: ClassVar[list[object]] = []

        assert estimate_tokens(Msg()) == 0  # type: ignore[arg-type]


class TestShouldCompact:
    def test_triggers_when_near_limit(self) -> None:
        settings = CompactionSettings(enabled=True, reserve_tokens=16384, keep_recent_tokens=20000)
        # context_window=100000, tokens=90000 -> 90000 > 83616 -> True
        assert should_compact(90000, 100000, settings) is True

    def test_no_trigger_with_room(self) -> None:
        settings = CompactionSettings(enabled=True, reserve_tokens=16384, keep_recent_tokens=20000)
        assert should_compact(50000, 100000, settings) is False

    def test_disabled_never_triggers(self) -> None:
        settings = CompactionSettings(enabled=False, reserve_tokens=16384, keep_recent_tokens=20000)
        assert should_compact(99999, 100000, settings) is False


class TestFindCutPoint:
    def _make_user_entry(self, entry_id: str, text: str = "hello") -> dict[str, object]:
        class Msg:
            role = "user"
            content = text

        return {"type": "message", "id": entry_id, "message": Msg()}

    def _make_assistant_entry(self, entry_id: str, text: str = "hi") -> dict[str, object]:
        class TextBlock:
            type = "text"

            def __init__(self, t: str) -> None:
                self.text = t

        class Msg:
            role = "assistant"

            def __init__(self, t: str) -> None:
                self.content = [TextBlock(t)]

        return {"type": "message", "id": entry_id, "message": Msg(text)}

    def test_empty_entries_returns_start(self) -> None:
        result = find_cut_point([], 0, 0, 1000)
        assert result.first_kept_entry_index == 0
        assert result.is_split_turn is False

    def test_keeps_recent_messages(self) -> None:
        # Create entries where we want to keep recent ones
        entries = [
            self._make_user_entry("u1", "x" * 100),  # 25 tokens
            self._make_assistant_entry("a1", "y" * 100),  # 25 tokens
            self._make_user_entry("u2", "x" * 100),  # 25 tokens
            self._make_assistant_entry("a2", "y" * 100),  # 25 tokens
        ]

        # keep_recent_tokens=30 should keep u2 and a2
        result = find_cut_point(entries, 0, 4, 30)
        assert result.first_kept_entry_index >= 0


class TestComputeFileLists:
    def test_empty_file_ops(self) -> None:
        ops = create_file_ops()
        read_files, modified_files = compute_file_lists(ops)
        assert read_files == []
        assert modified_files == []

    def test_read_only_files(self) -> None:
        ops = create_file_ops()
        ops.read.add("/a.py")
        ops.read.add("/b.py")
        read_files, modified_files = compute_file_lists(ops)
        assert read_files == ["/a.py", "/b.py"]
        assert modified_files == []

    def test_written_files(self) -> None:
        ops = create_file_ops()
        ops.written.add("/a.py")
        read_files, modified_files = compute_file_lists(ops)
        assert read_files == []
        assert "/a.py" in modified_files

    def test_edited_files(self) -> None:
        ops = create_file_ops()
        ops.edited.add("/a.py")
        read_files, modified_files = compute_file_lists(ops)
        assert read_files == []
        assert "/a.py" in modified_files

    def test_read_and_modified_files(self) -> None:
        ops = create_file_ops()
        ops.read.add("/a.py")
        ops.read.add("/b.py")
        ops.edited.add("/b.py")  # b.py was read and then edited
        read_files, modified_files = compute_file_lists(ops)
        assert read_files == ["/a.py"]  # only read, not modified
        assert "/b.py" in modified_files

    def test_deduplication(self) -> None:
        ops = create_file_ops()
        ops.written.add("/a.py")
        ops.edited.add("/a.py")
        _, modified_files = compute_file_lists(ops)
        assert modified_files.count("/a.py") == 1

    def test_sorted_output(self) -> None:
        ops = create_file_ops()
        ops.read.add("/z.py")
        ops.read.add("/a.py")
        read_files, _ = compute_file_lists(ops)
        assert read_files == ["/a.py", "/z.py"]


class TestExtractFileOpsFromMessage:
    def _make_tool_call_msg(self, tool_name: str, path: str) -> object:
        class Block:
            type = "toolCall"

            def __init__(self, name: str, path: str) -> None:
                self.name = name
                self.arguments = {"path": path}

        class Msg:
            role = "assistant"

            def __init__(self) -> None:
                self.content = [Block(tool_name, path)]

        return Msg()

    def test_read_tool_call(self) -> None:
        msg = self._make_tool_call_msg("read", "/foo.py")
        ops = create_file_ops()
        extract_file_ops_from_message(msg, ops)  # type: ignore[arg-type]
        assert "/foo.py" in ops.read

    def test_write_tool_call(self) -> None:
        msg = self._make_tool_call_msg("write", "/foo.py")
        ops = create_file_ops()
        extract_file_ops_from_message(msg, ops)  # type: ignore[arg-type]
        assert "/foo.py" in ops.written

    def test_edit_tool_call(self) -> None:
        msg = self._make_tool_call_msg("edit", "/foo.py")
        ops = create_file_ops()
        extract_file_ops_from_message(msg, ops)  # type: ignore[arg-type]
        assert "/foo.py" in ops.edited

    def test_non_assistant_message_ignored(self) -> None:
        class Msg:
            role = "user"
            content = "hello"

        ops = create_file_ops()
        extract_file_ops_from_message(Msg(), ops)  # type: ignore[arg-type]
        assert not ops.read and not ops.written and not ops.edited


class TestSerializeConversation:
    def test_user_message(self) -> None:
        class Msg:
            role = "user"
            content = "Hello"

        result = serialize_conversation([Msg()])
        assert "[User]: Hello" in result

    def test_assistant_message(self) -> None:
        class TextBlock:
            type = "text"
            text = "Hi there"

        class Msg:
            role = "assistant"
            content: ClassVar[list[object]] = [TextBlock()]

        result = serialize_conversation([Msg()])
        assert "[Assistant]: Hi there" in result

    def test_tool_result_message(self) -> None:
        class TextBlock:
            type = "text"
            text = "result data"

        class Msg:
            role = "toolResult"
            content: ClassVar[list[object]] = [TextBlock()]

        result = serialize_conversation([Msg()])
        assert "[Tool result]: result data" in result

    def test_empty_messages(self) -> None:
        result = serialize_conversation([])
        assert result == ""


class TestFormatFileOperations:
    def test_empty_returns_empty(self) -> None:
        assert format_file_operations([], []) == ""

    def test_read_files_only(self) -> None:
        result = format_file_operations(["/a.py"], [])
        assert "<read-files>" in result
        assert "/a.py" in result
        assert "<modified-files>" not in result

    def test_modified_files_only(self) -> None:
        result = format_file_operations([], ["/b.py"])
        assert "<modified-files>" in result
        assert "/b.py" in result
        assert "<read-files>" not in result

    def test_both_sections(self) -> None:
        result = format_file_operations(["/a.py"], ["/b.py"])
        assert "<read-files>" in result
        assert "<modified-files>" in result
