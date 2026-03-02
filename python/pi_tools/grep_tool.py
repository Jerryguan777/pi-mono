"""Grep tool — search file contents using ripgrep."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent
from pi_tools.path_utils import resolve_to_cwd
from pi_tools.truncate import DEFAULT_MAX_BYTES, GREP_MAX_LINE_LENGTH, truncate_line


class GrepTool(AgentTool):
    def __init__(self, cwd: str):
        self.name = "grep"
        self.label = "grep"
        self.description = (
            "Search file contents using regex. Uses ripgrep (rg) if available. "
            "Respects .gitignore. Max 100 matches, lines truncated to 500 chars."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "Directory or file to search in"},
                "glob": {"type": "string", "description": "Glob pattern to filter files (e.g. '*.py')"},
                "case_insensitive": {"type": "boolean", "description": "Case insensitive search"},
                "context": {"type": "number", "description": "Lines of context around matches"},
                "max_matches": {"type": "number", "description": "Maximum matches (default 100)"},
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
        glob_pattern = params.get("glob")
        case_insensitive = params.get("case_insensitive", False)
        context_lines = params.get("context", 0)
        max_matches = params.get("max_matches", 100)

        # Build rg command
        cmd = ["rg", "--json", "--no-heading"]

        if case_insensitive:
            cmd.append("-i")

        if context_lines:
            cmd.extend(["-C", str(int(context_lines))])

        cmd.extend(["-m", str(max_matches)])

        if glob_pattern:
            cmd.extend(["--glob", glob_pattern])

        cmd.append(pattern)
        cmd.append(search_path)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except FileNotFoundError:
            # rg not found, fall back to grep
            return await self._grep_fallback(pattern, search_path, glob_pattern, case_insensitive, max_matches)
        except asyncio.TimeoutError:
            raise ValueError("Search timed out after 30 seconds")

        if proc.returncode not in (0, 1):  # 1 = no matches
            error = stderr.decode("utf-8", errors="replace") if stderr else "Unknown error"
            raise ValueError(f"Search failed: {error}")

        if proc.returncode == 1:
            return AgentToolResult(content=[TextContent(text="No matches found.")])

        # Parse rg JSON output
        output_lines: list[str] = []
        total_bytes = 0

        for line in stdout.decode("utf-8", errors="replace").splitlines():
            if total_bytes > DEFAULT_MAX_BYTES:
                output_lines.append(f"\n[Output truncated at {DEFAULT_MAX_BYTES // 1024}KB]")
                break

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "match":
                match_data = data.get("data", {})
                file_path = match_data.get("path", {}).get("text", "")
                line_num = match_data.get("line_number", 0)
                text = match_data.get("lines", {}).get("text", "").rstrip("\n")

                # Make path relative
                try:
                    rel_path = os.path.relpath(file_path, self.cwd)
                except ValueError:
                    rel_path = file_path

                truncated_text, _ = truncate_line(text, GREP_MAX_LINE_LENGTH)
                result_line = f"{rel_path}:{line_num}:{truncated_text}"
                output_lines.append(result_line)
                total_bytes += len(result_line.encode("utf-8"))

        if not output_lines:
            return AgentToolResult(content=[TextContent(text="No matches found.")])

        return AgentToolResult(content=[TextContent(text="\n".join(output_lines))])

    async def _grep_fallback(
        self,
        pattern: str,
        search_path: str,
        glob_pattern: str | None,
        case_insensitive: bool,
        max_matches: int,
    ) -> AgentToolResult:
        """Fallback to grep -rn when rg is not available."""
        cmd = ["grep", "-rn"]
        if case_insensitive:
            cmd.append("-i")
        cmd.extend(["-m", str(max_matches)])
        if glob_pattern:
            cmd.extend(["--include", glob_pattern])
        cmd.append(pattern)
        cmd.append(search_path)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)

        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        if not output.strip():
            return AgentToolResult(content=[TextContent(text="No matches found.")])

        # Truncate lines
        result_lines = []
        for line in output.splitlines()[:max_matches]:
            truncated, _ = truncate_line(line, GREP_MAX_LINE_LENGTH)
            result_lines.append(truncated)

        return AgentToolResult(content=[TextContent(text="\n".join(result_lines))])
