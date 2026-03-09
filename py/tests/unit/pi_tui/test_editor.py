"""Comprehensive unit tests for pi_tui.components.editor."""

from __future__ import annotations

from unittest.mock import MagicMock

from pi_tui.components.editor import (
    Editor,
    EditorOptions,
    EditorTheme,
    TextChunk,
    word_wrap_line,
)
from pi_tui.components.select_list import SelectListTheme

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _identity(s: str) -> str:
    """Identity styling function (no-op)."""
    return s


def _make_select_list_theme() -> SelectListTheme:
    return SelectListTheme(
        selected_prefix=_identity,
        selected_text=_identity,
        description=_identity,
        scroll_info=_identity,
        no_match=_identity,
    )


def _make_theme() -> EditorTheme:
    return EditorTheme(
        border_color=_identity,
        select_list=_make_select_list_theme(),
    )


def _make_mock_tui() -> MagicMock:
    """Create a mock TUI with a mock terminal that has rows/columns."""
    tui = MagicMock()
    tui.terminal.rows = 40
    tui.terminal.columns = 80
    return tui


def _make_editor(
    tui: MagicMock | None = None,
    options: EditorOptions | None = None,
) -> Editor:
    if tui is None:
        tui = _make_mock_tui()
    return Editor(tui, _make_theme(), options)


# Legacy terminal escape sequences for common keys
_KEY_DATA = {
    "left": "\x1b[D",
    "right": "\x1b[C",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "home": "\x1b[H",
    "end": "\x1b[F",
    "backspace": "\x7f",
    "delete": "\x1b[3~",
    "enter": "\r",
    "shift_enter": "\x1b[27;2;13~",  # xterm modifyOtherKeys format
    "ctrl_u": "\x15",  # ctrl+u
    "ctrl_k": "\x0b",  # ctrl+k
    "ctrl_w": "\x17",  # ctrl+w
    "ctrl_y": "\x19",  # ctrl+y
    "ctrl_minus": "\x1f",  # ctrl+-  (undo)
    "ctrl_a": "\x01",  # ctrl+a (home)
    "ctrl_e": "\x05",  # ctrl+e (end)
}


# =========================================================================
# word_wrap_line tests
# =========================================================================


class TestWordWrapLine:
    def test_empty_line(self) -> None:
        result = word_wrap_line("", 10)
        assert len(result) == 1
        assert result[0].text == ""
        assert result[0].start_index == 0
        assert result[0].end_index == 0

    def test_zero_width(self) -> None:
        result = word_wrap_line("hello", 0)
        assert len(result) == 1
        assert result[0].text == ""

    def test_negative_width(self) -> None:
        result = word_wrap_line("hello", -5)
        assert len(result) == 1
        assert result[0].text == ""

    def test_short_line_no_wrap(self) -> None:
        result = word_wrap_line("hello", 10)
        assert len(result) == 1
        assert result[0].text == "hello"
        assert result[0].start_index == 0
        assert result[0].end_index == 5

    def test_exact_width_no_wrap(self) -> None:
        result = word_wrap_line("hello", 5)
        assert len(result) == 1
        assert result[0].text == "hello"

    def test_wrap_at_word_boundary(self) -> None:
        result = word_wrap_line("hello world", 6)
        assert len(result) == 2
        assert result[0].text == "hello "
        assert result[1].text == "world"

    def test_wrap_long_word_force_break(self) -> None:
        result = word_wrap_line("abcdefghij", 5)
        # Should force-break since no whitespace
        assert len(result) >= 2
        total_text = "".join(chunk.text for chunk in result)
        assert total_text == "abcdefghij"

    def test_wrap_multiple_words(self) -> None:
        result = word_wrap_line("the quick brown fox", 10)
        assert len(result) >= 2
        total_text = "".join(chunk.text for chunk in result)
        assert total_text == "the quick brown fox"

    def test_wrap_preserves_indices(self) -> None:
        text = "hello world"
        result = word_wrap_line(text, 6)
        for chunk in result:
            assert text[chunk.start_index : chunk.end_index] == chunk.text

    def test_single_char_width(self) -> None:
        result = word_wrap_line("ab cd", 1)
        assert len(result) >= 2
        total_text = "".join(chunk.text for chunk in result)
        assert total_text == "ab cd"


