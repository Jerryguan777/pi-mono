"""Tests for pi_coding_agent tools."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import pytest

from pi_coding_agent.core.tools.edit_diff import (
    detect_line_ending,
    fuzzy_find_text,
    generate_diff_string,
    normalize_for_fuzzy_match,
    normalize_to_lf,
    restore_line_endings,
    strip_bom,
)
from pi_coding_agent.core.tools.path_utils import expand_path, resolve_to_cwd
from pi_coding_agent.core.tools.truncate import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_LINES,
    format_size,
    truncate_head,
    truncate_line,
    truncate_tail,
)

# --- truncate tests ---


def test_format_size_bytes() -> None:
    assert format_size(500) == "500B"


def test_format_size_kb() -> None:
    result = format_size(2048)
    assert "KB" in result


def test_format_size_mb() -> None:
    result = format_size(2 * 1024 * 1024)
    assert "MB" in result


def test_truncate_head_no_truncation() -> None:
    content = "line1\nline2\nline3\n"
    result = truncate_head(content)
    assert result.truncated is False
    assert result.content == content
    assert result.total_lines == 3


def test_truncate_head_by_lines() -> None:
    lines = [f"line{i}\n" for i in range(DEFAULT_MAX_LINES + 10)]
    content = "".join(lines)
    result = truncate_head(content)
    assert result.truncated is True
    assert result.truncated_by == "lines"
    assert result.output_lines == DEFAULT_MAX_LINES


def test_truncate_head_by_bytes() -> None:
    # Create content that exceeds DEFAULT_MAX_BYTES but not DEFAULT_MAX_LINES
    content = "x" * (DEFAULT_MAX_BYTES + 1000)
    result = truncate_head(content, max_lines=DEFAULT_MAX_LINES)
    assert result.truncated is True
    assert result.truncated_by == "bytes"
    assert result.output_bytes <= DEFAULT_MAX_BYTES


def test_truncate_tail_no_truncation() -> None:
    content = "hello\nworld\n"
    result = truncate_tail(content)
    assert result.truncated is False
    assert result.content == content


def test_truncate_tail_by_lines() -> None:
    lines = [f"line{i}\n" for i in range(DEFAULT_MAX_LINES + 5)]
    content = "".join(lines)
    result = truncate_tail(content)
    assert result.truncated is True
    assert result.truncated_by == "lines"
    assert result.output_lines == DEFAULT_MAX_LINES
    # Last line should be at the end
    assert "line" in result.content


def test_truncate_tail_by_bytes() -> None:
    content = "x" * (DEFAULT_MAX_BYTES + 1000)
    result = truncate_tail(content, max_lines=DEFAULT_MAX_LINES)
    assert result.truncated is True
    assert result.truncated_by == "bytes"
    assert result.output_bytes <= DEFAULT_MAX_BYTES


def test_truncate_line_no_truncation() -> None:
    line = "short line"
    text, was_truncated = truncate_line(line)
    assert text == line
    assert was_truncated is False


def test_truncate_line_truncated() -> None:
    line = "x" * 600
    text, was_truncated = truncate_line(line)
    assert was_truncated is True
    assert len(text) == 500


# --- path_utils tests ---


def test_expand_path_tilde() -> None:
    home = os.path.expanduser("~")
    result = expand_path("~/test/file.py")
    assert result.startswith(home)
    assert "test/file.py" in result


def test_expand_path_strip_at() -> None:
    result = expand_path("@/some/path.py")
    assert not result.startswith("@")


def test_expand_path_unicode_spaces() -> None:
    # Non-breaking space
    result = expand_path("/path\u00a0with\u00a0spaces")
    assert "\u00a0" not in result
    assert " " in result


def test_resolve_to_cwd_absolute() -> None:
    result = resolve_to_cwd("/absolute/path", "/some/cwd")
    assert result == "/absolute/path"


def test_resolve_to_cwd_relative() -> None:
    result = resolve_to_cwd("relative/file.py", "/some/cwd")
    assert result == "/some/cwd/relative/file.py"


def test_resolve_to_cwd_dot() -> None:
    result = resolve_to_cwd("./file.py", "/some/cwd")
    assert result == "/some/cwd/file.py"


def test_resolve_to_cwd_path_traversal_normalized() -> None:
    # .. components must be normalized away to prevent path traversal
    result = resolve_to_cwd("../../etc/passwd", "/some/cwd")
    assert ".." not in result
    assert result == "/etc/passwd"


# --- edit_diff tests ---


def test_normalize_to_lf() -> None:
    text = "line1\r\nline2\r\nline3"
    result = normalize_to_lf(text)
    assert "\r\n" not in result
    assert result == "line1\nline2\nline3"


def test_restore_line_endings_crlf() -> None:
    text = "line1\nline2\n"
    result = restore_line_endings(text, "\r\n")
    assert result == "line1\r\nline2\r\n"


def test_restore_line_endings_lf() -> None:
    text = "line1\nline2\n"
    result = restore_line_endings(text, "\n")
    assert result == text


def test_detect_line_ending_crlf() -> None:
    text = "a\r\nb\r\nc"
    assert detect_line_ending(text) == "\r\n"


def test_detect_line_ending_lf() -> None:
    text = "a\nb\nc"
    assert detect_line_ending(text) == "\n"


def test_strip_bom_with_bom() -> None:
    bom, text = strip_bom("\ufeffhello")
    assert bom == "\ufeff"
    assert text == "hello"


def test_strip_bom_without_bom() -> None:
    bom, text = strip_bom("hello")
    assert bom == ""
    assert text == "hello"


def test_fuzzy_find_text_exact() -> None:
    content = "hello world\nfoo bar\n"
    result = fuzzy_find_text(content, "foo bar")
    assert result.found is True
    assert result.used_fuzzy_match is False
    assert content[result.index : result.index + result.match_length] == "foo bar"


def test_fuzzy_find_text_not_found() -> None:
    content = "hello world\n"
    result = fuzzy_find_text(content, "xyz nothere")
    assert result.found is False


def test_fuzzy_find_text_fuzzy_trailing_space() -> None:
    # Content has trailing spaces that the old_text doesn't
    content = "def foo():   \n    pass\n"
    old_text = "def foo():\n    pass"
    result = fuzzy_find_text(content, old_text)
    assert result.found is True
    assert result.used_fuzzy_match is True


def test_normalize_for_fuzzy_match_strips_trailing_whitespace() -> None:
    text = "line1   \nline2  \n"
    result = normalize_for_fuzzy_match(text)
    assert "   " not in result
    assert "line1" in result
    assert "line2" in result


def test_normalize_for_fuzzy_match_curly_quotes() -> None:
    text = "\u2018hello\u2019 and \u201cworld\u201d"
    result = normalize_for_fuzzy_match(text)
    assert "'" in result
    assert '"' in result
    assert "\u2018" not in result
    assert "\u201c" not in result


def test_generate_diff_string_no_change() -> None:
    content = "line1\nline2\n"
    result = generate_diff_string(content, content)
    assert result.diff == ""
    assert result.first_changed_line is None


def test_generate_diff_string_replacement() -> None:
    old = "line1\nline2\nline3\n"
    new = "line1\nLINE2\nline3\n"
    result = generate_diff_string(old, new)
    assert result.diff != ""
    assert result.first_changed_line is not None
    assert "-" in result.diff or "+" in result.diff


def test_generate_diff_string_addition() -> None:
    old = "line1\nline2\n"
    new = "line1\nnew_line\nline2\n"
    result = generate_diff_string(old, new)
    assert "+" in result.diff
    assert result.first_changed_line == 2


def test_generate_diff_string_deletion() -> None:
    old = "line1\ndelete_me\nline2\n"
    new = "line1\nline2\n"
    result = generate_diff_string(old, new)
    assert "-" in result.diff


# --- BashTool tests ---


@pytest.mark.asyncio
async def test_bash_tool_execute(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.bash import BashTool

    tool = BashTool(str(tmp_path))
    result = await tool.execute("id1", {"command": "echo hello"})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "hello" in text


@pytest.mark.asyncio
async def test_bash_tool_exit_code(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.bash import BashTool

    tool = BashTool(str(tmp_path))
    with pytest.raises(RuntimeError, match="exit"):
        await tool.execute("id1", {"command": "exit 1"})


@pytest.mark.asyncio
async def test_bash_tool_timeout(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.bash import BashTool

    tool = BashTool(str(tmp_path))
    with pytest.raises(RuntimeError, match="timed out"):
        await tool.execute("id1", {"command": "sleep 10", "timeout": 0.5})


@pytest.mark.asyncio
async def test_bash_tool_signal(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.bash import BashTool

    tool = BashTool(str(tmp_path))
    signal = asyncio.Event()

    async def set_signal_soon() -> None:
        await asyncio.sleep(0.1)
        signal.set()

    background_task = asyncio.create_task(set_signal_soon())
    with pytest.raises(RuntimeError, match="aborted"):
        await tool.execute("id1", {"command": "sleep 10"}, signal=signal)
    background_task.cancel()


@pytest.mark.asyncio
async def test_bash_tool_stderr(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.bash import BashTool

    tool = BashTool(str(tmp_path))
    # stderr goes to non-zero exit code
    with pytest.raises(RuntimeError):
        await tool.execute("id1", {"command": "echo error >&2; exit 1"})


@pytest.mark.asyncio
async def test_bash_tool_cwd_not_exist() -> None:
    from pi_coding_agent.core.tools.bash import BashTool

    tool = BashTool("/nonexistent/path/that/does/not/exist")
    with pytest.raises(RuntimeError, match="cwd does not exist"):
        await tool.execute("id1", {"command": "echo hi"})


# --- EditTool tests ---


@pytest.mark.asyncio
async def test_edit_tool_basic(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.edit import EditTool

    f = tmp_path / "test.py"
    f.write_text("hello world\nfoo bar\n")

    tool = EditTool(str(tmp_path))
    result = await tool.execute(
        "id1",
        {"path": str(f), "old_text": "foo bar", "new_text": "baz qux"},
    )
    text = result.content[0].text  # type: ignore[union-attr]
    assert "Edited" in text
    assert f.read_text() == "hello world\nbaz qux\n"


@pytest.mark.asyncio
async def test_edit_tool_file_not_found(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.edit import EditTool

    tool = EditTool(str(tmp_path))
    with pytest.raises(RuntimeError, match="not found"):
        await tool.execute(
            "id1",
            {"path": str(tmp_path / "nonexistent.py"), "old_text": "x", "new_text": "y"},
        )


@pytest.mark.asyncio
async def test_edit_tool_text_not_found(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.edit import EditTool

    f = tmp_path / "test.py"
    f.write_text("hello world\n")

    tool = EditTool(str(tmp_path))
    with pytest.raises(RuntimeError, match="not found"):
        await tool.execute(
            "id1",
            {"path": str(f), "old_text": "nonexistent text", "new_text": "replacement"},
        )


@pytest.mark.asyncio
async def test_edit_tool_multiple_occurrences(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.edit import EditTool

    f = tmp_path / "test.py"
    f.write_text("foo\nfoo\n")

    tool = EditTool(str(tmp_path))
    with pytest.raises(RuntimeError, match="multiple"):
        await tool.execute(
            "id1",
            {"path": str(f), "old_text": "foo", "new_text": "bar"},
        )


# --- ReadTool tests ---


@pytest.mark.asyncio
async def test_read_tool_basic(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.read import ReadTool

    f = tmp_path / "file.txt"
    f.write_text("line1\nline2\nline3\n")

    tool = ReadTool(str(tmp_path))
    result = await tool.execute("id1", {"path": str(f)})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "line1" in text
    assert "line2" in text


@pytest.mark.asyncio
async def test_read_tool_offset_limit(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.read import ReadTool

    f = tmp_path / "file.txt"
    lines = [f"line{i}\n" for i in range(1, 11)]
    f.write_text("".join(lines))

    tool = ReadTool(str(tmp_path))
    result = await tool.execute("id1", {"path": str(f), "offset": 3, "limit": 3})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "line3" in text
    assert "line4" in text
    assert "line5" in text
    # Should not contain line1 or line2 (before offset)
    assert "line1\n" not in text


@pytest.mark.asyncio
async def test_read_tool_first_line_exceeds_limit(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.read import ReadTool
    from pi_coding_agent.core.tools.truncate import DEFAULT_MAX_BYTES

    f = tmp_path / "huge_line.txt"
    # Write a single line that exceeds DEFAULT_MAX_BYTES
    f.write_bytes(b"x" * (DEFAULT_MAX_BYTES + 100) + b"\n")

    tool = ReadTool(str(tmp_path))
    result = await tool.execute("id1", {"path": str(f)})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "exceeds" in text
    assert "sed" in text


@pytest.mark.asyncio
async def test_read_tool_file_not_found(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.read import ReadTool

    tool = ReadTool(str(tmp_path))
    with pytest.raises(RuntimeError, match="not found"):
        await tool.execute("id1", {"path": str(tmp_path / "nonexistent.txt")})


@pytest.mark.asyncio
async def test_read_tool_image(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.read import ReadTool

    # Create a minimal PNG (1x1 pixel)
    # PNG header + IHDR + IDAT + IEND
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR"  # IHDR chunk length + type
        b"\x00\x00\x00\x01"  # width = 1
        b"\x00\x00\x00\x01"  # height = 1
        b"\x08\x02"  # bit depth = 8, color type = 2 (RGB)
        b"\x00\x00\x00"  # compression, filter, interlace
        b"\x90wS\xde"  # CRC
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"  # IDAT
        b"\x00\x00\x00\x00IEND\xaeB`\x82"  # IEND
    )
    f = tmp_path / "test.png"
    f.write_bytes(png_bytes)

    tool = ReadTool(str(tmp_path))
    result = await tool.execute("id1", {"path": str(f)})
    from pi_ai.types import ImageContent

    assert isinstance(result.content[0], ImageContent)
    assert result.content[0].mime_type == "image/png"


# --- WriteTool tests ---


@pytest.mark.asyncio
async def test_write_tool_new_file(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.write import WriteTool

    f = tmp_path / "new_file.txt"
    tool = WriteTool(str(tmp_path))
    result = await tool.execute("id1", {"path": str(f), "content": "hello world"})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "Written" in text
    assert f.read_text() == "hello world"


@pytest.mark.asyncio
async def test_write_tool_overwrite(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.write import WriteTool

    f = tmp_path / "existing.txt"
    f.write_text("old content")

    tool = WriteTool(str(tmp_path))
    await tool.execute("id1", {"path": str(f), "content": "new content"})
    assert f.read_text() == "new content"


@pytest.mark.asyncio
async def test_write_tool_create_dirs(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.write import WriteTool

    f = tmp_path / "a" / "b" / "c" / "file.txt"
    tool = WriteTool(str(tmp_path))
    await tool.execute("id1", {"path": str(f), "content": "nested"})
    assert f.exists()
    assert f.read_text() == "nested"


# --- GrepTool tests ---

rg_available = shutil.which("rg") is not None
requires_rg = pytest.mark.skipif(not rg_available, reason="ripgrep (rg) not installed")


@requires_rg
@pytest.mark.asyncio
async def test_grep_tool_basic(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.grep import GrepTool

    f = tmp_path / "test.py"
    f.write_text("def hello():\n    return 'world'\n\ndef foo():\n    pass\n")

    tool = GrepTool(str(tmp_path))
    result = await tool.execute("id1", {"pattern": "def ", "path": str(tmp_path)})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "hello" in text
    assert "foo" in text


@requires_rg
@pytest.mark.asyncio
async def test_grep_tool_no_matches(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.grep import GrepTool

    f = tmp_path / "test.txt"
    f.write_text("line1\nline2\n")

    tool = GrepTool(str(tmp_path))
    result = await tool.execute("id1", {"pattern": "xyz_nothere", "path": str(tmp_path)})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "No matches" in text


@requires_rg
@pytest.mark.asyncio
async def test_grep_tool_ignore_case(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.grep import GrepTool

    f = tmp_path / "test.txt"
    f.write_text("Hello World\nfoo bar\n")

    tool = GrepTool(str(tmp_path))
    result = await tool.execute(
        "id1",
        {"pattern": "hello world", "path": str(tmp_path), "ignore_case": True},
    )
    text = result.content[0].text  # type: ignore[union-attr]
    assert "Hello World" in text


@requires_rg
@pytest.mark.asyncio
async def test_grep_tool_literal(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.grep import GrepTool

    f = tmp_path / "test.py"
    f.write_text("result = func(a+b)\n")

    tool = GrepTool(str(tmp_path))
    result = await tool.execute(
        "id1",
        {"pattern": "func(a+b)", "path": str(tmp_path), "literal": True},
    )
    text = result.content[0].text  # type: ignore[union-attr]
    assert "func(a+b)" in text


# --- FindTool tests ---


@pytest.mark.asyncio
async def test_find_tool_basic(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.find import FindTool

    (tmp_path / "foo.py").write_text("")
    (tmp_path / "bar.py").write_text("")
    (tmp_path / "baz.txt").write_text("")

    tool = FindTool(str(tmp_path))
    result = await tool.execute("id1", {"pattern": "*.py", "path": str(tmp_path)})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "foo.py" in text
    assert "bar.py" in text
    assert "baz.txt" not in text


@pytest.mark.asyncio
async def test_find_tool_no_results(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.find import FindTool

    tool = FindTool(str(tmp_path))
    result = await tool.execute("id1", {"pattern": "*.xyz", "path": str(tmp_path)})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "No files" in text


@pytest.mark.asyncio
async def test_find_tool_excludes_node_modules(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.find import FindTool

    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "package.py").write_text("")
    (tmp_path / "main.py").write_text("")

    tool = FindTool(str(tmp_path))
    result = await tool.execute("id1", {"pattern": "**/*.py", "path": str(tmp_path)})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "main.py" in text
    assert "node_modules" not in text


# --- LsTool tests ---


@pytest.mark.asyncio
async def test_ls_tool_basic(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.ls import LsTool

    (tmp_path / "file.txt").write_text("")
    (tmp_path / "subdir").mkdir()

    tool = LsTool(str(tmp_path))
    result = await tool.execute("id1", {"path": str(tmp_path)})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "file.txt" in text
    assert "subdir/" in text


@pytest.mark.asyncio
async def test_ls_tool_limit(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.ls import LsTool

    for i in range(10):
        (tmp_path / f"file{i}.txt").write_text("")

    tool = LsTool(str(tmp_path))
    result = await tool.execute("id1", {"path": str(tmp_path), "limit": 3})
    text = result.content[0].text  # type: ignore[union-attr]
    lines = [line for line in text.split("\n") if line.strip() and not line.startswith("[")]
    assert len(lines) <= 3


@pytest.mark.asyncio
async def test_ls_tool_not_a_directory(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.ls import LsTool

    f = tmp_path / "file.txt"
    f.write_text("")

    tool = LsTool(str(tmp_path))
    with pytest.raises(RuntimeError, match="Not a directory"):
        await tool.execute("id1", {"path": str(f)})


@pytest.mark.asyncio
async def test_ls_tool_not_found(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.ls import LsTool

    tool = LsTool(str(tmp_path))
    with pytest.raises(RuntimeError, match="not found"):
        await tool.execute("id1", {"path": str(tmp_path / "nonexistent")})


@pytest.mark.asyncio
async def test_ls_tool_default_cwd(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools.ls import LsTool

    (tmp_path / "myfile.txt").write_text("")
    tool = LsTool(str(tmp_path))
    # No path param - uses cwd
    result = await tool.execute("id1", {})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "myfile.txt" in text


# --- Tool metadata (name/label/description/parameters) ---


def test_tool_metadata(tmp_path: Path) -> None:
    """Verify all tools expose required metadata properties."""
    from pi_coding_agent.core.tools.bash import BashTool
    from pi_coding_agent.core.tools.edit import EditTool
    from pi_coding_agent.core.tools.find import FindTool
    from pi_coding_agent.core.tools.grep import GrepTool
    from pi_coding_agent.core.tools.ls import LsTool
    from pi_coding_agent.core.tools.read import ReadTool
    from pi_coding_agent.core.tools.write import WriteTool

    tools = [
        BashTool(str(tmp_path)),
        EditTool(str(tmp_path)),
        FindTool(str(tmp_path)),
        GrepTool(str(tmp_path)),
        LsTool(str(tmp_path)),
        ReadTool(str(tmp_path)),
        WriteTool(str(tmp_path)),
    ]
    expected_names = {"bash", "edit", "find", "grep", "ls", "read", "write"}
    for tool in tools:
        assert tool.name in expected_names
        assert tool.label == tool.name
        assert len(tool.description) > 0
        assert tool.parameters["type"] == "object"
        assert "properties" in tool.parameters


# --- create_all_tools / create_coding_tools / create_read_only_tools ---


def test_factory_functions(tmp_path: Path) -> None:
    from pi_coding_agent.core.tools import (
        create_all_tools,
        create_coding_tools,
        create_read_only_tools,
    )

    coding = create_coding_tools(str(tmp_path))
    assert len(coding) == 4
    assert {t.name for t in coding} == {"read", "bash", "edit", "write"}

    readonly = create_read_only_tools(str(tmp_path))
    assert len(readonly) == 4
    assert {t.name for t in readonly} == {"read", "grep", "find", "ls"}

    all_tools = create_all_tools(str(tmp_path))
    assert set(all_tools.keys()) == {"read", "bash", "edit", "write", "grep", "find", "ls"}


# --- grep: rg not available raises RuntimeError ---


@pytest.mark.asyncio
async def test_grep_tool_rg_not_available(tmp_path: Path) -> None:
    """Test that RuntimeError is raised when rg is not installed."""
    import unittest.mock

    from pi_coding_agent.core.tools.grep import GrepTool

    tool = GrepTool(str(tmp_path))
    with (
        unittest.mock.patch("pi_coding_agent.core.tools.grep.shutil.which", return_value=None),
        pytest.raises(RuntimeError, match="ripgrep"),
    ):
        await tool.execute("id1", {"pattern": "def ", "path": str(tmp_path)})


# --- find glob fallback ---


@pytest.mark.asyncio
async def test_find_tool_glob_fallback(tmp_path: Path) -> None:
    """Test the Python glob fallback when fd is not available."""
    import unittest.mock

    from pi_coding_agent.core.tools.find import FindTool

    (tmp_path / "foo.py").write_text("")
    (tmp_path / "bar.txt").write_text("")

    tool = FindTool(str(tmp_path))
    with unittest.mock.patch("pi_coding_agent.core.tools.find.shutil.which", return_value=None):
        result = await tool.execute("id1", {"pattern": "*.py", "path": str(tmp_path)})
    text = result.content[0].text  # type: ignore[union-attr]
    assert "foo.py" in text
    assert "bar.txt" not in text


# --- fuzzy match index mapping edge cases ---


def test_map_normalized_index_trailing_spaces() -> None:
    """Ensure fuzzy_find_text correctly maps index when trailing spaces are stripped."""
    from pi_coding_agent.core.tools.edit_diff import fuzzy_find_text

    # Content has trailing spaces; old_text doesn't
    content = "def foo():   \n    return 42\n"
    old_text = "def foo():\n    return 42"
    result = fuzzy_find_text(content, old_text)
    assert result.found is True
    # The replacement should cover the entire matched region
    replaced = content[: result.index] + "def bar():\n    return 0" + content[result.index + result.match_length :]
    assert "def bar" in replaced
    assert "def foo" not in replaced


def test_normalizes_to_dashes() -> None:
    """Test that all new dash variants are normalized."""
    from pi_coding_agent.core.tools.edit_diff import normalize_for_fuzzy_match

    dashes = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
    for ch in dashes:
        result = normalize_for_fuzzy_match(ch)
        assert result == "-", f"Expected '-' for U+{ord(ch):04X}, got {result!r}"


def test_normalizes_to_extended_quotes() -> None:
    """Test that extended curly quote variants are normalized."""
    from pi_coding_agent.core.tools.edit_diff import normalize_for_fuzzy_match

    singles = "\u201a\u201b"
    doubles = "\u201e\u201f"
    for ch in singles:
        assert normalize_for_fuzzy_match(ch) == "'"
    for ch in doubles:
        assert normalize_for_fuzzy_match(ch) == '"'
