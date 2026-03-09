"""Word-level diff rendering with ANSI color highlighting."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from pi_coding_agent.modes.interactive.components._theme import theme


@dataclass
class RenderDiffOptions:
    """Options for render_diff().

    Port of RenderDiffOptions from packages/coding-agent/src/modes/interactive/components/diff.ts.
    """

    file_path: str | None = None


def _parse_diff_line(line: str) -> tuple[str, str, str] | None:
    """Parse a diff line into (prefix, line_num, content). Returns None if not a diff line."""
    m = re.match(r"^([+\-\s])(\s*\d*)\s(.*)$", line)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def _replace_tabs(text: str) -> str:
    return text.replace("\t", "   ")


def _render_intra_line_diff(old_content: str, new_content: str) -> tuple[str, str]:
    """Compute word-level diff and render with inverse highlighting on changed parts."""
    old_words = re.findall(r"\S+|\s+", old_content)
    new_words = re.findall(r"\S+|\s+", new_content)

    matcher = difflib.SequenceMatcher(None, old_words, new_words, autojunk=False)
    opcodes = matcher.get_opcodes()

    removed_line = ""
    added_line = ""
    is_first_removed = True
    is_first_added = True

    for tag, i1, i2, j1, j2 in opcodes:
        old_part = "".join(old_words[i1:i2])
        new_part = "".join(new_words[j1:j2])

        if tag == "equal":
            removed_line += old_part
            added_line += new_part
        elif tag == "delete":
            value = old_part
            if is_first_removed:
                leading = re.match(r"^(\s*)", value)
                ws = leading.group(1) if leading else ""
                value = value[len(ws) :]
                removed_line += ws
                is_first_removed = False
            if value:
                removed_line += theme.inverse(value)
        elif tag == "insert":
            value = new_part
            if is_first_added:
                leading = re.match(r"^(\s*)", value)
                ws = leading.group(1) if leading else ""
                value = value[len(ws) :]
                added_line += ws
                is_first_added = False
            if value:
                added_line += theme.inverse(value)
        elif tag == "replace":
            old_val = old_part
            new_val = new_part
            if is_first_removed:
                leading = re.match(r"^(\s*)", old_val)
                ws = leading.group(1) if leading else ""
                old_val = old_val[len(ws) :]
                removed_line += ws
                is_first_removed = False
            if is_first_added:
                leading = re.match(r"^(\s*)", new_val)
                ws = leading.group(1) if leading else ""
                new_val = new_val[len(ws) :]
                added_line += ws
                is_first_added = False
            if old_val:
                removed_line += theme.inverse(old_val)
            if new_val:
                added_line += theme.inverse(new_val)

    return removed_line, added_line


def render_diff(diff_text: str, file_path: str | None = None) -> str:
    """Render a diff string with colored lines and intra-line change highlighting.

    - Context lines: dim/gray
    - Removed lines: red, with inverse on changed tokens
    - Added lines: green, with inverse on changed tokens
    """
    lines = diff_text.split("\n")
    result: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        parsed = _parse_diff_line(line)

        if not parsed:
            result.append(theme.fg("toolDiffContext", line))
            i += 1
            continue

        prefix, _line_num, _content = parsed

        if prefix == "-":
            # Collect consecutive removed lines
            removed: list[tuple[str, str]] = []
            while i < len(lines):
                p = _parse_diff_line(lines[i])
                if not p or p[0] != "-":
                    break
                removed.append((p[1], p[2]))
                i += 1

            # Collect consecutive added lines
            added: list[tuple[str, str]] = []
            while i < len(lines):
                p = _parse_diff_line(lines[i])
                if not p or p[0] != "+":
                    break
                added.append((p[1], p[2]))
                i += 1

            if len(removed) == 1 and len(added) == 1:
                rem_num, rem_content = removed[0]
                add_num, add_content = added[0]
                rem_line, add_line = _render_intra_line_diff(
                    _replace_tabs(rem_content),
                    _replace_tabs(add_content),
                )
                result.append(theme.fg("toolDiffRemoved", f"-{rem_num} {rem_line}"))
                result.append(theme.fg("toolDiffAdded", f"+{add_num} {add_line}"))
            else:
                for num, content in removed:
                    result.append(theme.fg("toolDiffRemoved", f"-{num} {_replace_tabs(content)}"))
                for num, content in added:
                    result.append(theme.fg("toolDiffAdded", f"+{num} {_replace_tabs(content)}"))

        elif prefix == "+":
            parsed2 = _parse_diff_line(line)
            if parsed2:
                result.append(theme.fg("toolDiffAdded", f"+{parsed2[1]} {_replace_tabs(parsed2[2])}"))
            i += 1
        else:
            parsed2 = _parse_diff_line(line)
            if parsed2:
                result.append(theme.fg("toolDiffContext", f" {parsed2[1]} {_replace_tabs(parsed2[2])}"))
            i += 1

    return "\n".join(result)
