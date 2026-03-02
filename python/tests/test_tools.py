"""Tests for coding tools — filesystem tests, no API keys needed."""

import os
import tempfile

import pytest

from pi_tools.bash_tool import BashTool
from pi_tools.read_tool import ReadTool
from pi_tools.write_tool import WriteTool
from pi_tools.edit_tool import EditTool
from pi_tools.grep_tool import GrepTool
from pi_tools.find_tool import FindTool
from pi_tools.ls_tool import LsTool
from pi_tools.truncate import truncate_head, truncate_tail
from pi_tools.edit_diff import fuzzy_find_text, normalize_for_fuzzy_match, strip_bom, generate_diff_string
from pi_tools.path_utils import resolve_to_cwd, expand_path


@pytest.fixture
def workdir():
    with tempfile.TemporaryDirectory() as tmp:
        # Create some test files
        with open(os.path.join(tmp, "test.txt"), "w") as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5\n")
        with open(os.path.join(tmp, "hello.py"), "w") as f:
            f.write('print("hello world")\n')
        os.makedirs(os.path.join(tmp, "subdir"), exist_ok=True)
        with open(os.path.join(tmp, "subdir", "nested.txt"), "w") as f:
            f.write("nested content\n")
        yield tmp


# --- Path utils ---

def test_resolve_to_cwd():
    assert resolve_to_cwd("foo.txt", "/home/user") == "/home/user/foo.txt"
    assert resolve_to_cwd("/abs/path.txt", "/home/user") == "/abs/path.txt"
    assert resolve_to_cwd("./foo.txt", "/home/user") == "/home/user/foo.txt"


def test_expand_path():
    assert expand_path("@foo.txt") == "foo.txt"
    assert expand_path("~/foo.txt").startswith("/")


# --- Truncation ---

def test_truncate_head_no_truncation():
    result = truncate_head("line1\nline2\nline3")
    assert not result.truncated
    assert result.content == "line1\nline2\nline3"


def test_truncate_head_by_lines():
    content = "\n".join(f"line {i}" for i in range(3000))
    result = truncate_head(content, max_lines=100)
    assert result.truncated
    assert result.truncated_by == "lines"
    assert result.output_lines == 100


def test_truncate_tail_no_truncation():
    result = truncate_tail("line1\nline2\nline3")
    assert not result.truncated


def test_truncate_tail_by_lines():
    content = "\n".join(f"line {i}" for i in range(3000))
    result = truncate_tail(content, max_lines=100)
    assert result.truncated
    assert result.output_lines == 100
    # Should keep the last lines
    assert "line 2999" in result.content


# --- Edit diff ---

def test_strip_bom():
    bom, text = strip_bom("\ufeffhello")
    assert bom == "\ufeff"
    assert text == "hello"

    bom, text = strip_bom("hello")
    assert bom == ""
    assert text == "hello"


def test_fuzzy_find_exact():
    result = fuzzy_find_text("hello world", "world")
    assert result.found
    assert not result.is_fuzzy
    assert result.index == 6


def test_fuzzy_find_smart_quotes():
    result = fuzzy_find_text('hello "world"', "hello \u201cworld\u201d")
    assert result.found
    assert result.is_fuzzy


def test_normalize_for_fuzzy():
    text = normalize_for_fuzzy_match("hello   world")
    assert text == "hello world"


def test_generate_diff():
    result = generate_diff_string("hello\nworld\n", "hello\nearth\n")
    assert "diff" in result
    assert result["first_changed_line"] == 2


# --- Bash tool ---

@pytest.mark.asyncio
async def test_bash_echo(workdir):
    tool = BashTool(workdir)
    result = await tool.execute("tc1", {"command": "echo hello"})
    assert any("hello" in c.text for c in result.content)


@pytest.mark.asyncio
async def test_bash_ls(workdir):
    tool = BashTool(workdir)
    result = await tool.execute("tc1", {"command": "ls"})
    text = result.content[0].text
    assert "test.txt" in text


@pytest.mark.asyncio
async def test_bash_exit_code(workdir):
    tool = BashTool(workdir)
    with pytest.raises(ValueError, match="exited with code"):
        await tool.execute("tc1", {"command": "exit 1"})


