"""Minimal theme stub for the interactive components.

A real theme implementation would load JSON theme files and apply ANSI colors.
This stub provides the same interface with simple passthrough formatting.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from pi_tui.components.editor import EditorTheme
from pi_tui.components.markdown import MarkdownTheme
from pi_tui.components.select_list import SelectListTheme
from pi_tui.components.settings_list import SettingsListTheme

# All valid theme color keys (from theme.ts ThemeColor type)
ThemeColor = Literal[
    "accent",
    "border",
    "borderAccent",
    "borderMuted",
    "success",
    "error",
    "warning",
    "muted",
    "dim",
    "text",
    "thinkingText",
    "selectedBg",
    "userMessageBg",
    "userMessageText",
    "customMessageBg",
    "customMessageText",
    "customMessageLabel",
    "toolPendingBg",
    "toolSuccessBg",
    "toolErrorBg",
    "toolTitle",
    "toolOutput",
    "mdHeading",
    "mdLink",
    "mdLinkUrl",
    "mdCode",
    "mdCodeBlock",
    "mdCodeBlockBorder",
    "mdQuote",
    "mdQuoteBorder",
    "mdHr",
    "mdListBullet",
    "toolDiffAdded",
    "toolDiffRemoved",
    "toolDiffContext",
    "syntaxComment",
    "syntaxKeyword",
    "syntaxFunction",
    "syntaxVariable",
    "syntaxString",
    "syntaxNumber",
    "syntaxType",
    "syntaxOperator",
    "syntaxPunctuation",
    "thinkingOff",
    "thinkingMinimal",
    "thinkingLow",
    "thinkingMedium",
    "thinkingHigh",
    "thinkingXhigh",
    "bashMode",
]

# ANSI color codes for the default dark theme
_FG_COLORS: dict[str, str] = {
    "accent": "\x1b[38;5;75m",
    "border": "\x1b[38;5;238m",
    "borderAccent": "\x1b[38;5;75m",
    "borderMuted": "\x1b[38;5;236m",
    "success": "\x1b[38;5;114m",
    "error": "\x1b[38;5;203m",
    "warning": "\x1b[38;5;215m",
    "muted": "\x1b[38;5;245m",
    "dim": "\x1b[38;5;240m",
    "text": "\x1b[38;5;252m",
    "thinkingText": "\x1b[38;5;177m",
    "customMessageLabel": "\x1b[38;5;183m",
    "customMessageText": "\x1b[38;5;252m",
    "toolTitle": "\x1b[38;5;75m",
    "toolOutput": "\x1b[38;5;252m",
    "mdHeading": "\x1b[38;5;75m",
    "mdLink": "\x1b[38;5;114m",
    "mdLinkUrl": "\x1b[38;5;245m",
    "mdCode": "\x1b[38;5;221m",
    "mdCodeBlock": "\x1b[38;5;252m",
    "mdCodeBlockBorder": "\x1b[38;5;238m",
    "mdQuote": "\x1b[38;5;245m",
    "mdQuoteBorder": "\x1b[38;5;238m",
    "mdHr": "\x1b[38;5;238m",
    "mdListBullet": "\x1b[38;5;75m",
    "toolDiffAdded": "\x1b[38;5;114m",
    "toolDiffRemoved": "\x1b[38;5;203m",
    "toolDiffContext": "\x1b[38;5;245m",
    "bashMode": "\x1b[38;5;215m",
    "userMessageText": "\x1b[38;5;252m",
}

_BG_COLORS: dict[str, str] = {
    "selectedBg": "\x1b[48;5;235m",
    "userMessageBg": "\x1b[48;5;235m",
    "customMessageBg": "\x1b[48;5;53m",
    "toolPendingBg": "\x1b[48;5;234m",
    "toolSuccessBg": "\x1b[48;5;234m",
    "toolErrorBg": "\x1b[48;5;52m",
}

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_ITALIC = "\x1b[3m"
_INVERSE = "\x1b[7m"


@dataclass
class Theme:
    """Provides color formatting functions for UI components."""

    def fg(self, color: str, text: str) -> str:
        """Apply foreground color to text."""
        code = _FG_COLORS.get(color, "")
        if not code:
            return text
        return f"{code}{text}{_RESET}"

    def bg(self, color: str, text: str) -> str:
        """Apply background color to text."""
        code = _BG_COLORS.get(color, "")
        if not code:
            return text
        return f"{code}{text}{_RESET}"

    def bold(self, text: str) -> str:
        """Apply bold formatting."""
        return f"{_BOLD}{text}\x1b[22m"

    def italic(self, text: str) -> str:
        """Apply italic formatting."""
        return f"{_ITALIC}{text}\x1b[23m"

    def inverse(self, text: str) -> str:
        """Apply inverse video."""
        return f"{_INVERSE}{text}\x1b[27m"


# Singleton theme instance
theme = Theme()


def get_markdown_theme() -> MarkdownTheme:
    """Return a MarkdownTheme using the current theme colors."""
    return MarkdownTheme(
        heading=lambda t: theme.bold(theme.fg("mdHeading", t)),
        link=lambda t: theme.fg("mdLink", t),
        link_url=lambda t: theme.fg("mdLinkUrl", t),
        code=lambda t: theme.fg("mdCode", t),
        code_block=lambda t: theme.fg("mdCodeBlock", t),
        code_block_border=lambda t: theme.fg("mdCodeBlockBorder", t),
        quote=lambda t: theme.italic(theme.fg("mdQuote", t)),
        quote_border=lambda t: theme.fg("mdQuoteBorder", t),
        hr=lambda t: theme.fg("mdHr", t),
        list_bullet=lambda t: theme.fg("mdListBullet", t),
        bold=lambda t: theme.bold(t),
        italic=lambda t: theme.italic(t),
        strikethrough=lambda t: f"\x1b[9m{t}\x1b[29m",
        underline=lambda t: f"\x1b[4m{t}\x1b[24m",
    )


def get_select_list_theme() -> SelectListTheme:
    """Return a SelectListTheme using the current theme colors."""
    return SelectListTheme(
        selected_prefix=lambda t: theme.fg("accent", t),
        selected_text=lambda t: theme.fg("accent", t),
        description=lambda t: theme.fg("muted", t),
        scroll_info=lambda t: theme.fg("muted", t),
        no_match=lambda t: theme.fg("muted", t),
    )


def get_settings_list_theme() -> SettingsListTheme:
    """Return a SettingsListTheme using the current theme colors."""
    return SettingsListTheme(
        label=lambda t, _selected: t,
        value=lambda t, _selected: theme.fg("accent", t),
        description=lambda t: theme.fg("muted", t),
        hint=lambda t: theme.fg("dim", t),
    )


def get_editor_theme() -> EditorTheme:
    """Return an EditorTheme using the current theme colors."""
    return EditorTheme(
        border_color=lambda s: theme.fg("border", s),
        select_list=get_select_list_theme(),
    )


def get_available_themes() -> list[str]:
    """Return list of available theme names."""
    return ["dark", "light"]


def get_language_from_path(file_path: str) -> str | None:
    """Detect language from file extension for syntax highlighting."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".html": "html",
        ".css": "css",
        ".sql": "sql",
        ".rb": "ruby",
        ".php": "php",
    }
    _, ext = os.path.splitext(file_path)
    return ext_map.get(ext.lower())


def highlight_code(text: str, lang: str) -> list[str]:
    """Attempt syntax highlighting; fall back to plain lines on error."""
    try:
        from pygments import highlight as pyg_highlight  # type: ignore[import-untyped]
        from pygments.formatters import Terminal256Formatter  # type: ignore[import-untyped]
        from pygments.lexers import get_lexer_by_name  # type: ignore[import-untyped]
        from pygments.util import ClassNotFound  # type: ignore[import-untyped]

        try:
            lexer = get_lexer_by_name(lang, stripall=False)
            highlighted: str = pyg_highlight(text, lexer, Terminal256Formatter(style="monokai"))
            return highlighted.splitlines()
        except ClassNotFound:
            return text.splitlines()
    except ImportError:
        return text.splitlines()
