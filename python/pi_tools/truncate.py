"""Shared truncation utilities for tool outputs."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_BYTES = 50 * 1024  # 50KB
GREP_MAX_LINE_LENGTH = 500


@dataclass
class TruncationResult:
    content: str
    truncated: bool
    truncated_by: str | None  # "lines", "bytes", or None
    total_lines: int
    total_bytes: int
    output_lines: int
    output_bytes: int
    last_line_partial: bool = False
    first_line_exceeds_limit: bool = False
    max_lines: int = DEFAULT_MAX_LINES
    max_bytes: int = DEFAULT_MAX_BYTES


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def truncate_head(
    content: str,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TruncationResult:
    """Truncate from head (keep first N lines/bytes). For file reads."""
    total_bytes = len(content.encode("utf-8"))
    lines = content.split("\n")
    total_lines = len(lines)

    if total_lines <= max_lines and total_bytes <= max_bytes:
        return TruncationResult(
            content=content, truncated=False, truncated_by=None,
            total_lines=total_lines, total_bytes=total_bytes,
            output_lines=total_lines, output_bytes=total_bytes,
            max_lines=max_lines, max_bytes=max_bytes,
        )

    # Check if first line exceeds byte limit
    first_line_bytes = len(lines[0].encode("utf-8"))
    if first_line_bytes > max_bytes:
        return TruncationResult(
            content="", truncated=True, truncated_by="bytes",
            total_lines=total_lines, total_bytes=total_bytes,
            output_lines=0, output_bytes=0,
            first_line_exceeds_limit=True,
            max_lines=max_lines, max_bytes=max_bytes,
        )

    output_lines_arr: list[str] = []
    output_bytes_count = 0
    truncated_by = "lines"

    for i, line in enumerate(lines):
        if i >= max_lines:
            break
        line_bytes = len(line.encode("utf-8")) + (1 if i > 0 else 0)
        if output_bytes_count + line_bytes > max_bytes:
            truncated_by = "bytes"
            break
        output_lines_arr.append(line)
        output_bytes_count += line_bytes

    if len(output_lines_arr) >= max_lines and output_bytes_count <= max_bytes:
        truncated_by = "lines"

    output_content = "\n".join(output_lines_arr)
    final_bytes = len(output_content.encode("utf-8"))

    return TruncationResult(
        content=output_content, truncated=True, truncated_by=truncated_by,
        total_lines=total_lines, total_bytes=total_bytes,
        output_lines=len(output_lines_arr), output_bytes=final_bytes,
        max_lines=max_lines, max_bytes=max_bytes,
    )


def truncate_tail(
    content: str,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TruncationResult:
    """Truncate from tail (keep last N lines/bytes). For bash output."""
    total_bytes = len(content.encode("utf-8"))
    lines = content.split("\n")
    total_lines = len(lines)

    if total_lines <= max_lines and total_bytes <= max_bytes:
        return TruncationResult(
            content=content, truncated=False, truncated_by=None,
            total_lines=total_lines, total_bytes=total_bytes,
            output_lines=total_lines, output_bytes=total_bytes,
            max_lines=max_lines, max_bytes=max_bytes,
        )

    output_lines_arr: list[str] = []
    output_bytes_count = 0
    truncated_by = "lines"
    last_line_partial = False

    for i in range(len(lines) - 1, -1, -1):
        if len(output_lines_arr) >= max_lines:
            break
        line = lines[i]
        line_bytes = len(line.encode("utf-8")) + (1 if output_lines_arr else 0)

        if output_bytes_count + line_bytes > max_bytes:
            truncated_by = "bytes"
            if not output_lines_arr:
                # Take end of line (partial)
                truncated_line = _truncate_string_from_end(line, max_bytes)
                output_lines_arr.insert(0, truncated_line)
                output_bytes_count = len(truncated_line.encode("utf-8"))
                last_line_partial = True
            break

        output_lines_arr.insert(0, line)
        output_bytes_count += line_bytes

    if len(output_lines_arr) >= max_lines and output_bytes_count <= max_bytes:
        truncated_by = "lines"

    output_content = "\n".join(output_lines_arr)
    final_bytes = len(output_content.encode("utf-8"))

    return TruncationResult(
        content=output_content, truncated=True, truncated_by=truncated_by,
        total_lines=total_lines, total_bytes=total_bytes,
        output_lines=len(output_lines_arr), output_bytes=final_bytes,
        last_line_partial=last_line_partial,
        max_lines=max_lines, max_bytes=max_bytes,
    )


def _truncate_string_from_end(s: str, max_bytes: int) -> str:
    """Truncate a string to fit within byte limit, keeping the end."""
    buf = s.encode("utf-8")
    if len(buf) <= max_bytes:
        return s
    start = len(buf) - max_bytes
    # Find valid UTF-8 boundary
    while start < len(buf) and (buf[start] & 0xC0) == 0x80:
        start += 1
    return buf[start:].decode("utf-8")


def truncate_line(line: str, max_chars: int = GREP_MAX_LINE_LENGTH) -> tuple[str, bool]:
    """Truncate a single line, returning (text, was_truncated)."""
    if len(line) <= max_chars:
        return line, False
    return f"{line[:max_chars]}... [truncated]", True
