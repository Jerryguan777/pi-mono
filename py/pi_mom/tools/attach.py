"""Attach tool for sharing files to Slack — port of packages/mom/src/tools/attach.ts."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent


class AttachTool(AgentTool):
    """Attach a file to the Slack response."""

    def __init__(self, workspace_root: str) -> None:
        # Resolve symlinks once so all comparisons are against a canonical path
        self._workspace_root = os.path.realpath(workspace_root)
        self._upload_fn: Callable[[str, str | None], Awaitable[None]] | None = None

    def set_upload_fn(self, fn: Callable[[str, str | None], Awaitable[None]]) -> None:
        """Set the upload function for the current run (called per-run, not globally)."""
        self._upload_fn = fn

    @property
    def name(self) -> str:
        return "attach"

    @property
    def label(self) -> str:
        return "attach"

    @property
    def description(self) -> str:
        return (
            "Attach a file to your response. Use this to share files, images, or documents with the user. "
            "Only files from /workspace/ can be attached."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Brief description of what you're sharing (shown to user)",
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file to attach",
                },
                "title": {
                    "type": "string",
                    "description": "Title for the file (defaults to filename)",
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
        if self._upload_fn is None:
            raise RuntimeError("Upload function not configured")

        if signal is not None and signal.is_set():
            raise RuntimeError("Operation aborted")

        path: str = params["path"]
        title: str | None = params.get("title")

        absolute_path = os.path.realpath(path)

        # Validate the resolved path is within the workspace directory
        workspace = self._workspace_root
        if absolute_path != workspace and not absolute_path.startswith(workspace + os.sep):
            raise RuntimeError(f"File must be within workspace directory ({workspace}), got: {path}")

        file_name = title or os.path.basename(absolute_path)
        await self._upload_fn(absolute_path, file_name)

        return AgentToolResult(
            content=[TextContent(text=f"Attached file: {file_name}")],
            details=None,
        )
