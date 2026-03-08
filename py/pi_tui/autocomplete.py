"""File path and slash command autocomplete.

Port of autocomplete.ts. Implements autocomplete providers for file paths
(directory listing and fuzzy search via ``fd``) and slash commands.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypedDict

from pi_tui.components.select_list import SelectItem
from pi_tui.fuzzy import fuzzy_filter

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# AutocompleteItem is an alias for SelectItem since they share the same fields.
AutocompleteItem = SelectItem


@dataclass
class SlashCommand:
    """A slash command definition with optional argument completions."""

    name: str
    description: str | None = None
    get_argument_completions: Callable[[str], list[AutocompleteItem] | None] | None = None


class SuggestionResult(TypedDict):
    """Return type for get_suggestions."""

    items: list[AutocompleteItem]
    prefix: str


class CompletionResult(TypedDict):
    """Return type for apply_completion."""

    lines: list[str]
    cursor_line: int
    cursor_col: int


class AutocompleteProvider(Protocol):
    """Protocol for autocomplete providers."""

    def get_suggestions(
        self,
        lines: list[str],
        cursor_line: int,
        cursor_col: int,
    ) -> SuggestionResult | None:
        """Get autocomplete suggestions for current text/cursor position.

        Returns None if no suggestions are available.
        """
        ...

    def apply_completion(
        self,
        lines: list[str],
        cursor_line: int,
        cursor_col: int,
        item: AutocompleteItem,
        prefix: str,
    ) -> CompletionResult:
        """Apply the selected item.

        Returns the new text and cursor position.
        """
        ...


# ---------------------------------------------------------------------------
# Constants & private helpers
# ---------------------------------------------------------------------------

_PATH_DELIMITERS = frozenset(" \t\"'=")


def _find_last_delimiter(text: str) -> int:
    """Find the index of the last path delimiter in *text*, or -1."""
    for i in range(len(text) - 1, -1, -1):
        if text[i] in _PATH_DELIMITERS:
            return i
    return -1


def _find_unclosed_quote_start(text: str) -> int | None:
    """Return the index of the opening ``"`` of an unclosed quote, or None."""
    in_quotes = False
    quote_start = -1

    for i, ch in enumerate(text):
        if ch == '"':
            in_quotes = not in_quotes
            if in_quotes:
                quote_start = i

    return quote_start if in_quotes else None


def _is_token_start(text: str, index: int) -> bool:
    """Check whether *index* is at the start of a token."""
    return index == 0 or text[index - 1] in _PATH_DELIMITERS


def _extract_quoted_prefix(text: str) -> str | None:
    """Extract a quoted path prefix from an unclosed quote in *text*."""
    quote_start = _find_unclosed_quote_start(text)
    if quote_start is None:
        return None

    if quote_start > 0 and text[quote_start - 1] == "@":
        if not _is_token_start(text, quote_start - 1):
            return None
        return text[quote_start - 1 :]

    if not _is_token_start(text, quote_start):
        return None

    return text[quote_start:]


@dataclass
class _ParsedPrefix:
    raw_prefix: str
    is_at_prefix: bool
    is_quoted_prefix: bool


def _parse_path_prefix(prefix: str) -> _ParsedPrefix:
    """Parse a prefix string into its raw path, @-flag, and quoted-flag."""
    if prefix.startswith('@"'):
        return _ParsedPrefix(raw_prefix=prefix[2:], is_at_prefix=True, is_quoted_prefix=True)
    if prefix.startswith('"'):
        return _ParsedPrefix(raw_prefix=prefix[1:], is_at_prefix=False, is_quoted_prefix=True)
    if prefix.startswith("@"):
        return _ParsedPrefix(raw_prefix=prefix[1:], is_at_prefix=True, is_quoted_prefix=False)
    return _ParsedPrefix(raw_prefix=prefix, is_at_prefix=False, is_quoted_prefix=False)


def _build_completion_value(
    path: str,
    *,
    is_directory: bool,
    is_at_prefix: bool,
    is_quoted_prefix: bool,
) -> str:
    """Build the completion value string, adding quotes/@ as needed."""
    needs_quotes = is_quoted_prefix or " " in path
    prefix = "@" if is_at_prefix else ""

    if not needs_quotes:
        return f"{prefix}{path}"

    open_quote = f'{prefix}"'
    close_quote = '"'
    return f"{open_quote}{path}{close_quote}"


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------


