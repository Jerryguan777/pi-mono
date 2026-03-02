"""Bash tool — execute commands with timeout and output truncation."""

from __future__ import annotations

import asyncio
import os
import signal
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent
from pi_tools.truncate import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES, format_size, truncate_tail


class BashTool(AgentTool):
    def __init__(self, cwd: str):
        self.name = "bash"
        self.label = "bash"
        self.description = (
            f"Execute a bash command. Output is truncated to last {DEFAULT_MAX_LINES} lines "
            f"or {DEFAULT_MAX_BYTES // 1024}KB. Optionally provide a timeout in seconds."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command to execute"},
                "timeout": {"type": "number", "description": "Timeout in seconds (optional)"},
            },
            "required": ["command"],
        }
        self.cwd = cwd

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        command = params["command"]
        timeout = params.get("timeout")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.cwd,
                env={**os.environ},
                start_new_session=True,
            )

            try:
                stdout_data, _ = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    proc.kill()
                try:
                    await asyncio.wait_for(proc.communicate(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
                raise ValueError(f"Command timed out after {timeout} seconds")

            output = stdout_data.decode("utf-8", errors="replace") if stdout_data else ""

            # Apply tail truncation
            truncation = truncate_tail(output)
            output_text = truncation.content or "(no output)"

            if truncation.truncated:
                start_line = truncation.total_lines - truncation.output_lines + 1
                end_line = truncation.total_lines
                if truncation.truncated_by == "lines":
                    output_text += f"\n\n[Showing lines {start_line}-{end_line} of {truncation.total_lines}.]"
                else:
                    output_text += (
                        f"\n\n[Showing lines {start_line}-{end_line} of {truncation.total_lines} "
                        f"({format_size(DEFAULT_MAX_BYTES)} limit).]"
                    )

            exit_code = proc.returncode
            if exit_code and exit_code != 0:
                output_text += f"\n\nCommand exited with code {exit_code}"
                raise ValueError(output_text)

            return AgentToolResult(
                content=[TextContent(text=output_text)],
                details={"truncation": truncation if truncation.truncated else None},
            )

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(str(e)) from e