# =========================================================================
# Editor construction tests
# =========================================================================


class TestEditorConstruction:
    def test_default_construction(self) -> None:
        editor = _make_editor()
        assert editor.get_text() == ""
        assert editor.focused is False
        assert editor.on_submit is None
        assert editor.on_change is None

    def test_construction_with_options(self) -> None:
        opts = EditorOptions(padding_x=2, autocomplete_max_visible=8)
        editor = _make_editor(options=opts)
        assert editor.get_padding_x() == 2
        assert editor.get_autocomplete_max_visible() == 8

    def test_padding_x_clamped_to_zero(self) -> None:
        opts = EditorOptions(padding_x=-5)
        editor = _make_editor(options=opts)
        assert editor.get_padding_x() == 0

    def test_autocomplete_max_visible_clamped(self) -> None:
        opts = EditorOptions(autocomplete_max_visible=1)
        editor = _make_editor(options=opts)
        assert editor.get_autocomplete_max_visible() == 3

        opts2 = EditorOptions(autocomplete_max_visible=100)
        editor2 = _make_editor(options=opts2)
        assert editor2.get_autocomplete_max_visible() == 20


# =========================================================================
# get_text / set_text tests
# =========================================================================


class TestGetSetText:
    def test_get_text_empty(self) -> None:
        editor = _make_editor()
        assert editor.get_text() == ""

    def test_set_text_simple(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        assert editor.get_text() == "hello"

    def test_set_text_multiline(self) -> None:
        editor = _make_editor()
        editor.set_text("line1\nline2\nline3")
        assert editor.get_text() == "line1\nline2\nline3"

    def test_set_text_normalizes_crlf(self) -> None:
        editor = _make_editor()
        editor.set_text("line1\r\nline2\rline3")
        assert editor.get_text() == "line1\nline2\nline3"

    def test_set_text_moves_cursor_to_end(self) -> None:
        editor = _make_editor()
        editor.set_text("hello\nworld")
        cursor = editor.get_cursor()
        assert cursor["line"] == 1
        assert cursor["col"] == 5

    def test_set_text_fires_on_change(self) -> None:
        editor = _make_editor()
        changes: list[str] = []
        editor.on_change = lambda t: changes.append(t)
        editor.set_text("test")
        assert len(changes) == 1
        assert changes[0] == "test"

    def test_get_lines(self) -> None:
        editor = _make_editor()
        editor.set_text("a\nb\nc")
        assert editor.get_lines() == ["a", "b", "c"]

    def test_get_cursor_initial(self) -> None:
        editor = _make_editor()
        cursor = editor.get_cursor()
        assert cursor["line"] == 0
        assert cursor["col"] == 0


# =========================================================================
# Text insertion via handle_input
# =========================================================================


class TestTextInsertion:
    def test_insert_single_char(self) -> None:
        editor = _make_editor()
        editor.handle_input("a")
        assert editor.get_text() == "a"
        assert editor.get_cursor()["col"] == 1

    def test_insert_multiple_chars(self) -> None:
        editor = _make_editor()
        for ch in "hello":
            editor.handle_input(ch)
        assert editor.get_text() == "hello"
        assert editor.get_cursor()["col"] == 5

    def test_insert_in_middle(self) -> None:
        editor = _make_editor()
        editor.set_text("hllo")
        # Move cursor to position 1 (after 'h')
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["right"])
        editor.handle_input("e")
        assert editor.get_text() == "hello"

    def test_insert_fires_on_change(self) -> None:
        editor = _make_editor()
        changes: list[str] = []
        editor.on_change = lambda t: changes.append(t)
        editor.handle_input("x")
        assert len(changes) >= 1
        assert changes[-1] == "x"


# =========================================================================
# Cursor movement tests
# =========================================================================


