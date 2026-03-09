"""Multi-line text editor component with word wrapping, autocomplete, and kill ring.

Port of editor.ts. Provides a full-featured multi-line text editor with:
- Word wrapping for display
- Vertical scrolling
- Autocomplete integration (slash commands, file paths)
- Bracketed paste handling (large pastes stored as markers)
- Kill ring (Emacs-style kill/yank)
- Undo stack
- History navigation
- Character jump mode
- Sticky column for vertical cursor movement
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from pi_tui.autocomplete import (
    AutocompleteProvider,
    CombinedAutocompleteProvider,
    SuggestionResult,
)
from pi_tui.components.select_list import SelectList, SelectListTheme
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.keys import matches_key
from pi_tui.kill_ring import KillRing
from pi_tui.tui import CURSOR_MARKER, TUI
from pi_tui.undo_stack import UndoStack
from pi_tui.utils import (
    get_segmenter,
    is_punctuation_char,
    is_whitespace_char,
    visible_width,
)

_segmenter = get_segmenter()

# ---------------------------------------------------------------------------
# Kitty CSI-u printable decoding
# ---------------------------------------------------------------------------

_KITTY_CSI_U_RE = re.compile(r"^\x1b\[(\d+)(?::(\d*))?(?::(\d+))?(?:;(\d+))?(?::(\d+))?u$")
_KITTY_MOD_SHIFT = 1
_KITTY_MOD_ALT = 2
_KITTY_MOD_CTRL = 4


def _decode_kitty_printable(data: str) -> str | None:
    """Decode a printable CSI-u sequence, preferring the shifted key when present."""
    m = _KITTY_CSI_U_RE.match(data)
    if m is None:
        return None

    codepoint_str = m.group(1) or ""
    try:
        codepoint = int(codepoint_str)
    except ValueError:
        return None

    shifted_key: int | None = None
    g2 = m.group(2)
    if g2 is not None and len(g2) > 0:
        with contextlib.suppress(ValueError):
            shifted_key = int(g2)

    g4 = m.group(4)
    mod_value = int(g4) if g4 else 1
    modifier = mod_value - 1

    # Ignore CSI-u sequences used for Alt/Ctrl shortcuts
    if modifier & (_KITTY_MOD_ALT | _KITTY_MOD_CTRL):
        return None

    effective_codepoint = codepoint
    if (modifier & _KITTY_MOD_SHIFT) and shifted_key is not None:
        effective_codepoint = shifted_key

    if effective_codepoint < 32:
        return None

    try:
        return chr(effective_codepoint)
    except (ValueError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# TextChunk and word_wrap_line
# ---------------------------------------------------------------------------


@dataclass
class TextChunk:
    """Represents a chunk of text for word-wrap layout.

    Tracks both the text content and its position in the original line.
    """

    text: str
    start_index: int
    end_index: int


def word_wrap_line(line: str, max_width: int) -> list[TextChunk]:
    """Split a line into word-wrapped chunks.

    Wraps at word boundaries when possible, falling back to character-level
    wrapping for words longer than the available width.

    Args:
        line: The text line to wrap.
        max_width: Maximum visible width per chunk.

    Returns:
        List of chunks with text and position information.
    """
    if not line or max_width <= 0:
        return [TextChunk(text="", start_index=0, end_index=0)]

    line_width = visible_width(line)
    if line_width <= max_width:
        return [TextChunk(text=line, start_index=0, end_index=len(line))]

    chunks: list[TextChunk] = []
    segments = _segmenter(line)

    # Build indexed segments: (grapheme, char_index)
    indexed: list[tuple[str, int]] = []
    pos = 0
    for grapheme in segments:
        indexed.append((grapheme, pos))
        pos += len(grapheme)

    current_width = 0
    chunk_start = 0

    # Wrap opportunity tracking
    wrap_opp_index = -1
    wrap_opp_width = 0

    for i, (grapheme, char_index) in enumerate(indexed):
        g_width = visible_width(grapheme)
        is_ws = is_whitespace_char(grapheme)

        # Overflow check before advancing
        if current_width + g_width > max_width:
            if wrap_opp_index >= 0:
                # Backtrack to last wrap opportunity
                chunks.append(
                    TextChunk(
                        text=line[chunk_start:wrap_opp_index],
                        start_index=chunk_start,
                        end_index=wrap_opp_index,
                    )
                )
                chunk_start = wrap_opp_index
                current_width -= wrap_opp_width
            elif chunk_start < char_index:
                # No wrap opportunity: force-break at current position
                chunks.append(
                    TextChunk(
                        text=line[chunk_start:char_index],
                        start_index=chunk_start,
                        end_index=char_index,
                    )
                )
                chunk_start = char_index
                current_width = 0
            wrap_opp_index = -1

        # Advance
        current_width += g_width

        # Record wrap opportunity: whitespace followed by non-whitespace
        if is_ws and i + 1 < len(indexed):
            next_grapheme, next_index = indexed[i + 1]
            if not is_whitespace_char(next_grapheme):
                wrap_opp_index = next_index
                wrap_opp_width = current_width

    # Push final chunk
    chunks.append(
        TextChunk(
            text=line[chunk_start:],
            start_index=chunk_start,
            end_index=len(line),
        )
    )

    return chunks


# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------


@dataclass
class _EditorState:
    """Internal mutable state for the editor."""

    lines: list[str] = field(default_factory=lambda: [""])
    cursor_line: int = 0
    cursor_col: int = 0


@dataclass
class _LayoutLine:
    """A single visual line produced by layout."""

    text: str
    has_cursor: bool
    cursor_pos: int | None = None


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class EditorTheme:
    """Theme for the Editor component."""

    border_color: Callable[[str], str]
    select_list: SelectListTheme


@dataclass
class EditorOptions:
    """Configuration options for the Editor."""

    padding_x: int = 0
    autocomplete_max_visible: int = 5


# ---------------------------------------------------------------------------
# Visual line entry for cursor navigation
# ---------------------------------------------------------------------------


@dataclass
class _VisualLineEntry:
    """Maps a visual (display) line back to its logical position."""

    logical_line: int
    start_col: int
    length: int


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------


class Editor:
    """Multi-line text editor component.

    Implements Component and Focusable protocols from TUI.
    """

    def __init__(
        self,
        tui: TUI,
        theme: EditorTheme,
        options: EditorOptions | None = None,
    ) -> None:
        opts = options or EditorOptions()

        self._tui = tui
        self._theme = theme
        self.border_color: Callable[[str], str] = theme.border_color

        # Focusable interface
        self.focused: bool = False

        # Padding
        px = opts.padding_x
        self._padding_x: int = max(0, int(px)) if isinstance(px, (int, float)) else 0

        # Autocomplete
        max_vis = opts.autocomplete_max_visible
        self._autocomplete_max_visible: int = max(3, min(20, int(max_vis))) if isinstance(max_vis, (int, float)) else 5

        # Internal state
        self._state = _EditorState()
        self._last_width: int = 80
        self._scroll_offset: int = 0

        # Autocomplete support
        self._autocomplete_provider: AutocompleteProvider | None = None
        self._autocomplete_list: SelectList | None = None
        self._autocomplete_state: str | None = None  # "regular" | "force" | None
        self._autocomplete_prefix: str = ""

        # Paste tracking
        self._pastes: dict[int, str] = {}
        self._paste_counter: int = 0
        self._paste_buffer: str = ""
        self._is_in_paste: bool = False

        # History
        self._history: list[str] = []
        self._history_index: int = -1

        # Kill ring
        self._kill_ring = KillRing()
        self._last_action: str | None = None  # "kill" | "yank" | "type-word" | None

        # Character jump mode
        self._jump_mode: str | None = None  # "forward" | "backward" | None

        # Sticky column for vertical cursor movement
        self._preferred_visual_col: int | None = None

        # Undo
        self._undo_stack: UndoStack[_EditorState] = UndoStack()

        # Callbacks
        self.on_submit: Callable[[str], None] | None = None
        self.on_change: Callable[[str], None] | None = None
        self.disable_submit: bool = False

    # -- Property accessors --------------------------------------------------

    def get_padding_x(self) -> int:
        return self._padding_x

    def set_padding_x(self, padding: int) -> None:
        new_padding = max(0, int(padding)) if isinstance(padding, (int, float)) else 0
        if self._padding_x != new_padding:
            self._padding_x = new_padding
            self._tui.request_render()

    def get_autocomplete_max_visible(self) -> int:
        return self._autocomplete_max_visible

    def set_autocomplete_max_visible(self, max_visible: int) -> None:
        new_max = max(3, min(20, int(max_visible))) if isinstance(max_visible, (int, float)) else 5
        if self._autocomplete_max_visible != new_max:
            self._autocomplete_max_visible = new_max
            self._tui.request_render()

    def set_autocomplete_provider(self, provider: AutocompleteProvider) -> None:
        self._autocomplete_provider = provider

    # -- History -------------------------------------------------------------

    def add_to_history(self, text: str) -> None:
        """Add a prompt to history for up/down arrow navigation."""
        trimmed = text.strip()
        if not trimmed:
            return
        # Don't add consecutive duplicates
        if self._history and self._history[0] == trimmed:
            return
        self._history.insert(0, trimmed)
        if len(self._history) > 100:
            self._history.pop()

    # -- Query helpers -------------------------------------------------------

    def _is_editor_empty(self) -> bool:
        return len(self._state.lines) == 1 and self._state.lines[0] == ""

    def _is_on_first_visual_line(self) -> bool:
        visual_lines = self._build_visual_line_map(self._last_width)
        current = self._find_current_visual_line(visual_lines)
        return current == 0

    def _is_on_last_visual_line(self) -> bool:
        visual_lines = self._build_visual_line_map(self._last_width)
        current = self._find_current_visual_line(visual_lines)
        return current == len(visual_lines) - 1

    # -- History navigation --------------------------------------------------

    def _navigate_history(self, direction: int) -> None:
        """Navigate prompt history. direction: -1 = older, 1 = newer."""
        self._last_action = None
        if not self._history:
            return

        new_index = self._history_index - direction
        if new_index < -1 or new_index >= len(self._history):
            return

        # Capture state when first entering history browsing mode
        if self._history_index == -1 and new_index >= 0:
            self._push_undo_snapshot()

        self._history_index = new_index

        if self._history_index == -1:
            self._set_text_internal("")
        else:
            self._set_text_internal(self._history[self._history_index] or "")

    def _set_text_internal(self, text: str) -> None:
        """Internal setText that doesn't reset history state."""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        self._state.lines = lines if lines else [""]
        self._state.cursor_line = len(self._state.lines) - 1
        self._set_cursor_col(len(self._state.lines[self._state.cursor_line]))
        self._scroll_offset = 0

        if self.on_change:
            self.on_change(self.get_text())

    # -- Component protocol --------------------------------------------------

    def invalidate(self) -> None:
        """No cached state to invalidate currently."""

    @property
    def wants_key_release(self) -> bool:
        return False

    def render(self, width: int) -> list[str]:
        max_padding = max(0, (width - 1) // 2)
        padding_x = min(self._padding_x, max_padding)
        content_width = max(1, width - padding_x * 2)

        # Layout width: with padding the cursor can overflow into it,
        # without padding we reserve 1 column for the cursor.
        layout_width = max(1, content_width - (0 if padding_x else 1))

        # Store for cursor navigation (must match wrapping width)
        self._last_width = layout_width

        horizontal = self.border_color("\u2500")

        # Layout the text
        layout_lines = self._layout_text(layout_width)

        # Calculate max visible lines: 30% of terminal height, minimum 5 lines
        terminal_rows = self._tui.terminal.rows
        max_visible_lines = max(5, int(terminal_rows * 0.3))

        # Find cursor line index
        cursor_line_index = 0
        for i, ll in enumerate(layout_lines):
            if ll.has_cursor:
                cursor_line_index = i
                break

        # Adjust scroll offset to keep cursor visible
        if cursor_line_index < self._scroll_offset:
            self._scroll_offset = cursor_line_index
        elif cursor_line_index >= self._scroll_offset + max_visible_lines:
            self._scroll_offset = cursor_line_index - max_visible_lines + 1

        # Clamp scroll offset
        max_scroll_offset = max(0, len(layout_lines) - max_visible_lines)
        self._scroll_offset = max(0, min(self._scroll_offset, max_scroll_offset))

        # Get visible lines slice
        visible_lines = layout_lines[self._scroll_offset : self._scroll_offset + max_visible_lines]

        result: list[str] = []
        left_padding = " " * padding_x
        right_padding = left_padding

        # Top border (with scroll indicator if scrolled down)
        if self._scroll_offset > 0:
            indicator = f"\u2500\u2500\u2500 \u2191 {self._scroll_offset} more "
            remaining = width - visible_width(indicator)
            result.append(self.border_color(indicator + "\u2500" * max(0, remaining)))
        else:
            result.append(horizontal * width)

        # Render each visible layout line
        emit_cursor_marker = self.focused and not self._autocomplete_state

        for layout_line in visible_lines:
            display_text = layout_line.text
            line_visible_width = visible_width(layout_line.text)
            cursor_in_padding = False

            if layout_line.has_cursor and layout_line.cursor_pos is not None:
                before = display_text[: layout_line.cursor_pos]
                after = display_text[layout_line.cursor_pos :]

                marker = CURSOR_MARKER if emit_cursor_marker else ""

                if len(after) > 0:
                    # Cursor is on a character - replace with highlighted version
                    after_graphemes = _segmenter(after)
                    first_grapheme = after_graphemes[0] if after_graphemes else ""
                    rest_after = after[len(first_grapheme) :]
                    cursor = f"\x1b[7m{first_grapheme}\x1b[0m"
                    display_text = before + marker + cursor + rest_after
                else:
                    # Cursor at end - add highlighted space
                    cursor = "\x1b[7m \x1b[0m"
                    display_text = before + marker + cursor
                    line_visible_width += 1
                    if line_visible_width > content_width and padding_x > 0:
                        cursor_in_padding = True

            padding = " " * max(0, content_width - line_visible_width)
            line_right_padding = right_padding[1:] if cursor_in_padding else right_padding

            result.append(f"{left_padding}{display_text}{padding}{line_right_padding}")

        # Bottom border (with scroll indicator if more content below)
        lines_below = len(layout_lines) - (self._scroll_offset + len(visible_lines))
        if lines_below > 0:
            indicator = f"\u2500\u2500\u2500 \u2193 {lines_below} more "
            remaining = width - visible_width(indicator)
            result.append(self.border_color(indicator + "\u2500" * max(0, remaining)))
        else:
            result.append(horizontal * width)

        # Add autocomplete list if active
        if self._autocomplete_state and self._autocomplete_list:
            autocomplete_result = self._autocomplete_list.render(content_width)
            for line in autocomplete_result:
                line_width = visible_width(line)
                line_padding = " " * max(0, content_width - line_width)
                result.append(f"{left_padding}{line}{line_padding}{right_padding}")

        return result

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()

        # Handle character jump mode (awaiting next character to jump to)
        if self._jump_mode is not None:
            if kb.matches(data, "jumpForward") or kb.matches(data, "jumpBackward"):
                self._jump_mode = None
                return

            if ord(data[0]) >= 32 if data else False:
                direction = self._jump_mode
                self._jump_mode = None
                self._jump_to_char(data, direction)
                return

            # Control character - cancel and fall through
            self._jump_mode = None

        # Handle bracketed paste mode
        if "\x1b[200~" in data:
            self._is_in_paste = True
            self._paste_buffer = ""
            data = data.replace("\x1b[200~", "")

        if self._is_in_paste:
            self._paste_buffer += data
            end_index = self._paste_buffer.find("\x1b[201~")
            if end_index != -1:
                paste_content = self._paste_buffer[:end_index]
                if paste_content:
                    self._handle_paste(paste_content)
                self._is_in_paste = False
                remaining = self._paste_buffer[end_index + 6 :]
                self._paste_buffer = ""
                if remaining:
                    self.handle_input(remaining)
                return
            return

        # Ctrl+C - let parent handle
        if kb.matches(data, "copy"):
            return

        # Undo
        if kb.matches(data, "undo"):
            self._undo()
            return

        # Handle autocomplete mode
        if self._autocomplete_state and self._autocomplete_list:
            if kb.matches(data, "selectCancel"):
                self._cancel_autocomplete()
                return

            if kb.matches(data, "selectUp") or kb.matches(data, "selectDown"):
                self._autocomplete_list.handle_input(data)
                return

            if kb.matches(data, "tab"):
                selected = self._autocomplete_list.get_selected_item()
                if selected and self._autocomplete_provider:
                    self._push_undo_snapshot()
                    self._last_action = None
                    result = self._autocomplete_provider.apply_completion(
                        self._state.lines,
                        self._state.cursor_line,
                        self._state.cursor_col,
                        selected,
                        self._autocomplete_prefix,
                    )
                    self._state.lines = result["lines"]
                    self._state.cursor_line = result["cursor_line"]
                    self._set_cursor_col(result["cursor_col"])
                    self._cancel_autocomplete()
                    if self.on_change:
                        self.on_change(self.get_text())
                return

            if kb.matches(data, "selectConfirm"):
                selected = self._autocomplete_list.get_selected_item()
                if selected and self._autocomplete_provider:
                    self._push_undo_snapshot()
                    self._last_action = None
                    result = self._autocomplete_provider.apply_completion(
                        self._state.lines,
                        self._state.cursor_line,
                        self._state.cursor_col,
                        selected,
                        self._autocomplete_prefix,
                    )
                    self._state.lines = result["lines"]
                    self._state.cursor_line = result["cursor_line"]
                    self._set_cursor_col(result["cursor_col"])

                    if self._autocomplete_prefix.startswith("/"):
                        self._cancel_autocomplete()
                        # Fall through to submit
                    else:
                        self._cancel_autocomplete()
                        if self.on_change:
                            self.on_change(self.get_text())
                        return

        # Tab - trigger completion
        if kb.matches(data, "tab") and not self._autocomplete_state:
            self._handle_tab_completion()
            return

        # Deletion actions
        if kb.matches(data, "deleteToLineEnd"):
            self._delete_to_end_of_line()
            return
        if kb.matches(data, "deleteToLineStart"):
            self._delete_to_start_of_line()
            return
        if kb.matches(data, "deleteWordBackward"):
            self._delete_word_backwards()
            return
        if kb.matches(data, "deleteWordForward"):
            self._delete_word_forward()
            return
        if kb.matches(data, "deleteCharBackward") or matches_key(data, "shift+backspace"):
            self._handle_backspace()
            return
        if kb.matches(data, "deleteCharForward") or matches_key(data, "shift+delete"):
            self._handle_forward_delete()
            return

        # Kill ring actions
        if kb.matches(data, "yank"):
            self._yank()
            return
        if kb.matches(data, "yankPop"):
            self._yank_pop()
            return

        # Cursor movement actions
        if kb.matches(data, "cursorLineStart"):
            self._move_to_line_start()
            return
        if kb.matches(data, "cursorLineEnd"):
            self._move_to_line_end()
            return
        if kb.matches(data, "cursorWordLeft"):
            self._move_word_backwards()
            return
        if kb.matches(data, "cursorWordRight"):
            self._move_word_forwards()
            return

        # New line
        if (
            kb.matches(data, "newLine")
            or (len(data) > 1 and ord(data[0]) == 10)
            or data == "\x1b\r"
            or data == "\x1b[13;2~"
            or (len(data) > 1 and "\x1b" in data and "\r" in data)
            or (data == "\n" and len(data) == 1)
        ):
            if self._should_submit_on_backslash_enter(data, kb):
                self._handle_backspace()
                self._submit_value()
                return
            self._add_new_line()
            return

        # Submit (Enter)
        if kb.matches(data, "submit"):
            if self.disable_submit:
                return

            current_line = self._state.lines[self._state.cursor_line] or ""
            if (
                self._state.cursor_col > 0
                and self._state.cursor_col <= len(current_line)
                and current_line[self._state.cursor_col - 1] == "\\"
            ):
                self._handle_backspace()
                self._add_new_line()
                return

            self._submit_value()
            return

        # Arrow key navigation (with history support)
        if kb.matches(data, "cursorUp"):
            if self._is_editor_empty() or (self._history_index > -1 and self._is_on_first_visual_line()):
                self._navigate_history(-1)
            elif self._is_on_first_visual_line():
                self._move_to_line_start()
            else:
                self._move_cursor(-1, 0)
            return
        if kb.matches(data, "cursorDown"):
            if self._history_index > -1 and self._is_on_last_visual_line():
                self._navigate_history(1)
            elif self._is_on_last_visual_line():
                self._move_to_line_end()
            else:
                self._move_cursor(1, 0)
            return
        if kb.matches(data, "cursorRight"):
            self._move_cursor(0, 1)
            return
        if kb.matches(data, "cursorLeft"):
            self._move_cursor(0, -1)
            return

        # Page up/down
        if kb.matches(data, "pageUp"):
            self._page_scroll(-1)
            return
        if kb.matches(data, "pageDown"):
            self._page_scroll(1)
            return

        # Character jump mode triggers
        if kb.matches(data, "jumpForward"):
            self._jump_mode = "forward"
            return
        if kb.matches(data, "jumpBackward"):
            self._jump_mode = "backward"
            return

        # Shift+Space - insert regular space
        if matches_key(data, "shift+space"):
            self._insert_character(" ")
            return

        kitty_printable = _decode_kitty_printable(data)
        if kitty_printable is not None:
            self._insert_character(kitty_printable)
            return

        # Regular characters
        if data and ord(data[0]) >= 32:
            self._insert_character(data)

    # -- Layout --------------------------------------------------------------

    def _layout_text(self, content_width: int) -> list[_LayoutLine]:
        layout_lines: list[_LayoutLine] = []

        if not self._state.lines or (len(self._state.lines) == 1 and self._state.lines[0] == ""):
            layout_lines.append(_LayoutLine(text="", has_cursor=True, cursor_pos=0))
            return layout_lines

        for i, line in enumerate(self._state.lines):
            is_current_line = i == self._state.cursor_line
            line_vis_width = visible_width(line)

            if line_vis_width <= content_width:
                if is_current_line:
                    layout_lines.append(
                        _LayoutLine(
                            text=line,
                            has_cursor=True,
                            cursor_pos=self._state.cursor_col,
                        )
                    )
                else:
                    layout_lines.append(_LayoutLine(text=line, has_cursor=False))
            else:
                chunks = word_wrap_line(line, content_width)
                for chunk_index, chunk in enumerate(chunks):
                    cursor_pos = self._state.cursor_col
                    is_last_chunk = chunk_index == len(chunks) - 1

                    has_cursor_in_chunk = False
                    adjusted_cursor_pos = 0

                    if is_current_line:
                        if is_last_chunk:
                            has_cursor_in_chunk = cursor_pos >= chunk.start_index
                            adjusted_cursor_pos = cursor_pos - chunk.start_index
                        else:
                            has_cursor_in_chunk = cursor_pos >= chunk.start_index and cursor_pos < chunk.end_index
                            if has_cursor_in_chunk:
                                adjusted_cursor_pos = cursor_pos - chunk.start_index
                                if adjusted_cursor_pos > len(chunk.text):
                                    adjusted_cursor_pos = len(chunk.text)

                    if has_cursor_in_chunk:
                        layout_lines.append(
                            _LayoutLine(
                                text=chunk.text,
                                has_cursor=True,
                                cursor_pos=adjusted_cursor_pos,
                            )
                        )
                    else:
                        layout_lines.append(_LayoutLine(text=chunk.text, has_cursor=False))

        return layout_lines

    # -- Public text API -----------------------------------------------------

    def get_text(self) -> str:
        return "\n".join(self._state.lines)

    def get_expanded_text(self) -> str:
        """Get text with paste markers expanded to their actual content."""
        result = "\n".join(self._state.lines)
        for paste_id, paste_content in self._pastes.items():
            marker_regex = re.compile(rf"\[paste #{paste_id}( (\+\d+ lines|\d+ chars))?\]")
            result = marker_regex.sub(paste_content, result)
        return result

    def get_lines(self) -> list[str]:
        return list(self._state.lines)

    def get_cursor(self) -> dict[str, int]:
        return {"line": self._state.cursor_line, "col": self._state.cursor_col}

    def set_text(self, text: str) -> None:
        self._last_action = None
        self._history_index = -1
        if self.get_text() != text:
            self._push_undo_snapshot()
        self._set_text_internal(text)

    def insert_text_at_cursor(self, text: str) -> None:
        """Insert text at the current cursor position (programmatic)."""
        if not text:
            return
        self._push_undo_snapshot()
        self._last_action = None
        self._history_index = -1
        self._insert_text_at_cursor_internal(text)

    def _insert_text_at_cursor_internal(self, text: str) -> None:
        """Internal text insertion at cursor. Handles single and multi-line text."""
        if not text:
            return

        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        inserted_lines = normalized.split("\n")

        current_line = self._state.lines[self._state.cursor_line] or ""
        before_cursor = current_line[: self._state.cursor_col]
        after_cursor = current_line[self._state.cursor_col :]

        if len(inserted_lines) == 1:
            self._state.lines[self._state.cursor_line] = before_cursor + normalized + after_cursor
            self._set_cursor_col(self._state.cursor_col + len(normalized))
        else:
            new_lines = [
                *self._state.lines[: self._state.cursor_line],
                before_cursor + inserted_lines[0],
                *inserted_lines[1:-1],
                inserted_lines[-1] + after_cursor,
                *self._state.lines[self._state.cursor_line + 1 :],
            ]
            self._state.lines = new_lines
            self._state.cursor_line += len(inserted_lines) - 1
            self._set_cursor_col(len(inserted_lines[-1]))

        if self.on_change:
            self.on_change(self.get_text())

    # -- Character insertion -------------------------------------------------

    def _insert_character(self, char: str, skip_undo_coalescing: bool = False) -> None:
        self._history_index = -1

        if not skip_undo_coalescing:
            if is_whitespace_char(char) or self._last_action != "type-word":
                self._push_undo_snapshot()
            self._last_action = "type-word"

        line = self._state.lines[self._state.cursor_line] or ""
        before = line[: self._state.cursor_col]
        after = line[self._state.cursor_col :]

        self._state.lines[self._state.cursor_line] = before + char + after
        self._set_cursor_col(self._state.cursor_col + len(char))

        if self.on_change:
            self.on_change(self.get_text())

        # Check if we should trigger or update autocomplete
        if not self._autocomplete_state:
            if char == "/" and self._is_at_start_of_message():
                self._try_trigger_autocomplete()
            elif char == "@":
                current_line = self._state.lines[self._state.cursor_line] or ""
                text_before_cursor = current_line[: self._state.cursor_col]
                char_before_at = text_before_cursor[-2] if len(text_before_cursor) >= 2 else ""
                if len(text_before_cursor) == 1 or char_before_at == " " or char_before_at == "\t":
                    self._try_trigger_autocomplete()
            elif re.match(r"[a-zA-Z0-9.\-_]", char):
                current_line = self._state.lines[self._state.cursor_line] or ""
                text_before_cursor = current_line[: self._state.cursor_col]
                if self._is_in_slash_command_context(text_before_cursor) or re.search(
                    r"(?:^|[\s])@[^\s]*$", text_before_cursor
                ):
                    self._try_trigger_autocomplete()
        else:
            self._update_autocomplete()

    # -- Paste handling ------------------------------------------------------

    def _handle_paste(self, pasted_text: str) -> None:
        self._history_index = -1
        self._last_action = None

        self._push_undo_snapshot()

        clean_text = pasted_text.replace("\r\n", "\n").replace("\r", "\n")
        tab_expanded = clean_text.replace("\t", "    ")

        # Filter out non-printable characters except newlines
        filtered_text = "".join(ch for ch in tab_expanded if ch == "\n" or ord(ch) >= 32)

        # If pasting a file path, prepend space for readability
        if re.match(r"^[/~.]", filtered_text):
            current_line = self._state.lines[self._state.cursor_line] or ""
            char_before = current_line[self._state.cursor_col - 1] if self._state.cursor_col > 0 else ""
            if char_before and re.match(r"\w", char_before):
                filtered_text = f" {filtered_text}"

        pasted_lines = filtered_text.split("\n")
        total_chars = len(filtered_text)

        if len(pasted_lines) > 10 or total_chars > 1000:
            # Store the paste and insert a marker
            self._paste_counter += 1
            paste_id = self._paste_counter
            self._pastes[paste_id] = filtered_text

            marker = (
                f"[paste #{paste_id} +{len(pasted_lines)} lines]"
                if len(pasted_lines) > 10
                else f"[paste #{paste_id} {total_chars} chars]"
            )
            self._insert_text_at_cursor_internal(marker)
            return

        if len(pasted_lines) == 1:
            for ch in filtered_text:
                self._insert_character(ch, skip_undo_coalescing=True)
            return

        self._insert_text_at_cursor_internal(filtered_text)

    # -- New line / submit ---------------------------------------------------

    def _add_new_line(self) -> None:
        self._history_index = -1
        self._last_action = None
        self._push_undo_snapshot()

        current_line = self._state.lines[self._state.cursor_line] or ""
        before = current_line[: self._state.cursor_col]
        after = current_line[self._state.cursor_col :]

        self._state.lines[self._state.cursor_line] = before
        self._state.lines.insert(self._state.cursor_line + 1, after)

        self._state.cursor_line += 1
        self._set_cursor_col(0)

        if self.on_change:
            self.on_change(self.get_text())

    def _should_submit_on_backslash_enter(self, data: str, kb: object) -> bool:
        if self.disable_submit:
            return False
        if not matches_key(data, "enter"):
            return False
        real_kb = get_editor_keybindings()
        submit_keys = real_kb.get_keys("submit")
        has_shift_enter = "shift+enter" in submit_keys or "shift+return" in submit_keys
        if not has_shift_enter:
            return False

        current_line = self._state.lines[self._state.cursor_line] or ""
        return (
            self._state.cursor_col > 0
            and self._state.cursor_col <= len(current_line)
            and current_line[self._state.cursor_col - 1] == "\\"
        )

    def _submit_value(self) -> None:
        result = "\n".join(self._state.lines).strip()
        for paste_id, paste_content in self._pastes.items():
            marker_regex = re.compile(rf"\[paste #{paste_id}( (\+\d+ lines|\d+ chars))?\]")
            result = marker_regex.sub(paste_content, result)

        self._state = _EditorState()
        self._pastes.clear()
        self._paste_counter = 0
        self._history_index = -1
        self._scroll_offset = 0
        self._undo_stack.clear()
        self._last_action = None

        if self.on_change:
            self.on_change("")
        if self.on_submit:
            self.on_submit(result)

    # -- Backspace / delete --------------------------------------------------

    def _handle_backspace(self) -> None:
        self._history_index = -1
        self._last_action = None

        if self._state.cursor_col > 0:
            self._push_undo_snapshot()

            line = self._state.lines[self._state.cursor_line] or ""
            before_cursor = line[: self._state.cursor_col]

            graphemes = _segmenter(before_cursor)
            last_grapheme = graphemes[-1] if graphemes else ""
            grapheme_length = len(last_grapheme) if last_grapheme else 1

            before = line[: self._state.cursor_col - grapheme_length]
            after = line[self._state.cursor_col :]

            self._state.lines[self._state.cursor_line] = before + after
            self._set_cursor_col(self._state.cursor_col - grapheme_length)
        elif self._state.cursor_line > 0:
            self._push_undo_snapshot()

            current_line = self._state.lines[self._state.cursor_line] or ""
            previous_line = self._state.lines[self._state.cursor_line - 1] or ""

            self._state.lines[self._state.cursor_line - 1] = previous_line + current_line
            del self._state.lines[self._state.cursor_line]

            self._state.cursor_line -= 1
            self._set_cursor_col(len(previous_line))

        if self.on_change:
            self.on_change(self.get_text())

        # Update or re-trigger autocomplete after backspace
        if self._autocomplete_state:
            self._update_autocomplete()
        else:
            current_line = self._state.lines[self._state.cursor_line] or ""
            text_before_cursor = current_line[: self._state.cursor_col]
            if self._is_in_slash_command_context(text_before_cursor) or re.search(
                r"(?:^|[\s])@[^\s]*$", text_before_cursor
            ):
                self._try_trigger_autocomplete()

    def _handle_forward_delete(self) -> None:
        self._history_index = -1
        self._last_action = None

        current_line = self._state.lines[self._state.cursor_line] or ""

        if self._state.cursor_col < len(current_line):
            self._push_undo_snapshot()

            after_cursor = current_line[self._state.cursor_col :]
            graphemes = _segmenter(after_cursor)
            first_grapheme = graphemes[0] if graphemes else ""
            grapheme_length = len(first_grapheme) if first_grapheme else 1

            before = current_line[: self._state.cursor_col]
            after = current_line[self._state.cursor_col + grapheme_length :]
            self._state.lines[self._state.cursor_line] = before + after
        elif self._state.cursor_line < len(self._state.lines) - 1:
            self._push_undo_snapshot()

            next_line = self._state.lines[self._state.cursor_line + 1] or ""
            self._state.lines[self._state.cursor_line] = current_line + next_line
            del self._state.lines[self._state.cursor_line + 1]

        if self.on_change:
            self.on_change(self.get_text())

        # Update or re-trigger autocomplete after forward delete
        if self._autocomplete_state:
            self._update_autocomplete()
        else:
            current_line = self._state.lines[self._state.cursor_line] or ""
            text_before_cursor = current_line[: self._state.cursor_col]
            if self._is_in_slash_command_context(text_before_cursor) or re.search(
                r"(?:^|[\s])@[^\s]*$", text_before_cursor
            ):
                self._try_trigger_autocomplete()

    # -- Cursor column setter ------------------------------------------------

    def _set_cursor_col(self, col: int) -> None:
        """Set cursor column and clear preferredVisualCol."""
        self._state.cursor_col = col
        self._preferred_visual_col = None

    # -- Visual line map for cursor navigation -------------------------------

    def _build_visual_line_map(self, width: int) -> list[_VisualLineEntry]:
        visual_lines: list[_VisualLineEntry] = []

        for i, line in enumerate(self._state.lines):
            line_vis_width = visible_width(line)
            if len(line) == 0:
                visual_lines.append(_VisualLineEntry(logical_line=i, start_col=0, length=0))
            elif line_vis_width <= width:
                visual_lines.append(_VisualLineEntry(logical_line=i, start_col=0, length=len(line)))
            else:
                chunks = word_wrap_line(line, width)
                for chunk in chunks:
                    visual_lines.append(
                        _VisualLineEntry(
                            logical_line=i,
                            start_col=chunk.start_index,
                            length=chunk.end_index - chunk.start_index,
                        )
                    )

        return visual_lines

    def _find_current_visual_line(self, visual_lines: list[_VisualLineEntry]) -> int:
        for i, vl in enumerate(visual_lines):
            if vl.logical_line == self._state.cursor_line:
                col_in_segment = self._state.cursor_col - vl.start_col
                is_last_segment_of_line = (
                    i == len(visual_lines) - 1 or visual_lines[i + 1].logical_line != vl.logical_line
                )
                if col_in_segment >= 0 and (
                    col_in_segment < vl.length or (is_last_segment_of_line and col_in_segment <= vl.length)
                ):
                    return i
        return len(visual_lines) - 1

    # -- Cursor movement -----------------------------------------------------

    def _move_to_visual_line(
        self,
        visual_lines: list[_VisualLineEntry],
        current_visual_line: int,
        target_visual_line: int,
    ) -> None:
        current_vl = visual_lines[current_visual_line]
        target_vl = visual_lines[target_visual_line]

        current_visual_col = self._state.cursor_col - current_vl.start_col

        is_last_source_segment = (
            current_visual_line == len(visual_lines) - 1
            or visual_lines[current_visual_line + 1].logical_line != current_vl.logical_line
        )
        source_max_visual_col = current_vl.length if is_last_source_segment else max(0, current_vl.length - 1)

        is_last_target_segment = (
            target_visual_line == len(visual_lines) - 1
            or visual_lines[target_visual_line + 1].logical_line != target_vl.logical_line
        )
        target_max_visual_col = target_vl.length if is_last_target_segment else max(0, target_vl.length - 1)

        move_to_visual_col = self._compute_vertical_move_column(
            current_visual_col, source_max_visual_col, target_max_visual_col
        )

        self._state.cursor_line = target_vl.logical_line
        target_col = target_vl.start_col + move_to_visual_col
        logical_line = self._state.lines[target_vl.logical_line] or ""
        self._state.cursor_col = min(target_col, len(logical_line))

    def _compute_vertical_move_column(
        self,
        current_visual_col: int,
        source_max_visual_col: int,
        target_max_visual_col: int,
    ) -> int:
        """Implement sticky column decision table for vertical cursor movement."""
        has_preferred = self._preferred_visual_col is not None
        cursor_in_middle = current_visual_col < source_max_visual_col
        target_too_short = target_max_visual_col < current_visual_col

        if not has_preferred or cursor_in_middle:
            if target_too_short:
                self._preferred_visual_col = current_visual_col
                return target_max_visual_col
            self._preferred_visual_col = None
            return current_visual_col

        assert self._preferred_visual_col is not None
        target_cant_fit_preferred = target_max_visual_col < self._preferred_visual_col
        if target_too_short or target_cant_fit_preferred:
            return target_max_visual_col

        result = self._preferred_visual_col
        self._preferred_visual_col = None
        return result

    def _move_to_line_start(self) -> None:
        self._last_action = None
        self._set_cursor_col(0)

    def _move_to_line_end(self) -> None:
        self._last_action = None
        current_line = self._state.lines[self._state.cursor_line] or ""
        self._set_cursor_col(len(current_line))

    def _move_cursor(self, delta_line: int, delta_col: int) -> None:
        self._last_action = None
        visual_lines = self._build_visual_line_map(self._last_width)
        current_visual_line = self._find_current_visual_line(visual_lines)

        if delta_line != 0:
            target_visual_line = current_visual_line + delta_line
            if 0 <= target_visual_line < len(visual_lines):
                self._move_to_visual_line(visual_lines, current_visual_line, target_visual_line)

        if delta_col != 0:
            current_line = self._state.lines[self._state.cursor_line] or ""

            if delta_col > 0:
                if self._state.cursor_col < len(current_line):
                    after_cursor = current_line[self._state.cursor_col :]
                    graphemes = _segmenter(after_cursor)
                    first_grapheme = graphemes[0] if graphemes else ""
                    self._set_cursor_col(self._state.cursor_col + (len(first_grapheme) if first_grapheme else 1))
                elif self._state.cursor_line < len(self._state.lines) - 1:
                    self._state.cursor_line += 1
                    self._set_cursor_col(0)
                else:
                    current_vl = visual_lines[current_visual_line]
                    self._preferred_visual_col = self._state.cursor_col - current_vl.start_col
            else:
                if self._state.cursor_col > 0:
                    before_cursor = current_line[: self._state.cursor_col]
                    graphemes = _segmenter(before_cursor)
                    last_grapheme = graphemes[-1] if graphemes else ""
                    self._set_cursor_col(self._state.cursor_col - (len(last_grapheme) if last_grapheme else 1))
                elif self._state.cursor_line > 0:
                    self._state.cursor_line -= 1
                    prev_line = self._state.lines[self._state.cursor_line] or ""
                    self._set_cursor_col(len(prev_line))

    def _page_scroll(self, direction: int) -> None:
        """Scroll by a page (-1 for up, 1 for down)."""
        self._last_action = None
        terminal_rows = self._tui.terminal.rows
        page_size = max(5, int(terminal_rows * 0.3))

        visual_lines = self._build_visual_line_map(self._last_width)
        current_visual_line = self._find_current_visual_line(visual_lines)
        target_visual_line = max(
            0,
            min(len(visual_lines) - 1, current_visual_line + direction * page_size),
        )

        self._move_to_visual_line(visual_lines, current_visual_line, target_visual_line)

    def _move_word_backwards(self) -> None:
        self._last_action = None
        current_line = self._state.lines[self._state.cursor_line] or ""

        if self._state.cursor_col == 0:
            if self._state.cursor_line > 0:
                self._state.cursor_line -= 1
                prev_line = self._state.lines[self._state.cursor_line] or ""
                self._set_cursor_col(len(prev_line))
            return

        text_before_cursor = current_line[: self._state.cursor_col]
        graphemes = _segmenter(text_before_cursor)
        new_col = self._state.cursor_col

        # Skip trailing whitespace
        while graphemes and is_whitespace_char(graphemes[-1]):
            new_col -= len(graphemes.pop())

        if graphemes:
            last_g = graphemes[-1]
            if is_punctuation_char(last_g):
                while graphemes and is_punctuation_char(graphemes[-1]):
                    new_col -= len(graphemes.pop())
            else:
                while graphemes and not is_whitespace_char(graphemes[-1]) and not is_punctuation_char(graphemes[-1]):
                    new_col -= len(graphemes.pop())

        self._set_cursor_col(new_col)

    def _move_word_forwards(self) -> None:
        self._last_action = None
        current_line = self._state.lines[self._state.cursor_line] or ""

        if self._state.cursor_col >= len(current_line):
            if self._state.cursor_line < len(self._state.lines) - 1:
                self._state.cursor_line += 1
                self._set_cursor_col(0)
            return

        text_after_cursor = current_line[self._state.cursor_col :]
        graphemes = _segmenter(text_after_cursor)
        new_col = self._state.cursor_col
        idx = 0

        # Skip leading whitespace
        while idx < len(graphemes) and is_whitespace_char(graphemes[idx]):
            new_col += len(graphemes[idx])
            idx += 1

        if idx < len(graphemes):
            first_g = graphemes[idx]
            if is_punctuation_char(first_g):
                while idx < len(graphemes) and is_punctuation_char(graphemes[idx]):
                    new_col += len(graphemes[idx])
                    idx += 1
            else:
                while (
                    idx < len(graphemes)
                    and not is_whitespace_char(graphemes[idx])
                    and not is_punctuation_char(graphemes[idx])
                ):
                    new_col += len(graphemes[idx])
                    idx += 1

        self._set_cursor_col(new_col)

    # -- Delete operations ---------------------------------------------------

    def _delete_to_start_of_line(self) -> None:
        self._history_index = -1
        current_line = self._state.lines[self._state.cursor_line] or ""

        if self._state.cursor_col > 0:
            self._push_undo_snapshot()

            deleted_text = current_line[: self._state.cursor_col]
            self._kill_ring.push(
                deleted_text,
                prepend=True,
                accumulate=self._last_action == "kill",
            )
            self._last_action = "kill"

            self._state.lines[self._state.cursor_line] = current_line[self._state.cursor_col :]
            self._set_cursor_col(0)
        elif self._state.cursor_line > 0:
            self._push_undo_snapshot()

            self._kill_ring.push("\n", prepend=True, accumulate=self._last_action == "kill")
            self._last_action = "kill"

            previous_line = self._state.lines[self._state.cursor_line - 1] or ""
            self._state.lines[self._state.cursor_line - 1] = previous_line + current_line
            del self._state.lines[self._state.cursor_line]
            self._state.cursor_line -= 1
            self._set_cursor_col(len(previous_line))

        if self.on_change:
            self.on_change(self.get_text())

    def _delete_to_end_of_line(self) -> None:
        self._history_index = -1
        current_line = self._state.lines[self._state.cursor_line] or ""

        if self._state.cursor_col < len(current_line):
            self._push_undo_snapshot()

            deleted_text = current_line[self._state.cursor_col :]
            self._kill_ring.push(
                deleted_text,
                prepend=False,
                accumulate=self._last_action == "kill",
            )
            self._last_action = "kill"

            self._state.lines[self._state.cursor_line] = current_line[: self._state.cursor_col]
        elif self._state.cursor_line < len(self._state.lines) - 1:
            self._push_undo_snapshot()

            self._kill_ring.push("\n", prepend=False, accumulate=self._last_action == "kill")
            self._last_action = "kill"

            next_line = self._state.lines[self._state.cursor_line + 1] or ""
            self._state.lines[self._state.cursor_line] = current_line + next_line
            del self._state.lines[self._state.cursor_line + 1]

        if self.on_change:
            self.on_change(self.get_text())

    def _delete_word_backwards(self) -> None:
        self._history_index = -1
        current_line = self._state.lines[self._state.cursor_line] or ""

        if self._state.cursor_col == 0:
            if self._state.cursor_line > 0:
                self._push_undo_snapshot()

                self._kill_ring.push("\n", prepend=True, accumulate=self._last_action == "kill")
                self._last_action = "kill"

                previous_line = self._state.lines[self._state.cursor_line - 1] or ""
                self._state.lines[self._state.cursor_line - 1] = previous_line + current_line
                del self._state.lines[self._state.cursor_line]
                self._state.cursor_line -= 1
                self._set_cursor_col(len(previous_line))
        else:
            self._push_undo_snapshot()

            was_kill = self._last_action == "kill"

            old_cursor_col = self._state.cursor_col
            self._move_word_backwards()
            delete_from = self._state.cursor_col
            self._set_cursor_col(old_cursor_col)

            deleted_text = current_line[delete_from : self._state.cursor_col]
            self._kill_ring.push(deleted_text, prepend=True, accumulate=was_kill)
            self._last_action = "kill"

            self._state.lines[self._state.cursor_line] = (
                current_line[:delete_from] + current_line[self._state.cursor_col :]
            )
            self._set_cursor_col(delete_from)

        if self.on_change:
            self.on_change(self.get_text())

    def _delete_word_forward(self) -> None:
        self._history_index = -1
        current_line = self._state.lines[self._state.cursor_line] or ""

        if self._state.cursor_col >= len(current_line):
            if self._state.cursor_line < len(self._state.lines) - 1:
                self._push_undo_snapshot()

                self._kill_ring.push("\n", prepend=False, accumulate=self._last_action == "kill")
                self._last_action = "kill"

                next_line = self._state.lines[self._state.cursor_line + 1] or ""
                self._state.lines[self._state.cursor_line] = current_line + next_line
                del self._state.lines[self._state.cursor_line + 1]
        else:
            self._push_undo_snapshot()

            was_kill = self._last_action == "kill"

            old_cursor_col = self._state.cursor_col
            self._move_word_forwards()
            delete_to = self._state.cursor_col
            self._set_cursor_col(old_cursor_col)

            deleted_text = current_line[self._state.cursor_col : delete_to]
            self._kill_ring.push(deleted_text, prepend=False, accumulate=was_kill)
            self._last_action = "kill"

            self._state.lines[self._state.cursor_line] = (
                current_line[: self._state.cursor_col] + current_line[delete_to:]
            )

        if self.on_change:
            self.on_change(self.get_text())

    # -- Kill ring -----------------------------------------------------------

    def _yank(self) -> None:
        if self._kill_ring.length == 0:
            return

        self._push_undo_snapshot()

        text = self._kill_ring.peek()
        if text is None:
            return
        self._insert_yanked_text(text)
        self._last_action = "yank"

    def _yank_pop(self) -> None:
        if self._last_action != "yank" or self._kill_ring.length <= 1:
            return

        self._push_undo_snapshot()
        self._delete_yanked_text()
        self._kill_ring.rotate()

        text = self._kill_ring.peek()
        if text is None:
            return
        self._insert_yanked_text(text)
        self._last_action = "yank"

    def _insert_yanked_text(self, text: str) -> None:
        self._history_index = -1
        lines = text.split("\n")

        if len(lines) == 1:
            current_line = self._state.lines[self._state.cursor_line] or ""
            before = current_line[: self._state.cursor_col]
            after = current_line[self._state.cursor_col :]
            self._state.lines[self._state.cursor_line] = before + text + after
            self._set_cursor_col(self._state.cursor_col + len(text))
        else:
            current_line = self._state.lines[self._state.cursor_line] or ""
            before = current_line[: self._state.cursor_col]
            after = current_line[self._state.cursor_col :]

            self._state.lines[self._state.cursor_line] = before + (lines[0] or "")

            for idx in range(1, len(lines) - 1):
                self._state.lines.insert(self._state.cursor_line + idx, lines[idx] or "")

            last_line_index = self._state.cursor_line + len(lines) - 1
            self._state.lines.insert(last_line_index, (lines[-1] or "") + after)

            self._state.cursor_line = last_line_index
            self._set_cursor_col(len(lines[-1] or ""))

        if self.on_change:
            self.on_change(self.get_text())

    def _delete_yanked_text(self) -> None:
        yanked_text = self._kill_ring.peek()
        if not yanked_text:
            return

        yank_lines = yanked_text.split("\n")

        if len(yank_lines) == 1:
            current_line = self._state.lines[self._state.cursor_line] or ""
            delete_len = len(yanked_text)
            before = current_line[: self._state.cursor_col - delete_len]
            after = current_line[self._state.cursor_col :]
            self._state.lines[self._state.cursor_line] = before + after
            self._set_cursor_col(self._state.cursor_col - delete_len)
        else:
            start_line = self._state.cursor_line - (len(yank_lines) - 1)
            start_col = len(self._state.lines[start_line] or "") - len(yank_lines[0] or "")

            after_cursor = (self._state.lines[self._state.cursor_line] or "")[self._state.cursor_col :]
            before_yank = (self._state.lines[start_line] or "")[:start_col]

            self._state.lines[start_line : self._state.cursor_line + 1] = [before_yank + after_cursor]

            self._state.cursor_line = start_line
            self._set_cursor_col(start_col)

        if self.on_change:
            self.on_change(self.get_text())

    # -- Undo ----------------------------------------------------------------

    def _push_undo_snapshot(self) -> None:
        self._undo_stack.push(self._state)

    def _undo(self) -> None:
        self._history_index = -1
        snapshot = self._undo_stack.pop()
        if snapshot is None:
            return
        self._state.lines = snapshot.lines
        self._state.cursor_line = snapshot.cursor_line
        self._state.cursor_col = snapshot.cursor_col
        self._last_action = None
        self._preferred_visual_col = None
        if self.on_change:
            self.on_change(self.get_text())

    # -- Character jump ------------------------------------------------------

    def _jump_to_char(self, char: str, direction: str) -> None:
        """Jump to first occurrence of a character in the specified direction."""
        self._last_action = None
        is_forward = direction == "forward"
        lines = self._state.lines

        if is_forward:
            line_range = range(self._state.cursor_line, len(lines))
        else:
            line_range = range(self._state.cursor_line, -1, -1)

        for line_idx in line_range:
            line = lines[line_idx] or ""
            is_current_line = line_idx == self._state.cursor_line

            if is_current_line:
                search_from: int | None = self._state.cursor_col + 1 if is_forward else self._state.cursor_col - 1
            else:
                search_from = None

            if is_forward:
                idx = line.find(char, search_from or 0)
            else:
                if search_from is not None and search_from < 0:
                    idx = -1
                else:
                    idx = line.rfind(char, 0, (search_from + 1) if search_from is not None else len(line))

            if idx != -1:
                self._state.cursor_line = line_idx
                self._set_cursor_col(idx)
                return

    # -- Slash menu / autocomplete helpers -----------------------------------

    def _is_slash_menu_allowed(self) -> bool:
        return self._state.cursor_line == 0

    def _is_at_start_of_message(self) -> bool:
        if not self._is_slash_menu_allowed():
            return False
        current_line = self._state.lines[self._state.cursor_line] or ""
        before_cursor = current_line[: self._state.cursor_col]
        stripped = before_cursor.strip()
        return stripped == "" or stripped == "/"

    def _is_in_slash_command_context(self, text_before_cursor: str) -> bool:
        return self._is_slash_menu_allowed() and text_before_cursor.lstrip().startswith("/")

    # -- Autocomplete --------------------------------------------------------

    def _try_trigger_autocomplete(self, explicit_tab: bool = False) -> None:
        if not self._autocomplete_provider:
            return

        if explicit_tab:
            provider = self._autocomplete_provider
            if isinstance(provider, CombinedAutocompleteProvider):
                should_trigger = provider.should_trigger_file_completion(
                    self._state.lines,
                    self._state.cursor_line,
                    self._state.cursor_col,
                )
                if not should_trigger:
                    return

        suggestions: SuggestionResult | None = self._autocomplete_provider.get_suggestions(
            self._state.lines,
            self._state.cursor_line,
            self._state.cursor_col,
        )

        if suggestions and suggestions["items"]:
            self._autocomplete_prefix = suggestions["prefix"]
            self._autocomplete_list = SelectList(
                suggestions["items"],
                self._autocomplete_max_visible,
                self._theme.select_list,
            )
            self._autocomplete_state = "regular"
        else:
            self._cancel_autocomplete()

    def _handle_tab_completion(self) -> None:
        if not self._autocomplete_provider:
            return

        current_line = self._state.lines[self._state.cursor_line] or ""
        before_cursor = current_line[: self._state.cursor_col]

        if self._is_in_slash_command_context(before_cursor) and " " not in before_cursor.lstrip():
            self._handle_slash_command_completion()
        else:
            self._force_file_autocomplete(explicit_tab=True)

    def _handle_slash_command_completion(self) -> None:
        self._try_trigger_autocomplete(explicit_tab=True)

    def _force_file_autocomplete(self, explicit_tab: bool = False) -> None:
        if not self._autocomplete_provider:
            return

        provider = self._autocomplete_provider
        if not isinstance(provider, CombinedAutocompleteProvider):
            self._try_trigger_autocomplete(explicit_tab=True)
            return

        if not hasattr(provider, "get_force_file_suggestions"):
            self._try_trigger_autocomplete(explicit_tab=True)
            return

        suggestions = provider.get_force_file_suggestions(
            self._state.lines,
            self._state.cursor_line,
            self._state.cursor_col,
        )

        if suggestions and suggestions["items"]:
            if explicit_tab and len(suggestions["items"]) == 1:
                item = suggestions["items"][0]
                self._push_undo_snapshot()
                self._last_action = None
                result = self._autocomplete_provider.apply_completion(
                    self._state.lines,
                    self._state.cursor_line,
                    self._state.cursor_col,
                    item,
                    suggestions["prefix"],
                )
                self._state.lines = result["lines"]
                self._state.cursor_line = result["cursor_line"]
                self._set_cursor_col(result["cursor_col"])
                if self.on_change:
                    self.on_change(self.get_text())
                return

            self._autocomplete_prefix = suggestions["prefix"]
            self._autocomplete_list = SelectList(
                suggestions["items"],
                self._autocomplete_max_visible,
                self._theme.select_list,
            )
            self._autocomplete_state = "force"
        else:
            self._cancel_autocomplete()

    def _cancel_autocomplete(self) -> None:
        self._autocomplete_state = None
        self._autocomplete_list = None
        self._autocomplete_prefix = ""

    def is_showing_autocomplete(self) -> bool:
        return self._autocomplete_state is not None

    def _update_autocomplete(self) -> None:
        if not self._autocomplete_state or not self._autocomplete_provider:
            return

        if self._autocomplete_state == "force":
            self._force_file_autocomplete()
            return

        suggestions = self._autocomplete_provider.get_suggestions(
            self._state.lines,
            self._state.cursor_line,
            self._state.cursor_col,
        )
        if suggestions and suggestions["items"]:
            self._autocomplete_prefix = suggestions["prefix"]
            self._autocomplete_list = SelectList(
                suggestions["items"],
                self._autocomplete_max_visible,
                self._theme.select_list,
            )
        else:
            self._cancel_autocomplete()


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "Editor",
    "EditorOptions",
    "EditorTheme",
    "TextChunk",
    "word_wrap_line",
]
