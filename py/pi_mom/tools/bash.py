"""Bash execution tool — port of packages/mom/src/tools/bash.ts."""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent
from pi_mom.sandbox import Executor
from pi_mom.tools.truncate import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES, format_size, truncate_tail


class BashTool(AgentTool):
    """Execute bash commands through the configured sandbox executor."""

    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    @property
    def name(self) -> str:
        return "bash"

    @property
    def label(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return (
            f"Execute a bash command in the current working directory. Returns stdout and stderr. "
            f"Output is truncated to last {DEFAULT_MAX_LINES} lines or {DEFAULT_MAX_BYTES // 1024}KB "
            f"(whichever is hit first). If truncated, full output is saved to a temp file. "
            f"Optionally provide a timeout in seconds."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Brief description of what this command does (shown to user)",
                },
                "command": {
                    "type": "string",
                    "description": "Bash command to execute",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (optional, no default timeout)",
                },
            },
            "required": ["label", "command"],
        }

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        command: str = params["command"]
        timeout: int | None = params.get("timeout")

        result = await self._executor.exec(command, timeout=timeout, signal=signal)

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr

        total_bytes = len(output.encode("utf-8"))

        # Write to temp file if output exceeds limit
        temp_file_path: str | None = None
        if total_bytes > DEFAULT_MAX_BYTES:
            fd, temp_file_path = tempfile.mkstemp(prefix="mom-bash-", suffix=".log")
            try:
                os.write(fd, output.encode("utf-8"))
            finally:
                os.close(fd)

        # Apply tail truncation
        truncation = truncate_tail(output)
        output_text = truncation.content or "(no output)"

        details: dict[str, Any] | None = None

        if truncation.truncated:
            details = {
                "truncation": truncation,
                "fullOutputPath": temp_file_path,
            }

            start_line = truncation.total_lines - truncation.output_lines + 1
            end_line = truncation.total_lines

            if truncation.last_line_partial:
                last_line = output.split("\n")[-1] if "\n" in output else output
                last_line_size = format_size(len(last_line.encode("utf-8")))
                output_text += (
                    f"\n\n[Showing last {format_size(truncation.output_bytes)} of line {end_line} "
                    f"(line is {last_line_size}). Full output: {temp_file_path}]"
                )
            elif truncation.truncated_by == "lines":
                output_text += (
                    f"\n\n[Showing lines {start_line}-{end_line} of {truncation.total_lines}. "
                    f"Full output: {temp_file_path}]"
                )
            else:
                output_text += (
                    f"\n\n[Showing lines {start_line}-{end_line} of {truncation.total_lines} "
                    f"({format_size(DEFAULT_MAX_BYTES)} limit). Full output: {temp_file_path}]"
                )

        if result.code != 0:
            raise RuntimeError(f"{output_text}\n\nCommand exited with code {result.code}".strip())

        return AgentToolResult(
            content=[TextContent(text=output_text)],
            details=details,
        )