class TestCursorMovement:
    def test_move_left(self) -> None:
        editor = _make_editor()
        editor.set_text("abc")
        # Cursor is at end (col=3). Move left.
        editor.handle_input(_KEY_DATA["left"])
        assert editor.get_cursor()["col"] == 2

    def test_move_right(self) -> None:
        editor = _make_editor()
        editor.set_text("abc")
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["right"])
        assert editor.get_cursor()["col"] == 1

    def test_move_left_at_start_stays(self) -> None:
        editor = _make_editor()
        editor.set_text("abc")
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["left"])
        # Should stay at 0 (single line, no previous line)
        assert editor.get_cursor()["col"] == 0
        assert editor.get_cursor()["line"] == 0

    def test_move_right_at_end_stays(self) -> None:
        editor = _make_editor()
        editor.set_text("abc")
        # Cursor is at end (col=3)
        editor.handle_input(_KEY_DATA["right"])
        assert editor.get_cursor()["col"] == 3

    def test_home_key(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["home"])
        assert editor.get_cursor()["col"] == 0

    def test_end_key(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["end"])
        assert editor.get_cursor()["col"] == 5

    def test_ctrl_a_line_start(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["ctrl_a"])
        assert editor.get_cursor()["col"] == 0

    def test_ctrl_e_line_end(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["ctrl_e"])
        assert editor.get_cursor()["col"] == 5

    def test_move_left_wraps_to_previous_line(self) -> None:
        editor = _make_editor()
        editor.set_text("ab\ncd")
        # Cursor at end of line 1 (line=1, col=2)
        # Move to start of line 1
        editor.handle_input(_KEY_DATA["home"])
        assert editor.get_cursor()["line"] == 1
        assert editor.get_cursor()["col"] == 0
        # Move left should go to end of line 0
        editor.handle_input(_KEY_DATA["left"])
        assert editor.get_cursor()["line"] == 0
        assert editor.get_cursor()["col"] == 2

    def test_move_right_wraps_to_next_line(self) -> None:
        editor = _make_editor()
        editor.set_text("ab\ncd")
        # Move to end of first line
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["up"])
        editor.handle_input(_KEY_DATA["end"])
        assert editor.get_cursor()["line"] == 0
        assert editor.get_cursor()["col"] == 2
        # Move right should go to start of next line
        editor.handle_input(_KEY_DATA["right"])
        assert editor.get_cursor()["line"] == 1
        assert editor.get_cursor()["col"] == 0


# =========================================================================
# Up/Down cursor movement (visual lines)
# =========================================================================


class TestVerticalMovement:
    def test_move_up_on_first_line_goes_to_start(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        # On first visual line, up should go to line start
        editor.handle_input(_KEY_DATA["up"])
        assert editor.get_cursor()["col"] == 0

    def test_move_down_on_last_line_goes_to_end(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["home"])
        # On last visual line, down should go to line end
        editor.handle_input(_KEY_DATA["down"])
        assert editor.get_cursor()["col"] == 5

    def test_move_up_multiline(self) -> None:
        editor = _make_editor()
        editor.set_text("first\nsecond")
        # Cursor at end of line 1
        editor.handle_input(_KEY_DATA["up"])
        assert editor.get_cursor()["line"] == 0

    def test_move_down_multiline(self) -> None:
        editor = _make_editor()
        editor.set_text("first\nsecond")
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["up"])
        # Now on line 0
        editor.handle_input(_KEY_DATA["down"])
        assert editor.get_cursor()["line"] == 1


# =========================================================================
# Deletion tests
# =========================================================================