def _walk_directory_with_fd(
    base_dir: str,
    fd_path: str,
    query: str,
    max_results: int,
) -> list[dict[str, object]]:
    """Use the ``fd`` command to walk a directory tree.

    Returns a list of dicts with ``path`` (str) and ``is_directory`` (bool).
    """
    args: list[str] = [
        fd_path,
        "--base-directory",
        base_dir,
        "--max-results",
        str(max_results),
        "--type",
        "f",
        "--type",
        "d",
        "--full-path",
        "--hidden",
        "--exclude",
        ".git",
        "--exclude",
        ".git/*",
        "--exclude",
        ".git/**",
    ]

    if query:
        args.append(query)

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    if result.returncode != 0 or not result.stdout:
        return []

    entries: list[dict[str, object]] = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        normalized = line.rstrip("/")
        if normalized == ".git" or normalized.startswith(".git/") or "/.git/" in normalized:
            continue
        is_directory = line.endswith("/")
        entries.append({"path": line, "is_directory": is_directory})

    return entries


def _expand_home_path(path: str) -> str:
    """Expand ``~/`` to the user's home directory."""
    if path.startswith("~/"):
        expanded = os.path.join(os.path.expanduser("~"), path[2:])
        if path.endswith("/") and not expanded.endswith("/"):
            return expanded + "/"
        return expanded
    if path == "~":
        return os.path.expanduser("~")
    return path


# ---------------------------------------------------------------------------
# CombinedAutocompleteProvider
# ---------------------------------------------------------------------------


