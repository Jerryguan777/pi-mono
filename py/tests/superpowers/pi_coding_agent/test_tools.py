"""Tests for coding agent tools — real file I/O with temp directories.

Ported from python-superpowers. Adapted to use the rewrite's tool
execute() signature: (tool_call_id, params, signal, on_update).
"""

from __future__ import annotations

import os
import shutil

import pytest
from pi_coding_agent.core.tools import (
    create_all_tools,
    create_coding_tools,
    create_bash_tool,
    create_edit_tool,
    create_find_tool,
    create_grep_tool,
    create_read_tool,
    create_write_tool,
)

_has_rg = shutil.which("rg") is not None

# ── Read tool tests ──────────────────────────────────────────────────


class TestReadTool:
    @pytest.fixture()
    def tool(self, tmp_path):
        return create_read_tool(str(tmp_path))

    @pytest.mark.asyncio
    async def test_read_file(self, tool, tmp_path) -> None:
        p = tmp_path / "hello.txt"
        p.write_text("line1\nline2\nline3\n")
        result = await tool.execute("tc_1", {"path": str(p)})
        assert not result.content[0].text == ""
        text = result.content[0].text
        assert "line1" in text
        assert "line2" in text
        assert "line3" in text

    @pytest.mark.asyncio
    async def test_read_with_offset_and_limit(self, tool, tmp_path) -> None:
        p = tmp_path / "lines.txt"
        p.write_text("\n".join(f"line{i}" for i in range(1, 11)))
        result = await tool.execute("tc_1", {"path": str(p), "offset": 2, "limit": 3})
        text = result.content[0].text
        # Should contain lines from offset, limited count
        assert "line3" in text or "line4" in text

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, tool) -> None:
        # TS design: tools throw exceptions on errors; agent_loop catches them.
        # Direct tool.execute() calls should expect exceptions.
        with pytest.raises(RuntimeError, match="File not found"):
            await tool.execute("tc_1", {"path": "/nonexistent/file.txt"})


# ── Write tool tests ─────────────────────────────────────────────────


class TestWriteTool:
    @pytest.fixture()
    def tool(self, tmp_path):
        return create_write_tool(str(tmp_path))

    @pytest.mark.asyncio
    async def test_write_file(self, tool, tmp_path) -> None:
        fp = str(tmp_path / "out.txt")
        result = await tool.execute("tc_1", {"path": fp, "content": "hello world"})
        assert os.path.exists(fp)
        with open(fp) as f:
            assert f.read() == "hello world"

    @pytest.mark.asyncio
    async def test_write_creates_parent_dirs(self, tool, tmp_path) -> None:
        fp = str(tmp_path / "a" / "b" / "c.txt")
        result = await tool.execute("tc_1", {"path": fp, "content": "nested"})
        with open(fp) as f:
            assert f.read() == "nested"

    @pytest.mark.asyncio
    async def test_write_relative_path(self, tool, tmp_path) -> None:
        result = await tool.execute("tc_1", {"path": "relwrite.txt", "content": "relative"})
        target = tmp_path / "relwrite.txt"
        assert target.exists()
        assert target.read_text() == "relative"


# ── Edit tool tests ──────────────────────────────────────────────────


class TestEditTool:
    @pytest.fixture()
    def tool(self, tmp_path):
        return create_edit_tool(str(tmp_path))

    @pytest.mark.asyncio
    async def test_edit_single_replace(self, tool, tmp_path) -> None:
        p = tmp_path / "edit.txt"
        p.write_text("foo bar baz")
        result = await tool.execute("tc_1", {"path": str(p), "old_text": "bar", "new_text": "qux"})
        assert p.read_text() == "foo qux baz"

    @pytest.mark.asyncio
    async def test_edit_not_found(self, tool, tmp_path) -> None:
        # TS design: tool throws when old_text not found
        p = tmp_path / "edit2.txt"
        p.write_text("foo bar baz")
        with pytest.raises(RuntimeError, match="old_text not found"):
            await tool.execute("tc_1", {"path": str(p), "old_text": "xyz", "new_text": "abc"})

    @pytest.mark.asyncio
    async def test_edit_file_not_found(self, tool) -> None:
        # TS design: tool throws when file not found
        with pytest.raises(RuntimeError, match="File not found"):
            await tool.execute(
                "tc_1",
                {
                    "path": "/nonexistent/file.txt",
                    "old_text": "a",
                    "new_text": "b",
                },
            )


