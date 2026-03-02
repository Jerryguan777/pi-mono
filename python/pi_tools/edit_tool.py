"""Edit tool — replace text in files with fuzzy matching."""

from __future__ import annotations

import os
from typing import Any

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent
from pi_tools.edit_diff import (
    detect_line_ending,
    fuzzy_find_text,
    generate_diff_string,
    normalize_for_fuzzy_match,
    normalize_to_lf,
    restore_line_endings,
    strip_bom,
)
from pi_tools.path_utils import resolve_to_cwd


class EditTool(AgentTool):
    def __init__(self, cwd: str):
        self.name = "edit"
        self.label = "edit"
        self.description = (
            "Edit a file by replacing exact text. The oldText must match exactly "
            "(including whitespace). Use this for precise, surgical edits."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to edit"},
                "oldText": {"type": "string", "description": "Exact text to find and replace"},
                "newText": {"type": "string", "description": "New text to replace with"},
            },
            "required": ["path", "oldText", "newText"],
        }
        self.cwd = cwd

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        path = params["path"]
        old_text = params["oldText"]
        new_text = params["newText"]

        absolute_path = resolve_to_cwd(path, self.cwd)

        if not os.path.exists(absolute_path):
            raise FileNotFoundError(f"File not found: {path}")

        with open(absolute_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # Strip BOM
        bom, content = strip_bom(raw_content)
        original_ending = detect_line_ending(content)
        normalized_content = normalize_to_lf(content)
        normalized_old = normalize_to_lf(old_text)
        normalized_new = normalize_to_lf(new_text)

        # Find text with fuzzy matching
        match_result = fuzzy_find_text(normalized_content, normalized_old)

        if not match_result.found:
            raise ValueError(
                f"Could not find the exact text in {path}. "
                "The old text must match exactly including all whitespace and newlines."
            )

        # Check for multiple occurrences
        fuzzy_content = normalize_for_fuzzy_match(normalized_content)
        fuzzy_old = normalize_for_fuzzy_match(normalized_old)
        occurrences = fuzzy_content.count(fuzzy_old)

        if occurrences > 1:
            raise ValueError(
                f"Found {occurrences} occurrences of the text in {path}. "
                "The text must be unique. Please provide more context."
            )

        # Perform replacement
        base_content = match_result.content_for_replacement
        new_content = (
            base_content[:match_result.index]
            + normalized_new
            + base_content[match_result.index + match_result.match_length:]
        )

        if base_content == new_content:
            raise ValueError(
                f"No changes made to {path}. The replacement produced identical content."
            )

        final_content = bom + restore_line_endings(new_content, original_ending)

        with open(absolute_path, "w", encoding="utf-8") as f:
            f.write(final_content)

        diff_result = generate_diff_string(base_content, new_content, path)

        return AgentToolResult(
            content=[TextContent(text=f"Successfully replaced text in {path}.")],
            details={"diff": diff_result["diff"], "first_changed_line": diff_result["first_changed_line"]},
        )
