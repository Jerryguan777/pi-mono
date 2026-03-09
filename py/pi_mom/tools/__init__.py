"""Tools package for pi_mom — port of packages/mom/src/tools/index.ts."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pi_agent.types import AgentTool
from pi_mom.sandbox import Executor
from pi_mom.tools.attach import AttachTool
from pi_mom.tools.bash import BashTool
from pi_mom.tools.edit import EditTool
from pi_mom.tools.read import ReadTool
from pi_mom.tools.write import WriteTool

__all__ = [
    "AttachTool",
    "BashTool",
    "EditTool",
    "ReadTool",
    "WriteTool",
    "attach_tool",
    "create_bash_tool",
    "create_edit_tool",
    "create_mom_tools",
    "create_read_tool",
    "create_write_tool",
    "set_upload_function",
]

# Module-level upload function reference (mirrors TS global setUploadFunction)
_upload_fn: Callable[[str, str | None], Awaitable[None]] | None = None


def set_upload_function(fn: Callable[[str, str | None], Awaitable[None]]) -> None:
    """Set the global upload function used by the attach tool.

    This mirrors the TS setUploadFunction export: a module-level setter
    that configures the upload callback before running the agent.
    """
    global _upload_fn
    _upload_fn = fn


def attach_tool(workspace_root: str) -> AttachTool:
    """Create an AttachTool instance for the given workspace root."""
    tool = AttachTool(workspace_root)
    if _upload_fn is not None:
        tool.set_upload_fn(_upload_fn)
    return tool


def create_bash_tool(executor: Executor) -> BashTool:
    """Create a BashTool for the given executor."""
    return BashTool(executor)


def create_read_tool(executor: Executor) -> ReadTool:
    """Create a ReadTool for the given executor."""
    return ReadTool(executor)


def create_edit_tool(executor: Executor) -> EditTool:
    """Create an EditTool for the given executor."""
    return EditTool(executor)


def create_write_tool(executor: Executor) -> WriteTool:
    """Create a WriteTool for the given executor."""
    return WriteTool(executor)


def create_mom_tools(executor: Executor, workspace_root: str) -> list[AgentTool]:
    """Create the standard set of mom tools for the given executor."""
    return [
        create_read_tool(executor),
        create_bash_tool(executor),
        create_edit_tool(executor),
        create_write_tool(executor),
        attach_tool(workspace_root),
    ]
