"""Tools package for pi_mom — port of packages/mom/src/tools/index.ts."""

from __future__ import annotations

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
    "create_mom_tools",
]


def create_mom_tools(executor: Executor, workspace_root: str) -> list[AgentTool]:
    """Create the standard set of mom tools for the given executor."""
    return [
        ReadTool(executor),
        BashTool(executor),
        EditTool(executor),
        WriteTool(executor),
        AttachTool(workspace_root),
    ]
