"""Shared truncation utilities for tool outputs — port of packages/mom/src/tools/truncate.ts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_BYTES = 50 * 1024  # 50 KB


@dataclass
class TruncationResult:
    """Result of a truncation operation."""

    content: str
    truncated: bool
    truncated_by: Literal["lines", "bytes"] | None
    total_lines: int
    total_bytes: int
    output_lines: int
    output_bytes: int
    last_line_partial: bool
    first_line_exceeds_limit: bool


def format_size(num_bytes: int) -> str:
    """Format a byte count as a human-readable size string."""
    if num_bytes < 1024:
        return f"{num_bytes}B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f}KB"
    return f"{num_bytes / (1024 * 1024):.1f}MB"


def truncate_head(
    content: str,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TruncationResult:
    """Truncate content from the head (keep first N lines/bytes).

    Suitable for file reads where you want to see the beginning.
    Never returns partial lines. If the first line exceeds the byte limit,
    returns empty content with first_line_exceeds_limit=True.
    """
    total_bytes = len(content.encode("utf-8"))
    lines = content.split("\n")
    total_lines = len(lines)

    # No truncation needed
    if total_lines <= max_lines and total_bytes <= max_bytes:
        return TruncationResult(
            content=content,
            truncated=False,
            truncated_by=None,
            total_lines=total_lines,
            total_bytes=total_bytes,
            output_lines=total_lines,
            output_bytes=total_bytes,
            last_line_partial=False,
            first_line_exceeds_limit=False,
        )

    # Check if first line alone exceeds byte limit
    first_line_bytes = len(lines[0].encode("utf-8"))
    if first_line_bytes > max_bytes:
        return TruncationResult(
            content="",
            truncated=True,
            truncated_by="bytes",
            total_lines=total_lines,
            total_bytes=total_bytes,
            output_lines=0,
            output_bytes=0,
            last_line_partial=False,
            first_line_exceeds_limit=True,
        )

    # Collect complete lines that fit
    output_lines_arr: list[str] = []
    output_bytes_count = 0
    truncated_by: Literal["lines", "bytes"] = "lines"

    for i, line in enumerate(lines):
        if i >= max_lines:
            break
        line_bytes = len(line.encode("utf-8")) + (1 if i > 0 else 0)  # +1 for newline

        if output_bytes_count + line_bytes > max_bytes:
            truncated_by = "bytes"
            break

        output_lines_arr.append(line)
        output_bytes_count += line_bytes

    # If we exited due to line limit
    if len(output_lines_arr) >= max_lines and output_bytes_count <= max_bytes:
        truncated_by = "lines"

    output_content = "\n".join(output_lines_arr)
    final_output_bytes = len(output_content.encode("utf-8"))

    return TruncationResult(
        content=output_content,
        truncated=True,
        truncated_by=truncated_by,
        total_lines=total_lines,
        total_bytes=total_bytes,
        output_lines=len(output_lines_arr),
        output_bytes=final_output_bytes,
        last_line_partial=False,
        first_line_exceeds_limit=False,
    )


def truncate_tail(
    content: str,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TruncationResult:
    """Truncate content from the tail (keep last N lines/bytes).

    Suitable for bash output where you want to see the end (errors, final results).
    May return a partial first line if the last line of the original content exceeds
    the byte limit.
    """
    total_bytes = len(content.encode("utf-8"))
    lines = content.split("\n")
    total_lines = len(lines)

    # No truncation needed
    if total_lines <= max_lines and total_bytes <= max_bytes:
        return TruncationResult(
            content=content,
            truncated=False,
            truncated_by=None,
            total_lines=total_lines,
            total_bytes=total_bytes,
            output_lines=total_lines,
            output_bytes=total_bytes,
            last_line_partial=False,
            first_line_exceeds_limit=False,
        )

    # Work backwards from the end
    output_lines_arr: list[str] = []
    output_bytes_count = 0
    truncated_by: Literal["lines", "bytes"] = "lines"
    last_line_partial = False

    for i in range(len(lines) - 1, -1, -1):
        if len(output_lines_arr) >= max_lines:
            break
        line = lines[i]
        line_bytes = len(line.encode("utf-8")) + (1 if output_lines_arr else 0)  # +1 for newline

        if output_bytes_count + line_bytes > max_bytes:
            truncated_by = "bytes"
            # Edge case: if we haven't added ANY lines yet and this line exceeds max_bytes,
            # take the end of the line (partial)
            if not output_lines_arr:
                truncated_line = _truncate_string_to_bytes_from_end(line, max_bytes)
                output_lines_arr.insert(0, truncated_line)
                output_bytes_count = len(truncated_line.encode("utf-8"))
                last_line_partial = True
            break

        output_lines_arr.insert(0, line)
        output_bytes_count += line_bytes

    # If we exited due to line limit
    if len(output_lines_arr) >= max_lines and output_bytes_count <= max_bytes:
        truncated_by = "lines"

    output_content = "\n".join(output_lines_arr)
    final_output_bytes = len(output_content.encode("utf-8"))

    return TruncationResult(
        content=output_content,
        truncated=True,
        truncated_by=truncated_by,
        total_lines=total_lines,
        total_bytes=total_bytes,
        output_lines=len(output_lines_arr),
        output_bytes=final_output_bytes,
        last_line_partial=last_line_partial,
        first_line_exceeds_limit=False,
    )


def _truncate_string_to_bytes_from_end(s: str, max_bytes: int) -> str:
    """Truncate a string to fit within a byte limit (from the end).

    Handles multi-byte UTF-8 characters correctly.
    """
    encoded = s.encode("utf-8")
    if len(encoded) <= max_bytes:
        return s

    # Start from the end, skip max_bytes back
    start = len(encoded) - max_bytes

    # Find a valid UTF-8 boundary (start of a character)
    while start < len(encoded) and (encoded[start] & 0xC0) == 0x80:
        start += 1

    return encoded[start:].decode("utf-8", errors="replace")