class TestDeletion:
    def test_backspace_single_char(self) -> None:
        editor = _make_editor()
        editor.set_text("abc")
        editor.handle_input(_KEY_DATA["backspace"])
        assert editor.get_text() == "ab"
        assert editor.get_cursor()["col"] == 2

    def test_backspace_at_start_of_line_joins(self) -> None:
        editor = _make_editor()
        editor.set_text("ab\ncd")
        # Move to start of line 1
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["backspace"])
        assert editor.get_text() == "abcd"
        assert editor.get_cursor()["line"] == 0
        assert editor.get_cursor()["col"] == 2

    def test_backspace_at_start_of_first_line_noop(self) -> None:
        editor = _make_editor()
        editor.set_text("abc")
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["backspace"])
        assert editor.get_text() == "abc"

    def test_delete_key(self) -> None:
        editor = _make_editor()
        editor.set_text("abc")
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["delete"])
        assert editor.get_text() == "bc"
        assert editor.get_cursor()["col"] == 0

    def test_delete_at_end_of_line_joins(self) -> None:
        editor = _make_editor()
        editor.set_text("ab\ncd")
        # Move to end of first line
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["up"])
        editor.handle_input(_KEY_DATA["end"])
        editor.handle_input(_KEY_DATA["delete"])
        assert editor.get_text() == "abcd"

    def test_delete_at_end_of_last_line_noop(self) -> None:
        editor = _make_editor()
        editor.set_text("abc")
        editor.handle_input(_KEY_DATA["delete"])
        assert editor.get_text() == "abc"

    def test_ctrl_u_delete_to_line_start(self) -> None:
        editor = _make_editor()
        editor.set_text("hello world")
        # Cursor at end (col=11)
        editor.handle_input(_KEY_DATA["ctrl_u"])
        assert editor.get_text() == ""
        assert editor.get_cursor()["col"] == 0

    def test_ctrl_k_delete_to_line_end(self) -> None:
        editor = _make_editor()
        editor.set_text("hello world")
        editor.handle_input(_KEY_DATA["home"])
        editor.handle_input(_KEY_DATA["ctrl_k"])
        assert editor.get_text() == ""

    def test_ctrl_w_delete_word_backward(self) -> None:
        editor = _make_editor()
        editor.set_text("hello world")
        editor.handle_input(_KEY_DATA["ctrl_w"])
        assert editor.get_text() == "hello "
        assert editor.get_cursor()["col"] == 6


# =========================================================================
# New line / multiline editing
# =========================================================================


class TestMultilineEditing:
    def test_new_line_via_shift_enter(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        # Shift+Enter adds new line
        editor.handle_input(_KEY_DATA["shift_enter"])
        assert editor.get_text() == "hello\n"
        assert editor.get_cursor()["line"] == 1
        assert editor.get_cursor()["col"] == 0

    def test_new_line_splits_at_cursor(self) -> None:
        editor = _make_editor()
        editor.set_text("helloworld")
        # Move cursor to middle
        editor.handle_input(_KEY_DATA["home"])
        for _ in range(5):
            editor.handle_input(_KEY_DATA["right"])
        editor.handle_input(_KEY_DATA["shift_enter"])
        assert editor.get_text() == "hello\nworld"

    def test_submit_via_enter(self) -> None:
        editor = _make_editor()
        submitted: list[str] = []
        editor.on_submit = lambda t: submitted.append(t)
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["enter"])
        assert len(submitted) == 1
        assert submitted[0] == "hello"

    def test_submit_clears_editor(self) -> None:
        editor = _make_editor()
        editor.on_submit = lambda t: None
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["enter"])
        assert editor.get_text() == ""

    def test_disable_submit(self) -> None:
        editor = _make_editor()
        submitted: list[str] = []
        editor.on_submit = lambda t: submitted.append(t)
        editor.disable_submit = True
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["enter"])
        assert len(submitted) == 0
        # Text should still be there
        assert editor.get_text() == "hello"


# =========================================================================
# Kill ring / clipboard tests
# =========================================================================


