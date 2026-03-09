"""Shared utility for truncating text to visual lines (accounting for line wrapping).

Used by tool_execution.py and bash_execution.py for consistent behavior.
"""

from __future__ import annotations

from dataclasses import dataclass

from pi_tui.components.text import Text


@dataclass
class VisualTruncateResult:
    """Result of a visual truncation operation."""

    visual_lines: list[str]
    """The visual lines to display."""
    skipped_count: int
    """Number of visual lines that were skipped (hidden)."""


def truncate_to_visual_lines(
    text: str,
    max_visual_lines: int,
    width: int,
    padding_x: int = 0,
) -> VisualTruncateResult:
    """Truncate text to a maximum number of visual lines (from the end).

    This accounts for line wrapping based on terminal width.

    Args:
        text: The text content (may contain newlines).
        max_visual_lines: Maximum number of visual lines to show.
        width: Terminal/render width.
        padding_x: Horizontal padding for Text component (default 0).
                   Use 0 when result will be placed in a Box (Box adds its own padding).
                   Use 1 when result will be placed in a plain Container.

    Returns:
        The truncated visual lines and count of skipped lines.
    """
    if not text:
        return VisualTruncateResult(visual_lines=[], skipped_count=0)

    temp_text = Text(text, padding_x, 0)
    all_visual_lines = temp_text.render(width)

    if len(all_visual_lines) <= max_visual_lines:
        return VisualTruncateResult(visual_lines=all_visual_lines, skipped_count=0)

    truncated_lines = all_visual_lines[-max_visual_lines:]
    skipped_count = len(all_visual_lines) - max_visual_lines

    return VisualTruncateResult(visual_lines=truncated_lines, skipped_count=skipped_count)
