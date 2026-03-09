"""Tools package for pi_coding_agent."""

from __future__ import annotations

from typing import Any, Literal

from pi_agent.types import AgentTool

from .bash import BashTool
from .edit import EditTool
from .find import FindTool
from .grep import GrepTool
from .ls import LsTool
from .read import ReadTool
from .truncate import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_LINES,
    TruncationResult,
    format_size,
    truncate_head,
    truncate_line,
    truncate_tail,
)
from .write import WriteTool

ToolName = Literal["read", "bash", "edit", "write", "grep", "find", "ls"]


def create_coding_tools(cwd: str, **kwargs: Any) -> list[AgentTool]:
    """Create coding tools: read, bash, edit, write."""
    return [ReadTool(cwd), BashTool(cwd), EditTool(cwd), WriteTool(cwd)]


def create_read_only_tools(cwd: str, **kwargs: Any) -> list[AgentTool]:
    """Create read-only tools: read, grep, find, ls."""
    return [ReadTool(cwd), GrepTool(cwd), FindTool(cwd), LsTool(cwd)]


def create_all_tools(cwd: str, **kwargs: Any) -> dict[str, AgentTool]:
    """Create all tools configured for a working directory."""
    return {
        "read": ReadTool(cwd),
        "bash": BashTool(cwd),
        "edit": EditTool(cwd),
        "write": WriteTool(cwd),
        "grep": GrepTool(cwd),
        "find": FindTool(cwd),
        "ls": LsTool(cwd),
    }


__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_LINES",
    "BashTool",
    "EditTool",
    "FindTool",
    "GrepTool",
    "LsTool",
    "ReadTool",
    "ToolName",
    "TruncationResult",
    "WriteTool",
    "create_all_tools",
    "create_coding_tools",
    "create_read_only_tools",
    "format_size",
    "truncate_head",
    "truncate_line",
    "truncate_tail",
]
