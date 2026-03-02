"""Read tool — read file contents with truncation."""

from __future__ import annotations

import os
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import ImageContent, TextContent
from pi_tools.path_utils import resolve_to_cwd
from pi_tools.truncate import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES, format_size, truncate_head


class ReadTool(AgentTool):
    def __init__(self, cwd: str):
        self.name = "read"
        self.label = "read"
        self.description = (
            f"Read file contents. Output truncated to {DEFAULT_MAX_LINES} lines or "
            f"{DEFAULT_MAX_BYTES // 1024}KB. Use offset/limit for large files."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read"},
                "offset": {"type": "number", "description": "Line number to start from (1-indexed)"},
                "limit": {"type": "number", "description": "Maximum number of lines to read"},
            },
            "required": ["path"],
        }
        self.cwd = cwd

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        path = params["path"]
        offset = params.get("offset")
        limit = params.get("limit")

        absolute_path = resolve_to_cwd(path, self.cwd)

        if not os.path.exists(absolute_path):
            raise FileNotFoundError(f"File not found: {path}")

        if not os.path.isfile(absolute_path):
            raise ValueError(f"Not a file: {path}")

        # Check if it's an image
        ext = os.path.splitext(absolute_path)[1].lower()
        image_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                       ".gif": "image/gif", ".webp": "image/webp"}

        if ext in image_types:
            import base64
            with open(absolute_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            mime_type = image_types[ext]
            return AgentToolResult(
                content=[
                    TextContent(text=f"Read image file [{mime_type}]"),
                    ImageContent(data=data, mime_type=mime_type),
                ],
            )

        # Read as text
        with open(absolute_path, "r", encoding="utf-8", errors="replace") as f:
            text_content = f.read()

        all_lines = text_content.split("\n")
        total_lines = len(all_lines)

        # Apply offset (1-indexed to 0-indexed)
        start_line = max(0, (offset or 1) - 1)
        start_display = start_line + 1

        if start_line >= len(all_lines):
            raise ValueError(f"Offset {offset} is beyond end of file ({total_lines} lines total)")

        # Apply limit
        if limit is not None:
            end_line = min(start_line + int(limit), len(all_lines))
            selected = "\n".join(all_lines[start_line:end_line])
            user_limited_lines = end_line - start_line
        else:
            selected = "\n".join(all_lines[start_line:])
            user_limited_lines = None

        # Apply truncation
        truncation = truncate_head(selected)

        if truncation.first_line_exceeds_limit:
            first_line_size = format_size(len(all_lines[start_line].encode("utf-8")))
            output_text = (
                f"[Line {start_display} is {first_line_size}, exceeds {format_size(DEFAULT_MAX_BYTES)} limit. "
                f"Use bash: sed -n '{start_display}p' {path} | head -c {DEFAULT_MAX_BYTES}]"
            )
        elif truncation.truncated:
            end_display = start_display + truncation.output_lines - 1
            next_offset = end_display + 1
            output_text = truncation.content
            if truncation.truncated_by == "lines":
                output_text += f"\n\n[Showing lines {start_display}-{end_display} of {total_lines}. Use offset={next_offset} to continue.]"
            else:
                output_text += (
                    f"\n\n[Showing lines {start_display}-{end_display} of {total_lines} "
                    f"({format_size(DEFAULT_MAX_BYTES)} limit). Use offset={next_offset} to continue.]"
                )
        elif user_limited_lines is not None and start_line + user_limited_lines < len(all_lines):
            remaining = len(all_lines) - (start_line + user_limited_lines)
            next_offset = start_line + user_limited_lines + 1
            output_text = truncation.content
            output_text += f"\n\n[{remaining} more lines in file. Use offset={next_offset} to continue.]"
        else:
            output_text = truncation.content

        return AgentToolResult(content=[TextContent(text=output_text)])