class CombinedAutocompleteProvider:
    """Provider that handles slash commands, @-file fuzzy search, and file paths."""

    def __init__(
        self,
        commands: list[SlashCommand | AutocompleteItem] | None = None,
        base_path: str | None = None,
        fd_path: str | None = None,
    ) -> None:
        self.commands: list[SlashCommand | AutocompleteItem] = commands or []
        self.base_path: str = base_path or os.getcwd()
        self.fd_path: str | None = fd_path

    # -- public API ----------------------------------------------------------

    def get_suggestions(
        self,
        lines: list[str],
        cursor_line: int,
        cursor_col: int,
    ) -> SuggestionResult | None:
        """Get autocomplete suggestions for current text/cursor position."""
        current_line = lines[cursor_line] if cursor_line < len(lines) else ""
        text_before_cursor = current_line[:cursor_col]

        # Check for @ file reference (fuzzy search)
        at_prefix = self._extract_at_prefix(text_before_cursor)
        if at_prefix is not None:
            parsed = _parse_path_prefix(at_prefix)
            suggestions = self._get_fuzzy_file_suggestions(parsed.raw_prefix, is_quoted_prefix=parsed.is_quoted_prefix)
            if not suggestions:
                return None
            return {"items": suggestions, "prefix": at_prefix}

        # Check for slash commands
        if text_before_cursor.startswith("/"):
            space_index = text_before_cursor.find(" ")

            if space_index == -1:
                # No space yet - complete command names with fuzzy matching
                prefix = text_before_cursor[1:]  # Remove the "/"

                @dataclass
                class _CmdItem:
                    name: str
                    label: str
                    description: str | None

                command_items = [
                    _CmdItem(
                        name=cmd.name if isinstance(cmd, SlashCommand) else cmd.value,
                        label=cmd.name if isinstance(cmd, SlashCommand) else cmd.label,
                        description=cmd.description,
                    )
                    for cmd in self.commands
                ]

                filtered = fuzzy_filter(command_items, prefix, lambda item: item.name)
                result_items = [
                    AutocompleteItem(
                        value=item.name,
                        label=item.label,
                        description=item.description,
                    )
                    for item in filtered
                ]

                if not result_items:
                    return None
                return {"items": result_items, "prefix": text_before_cursor}
            else:
                # Space found - complete command arguments
                command_name = text_before_cursor[1:space_index]
                argument_text = text_before_cursor[space_index + 1 :]

                command = None
                for cmd in self.commands:
                    name = cmd.name if isinstance(cmd, SlashCommand) else cmd.value
                    if name == command_name:
                        command = cmd
                        break

                if command is None or not isinstance(command, SlashCommand) or command.get_argument_completions is None:
                    return None

                argument_suggestions = command.get_argument_completions(argument_text)
                if not argument_suggestions:
                    return None

                return {"items": argument_suggestions, "prefix": argument_text}

        # Check for file paths
        path_match = self._extract_path_prefix(text_before_cursor, force_extract=False)

        if path_match is not None:
            suggestions = self._get_file_suggestions(path_match)
            if not suggestions:
                return None

            if len(suggestions) == 1 and suggestions[0].value == path_match and not path_match.endswith("/"):
                return {"items": suggestions, "prefix": path_match}

            return {"items": suggestions, "prefix": path_match}

        return None

    def apply_completion(
        self,
        lines: list[str],
        cursor_line: int,
        cursor_col: int,
        item: AutocompleteItem,
        prefix: str,
    ) -> CompletionResult:
        """Apply the selected completion item."""
        current_line = lines[cursor_line] if cursor_line < len(lines) else ""
        before_prefix = current_line[: cursor_col - len(prefix)]
        after_cursor = current_line[cursor_col:]
        is_quoted_prefix = prefix.startswith('"') or prefix.startswith('@"')
        has_leading_quote_after = after_cursor.startswith('"')
        has_trailing_quote_in_item = item.value.endswith('"')
        adjusted_after = (
            after_cursor[1:]
            if is_quoted_prefix and has_trailing_quote_in_item and has_leading_quote_after
            else after_cursor
        )

        # Slash command completion
        is_slash_command = prefix.startswith("/") and before_prefix.strip() == "" and "/" not in prefix[1:]
        if is_slash_command:
            new_line = f"{before_prefix}/{item.value} {adjusted_after}"
            new_lines = list(lines)
            new_lines[cursor_line] = new_line
            return {
                "lines": new_lines,
                "cursor_line": cursor_line,
                "cursor_col": len(before_prefix) + len(item.value) + 2,
            }

        # File attachment completion (@ prefix)
        if prefix.startswith("@"):
            is_directory = item.label.endswith("/")
            suffix = "" if is_directory else " "
            new_line = f"{before_prefix}{item.value}{suffix}{adjusted_after}"
            new_lines = list(lines)
            new_lines[cursor_line] = new_line

            has_trailing_quote = item.value.endswith('"')
            cursor_offset = len(item.value) - 1 if is_directory and has_trailing_quote else len(item.value)

            return {
                "lines": new_lines,
                "cursor_line": cursor_line,
                "cursor_col": len(before_prefix) + cursor_offset + len(suffix),
            }

        # Slash command argument completion
        text_before_cursor = current_line[:cursor_col]
        if "/" in text_before_cursor and " " in text_before_cursor:
            new_line = before_prefix + item.value + adjusted_after
            new_lines = list(lines)
            new_lines[cursor_line] = new_line

            is_directory = item.label.endswith("/")
            has_trailing_quote = item.value.endswith('"')
            cursor_offset = len(item.value) - 1 if is_directory and has_trailing_quote else len(item.value)

            return {
                "lines": new_lines,
                "cursor_line": cursor_line,
                "cursor_col": len(before_prefix) + cursor_offset,
            }

        # File path completion
        new_line = before_prefix + item.value + adjusted_after
        new_lines = list(lines)
        new_lines[cursor_line] = new_line

        is_directory = item.label.endswith("/")
        has_trailing_quote = item.value.endswith('"')
        cursor_offset = len(item.value) - 1 if is_directory and has_trailing_quote else len(item.value)

        return {
            "lines": new_lines,
            "cursor_line": cursor_line,
            "cursor_col": len(before_prefix) + cursor_offset,
        }

    def get_force_file_suggestions(
        self,
        lines: list[str],
        cursor_line: int,
        cursor_col: int,
    ) -> SuggestionResult | None:
        """Force file completion (called on Tab key) - always returns suggestions."""
        current_line = lines[cursor_line] if cursor_line < len(lines) else ""
        text_before_cursor = current_line[:cursor_col]

        # Don't trigger if typing a slash command at the start of the line
        trimmed = text_before_cursor.strip()
        if trimmed.startswith("/") and " " not in trimmed:
            return None

        path_match = self._extract_path_prefix(text_before_cursor, force_extract=True)
        if path_match is not None:
            suggestions = self._get_file_suggestions(path_match)
            if not suggestions:
                return None
            return {"items": suggestions, "prefix": path_match}

        return None

    def should_trigger_file_completion(
        self,
        lines: list[str],
        cursor_line: int,
        cursor_col: int,
    ) -> bool:
        """Check if Tab should trigger file completion."""
        current_line = lines[cursor_line] if cursor_line < len(lines) else ""
        text_before_cursor = current_line[:cursor_col]

        trimmed = text_before_cursor.strip()
        return not (trimmed.startswith("/") and " " not in trimmed)

    # -- private helpers -----------------------------------------------------

    def _extract_at_prefix(self, text: str) -> str | None:
        """Extract @ prefix for fuzzy file suggestions."""
        quoted_prefix = _extract_quoted_prefix(text)
        if quoted_prefix is not None and quoted_prefix.startswith('@"'):
            return quoted_prefix

        last_delim = _find_last_delimiter(text)
        token_start = 0 if last_delim == -1 else last_delim + 1

        if token_start < len(text) and text[token_start] == "@":
            return text[token_start:]

        return None

    def _extract_path_prefix(self, text: str, *, force_extract: bool = False) -> str | None:
        """Extract a path-like prefix from text before cursor."""
        quoted_prefix = _extract_quoted_prefix(text)
        if quoted_prefix is not None:
            return quoted_prefix

        last_delim = _find_last_delimiter(text)
        path_prefix = text if last_delim == -1 else text[last_delim + 1 :]

        if force_extract:
            return path_prefix

        # For natural triggers, return if it looks like a path
        if "/" in path_prefix or path_prefix.startswith(".") or path_prefix.startswith("~/"):
            return path_prefix

        # Empty after a space
        if path_prefix == "" and text.endswith(" "):
            return path_prefix

        return None

    def _resolve_scoped_fuzzy_query(self, raw_query: str) -> dict[str, str] | None:
        """Resolve a scoped fuzzy query like ``src/foo`` into base_dir + query."""
        slash_index = raw_query.rfind("/")
        if slash_index == -1:
            return None

        display_base = raw_query[: slash_index + 1]
        query = raw_query[slash_index + 1 :]

        if display_base.startswith("~/"):
            base_dir = _expand_home_path(display_base)
        elif display_base.startswith("/"):
            base_dir = display_base
        else:
            base_dir = os.path.join(self.base_path, display_base)

        try:
            if not Path(base_dir).is_dir():
                return None
        except OSError:
            return None

        return {"base_dir": base_dir, "query": query, "display_base": display_base}

    @staticmethod
    def _scoped_path_for_display(display_base: str, relative_path: str) -> str:
        if display_base == "/":
            return f"/{relative_path}"
        return f"{display_base}{relative_path}"

    def _get_file_suggestions(self, prefix: str) -> list[AutocompleteItem]:
        """Get file/directory suggestions for a given path prefix."""
        try:
            parsed = _parse_path_prefix(prefix)
            raw_prefix = parsed.raw_prefix
            is_at_prefix = parsed.is_at_prefix
            is_quoted_prefix = parsed.is_quoted_prefix
            expanded_prefix = raw_prefix

            # Handle home directory expansion
            if expanded_prefix.startswith("~"):
                expanded_prefix = _expand_home_path(expanded_prefix)

            is_root_prefix = raw_prefix in ("", "./", "../", "~", "~/", "/") or (is_at_prefix and raw_prefix == "")

            if is_root_prefix or raw_prefix.endswith("/"):
                if raw_prefix.startswith("~") or expanded_prefix.startswith("/"):
                    search_dir = expanded_prefix
                else:
                    search_dir = os.path.join(self.base_path, expanded_prefix)
                search_prefix = ""
            else:
                dir_part = os.path.dirname(expanded_prefix)
                file_part = os.path.basename(expanded_prefix)
                if raw_prefix.startswith("~") or expanded_prefix.startswith("/"):
                    search_dir = dir_part
                else:
                    search_dir = os.path.join(self.base_path, dir_part)
                search_prefix = file_part

            suggestions: list[AutocompleteItem] = []
            search_path = Path(search_dir)

            for entry in sorted(search_path.iterdir()):
                name = entry.name
                if not name.lower().startswith(search_prefix.lower()):
                    continue

                is_directory = entry.is_dir()
                if not is_directory and entry.is_symlink():
                    with contextlib.suppress(OSError):
                        is_directory = entry.resolve().is_dir()

                display_prefix = raw_prefix

                if display_prefix.endswith("/"):
                    relative_path = display_prefix + name
                elif "/" in display_prefix:
                    if display_prefix.startswith("~/"):
                        home_relative_dir = display_prefix[2:]
                        dir_name = os.path.dirname(home_relative_dir)
                        relative_path = f"~/{name}" if dir_name == "." else f"~/{os.path.join(dir_name, name)}"
                    elif display_prefix.startswith("/"):
                        dir_name = os.path.dirname(display_prefix)
                        relative_path = f"/{name}" if dir_name == "/" else f"{dir_name}/{name}"
                    else:
                        relative_path = os.path.join(os.path.dirname(display_prefix), name)
                else:
                    relative_path = f"~/{name}" if display_prefix.startswith("~") else name

                path_value = f"{relative_path}/" if is_directory else relative_path
                value = _build_completion_value(
                    path_value,
                    is_directory=is_directory,
                    is_at_prefix=is_at_prefix,
                    is_quoted_prefix=is_quoted_prefix,
                )

                suggestions.append(
                    AutocompleteItem(
                        value=value,
                        label=name + ("/" if is_directory else ""),
                    )
                )

            # Sort directories first, then alphabetically
            suggestions.sort(
                key=lambda s: (
                    0 if s.value.endswith("/") or (s.value.endswith('/"') and '"' in s.value) else 1,
                    s.label.lower(),
                )
            )

            return suggestions
        except OSError:
            return []

    def _score_entry(self, file_path: str, query: str, *, is_directory: bool) -> int:
        """Score an entry against the query (higher = better match)."""
        file_name = os.path.basename(file_path.rstrip("/"))
        lower_name = file_name.lower()
        lower_query = query.lower()

        score = 0
        if lower_name == lower_query:
            score = 100
        elif lower_name.startswith(lower_query):
            score = 80
        elif lower_query in lower_name:
            score = 50
        elif lower_query in file_path.lower():
            score = 30

        if is_directory and score > 0:
            score += 10

        return score

    def _get_fuzzy_file_suggestions(self, query: str, *, is_quoted_prefix: bool) -> list[AutocompleteItem]:
        """Fuzzy file search using fd (fast, respects .gitignore)."""
        if not self.fd_path:
            return []

        try:
            scoped = self._resolve_scoped_fuzzy_query(query)
            fd_base_dir = scoped["base_dir"] if scoped else self.base_path
            fd_query = scoped["query"] if scoped else query
            entries = _walk_directory_with_fd(fd_base_dir, self.fd_path, fd_query, 100)

            # Score entries
            scored: list[tuple[dict[str, object], int]] = []
            for entry in entries:
                entry_path = str(entry["path"])
                entry_is_dir = bool(entry["is_directory"])
                s = self._score_entry(entry_path, fd_query, is_directory=entry_is_dir) if fd_query else 1
                if s > 0:
                    scored.append((entry, s))

            scored.sort(key=lambda x: x[1], reverse=True)
            top_entries = scored[:20]

            suggestions: list[AutocompleteItem] = []
            for entry, _ in top_entries:
                entry_path = str(entry["path"])
                is_directory = bool(entry["is_directory"])
                path_without_slash = entry_path.rstrip("/") if is_directory else entry_path
                display_path = (
                    self._scoped_path_for_display(scoped["display_base"], path_without_slash)
                    if scoped
                    else path_without_slash
                )
                entry_name = os.path.basename(path_without_slash)
                completion_path = f"{display_path}/" if is_directory else display_path
                value = _build_completion_value(
                    completion_path,
                    is_directory=is_directory,
                    is_at_prefix=True,
                    is_quoted_prefix=is_quoted_prefix,
                )

                suggestions.append(
                    AutocompleteItem(
                        value=value,
                        label=entry_name + ("/" if is_directory else ""),
                        description=display_path,
                    )
                )

            return suggestions
        except OSError:
            return []