# ── Bash tool tests ──────────────────────────────────────────────────


class TestBashTool:
    @pytest.fixture()
    def tool(self, tmp_path):
        return create_bash_tool(str(tmp_path))

    @pytest.mark.asyncio
    async def test_bash_echo(self, tool) -> None:
        result = await tool.execute("tc_1", {"command": "echo hello"})
        assert "hello" in result.content[0].text

    @pytest.mark.asyncio
    async def test_bash_nonzero_exit(self, tool) -> None:
        # TS design: bash tool throws on non-zero exit code;
        # agent_loop catches and wraps as ToolResultMessage(is_error=True)
        with pytest.raises(RuntimeError, match="exited with code 1"):
            await tool.execute("tc_1", {"command": "exit 1"})

    @pytest.mark.asyncio
    async def test_bash_stderr_merged(self, tool) -> None:
        result = await tool.execute("tc_1", {"command": "echo err >&2"})
        # stderr should be captured
        assert "err" in result.content[0].text

    @pytest.mark.asyncio
    async def test_bash_cwd(self, tool, tmp_path) -> None:
        result = await tool.execute("tc_1", {"command": "pwd"})
        assert str(tmp_path) in result.content[0].text


# ── Grep tool tests ──────────────────────────────────────────────────


@pytest.mark.skipif(not _has_rg, reason="ripgrep (rg) not installed")
class TestGrepTool:
    @pytest.fixture()
    def tool(self, tmp_path):
        return create_grep_tool(str(tmp_path))

    @pytest.mark.asyncio
    async def test_grep_finds_match(self, tool, tmp_path) -> None:
        p = tmp_path / "search.txt"
        p.write_text("hello world\ngoodbye world\n")
        result = await tool.execute("tc_1", {"pattern": "hello", "path": str(tmp_path)})
        assert "hello" in result.content[0].text

    @pytest.mark.asyncio
    async def test_grep_no_matches(self, tool, tmp_path) -> None:
        p = tmp_path / "search2.txt"
        p.write_text("nothing here\n")
        result = await tool.execute("tc_1", {"pattern": "zzzzz", "path": str(tmp_path)})
        text = result.content[0].text.lower()
        assert "no match" in text or "0 match" in text or text.strip() == ""


# ── Find tool tests ──────────────────────────────────────────────────


class TestFindTool:
    @pytest.fixture()
    def tool(self, tmp_path):
        return create_find_tool(str(tmp_path))

    @pytest.mark.asyncio
    async def test_find_files(self, tool, tmp_path) -> None:
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")
        result = await tool.execute("tc_1", {"pattern": "*.py"})
        text = result.content[0].text
        assert "a.py" in text
        assert "b.py" in text
        assert "c.txt" not in text

    @pytest.mark.asyncio
    async def test_find_recursive(self, tool, tmp_path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("")
        result = await tool.execute("tc_1", {"pattern": "**/*.py"})
        assert "deep.py" in result.content[0].text


# ── Index tests ──────────────────────────────────────────────────────


class TestToolIndex:
    def test_create_coding_tools(self, tmp_path) -> None:
        tools = create_coding_tools(str(tmp_path))
        names = {t.name for t in tools}
        assert "read" in names
        assert "bash" in names
        assert "edit" in names
        assert "write" in names

    def test_create_all_tools(self, tmp_path) -> None:
        tools = create_all_tools(str(tmp_path))
        # In the rewrite, create_all_tools returns a dict
        if isinstance(tools, dict):
            names = set(tools.keys())
        else:
            names = {t.name for t in tools}
        assert "read" in names
        assert "bash" in names
        assert "edit" in names
        assert "write" in names
        assert "grep" in names
        assert "find" in names