class TestKillRing:
    def test_kill_to_end_and_yank(self) -> None:
        editor = _make_editor()
        editor.set_text("hello world")
        editor.handle_input(_KEY_DATA["home"])
        # Kill to end of line (ctrl+k)
        editor.handle_input(_KEY_DATA["ctrl_k"])
        assert editor.get_text() == ""
        # Yank back (ctrl+y)
        editor.handle_input(_KEY_DATA["ctrl_y"])
        assert editor.get_text() == "hello world"

    def test_kill_to_start_and_yank(self) -> None:
        editor = _make_editor()
        editor.set_text("hello world")
        # Kill to start of line (ctrl+u)
        editor.handle_input(_KEY_DATA["ctrl_u"])
        assert editor.get_text() == ""
        # Yank back
        editor.handle_input(_KEY_DATA["ctrl_y"])
        assert editor.get_text() == "hello world"

    def test_kill_word_backward_and_yank(self) -> None:
        editor = _make_editor()
        editor.set_text("hello world")
        # Kill word backward (ctrl+w)
        editor.handle_input(_KEY_DATA["ctrl_w"])
        assert editor.get_text() == "hello "
        # Yank
        editor.handle_input(_KEY_DATA["ctrl_y"])
        assert editor.get_text() == "hello world"

    def test_consecutive_kills_accumulate(self) -> None:
        editor = _make_editor()
        editor.set_text("aaa bbb ccc")
        # Kill word backward twice in succession
        editor.handle_input(_KEY_DATA["ctrl_w"])
        editor.handle_input(_KEY_DATA["ctrl_w"])
        assert editor.get_text() == "aaa "
        # Yank should give us "bbb ccc" (accumulated)
        editor.handle_input(_KEY_DATA["ctrl_y"])
        assert editor.get_text() == "aaa bbb ccc"

    def test_yank_with_empty_kill_ring_noop(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["ctrl_y"])
        assert editor.get_text() == "hello"


# =========================================================================
# Undo tests
# =========================================================================


