"""Find tool — find files by glob pattern."""

from __future__ import annotations

import asyncio
import glob
import os
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent
from pi_tools.path_utils import resolve_to_cwd
from pi_tools.truncate import DEFAULT_MAX_BYTES


class FindTool(AgentTool):
    def __init__(self, cwd: str):
        self.name = "find"
        self.label = "find"
        self.description = (
            "Find files by glob pattern. Respects .gitignore. "
            "Max 1000 results. Use ** for recursive matching."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
                "path": {"type": "string", "description": "Directory to search in"},
                "max_results": {"type": "number", "description": "Maximum results (default 1000)"},
            },
            "required": ["pattern"],
        }
        self.cwd = cwd

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        pattern = params["pattern"]
        search_path = resolve_to_cwd(params.get("path", "."), self.cwd)
        max_results = int(params.get("max_results", 1000))

        # Try fd first, fall back to glob
        try:
            return await self._fd_search(pattern, search_path, max_results)
        except FileNotFoundError:
            return await self._glob_search(pattern, search_path, max_results)

    async def _fd_search(
        self,
        pattern: str,
        search_path: str,
        max_results: int,
    ) -> AgentToolResult:
        """Use fd for fast file finding."""
        cmd = ["fd", "--glob", pattern, search_path, "--max-results", str(max_results)]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        if proc.returncode not in (0, 1):
            error = stderr.decode("utf-8", errors="replace") if stderr else "Unknown error"
            raise ValueError(f"Find failed: {error}")

        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        if not output.strip():
            return AgentToolResult(content=[TextContent(text="No files found.")])

        # Make paths relative and truncate
        lines = []
        total_bytes = 0
        for line in output.splitlines():
            try:
                rel = os.path.relpath(line.strip(), self.cwd)
            except ValueError:
                rel = line.strip()
            lines.append(rel)
            total_bytes += len(rel.encode("utf-8")) + 1
            if total_bytes > DEFAULT_MAX_BYTES:
                lines.append(f"[Truncated at {DEFAULT_MAX_BYTES // 1024}KB]")
                break

        return AgentToolResult(content=[TextContent(text="\n".join(lines))])

    async def _glob_search(
        self,
        pattern: str,
        search_path: str,
        max_results: int,
    ) -> AgentToolResult:
        """Fallback to Python glob."""
        full_pattern = os.path.join(search_path, pattern)
        matches = glob.glob(full_pattern, recursive=True)
        matches.sort()
        matches = matches[:max_results]

        if not matches:
            return AgentToolResult(content=[TextContent(text="No files found.")])

        lines = []
        total_bytes = 0
        for match in matches:
            try:
                rel = os.path.relpath(match, self.cwd)
            except ValueError:
                rel = match
            lines.append(rel)
            total_bytes += len(rel.encode("utf-8")) + 1
            if total_bytes > DEFAULT_MAX_BYTES:
                lines.append(f"[Truncated at {DEFAULT_MAX_BYTES // 1024}KB]")
                break

        return AgentToolResult(content=[TextContent(text="\n".join(lines))])
