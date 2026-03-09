"""File edit tool — port of packages/mom/src/tools/edit.ts."""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent
from pi_mom.sandbox import Executor


def _generate_diff_string(old_content: str, new_content: str, context_lines: int = 4) -> str:
    """Generate a simple unified diff string with line numbers and context."""
    old_lines = old_content.split("\n")
    new_lines = new_content.split("\n")

    # Find changed regions using a simple LCS-based comparison
    import difflib

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    output: list[str] = []
    line_num_width = max(len(str(len(old_lines))), len(str(len(new_lines))))

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            # Show context lines around changes
            pass
        elif tag in ("replace", "delete", "insert"):
            # Show removed lines
            for i in range(i1, i2):
                line_num = str(i + 1).rjust(line_num_width)
                output.append(f"-{line_num} {old_lines[i]}")
            # Show added lines
            for j in range(j1, j2):
                line_num = str(j + 1).rjust(line_num_width)
                output.append(f"+{line_num} {new_lines[j]}")

    # If no explicit diff parts were output, produce a minimal summary
    if not output:
        output.append("(no diff)")

    return "\n".join(output)


class EditTool(AgentTool):
    """Edit a file by replacing exact text."""

    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    @property
    def name(self) -> str:
        return "edit"

    @property
    def label(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return (
            "Edit a file by replacing exact text. The oldText must match exactly "
            "(including whitespace). Use this for precise, surgical edits."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Brief description of the edit you're making (shown to user)",
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit (relative or absolute)",
                },
                "oldText": {
                    "type": "string",
                    "description": "Exact text to find and replace (must match exactly)",
                },
                "newText": {
                    "type": "string",
                    "description": "New text to replace the old text with",
                },
            },
            "required": ["label", "path", "oldText", "newText"],
        }

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        path: str = params["path"]
        old_text: str = params["oldText"]
        new_text: str = params["newText"]

        # Read the file
        read_result = await self._executor.exec(f"cat {shlex.quote(path)}", signal=signal)
        if read_result.code != 0:
            raise RuntimeError(read_result.stderr or f"File not found: {path}")

        content = read_result.stdout

        # Check if old text exists
        if old_text not in content:
            raise RuntimeError(
                f"Could not find the exact text in {path}. "
                "The old text must match exactly including all whitespace and newlines."
            )

        # Count occurrences
        occurrences = content.count(old_text)
        if occurrences > 1:
            raise RuntimeError(
                f"Found {occurrences} occurrences of the text in {path}. "
                "The text must be unique. Please provide more context to make it unique."
            )

        # Perform replacement
        idx = content.index(old_text)
        new_content = content[:idx] + new_text + content[idx + len(old_text) :]

        if content == new_content:
            raise RuntimeError(
                f"No changes made to {path}. The replacement produced identical content. "
                "This might indicate an issue with special characters or the text not existing as expected."
            )

        # Write the file back
        write_result = await self._executor.exec(
            f"printf '%s' {shlex.quote(new_content)} > {shlex.quote(path)}",
            signal=signal,
        )
        if write_result.code != 0:
            raise RuntimeError(write_result.stderr or f"Failed to write file: {path}")

        diff_str = _generate_diff_string(content, new_content)

        return AgentToolResult(
            content=[
                TextContent(
                    text=(
                        f"Successfully replaced text in {path}. "
                        f"Changed {len(old_text)} characters to {len(new_text)} characters."
                    )
                )
            ],
            details={"diff": diff_str},
        )
