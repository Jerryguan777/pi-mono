"""File read tool — port of packages/mom/src/tools/read.ts."""

from __future__ import annotations

import asyncio
import os
import shlex
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import ImageContent, TextContent
from pi_mom.sandbox import Executor
from pi_mom.tools.truncate import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES, format_size, truncate_head

_IMAGE_MIME_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _is_image_file(file_path: str) -> str | None:
    """Return the MIME type if the file is a supported image, else None."""
    ext = os.path.splitext(file_path)[1].lower()
    return _IMAGE_MIME_TYPES.get(ext)


class ReadTool(AgentTool):
    """Read the contents of a file (text or image)."""

    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    @property
    def name(self) -> str:
        return "read"

    @property
    def label(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return (
            f"Read the contents of a file. Supports text files and images (jpg, png, gif, webp). "
            f"Images are sent as attachments. For text files, output is truncated to "
            f"{DEFAULT_MAX_LINES} lines or {DEFAULT_MAX_BYTES // 1024}KB (whichever is hit first). "
            f"Use offset/limit for large files."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Brief description of what you're reading and why (shown to user)",
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative or absolute)",
                },
                "offset": {
                    "type": "number",
                    "description": "Line number to start reading from (1-indexed)",
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum number of lines to read",
                },
            },
            "required": ["label", "path"],
        }

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        path: str = params["path"]
        offset: int | None = params.get("offset")
        limit: int | None = params.get("limit")

        mime_type = _is_image_file(path)

        if mime_type:
            # Read as image (binary) - use base64
            result = await self._executor.exec(f"base64 < {shlex.quote(path)}", signal=signal)
            if result.code != 0:
                raise RuntimeError(result.stderr or f"Failed to read file: {path}")
            base64_data = result.stdout.replace("\n", "").replace("\r", "").replace(" ", "")
            return AgentToolResult(
                content=[
                    TextContent(text=f"Read image file [{mime_type}]"),
                    ImageContent(data=base64_data, mime_type=mime_type),
                ],
                details=None,
            )

        # Get total line count first
        count_result = await self._executor.exec(f"wc -l < {shlex.quote(path)}", signal=signal)
        if count_result.code != 0:
            raise RuntimeError(count_result.stderr or f"Failed to read file: {path}")
        # wc -l counts newlines, not lines
        total_file_lines = int(count_result.stdout.strip()) + 1

        # Apply offset if specified (1-indexed)
        start_line = max(1, offset) if offset else 1

        if start_line > total_file_lines:
            raise RuntimeError(f"Offset {offset} is beyond end of file ({total_file_lines} lines total)")

        # Read content with offset
        cmd = f"cat {shlex.quote(path)}" if start_line == 1 else f"tail -n +{start_line} {shlex.quote(path)}"

        result = await self._executor.exec(cmd, signal=signal)
        if result.code != 0:
            raise RuntimeError(result.stderr or f"Failed to read file: {path}")

        selected_content = result.stdout
        user_limited_lines: int | None = None

        # Apply user limit if specified
        if limit is not None:
            file_lines = selected_content.split("\n")
            end_line = min(limit, len(file_lines))
            selected_content = "\n".join(file_lines[:end_line])
            user_limited_lines = end_line

        # Apply truncation (respects both line and byte limits)
        truncation = truncate_head(selected_content)

        output_text: str
        details: dict[str, Any] | None = None

        if truncation.first_line_exceeds_limit:
            first_line = selected_content.split("\n")[0] if selected_content else ""
            first_line_size = format_size(len(first_line.encode("utf-8")))
            output_text = (
                f"[Line {start_line} is {first_line_size}, exceeds {format_size(DEFAULT_MAX_BYTES)} limit. "
                f"Use bash: sed -n '{start_line}p' {path} | head -c {DEFAULT_MAX_BYTES}]"
            )
            details = {"truncation": truncation}
        elif truncation.truncated:
            end_line_display = start_line + truncation.output_lines - 1
            next_offset = end_line_display + 1

            output_text = truncation.content
            if truncation.truncated_by == "lines":
                output_text += (
                    f"\n\n[Showing lines {start_line}-{end_line_display} of {total_file_lines}. "
                    f"Use offset={next_offset} to continue]"
                )
            else:
                output_text += (
                    f"\n\n[Showing lines {start_line}-{end_line_display} of {total_file_lines} "
                    f"({format_size(DEFAULT_MAX_BYTES)} limit). Use offset={next_offset} to continue]"
                )
            details = {"truncation": truncation}
        elif user_limited_lines is not None:
            lines_from_start = (start_line - 1) + user_limited_lines
            if lines_from_start < total_file_lines:
                remaining = total_file_lines - lines_from_start
                next_offset = start_line + user_limited_lines
                output_text = truncation.content
                output_text += f"\n\n[{remaining} more lines in file. Use offset={next_offset} to continue]"
            else:
                output_text = truncation.content
        else:
            output_text = truncation.content

        return AgentToolResult(
            content=[TextContent(text=output_text)],
            details=details,
        )
