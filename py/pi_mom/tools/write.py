"""File write tool — port of packages/mom/src/tools/write.ts."""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent
from pi_mom.sandbox import Executor


class WriteTool(AgentTool):
    """Write content to a file, creating parent directories as needed."""

    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    @property
    def name(self) -> str:
        return "write"

    @property
    def label(self) -> str:
        return "write"

    @property
    def description(self) -> str:
        return (
            "Write content to a file. Creates the file if it doesn't exist, "
            "overwrites if it does. Automatically creates parent directories."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Brief description of what you're writing (shown to user)",
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file to write (relative or absolute)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["label", "path", "content"],
        }

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        path: str = params["path"]
        content: str = params["content"]

        # Determine parent directory
        dir_path = path[: path.rfind("/")] if "/" in path else "."

        cmd = f"mkdir -p {shlex.quote(dir_path)} && printf '%s' {shlex.quote(content)} > {shlex.quote(path)}"
        result = await self._executor.exec(cmd, signal=signal)
        if result.code != 0:
            raise RuntimeError(result.stderr or f"Failed to write file: {path}")

        return AgentToolResult(
            content=[TextContent(text=f"Successfully wrote {len(content)} bytes to {path}")],
            details=None,
        )
