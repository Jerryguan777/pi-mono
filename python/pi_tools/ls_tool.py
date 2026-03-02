"""Ls tool — list directory contents."""

from __future__ import annotations

import os
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent
from pi_tools.path_utils import resolve_to_cwd
from pi_tools.truncate import DEFAULT_MAX_BYTES


class LsTool(AgentTool):
    def __init__(self, cwd: str):
        self.name = "ls"
        self.label = "ls"
        self.description = "List directory contents. Includes dotfiles. Max 500 entries."
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: current dir)"},
            },
            "required": [],
        }
        self.cwd = cwd

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        path = resolve_to_cwd(params.get("path", "."), self.cwd)

        if not os.path.exists(path):
            raise FileNotFoundError(f"Directory not found: {params.get('path', '.')}")

        if not os.path.isdir(path):
            raise ValueError(f"Not a directory: {params.get('path', '.')}")

        entries = os.listdir(path)
        entries.sort(key=str.lower)

        # Limit entries
        max_entries = 500
        truncated = len(entries) > max_entries
        entries = entries[:max_entries]

        # Format with directory indicator
        lines = []
        total_bytes = 0
        for entry in entries:
            full_path = os.path.join(path, entry)
            suffix = "/" if os.path.isdir(full_path) else ""
            line = f"{entry}{suffix}"
            lines.append(line)
            total_bytes += len(line.encode("utf-8")) + 1
            if total_bytes > DEFAULT_MAX_BYTES:
                lines.append(f"[Truncated at {DEFAULT_MAX_BYTES // 1024}KB]")
                break

        if truncated:
            lines.append(f"[Showing {max_entries} of {len(os.listdir(path))} entries]")

        return AgentToolResult(content=[TextContent(text="\n".join(lines))])
