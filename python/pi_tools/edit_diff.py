"""Edit diff utilities — fuzzy matching + unified diff generation."""

from __future__ import annotations

import difflib
import re
import unicodedata


def detect_line_ending(text: str) -> str:
    """Detect the predominant line ending (CRLF vs LF)."""
    crlf_count = text.count("\r\n")
    lf_count = text.count("\n") - crlf_count
    return "\r\n" if crlf_count > lf_count else "\n"


def normalize_to_lf(text: str) -> str:
    """Normalize all line endings to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def restore_line_endings(text: str, ending: str) -> str:
    """Restore line endings to the original style."""
    if ending == "\r\n":
        return text.replace("\n", "\r\n")
    return text


def strip_bom(text: str) -> tuple[str, str]:
    """Strip UTF-8 BOM, returning (bom, text_without_bom)."""
    if text.startswith("\ufeff"):
        return "\ufeff", text[1:]
    return "", text


def normalize_for_fuzzy_match(text: str) -> str:
    """Normalize text for fuzzy matching: smart quotes, dashes, spaces."""
    # Smart quotes to ASCII
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    # Dashes
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    # Normalize whitespace (but preserve newlines)
    lines = text.split("\n")
    normalized_lines = []
    for line in lines:
        # Collapse multiple spaces to single
        line = re.sub(r"[ \t]+", " ", line)
        # Strip trailing whitespace
        line = line.rstrip()
        normalized_lines.append(line)
    return "\n".join(normalized_lines)


class FuzzyMatchResult:
    def __init__(
        self,
        found: bool,
        index: int = -1,
        match_length: int = 0,
        is_fuzzy: bool = False,
        content_for_replacement: str = "",
    ):
        self.found = found
        self.index = index
        self.match_length = match_length
        self.is_fuzzy = is_fuzzy
        self.content_for_replacement = content_for_replacement


def fuzzy_find_text(content: str, search: str) -> FuzzyMatchResult:
    """Find text with exact match first, then fuzzy fallback."""
    # Try exact match
    idx = content.find(search)
    if idx != -1:
        return FuzzyMatchResult(
            found=True,
            index=idx,
            match_length=len(search),
            is_fuzzy=False,
            content_for_replacement=content,
        )

    # Try fuzzy match
    fuzzy_content = normalize_for_fuzzy_match(content)
    fuzzy_search = normalize_for_fuzzy_match(search)

    idx = fuzzy_content.find(fuzzy_search)
    if idx != -1:
        return FuzzyMatchResult(
            found=True,
            index=idx,
            match_length=len(fuzzy_search),
            is_fuzzy=True,
            content_for_replacement=fuzzy_content,
        )

    return FuzzyMatchResult(found=False)


def generate_diff_string(old_text: str, new_text: str, filename: str = "file") -> dict:
    """Generate a unified diff string between old and new text."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
    )

    diff_str = "\n".join(diff)

    # Find first changed line
    first_changed_line = None
    for i, (old, new) in enumerate(zip(old_lines, new_lines)):
        if old != new:
            first_changed_line = i + 1
            break
    if first_changed_line is None and len(old_lines) != len(new_lines):
        first_changed_line = min(len(old_lines), len(new_lines)) + 1

    return {"diff": diff_str, "first_changed_line": first_changed_line}