class TestUndo:
    def test_undo_insertion(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        # Type a space (creates undo snapshot for whitespace)
        editor.handle_input(" ")
        assert editor.get_text() == "hello "
        # Undo
        editor.handle_input(_KEY_DATA["ctrl_minus"])
        assert editor.get_text() == "hello"

    def test_undo_backspace(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["backspace"])
        assert editor.get_text() == "hell"
        editor.handle_input(_KEY_DATA["ctrl_minus"])
        assert editor.get_text() == "hello"

    def test_undo_set_text(self) -> None:
        editor = _make_editor()
        editor.set_text("first")
        editor.set_text("second")
        editor.handle_input(_KEY_DATA["ctrl_minus"])
        assert editor.get_text() == "first"

    def test_undo_empty_stack_noop(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        # Clear undo state by doing set_text, then many undos
        editor.handle_input(_KEY_DATA["ctrl_minus"])
        editor.handle_input(_KEY_DATA["ctrl_minus"])
        editor.handle_input(_KEY_DATA["ctrl_minus"])
        # Should not crash, text should be empty or original
        assert isinstance(editor.get_text(), str)

    def test_multiple_undos(self) -> None:
        editor = _make_editor()
        editor.set_text("a")
        editor.set_text("b")
        editor.set_text("c")
        editor.handle_input(_KEY_DATA["ctrl_minus"])
        assert editor.get_text() == "b"
        editor.handle_input(_KEY_DATA["ctrl_minus"])
        assert editor.get_text() == "a"


# =========================================================================
# Render tests
# =========================================================================


class TestRender:
    def test_render_empty_editor(self) -> None:
        editor = _make_editor()
        result = editor.render(40)
        # Should have top border, content line, bottom border
        assert len(result) >= 3
        # First and last lines should be borders (made of horizontal lines)
        assert "\u2500" in result[0]
        assert "\u2500" in result[-1]

    def test_render_with_text(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        result = editor.render(40)
        assert len(result) >= 3
        # Content should contain "hello"
        content_lines = result[1:-1]
        combined = "".join(content_lines)
        assert "hello" in combined

    def test_render_multiline(self) -> None:
        editor = _make_editor()
        editor.set_text("line1\nline2")
        result = editor.render(40)
        # Should have top border, 2 content lines, bottom border
        assert len(result) >= 4
        content = result[1:-1]
        assert any("line1" in line for line in content)
        assert any("line2" in line for line in content)

    def test_render_focused_shows_cursor(self) -> None:
        editor = _make_editor()
        editor.focused = True
        editor.set_text("hi")
        result = editor.render(40)
        # When focused, the cursor marker and/or reverse video should appear
        content = "".join(result[1:-1])
        # Check for reverse video escape (cursor visualization)
        assert "\x1b[7m" in content

    def test_render_unfocused_no_cursor_marker(self) -> None:
        editor = _make_editor()
        editor.focused = False
        editor.set_text("hi")
        result = editor.render(40)
        content = "".join(result[1:-1])
        # The CURSOR_MARKER should not be present
        from pi_tui.tui import CURSOR_MARKER

        assert CURSOR_MARKER not in content

    def test_render_with_padding(self) -> None:
        opts = EditorOptions(padding_x=2)
        editor = _make_editor(options=opts)
        editor.set_text("hi")
        result = editor.render(40)
        # Content lines should have leading spaces for padding
        content = result[1]
        assert content.startswith("  ")

    def test_render_width_1(self) -> None:
        editor = _make_editor()
        editor.set_text("abc")
        # Should not crash with very small width
        result = editor.render(1)
        assert len(result) >= 3


# =========================================================================
# EditorState management
# =========================================================================


class TestEditorState:
    def test_initial_state(self) -> None:
        editor = _make_editor()
        assert editor.get_lines() == [""]
        assert editor.get_cursor() == {"line": 0, "col": 0}

    def test_state_after_typing(self) -> None:
        editor = _make_editor()
        for ch in "abc":
            editor.handle_input(ch)
        assert editor.get_lines() == ["abc"]
        assert editor.get_cursor() == {"line": 0, "col": 3}

    def test_state_after_newline(self) -> None:
        editor = _make_editor()
        for ch in "ab":
            editor.handle_input(ch)
        editor.handle_input(_KEY_DATA["shift_enter"])
        for ch in "cd":
            editor.handle_input(ch)
        assert editor.get_lines() == ["ab", "cd"]
        assert editor.get_cursor() == {"line": 1, "col": 2}


# =========================================================================
# insert_text_at_cursor tests
# =========================================================================


class TestInsertTextAtCursor:
    def test_insert_single_line(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        editor.handle_input(_KEY_DATA["home"])
        editor.insert_text_at_cursor("say ")
        assert editor.get_text() == "say hello"

    def test_insert_multiline(self) -> None:
        editor = _make_editor()
        editor.set_text("start end")
        # Move cursor after "start "
        editor.handle_input(_KEY_DATA["home"])
        for _ in range(6):
            editor.handle_input(_KEY_DATA["right"])
        editor.insert_text_at_cursor("line1\nline2\n")
        assert "line1" in editor.get_text()
        assert "line2" in editor.get_text()

    def test_insert_empty_string_noop(self) -> None:
        editor = _make_editor()
        editor.set_text("hello")
        editor.insert_text_at_cursor("")
        assert editor.get_text() == "hello"


# =========================================================================
# History tests
# =========================================================================


class TestHistory:
    def test_add_to_history(self) -> None:
        editor = _make_editor()
        editor.add_to_history("first")
        editor.add_to_history("second")
        # Navigate history with up arrow
        editor.handle_input(_KEY_DATA["up"])
        assert editor.get_text() == "second"
        editor.handle_input(_KEY_DATA["up"])
        assert editor.get_text() == "first"

    def test_history_navigate_back(self) -> None:
        editor = _make_editor()
        editor.add_to_history("first")
        editor.add_to_history("second")
        editor.handle_input(_KEY_DATA["up"])
        editor.handle_input(_KEY_DATA["up"])
        # Navigate back
        editor.handle_input(_KEY_DATA["down"])
        assert editor.get_text() == "second"

    def test_history_no_consecutive_duplicates(self) -> None:
        editor = _make_editor()
        editor.add_to_history("same")
        editor.add_to_history("same")
        editor.handle_input(_KEY_DATA["up"])
        assert editor.get_text() == "same"
        # Second up should not find another "same"
        editor.handle_input(_KEY_DATA["up"])
        # Should stay at the same entry
        assert editor.get_text() == "same"

    def test_history_empty_not_added(self) -> None:
        editor = _make_editor()
        editor.add_to_history("")
        editor.add_to_history("   ")
        # No entries should have been added
        editor.handle_input(_KEY_DATA["up"])
        assert editor.get_text() == ""


# =========================================================================
# Padding / property setter tests
# =========================================================================


class TestPropertySetters:
    def test_set_padding_x(self) -> None:
        tui = _make_mock_tui()
        editor = _make_editor(tui=tui)
        editor.set_padding_x(4)
        assert editor.get_padding_x() == 4
        tui.request_render.assert_called()

    def test_set_padding_x_negative(self) -> None:
        editor = _make_editor()
        editor.set_padding_x(-10)
        assert editor.get_padding_x() == 0

    def test_set_autocomplete_max_visible(self) -> None:
        tui = _make_mock_tui()
        editor = _make_editor(tui=tui)
        editor.set_autocomplete_max_visible(10)
        assert editor.get_autocomplete_max_visible() == 10

    def test_set_autocomplete_max_visible_clamped(self) -> None:
        editor = _make_editor()
        editor.set_autocomplete_max_visible(1)
        assert editor.get_autocomplete_max_visible() == 3
        editor.set_autocomplete_max_visible(50)
        assert editor.get_autocomplete_max_visible() == 20


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    def test_backspace_on_empty(self) -> None:
        editor = _make_editor()
        editor.handle_input(_KEY_DATA["backspace"])
        assert editor.get_text() == ""

    def test_delete_on_empty(self) -> None:
        editor = _make_editor()
        editor.handle_input(_KEY_DATA["delete"])
        assert editor.get_text() == ""

    def test_ctrl_k_on_empty(self) -> None:
        editor = _make_editor()
        editor.handle_input(_KEY_DATA["ctrl_k"])
        assert editor.get_text() == ""

    def test_ctrl_u_on_empty(self) -> None:
        editor = _make_editor()
        editor.handle_input(_KEY_DATA["ctrl_u"])
        assert editor.get_text() == ""

    def test_invalidate_does_not_crash(self) -> None:
        editor = _make_editor()
        editor.invalidate()  # Should be a no-op

    def test_wants_key_release(self) -> None:
        editor = _make_editor()
        assert editor.wants_key_release is False

    def test_is_showing_autocomplete_default(self) -> None:
        editor = _make_editor()
        assert editor.is_showing_autocomplete() is False

    def test_rapid_insert_and_delete(self) -> None:
        editor = _make_editor()
        for ch in "hello world":
            editor.handle_input(ch)
        for _ in range(5):
            editor.handle_input(_KEY_DATA["backspace"])
        assert editor.get_text() == "hello "

    def test_multiline_backspace_join_all(self) -> None:
        editor = _make_editor()
        editor.set_text("a\nb\nc")
        # Cursor at end of line 2 (last line)
        # Go to start of line 2
        editor.handle_input(_KEY_DATA["home"])
        # Backspace joins with line 1
        editor.handle_input(_KEY_DATA["backspace"])
        assert "b" in editor.get_text()
        assert editor.get_cursor()["line"] == 1


# =========================================================================
# TextChunk dataclass tests
# =========================================================================


class TestTextChunk:
    def test_creation(self) -> None:
        chunk = TextChunk(text="hello", start_index=0, end_index=5)
        assert chunk.text == "hello"
        assert chunk.start_index == 0
        assert chunk.end_index == 5

    def test_equality(self) -> None:
        a = TextChunk(text="abc", start_index=0, end_index=3)
        b = TextChunk(text="abc", start_index=0, end_index=3)
        assert a == b

    def test_inequality(self) -> None:
        a = TextChunk(text="abc", start_index=0, end_index=3)
        b = TextChunk(text="xyz", start_index=0, end_index=3)
        assert a != b
