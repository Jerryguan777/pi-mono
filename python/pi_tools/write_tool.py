"""Write tool — write content to files."""

from __future__ import annotations

import os
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent
from pi_tools.path_utils import resolve_to_cwd


class WriteTool(AgentTool):
    def __init__(self, cwd: str):
        self.name = "write"
        self.label = "write"
        self.description = (
            "Write content to a file. Creates the file if it doesn't exist, "
            "overwrites if it does. Automatically creates parent directories."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
        }
        self.cwd = cwd

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        path = params["path"]
        content = params["content"]

        absolute_path = resolve_to_cwd(path, self.cwd)
        dir_path = os.path.dirname(absolute_path)

        os.makedirs(dir_path, exist_ok=True)

        with open(absolute_path, "w", encoding="utf-8") as f:
            f.write(content)

        return AgentToolResult(
            content=[TextContent(text=f"Successfully wrote {len(content)} bytes to {path}")],
        )