@pytest.mark.asyncio
async def test_bash_timeout(workdir):
    tool = BashTool(workdir)
    with pytest.raises(ValueError, match="timed out"):
        await tool.execute("tc1", {"command": "sleep 10", "timeout": 1})


# --- Read tool ---

@pytest.mark.asyncio
async def test_read_file(workdir):
    tool = ReadTool(workdir)
    result = await tool.execute("tc1", {"path": "test.txt"})
    text = result.content[0].text
    assert "line 1" in text
    assert "line 5" in text


@pytest.mark.asyncio
async def test_read_file_with_offset(workdir):
    tool = ReadTool(workdir)
    result = await tool.execute("tc1", {"path": "test.txt", "offset": 3})
    text = result.content[0].text
    assert "line 3" in text
    assert "line 1" not in text


@pytest.mark.asyncio
async def test_read_file_with_limit(workdir):
    tool = ReadTool(workdir)
    result = await tool.execute("tc1", {"path": "test.txt", "offset": 1, "limit": 2})
    text = result.content[0].text
    assert "line 1" in text
    assert "line 2" in text
    assert "more lines" in text.lower() or "offset=" in text


@pytest.mark.asyncio
async def test_read_file_not_found(workdir):
    tool = ReadTool(workdir)
    with pytest.raises(FileNotFoundError):
        await tool.execute("tc1", {"path": "nonexistent.txt"})


# --- Write tool ---

@pytest.mark.asyncio
async def test_write_file(workdir):
    tool = WriteTool(workdir)
    result = await tool.execute("tc1", {"path": "new.txt", "content": "new content"})
    assert "Successfully wrote" in result.content[0].text
    assert os.path.exists(os.path.join(workdir, "new.txt"))
    with open(os.path.join(workdir, "new.txt")) as f:
        assert f.read() == "new content"


@pytest.mark.asyncio
async def test_write_creates_dirs(workdir):
    tool = WriteTool(workdir)
    result = await tool.execute("tc1", {"path": "deep/nested/file.txt", "content": "hello"})
    assert os.path.exists(os.path.join(workdir, "deep", "nested", "file.txt"))


# --- Edit tool ---

@pytest.mark.asyncio
async def test_edit_replace(workdir):
    tool = EditTool(workdir)
    result = await tool.execute("tc1", {
        "path": "test.txt",
        "oldText": "line 3",
        "newText": "modified line 3",
    })
    assert "Successfully replaced" in result.content[0].text
    with open(os.path.join(workdir, "test.txt")) as f:
        content = f.read()
    assert "modified line 3" in content
    assert "\nline 3\n" not in content


@pytest.mark.asyncio
async def test_edit_not_found(workdir):
    tool = EditTool(workdir)
    with pytest.raises(ValueError, match="Could not find"):
        await tool.execute("tc1", {
            "path": "test.txt",
            "oldText": "nonexistent text",
            "newText": "replacement",
        })


# --- Grep tool ---

@pytest.mark.asyncio
async def test_grep_find_pattern(workdir):
    tool = GrepTool(workdir)
    result = await tool.execute("tc1", {"pattern": "hello", "path": "."})
    text = result.content[0].text
    assert "hello" in text.lower()


@pytest.mark.asyncio
async def test_grep_no_match(workdir):
    tool = GrepTool(workdir)
    result = await tool.execute("tc1", {"pattern": "zzz_nonexistent_zzz", "path": "."})
    assert "No matches" in result.content[0].text


# --- Find tool ---

@pytest.mark.asyncio
async def test_find_files(workdir):
    tool = FindTool(workdir)
    result = await tool.execute("tc1", {"pattern": "*.txt", "path": "."})
    text = result.content[0].text
    assert "test.txt" in text


# --- Ls tool ---

@pytest.mark.asyncio
async def test_ls_directory(workdir):
    tool = LsTool(workdir)
    result = await tool.execute("tc1", {"path": "."})
    text = result.content[0].text
    assert "test.txt" in text
    assert "hello.py" in text
    assert "subdir/" in text


@pytest.mark.asyncio
async def test_ls_not_found(workdir):
    tool = LsTool(workdir)
    with pytest.raises(FileNotFoundError):
        await tool.execute("tc1", {"path": "nonexistent"})
