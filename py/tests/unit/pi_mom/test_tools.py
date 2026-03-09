"""Tests for pi_mom tools (truncate, bash, read, edit, write, attach)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pi_mom.sandbox import ExecResult
from pi_mom.tools.attach import AttachTool
from pi_mom.tools.bash import BashTool
from pi_mom.tools.edit import EditTool
from pi_mom.tools.read import ReadTool
from pi_mom.tools.truncate import (
    DEFAULT_MAX_BYTES,
    format_size,
    truncate_head,
    truncate_tail,
)
from pi_mom.tools.write import WriteTool

# ============================================================================
# Truncate tests
# ============================================================================


class TestFormatSize:
    def test_bytes(self) -> None:
        assert format_size(500) == "500B"

    def test_kilobytes(self) -> None:
        assert "KB" in format_size(2048)

    def test_megabytes(self) -> None:
        assert "MB" in format_size(2 * 1024 * 1024)


class TestTruncateHead:
    def test_no_truncation_needed(self) -> None:
        content = "line1\nline2\nline3"
        result = truncate_head(content)
        assert not result.truncated
        assert result.content == content
        assert result.truncated_by is None

    def test_line_limit(self) -> None:
        content = "\n".join(f"line{i}" for i in range(3000))
        result = truncate_head(content, max_lines=100)
        assert result.truncated
        assert result.truncated_by == "lines"
        assert result.output_lines == 100

    def test_byte_limit(self) -> None:
        # Content that exceeds byte limit but not line limit
        content = "x" * 60000
        result = truncate_head(content, max_bytes=1000)
        assert result.truncated
        assert result.truncated_by == "bytes"

    def test_first_line_exceeds_byte_limit(self) -> None:
        # Single line that exceeds the byte limit
        content = "x" * 60000 + "\nsecond line"
        result = truncate_head(content, max_bytes=1000)
        assert result.truncated
        assert result.first_line_exceeds_limit

    def test_empty_content(self) -> None:
        result = truncate_head("")
        assert not result.truncated
        assert result.content == ""

    def test_byte_limit_multi_line(self) -> None:
        """Multiple lines that cumulatively exceed byte limit should truncate by bytes."""
        # Each line is small, but many together exceed 100 bytes
        content = "\n".join(f"line{i:04d}" for i in range(50))
        result = truncate_head(content, max_bytes=100)
        assert result.truncated
        assert result.truncated_by == "bytes"


class TestTruncateTail:
    def test_no_truncation_needed(self) -> None:
        content = "line1\nline2\nline3"
        result = truncate_tail(content)
        assert not result.truncated
        assert result.content == content

    def test_byte_limit_multiple_lines(self) -> None:
        """Byte limit should truncate across multiple lines."""
        # Each line is small, but many lines exceed the byte limit
        content = "\n".join(f"line{i:04d}" for i in range(200))
        result = truncate_tail(content, max_bytes=100)
        assert result.truncated
        assert result.truncated_by == "bytes"

    def test_line_limit(self) -> None:
        content = "\n".join(f"line{i}" for i in range(3000))
        result = truncate_tail(content, max_lines=100)
        assert result.truncated
        assert result.truncated_by == "lines"
        assert result.output_lines == 100
        # Should show last 100 lines
        assert "line2999" in result.content

    def test_byte_limit_partial_line(self) -> None:
        # Single line that exceeds byte limit
        content = "x" * 60000
        result = truncate_tail(content, max_bytes=1000)
        assert result.truncated
        assert result.last_line_partial

    def test_tail_content_ordering(self) -> None:
        """Tail truncation should keep the last lines."""
        content = "\n".join([f"line{i}" for i in range(100)])
        result = truncate_tail(content, max_lines=10)
        lines = result.content.split("\n")
        assert lines[-1] == "line99"


# ============================================================================
# Mock executor
# ============================================================================


def _make_executor(
    stdout: str = "",
    stderr: str = "",
    code: int = 0,
) -> Any:
    executor = MagicMock()
    executor.exec = AsyncMock(return_value=ExecResult(stdout=stdout, stderr=stderr, code=code))
    executor.get_workspace_path = MagicMock(return_value="/workspace")
    return executor


# ============================================================================
# BashTool tests
# ============================================================================


class TestBashTool:
    @pytest.mark.asyncio
    async def test_successful_command(self) -> None:
        executor = _make_executor(stdout="hello world\n")
        tool = BashTool(executor)
        result = await tool.execute("id1", {"label": "test", "command": "echo hello world"})
        assert "hello world" in result.content[0].text  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_failed_command(self) -> None:
        executor = _make_executor(stdout="error output", stderr="error", code=1)
        tool = BashTool(executor)
        with pytest.raises(RuntimeError, match="exited with code 1"):
            await tool.execute("id1", {"label": "test", "command": "false"})

    @pytest.mark.asyncio
    async def test_no_output(self) -> None:
        executor = _make_executor()
        tool = BashTool(executor)
        result = await tool.execute("id1", {"label": "test", "command": "true"})
        assert "(no output)" in result.content[0].text  # type: ignore[union-attr]

    def test_tool_name(self) -> None:
        executor = _make_executor()
        tool = BashTool(executor)
        assert tool.name == "bash"
        assert tool.label == "bash"

    def test_parameters_schema(self) -> None:
        executor = _make_executor()
        tool = BashTool(executor)
        params = tool.parameters
        assert "command" in params["properties"]
        assert "label" in params["properties"]

    def test_description_contains_limits(self) -> None:
        executor = _make_executor()
        tool = BashTool(executor)
        assert "truncated" in tool.description.lower() or "KB" in tool.description

    @pytest.mark.asyncio
    async def test_large_output_truncated(self) -> None:
        """Output exceeding line limit should be truncated."""
        # Generate output with more than DEFAULT_MAX_LINES lines
        lines = "\n".join(f"line{i}" for i in range(3000))
        executor = _make_executor(stdout=lines)
        tool = BashTool(executor)
        result = await tool.execute("id1", {"label": "test", "command": "yes | head -3000"})
        text = result.content[0].text  # type: ignore[union-attr]
        assert "Showing lines" in text or "Full output" in text

    @pytest.mark.asyncio
    async def test_large_output_has_details(self) -> None:
        """Truncated output should include details with truncation info."""
        lines = "\n".join(f"line{i}" for i in range(3000))
        executor = _make_executor(stdout=lines)
        tool = BashTool(executor)
        result = await tool.execute("id1", {"label": "test", "command": "yes"})
        # details should be set when truncated
        assert result.details is not None

    @pytest.mark.asyncio
    async def test_stdout_and_stderr_combined(self) -> None:
        """Both stdout and stderr should appear in output."""
        executor = _make_executor(stdout="out line", stderr="err line")
        tool = BashTool(executor)
        result = await tool.execute("id1", {"label": "test", "command": "cmd"})
        text = result.content[0].text  # type: ignore[union-attr]
        assert "out line" in text
        assert "err line" in text


# ============================================================================
# ReadTool tests
# ============================================================================


class TestReadTool:
    @pytest.mark.asyncio
    async def test_read_text_file(self) -> None:
        executor = MagicMock()
        # wc -l returns "5", then cat returns content
        executor.exec = AsyncMock(
            side_effect=[
                ExecResult(stdout="5", stderr="", code=0),
                ExecResult(stdout="line1\nline2\nline3", stderr="", code=0),
            ]
        )
        tool = ReadTool(executor)
        result = await tool.execute("id1", {"label": "read", "path": "/tmp/test.txt"})
        assert "line1" in result.content[0].text  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_read_image_file(self) -> None:
        executor = _make_executor(stdout="aGVsbG8=")  # base64 "hello"
        tool = ReadTool(executor)
        result = await tool.execute("id1", {"label": "read", "path": "/tmp/test.png"})
        # Should have text part + image part
        assert len(result.content) == 2
        assert result.content[1].type == "image"

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        executor = _make_executor(stderr="No such file", code=1)
        # Need to mock count result first
        executor.exec = AsyncMock(return_value=ExecResult(stdout="", stderr="No such file", code=1))
        tool = ReadTool(executor)
        with pytest.raises(RuntimeError):
            await tool.execute("id1", {"label": "read", "path": "/nonexistent.txt"})

    def test_tool_name(self) -> None:
        executor = _make_executor()
        tool = ReadTool(executor)
        assert tool.name == "read"

    @pytest.mark.asyncio
    async def test_read_with_offset(self) -> None:
        executor = MagicMock()
        executor.exec = AsyncMock(
            side_effect=[
                ExecResult(stdout="10", stderr="", code=0),  # wc -l
                ExecResult(stdout="line5\nline6", stderr="", code=0),  # tail
            ]
        )
        tool = ReadTool(executor)
        result = await tool.execute("id1", {"label": "read", "path": "/tmp/test.txt", "offset": 5})
        assert "line5" in result.content[0].text  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_read_with_limit(self) -> None:
        executor = MagicMock()
        content = "\n".join(f"line{i}" for i in range(20))
        executor.exec = AsyncMock(
            side_effect=[
                ExecResult(stdout="20", stderr="", code=0),
                ExecResult(stdout=content, stderr="", code=0),
            ]
        )
        tool = ReadTool(executor)
        result = await tool.execute("id1", {"label": "read", "path": "/tmp/test.txt", "limit": 5})
        # Content should be truncated; 5 more lines message may appear
        text = result.content[0].text  # type: ignore[union-attr]
        assert text is not None

    @pytest.mark.asyncio
    async def test_read_offset_beyond_file(self) -> None:
        executor = MagicMock()
        executor.exec = AsyncMock(return_value=ExecResult(stdout="5", stderr="", code=0))
        tool = ReadTool(executor)
        with pytest.raises(RuntimeError, match="Offset"):
            await tool.execute("id1", {"label": "read", "path": "/tmp/test.txt", "offset": 100})

    @pytest.mark.asyncio
    async def test_read_image_fails(self) -> None:
        executor = _make_executor(stdout="", stderr="no such file", code=1)
        tool = ReadTool(executor)
        with pytest.raises(RuntimeError):
            await tool.execute("id1", {"label": "read", "path": "/tmp/missing.png"})

    @pytest.mark.asyncio
    async def test_read_with_limit_shows_remaining(self) -> None:
        """When limit is set and more lines remain, show remaining count."""
        executor = MagicMock()
        content = "\n".join(f"line{i}" for i in range(30))
        executor.exec = AsyncMock(
            side_effect=[
                ExecResult(stdout="30", stderr="", code=0),  # wc -l
                ExecResult(stdout=content, stderr="", code=0),  # cat
            ]
        )
        tool = ReadTool(executor)
        result = await tool.execute("id1", {"label": "read", "path": "/tmp/test.txt", "limit": 5})
        text = result.content[0].text  # type: ignore[union-attr]
        # Should mention there are more lines
        assert "more lines" in text or "offset" in text

    def test_tool_description(self) -> None:
        executor = _make_executor()
        tool = ReadTool(executor)
        assert "Read" in tool.description
        assert tool.label == "read"

    def test_tool_parameters(self) -> None:
        executor = _make_executor()
        tool = ReadTool(executor)
        params = tool.parameters
        assert "path" in params["properties"]
        assert "offset" in params["properties"]
        assert "limit" in params["properties"]

    @pytest.mark.asyncio
    async def test_read_file_exec_fails(self) -> None:
        """When cat/tail exec fails, RuntimeError should be raised."""
        executor = MagicMock()
        executor.exec = AsyncMock(
            side_effect=[
                ExecResult(stdout="10", stderr="", code=0),  # wc -l succeeds
                ExecResult(stdout="", stderr="Permission denied", code=1),  # read fails
            ]
        )
        tool = ReadTool(executor)
        with pytest.raises(RuntimeError, match="Permission denied"):
            await tool.execute("id1", {"label": "read", "path": "/restricted.txt"})

    @pytest.mark.asyncio
    async def test_read_file_first_line_exceeds_byte_limit(self) -> None:
        """When first line exceeds byte limit, special message is returned."""

        executor = MagicMock()
        # Single very large line
        huge_line = "x" * (DEFAULT_MAX_BYTES + 1000)
        executor.exec = AsyncMock(
            side_effect=[
                ExecResult(stdout="1", stderr="", code=0),  # wc -l
                ExecResult(stdout=huge_line, stderr="", code=0),  # cat
            ]
        )
        tool = ReadTool(executor)
        result = await tool.execute("id1", {"label": "read", "path": "/large.txt"})
        text = result.content[0].text  # type: ignore[union-attr]
        assert "exceeds" in text or "limit" in text


# ============================================================================
# EditTool tests
# ============================================================================


class TestEditTool:
    @pytest.mark.asyncio
    async def test_successful_edit(self) -> None:
        file_content = "hello world\nfoo bar\n"
        executor = MagicMock()
        executor.exec = AsyncMock(
            side_effect=[
                ExecResult(stdout=file_content, stderr="", code=0),  # cat
                ExecResult(stdout="", stderr="", code=0),  # write back
            ]
        )
        tool = EditTool(executor)
        result = await tool.execute(
            "id1",
            {"label": "edit", "path": "/tmp/test.txt", "oldText": "hello world", "newText": "goodbye world"},
        )
        assert "Successfully replaced" in result.content[0].text  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_text_not_found(self) -> None:
        executor = _make_executor(stdout="some content\n")
        tool = EditTool(executor)
        with pytest.raises(RuntimeError, match="Could not find"):
            await tool.execute(
                "id1",
                {"label": "edit", "path": "/tmp/test.txt", "oldText": "MISSING", "newText": "replacement"},
            )

    @pytest.mark.asyncio
    async def test_multiple_occurrences(self) -> None:
        executor = _make_executor(stdout="foo foo foo\n")
        tool = EditTool(executor)
        with pytest.raises(RuntimeError, match="3 occurrences"):
            await tool.execute(
                "id1",
                {"label": "edit", "path": "/tmp/test.txt", "oldText": "foo", "newText": "bar"},
            )

    def test_tool_name(self) -> None:
        executor = _make_executor()
        tool = EditTool(executor)
        assert tool.name == "edit"

    def test_tool_label_and_description(self) -> None:
        executor = _make_executor()
        tool = EditTool(executor)
        assert tool.label == "edit"
        assert "edit" in tool.description.lower()

    def test_parameters_schema(self) -> None:
        executor = _make_executor()
        tool = EditTool(executor)
        params = tool.parameters
        assert "path" in params["properties"]
        assert "oldText" in params["properties"]
        assert "newText" in params["properties"]


# ============================================================================
# WriteTool tests
# ============================================================================


class TestWriteTool:
    @pytest.mark.asyncio
    async def test_successful_write(self) -> None:
        executor = _make_executor()
        tool = WriteTool(executor)
        result = await tool.execute(
            "id1",
            {"label": "write", "path": "/tmp/test.txt", "content": "hello world"},
        )
        assert "Successfully wrote" in result.content[0].text  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_write_failure(self) -> None:
        executor = _make_executor(code=1, stderr="Permission denied")
        tool = WriteTool(executor)
        with pytest.raises(RuntimeError, match="Permission denied"):
            await tool.execute(
                "id1",
                {"label": "write", "path": "/readonly/test.txt", "content": "data"},
            )

    def test_tool_name(self) -> None:
        executor = _make_executor()
        tool = WriteTool(executor)
        assert tool.name == "write"

    def test_tool_label_and_description(self) -> None:
        executor = _make_executor()
        tool = WriteTool(executor)
        assert tool.label == "write"
        assert "write" in tool.description.lower()

    def test_parameters_schema(self) -> None:
        executor = _make_executor()
        tool = WriteTool(executor)
        params = tool.parameters
        assert "path" in params["properties"]
        assert "content" in params["properties"]

    @pytest.mark.asyncio
    async def test_write_path_no_slash(self) -> None:
        """Writing to path without slash should still work (dir_path='.')."""
        executor = _make_executor()
        tool = WriteTool(executor)
        result = await tool.execute("id1", {"label": "write", "path": "myfile.txt", "content": "data"})
        assert "Successfully wrote" in result.content[0].text  # type: ignore[union-attr]


# ============================================================================
# AttachTool tests
# ============================================================================


class TestAttachTool:
    @pytest.mark.asyncio
    async def test_no_upload_function(self, tmp_path: Any) -> None:
        tool = AttachTool(str(tmp_path))
        with pytest.raises(RuntimeError, match="Upload function not configured"):
            await tool.execute("id1", {"label": "attach", "path": str(tmp_path)})

    @pytest.mark.asyncio
    async def test_with_upload_function(self, tmp_path: Any) -> None:
        uploaded_paths: list[str] = []

        async def _mock_upload(path: str, title: str | None) -> None:
            uploaded_paths.append(path)

        # Create a temp file so os.path.realpath works
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"fake png data")

        tool = AttachTool(str(tmp_path))
        tool.set_upload_fn(_mock_upload)
        result = await tool.execute("id1", {"label": "share", "path": str(test_file)})
        assert "Attached file" in result.content[0].text  # type: ignore[union-attr]
        assert len(uploaded_paths) == 1

    def test_tool_name(self, tmp_path: Any) -> None:
        tool = AttachTool(str(tmp_path))
        assert tool.name == "attach"

    def test_tool_label_description_parameters(self, tmp_path: Any) -> None:
        tool = AttachTool(str(tmp_path))
        assert tool.label == "attach"
        assert "attach" in tool.description.lower() or "file" in tool.description.lower()
        params = tool.parameters
        assert "path" in params["properties"]

    @pytest.mark.asyncio
    async def test_aborted_signal_raises(self, tmp_path: Any) -> None:
        """If signal is set when execute is called, should raise RuntimeError."""

        async def _mock_upload(path: str, title: str | None) -> None:
            pass

        signal = asyncio.Event()
        signal.set()

        tool = AttachTool(str(tmp_path))
        tool.set_upload_fn(_mock_upload)
        with pytest.raises(RuntimeError, match="aborted"):
            await tool.execute("id1", {"label": "share", "path": str(tmp_path)}, signal=signal)

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path: Any) -> None:
        """Files outside the workspace root must be rejected."""

        async def _mock_upload(path: str, title: str | None) -> None:
            pass

        tool = AttachTool(str(tmp_path))
        tool.set_upload_fn(_mock_upload)
        with pytest.raises(RuntimeError, match="workspace"):
            await tool.execute("id1", {"label": "share", "path": "/etc/passwd"})

    @pytest.mark.asyncio
    async def test_path_traversal_symlink_blocked(self, tmp_path: Any) -> None:
        """Symlinks that resolve outside the workspace must be rejected."""
        import os

        outside_file = tmp_path.parent / "outside.txt"
        outside_file.write_text("secret")
        symlink = tmp_path / "link.txt"
        os.symlink(str(outside_file), str(symlink))

        async def _mock_upload(path: str, title: str | None) -> None:
            pass

        tool = AttachTool(str(tmp_path))
        tool.set_upload_fn(_mock_upload)
        with pytest.raises(RuntimeError, match="workspace"):
            await tool.execute("id1", {"label": "share", "path": str(symlink)})

    @pytest.mark.asyncio
    async def test_per_run_upload_fn_isolation(self, tmp_path: Any) -> None:
        """set_upload_fn is per-instance, so two tools are fully independent."""
        calls_a: list[str] = []
        calls_b: list[str] = []

        async def _upload_a(path: str, title: str | None) -> None:
            calls_a.append(path)

        async def _upload_b(path: str, title: str | None) -> None:
            calls_b.append(path)

        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("a")
        file_b.write_text("b")

        workspace_a = tmp_path / "ws_a"
        workspace_b = tmp_path / "ws_b"
        workspace_a.mkdir()
        workspace_b.mkdir()
        (workspace_a / "a.txt").write_text("a")
        (workspace_b / "b.txt").write_text("b")

        tool_a = AttachTool(str(workspace_a))
        tool_b = AttachTool(str(workspace_b))
        tool_a.set_upload_fn(_upload_a)
        tool_b.set_upload_fn(_upload_b)

        await tool_a.execute("id1", {"label": "x", "path": str(workspace_a / "a.txt")})
        await tool_b.execute("id2", {"label": "x", "path": str(workspace_b / "b.txt")})

        assert len(calls_a) == 1
        assert len(calls_b) == 1


class TestCreateMomTools:
    def test_returns_all_tools(self) -> None:
        from pi_mom.tools import create_mom_tools

        executor = _make_executor()
        tools = create_mom_tools(executor, "/workspace")
        assert len(tools) == 5
        tool_names = {t.name for t in tools}
        assert "read" in tool_names
        assert "bash" in tool_names
        assert "edit" in tool_names
        assert "write" in tool_names
        assert "attach" in tool_names
