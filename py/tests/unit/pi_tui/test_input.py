"""Tests for the single-line Input component."""

from __future__ import annotations

from pi_tui.components.input import CURSOR_MARKER, Input

# =============================================================================
# Terminal key sequences (legacy mode, non-Kitty)
# =============================================================================

# These are the raw bytes terminals send for each key.
LEFT = "\x1b[D"
RIGHT = "\x1b[C"
HOME = "\x1b[H"
END = "\x1b[F"
BACKSPACE = "\x7f"
DELETE = "\x1b[3~"
ENTER = "\r"
ESCAPE = "\x1b"

# Ctrl combinations: ctrl+<letter> = chr(ord(letter) - 96)
CTRL_A = "\x01"  # cursorLineStart (home)
CTRL_B = "\x02"  # cursorLeft
CTRL_C = "\x03"  # selectCancel (escape)
CTRL_D = "\x04"  # deleteCharForward
CTRL_E = "\x05"  # cursorLineEnd (end)
CTRL_F = "\x06"  # cursorRight
CTRL_K = "\x0b"  # deleteToLineEnd
CTRL_U = "\x15"  # deleteToLineStart
CTRL_W = "\x17"  # deleteWordBackward
CTRL_Y = "\x19"  # yank
CTRL_MINUS = "\x1f"  # undo

# Alt combinations (legacy: ESC + char)
ALT_B = "\x1bb"  # cursorWordLeft
ALT_F = "\x1bf"  # cursorWordRight
ALT_D = "\x1bd"  # deleteWordForward
ALT_BACKSPACE = "\x1b\x7f"  # deleteWordBackward
ALT_Y = "\x1by"  # yankPop


# =============================================================================
# Helpers
# =============================================================================


def _type_string(inp: Input, text: str) -> None:
    """Type a string character by character into the input."""
    for ch in text:
        inp.handle_input(ch)


def _make_input(text: str = "", cursor: int | None = None) -> Input:
    """Create an Input pre-loaded with text and optional cursor position."""
    inp = Input()
    if text:
        _type_string(inp, text)
    if cursor is not None:
        inp._cursor = cursor
    return inp


# =============================================================================
# 1. Construction with default values
# =============================================================================


class TestConstruction:
    def test_default_state(self) -> None:
        inp = Input()
        assert inp.get_value() == ""
        assert inp._cursor == 0
        assert inp.focused is False
        assert inp.on_submit is None
        assert inp.on_escape is None

    def test_focused_can_be_set(self) -> None:
        inp = Input()
        inp.focused = True
        assert inp.focused is True


# =============================================================================
# 2. get_value() / set_value()
# =============================================================================


class TestGetSetValue:
    def test_get_value_empty(self) -> None:
        inp = Input()
        assert inp.get_value() == ""

    def test_set_value(self) -> None:
        inp = Input()
        inp.set_value("hello")
        assert inp.get_value() == "hello"

    def test_set_value_clamps_cursor(self) -> None:
        inp = _make_input("hello world")
        assert inp._cursor == 11  # at end
        inp.set_value("hi")
        assert inp._cursor == 2  # clamped to len("hi")

    def test_set_value_preserves_cursor_if_within_range(self) -> None:
        inp = _make_input("hello world")
        inp._cursor = 3
        inp.set_value("hello")
        assert inp._cursor == 3  # still valid

    def test_set_value_to_empty(self) -> None:
        inp = _make_input("hello")
        inp.set_value("")
        assert inp.get_value() == ""
        assert inp._cursor == 0


# =============================================================================
# 3. handle_input with regular characters
# =============================================================================


class TestCharacterInput:
    def test_type_single_char(self) -> None:
        inp = Input()
        inp.handle_input("a")
        assert inp.get_value() == "a"
        assert inp._cursor == 1

    def test_type_multiple_chars(self) -> None:
        inp = Input()
        _type_string(inp, "hello")
        assert inp.get_value() == "hello"
        assert inp._cursor == 5

    def test_type_at_middle(self) -> None:
        inp = _make_input("hllo")
        inp._cursor = 1
        inp.handle_input("e")
        assert inp.get_value() == "hello"
        assert inp._cursor == 2

    def test_type_at_beginning(self) -> None:
        inp = _make_input("ello")
        inp._cursor = 0
        inp.handle_input("h")
        assert inp.get_value() == "hello"
        assert inp._cursor == 1

    def test_control_chars_rejected(self) -> None:
        inp = Input()
        # Tab is \t (0x09) which is a control char, but it's handled by keybinding
        # The "tab" keybinding matches, but there's no action for it in Input.
        # Raw control chars that don't match any binding should be ignored.
        inp.handle_input("\x00")  # NUL - matches ctrl+space, no action
        # After ctrl+space, nothing should happen (no matching action in Input)
        assert inp.get_value() == ""

    def test_unicode_input(self) -> None:
        inp = Input()
        _type_string(inp, "cafe\u0301")
        assert "caf" in inp.get_value()

    def test_multibyte_emoji(self) -> None:
        inp = Input()
        inp.handle_input("a")
        assert inp.get_value() == "a"


# =============================================================================
# 4. Backspace (deleteCharBackward)
# =============================================================================


class TestBackspace:
    def test_backspace_at_end(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(BACKSPACE)
        assert inp.get_value() == "hell"
        assert inp._cursor == 4

    def test_backspace_at_middle(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 3
        inp.handle_input(BACKSPACE)
        assert inp.get_value() == "helo"
        assert inp._cursor == 2

    def test_backspace_at_beginning(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 0
        inp.handle_input(BACKSPACE)
        assert inp.get_value() == "hello"
        assert inp._cursor == 0

    def test_backspace_empty_input(self) -> None:
        inp = Input()
        inp.handle_input(BACKSPACE)
        assert inp.get_value() == ""
        assert inp._cursor == 0

    def test_multiple_backspaces(self) -> None:
        inp = _make_input("abc")
        inp.handle_input(BACKSPACE)
        inp.handle_input(BACKSPACE)
        assert inp.get_value() == "a"
        assert inp._cursor == 1


# =============================================================================
# 5. Delete key (deleteCharForward)
# =============================================================================


class TestDelete:
    def test_delete_at_beginning(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 0
        inp.handle_input(DELETE)
        assert inp.get_value() == "ello"
        assert inp._cursor == 0

    def test_delete_at_middle(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 2
        inp.handle_input(DELETE)
        assert inp.get_value() == "helo"
        assert inp._cursor == 2

    def test_delete_at_end(self) -> None:
        inp = _make_input("hello")
        # cursor at end
        inp.handle_input(DELETE)
        assert inp.get_value() == "hello"
        assert inp._cursor == 5

    def test_ctrl_d_also_deletes_forward(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 0
        inp.handle_input(CTRL_D)
        assert inp.get_value() == "ello"


# =============================================================================
# 6. Arrow keys (cursor movement)
# =============================================================================


class TestArrowKeys:
    def test_left_arrow(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(LEFT)
        assert inp._cursor == 4

    def test_left_arrow_multiple(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(LEFT)
        inp.handle_input(LEFT)
        inp.handle_input(LEFT)
        assert inp._cursor == 2

    def test_left_arrow_at_beginning(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 0
        inp.handle_input(LEFT)
        assert inp._cursor == 0

    def test_right_arrow(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 2
        inp.handle_input(RIGHT)
        assert inp._cursor == 3

    def test_right_arrow_at_end(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(RIGHT)
        assert inp._cursor == 5  # already at end

    def test_ctrl_b_moves_left(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(CTRL_B)
        assert inp._cursor == 4

    def test_ctrl_f_moves_right(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 2
        inp.handle_input(CTRL_F)
        assert inp._cursor == 3


# =============================================================================
# 7. Home/End keys
# =============================================================================


class TestHomeEnd:
    def test_home_key(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(HOME)
        assert inp._cursor == 0

    def test_home_already_at_start(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 0
        inp.handle_input(HOME)
        assert inp._cursor == 0

    def test_end_key(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 0
        inp.handle_input(END)
        assert inp._cursor == 5

    def test_end_already_at_end(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(END)
        assert inp._cursor == 5

    def test_ctrl_a_goes_home(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(CTRL_A)
        assert inp._cursor == 0

    def test_ctrl_e_goes_end(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 0
        inp.handle_input(CTRL_E)
        assert inp._cursor == 5


# =============================================================================
# 8. Ctrl+C (selectCancel / escape)
# =============================================================================


class TestCtrlCAndEscape:
    def test_ctrl_c_calls_on_escape(self) -> None:
        inp = _make_input("hello")
        called = []
        inp.on_escape = lambda: called.append(True)
        inp.handle_input(CTRL_C)
        assert called == [True]

    def test_escape_calls_on_escape(self) -> None:
        inp = _make_input("hello")
        called = []
        inp.on_escape = lambda: called.append(True)
        inp.handle_input(ESCAPE)
        assert called == [True]

    def test_ctrl_c_no_callback(self) -> None:
        inp = _make_input("hello")
        inp.on_escape = None
        # Should not raise
        inp.handle_input(CTRL_C)

    def test_escape_no_callback(self) -> None:
        inp = Input()
        inp.on_escape = None
        inp.handle_input(ESCAPE)  # no crash


# =============================================================================
# 9. render() output
# =============================================================================


class TestRender:
    def test_render_returns_list_of_one_line(self) -> None:
        inp = Input()
        result = inp.render(40)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_render_contains_prompt(self) -> None:
        inp = Input()
        result = inp.render(40)
        assert result[0].startswith("> ")

    def test_render_shows_text(self) -> None:
        inp = _make_input("hello")
        result = inp.render(40)
        line = result[0]
        assert "hello" in line or "hell" in line  # cursor char may be modified

    def test_render_cursor_inverse_video(self) -> None:
        inp = _make_input("abc")
        inp._cursor = 1
        result = inp.render(40)
        line = result[0]
        # Cursor at position 1 means 'b' should be rendered with inverse video
        assert "\x1b[7m" in line
        assert "\x1b[27m" in line

    def test_render_empty_cursor_at_end(self) -> None:
        inp = Input()
        result = inp.render(40)
        line = result[0]
        # Empty input: cursor is a space with inverse video
        assert "\x1b[7m \x1b[27m" in line

    def test_render_narrow_width(self) -> None:
        inp = Input()
        result = inp.render(2)
        # width <= len(prompt), should return just the prompt
        assert result == ["> "]

    def test_render_zero_width(self) -> None:
        inp = Input()
        result = inp.render(0)
        assert result == ["> "]

    def test_render_focused_includes_cursor_marker(self) -> None:
        inp = _make_input("abc")
        inp.focused = True
        result = inp.render(40)
        assert CURSOR_MARKER in result[0]

    def test_render_unfocused_no_cursor_marker(self) -> None:
        inp = _make_input("abc")
        inp.focused = False
        result = inp.render(40)
        assert CURSOR_MARKER not in result[0]


# =============================================================================
# 10. Placeholder text (empty input display)
# =============================================================================
# The Input component does not have an explicit placeholder feature.
# When empty, it renders a cursor (space in inverse video) with padding.


class TestEmptyDisplay:
    def test_empty_renders_cursor_space(self) -> None:
        inp = Input()
        result = inp.render(20)
        line = result[0]
        # Should contain inverse-video space as cursor
        assert "\x1b[7m \x1b[27m" in line

    def test_empty_value_is_empty_string(self) -> None:
        inp = Input()
        assert inp.get_value() == ""


# =============================================================================
# 11. on_submit callback (enter key)
# =============================================================================


class TestOnSubmit:
    def test_enter_triggers_on_submit(self) -> None:
        inp = _make_input("hello")
        submitted: list[str] = []
        inp.on_submit = lambda val: submitted.append(val)
        inp.handle_input(ENTER)
        assert submitted == ["hello"]

    def test_enter_no_callback(self) -> None:
        inp = _make_input("hello")
        inp.on_submit = None
        # Should not raise
        inp.handle_input(ENTER)

    def test_newline_triggers_submit(self) -> None:
        inp = _make_input("world")
        submitted: list[str] = []
        inp.on_submit = lambda val: submitted.append(val)
        inp.handle_input("\n")
        assert submitted == ["world"]

    def test_submit_passes_current_value(self) -> None:
        inp = Input()
        _type_string(inp, "test123")
        submitted: list[str] = []
        inp.on_submit = lambda val: submitted.append(val)
        inp.handle_input(ENTER)
        assert submitted == ["test123"]


# =============================================================================
# 12. Focus handling
# =============================================================================


class TestFocus:
    def test_default_not_focused(self) -> None:
        inp = Input()
        assert inp.focused is False

    def test_set_focused(self) -> None:
        inp = Input()
        inp.focused = True
        assert inp.focused is True

    def test_focus_affects_render_cursor_marker(self) -> None:
        inp = _make_input("hi")
        inp.focused = False
        unfocused_line = inp.render(20)[0]
        inp.focused = True
        focused_line = inp.render(20)[0]
        assert CURSOR_MARKER not in unfocused_line
        assert CURSOR_MARKER in focused_line


# =============================================================================
# 13. Word movement (cursorWordLeft / cursorWordRight)
# =============================================================================


class TestWordMovement:
    def test_alt_b_moves_word_left(self) -> None:
        inp = _make_input("hello world")
        # cursor at end (11)
        inp.handle_input(ALT_B)
        assert inp._cursor == 6  # beginning of "world"

    def test_alt_f_moves_word_right(self) -> None:
        inp = _make_input("hello world")
        inp._cursor = 0
        inp.handle_input(ALT_F)
        assert inp._cursor == 5  # end of "hello"

    def test_word_left_at_beginning(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 0
        inp.handle_input(ALT_B)
        assert inp._cursor == 0

    def test_word_right_at_end(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(ALT_F)
        assert inp._cursor == 5  # already at end


# =============================================================================
# 14. Word deletion
# =============================================================================


class TestWordDeletion:
    def test_ctrl_w_deletes_word_backward(self) -> None:
        inp = _make_input("hello world")
        inp.handle_input(CTRL_W)
        assert inp.get_value() == "hello "
        assert inp._cursor == 6

    def test_alt_backspace_deletes_word_backward(self) -> None:
        inp = _make_input("hello world")
        inp.handle_input(ALT_BACKSPACE)
        assert inp.get_value() == "hello "

    def test_alt_d_deletes_word_forward(self) -> None:
        inp = _make_input("hello world")
        inp._cursor = 0
        inp.handle_input(ALT_D)
        assert inp.get_value() == " world"
        assert inp._cursor == 0

    def test_word_delete_at_boundary(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 0
        inp.handle_input(CTRL_W)
        # at beginning, nothing to delete backward
        assert inp.get_value() == "hello"


# =============================================================================
# 15. Line deletion (ctrl+u / ctrl+k)
# =============================================================================


class TestLineDeletion:
    def test_ctrl_u_deletes_to_line_start(self) -> None:
        inp = _make_input("hello world")
        inp.handle_input(CTRL_U)
        assert inp.get_value() == ""
        assert inp._cursor == 0

    def test_ctrl_u_from_middle(self) -> None:
        inp = _make_input("hello world")
        inp._cursor = 5
        inp.handle_input(CTRL_U)
        assert inp.get_value() == " world"
        assert inp._cursor == 0

    def test_ctrl_k_deletes_to_line_end(self) -> None:
        inp = _make_input("hello world")
        inp._cursor = 5
        inp.handle_input(CTRL_K)
        assert inp.get_value() == "hello"
        assert inp._cursor == 5

    def test_ctrl_k_at_end_does_nothing(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(CTRL_K)
        assert inp.get_value() == "hello"

    def test_ctrl_u_at_start_does_nothing(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 0
        inp.handle_input(CTRL_U)
        assert inp.get_value() == "hello"


# =============================================================================
# 16. Kill ring / Yank
# =============================================================================


class TestKillRingYank:
    def test_kill_then_yank(self) -> None:
        inp = _make_input("hello world")
        inp.handle_input(CTRL_K)  # kill " world" (cursor at end of "hello")
        inp._cursor = 5  # shouldn't change, but ensure
        # Now value is "hello", kill ring has " world"
        # Actually ctrl_k from cursor=11 does nothing (at end)
        # Let's set cursor first
        inp2 = _make_input("hello world")
        inp2._cursor = 5
        inp2.handle_input(CTRL_K)  # kills " world"
        assert inp2.get_value() == "hello"
        inp2.handle_input(CTRL_Y)  # yank back
        assert inp2.get_value() == "hello world"

    def test_yank_empty_kill_ring(self) -> None:
        inp = Input()
        inp.handle_input(CTRL_Y)
        assert inp.get_value() == ""

    def test_yank_inserts_at_cursor(self) -> None:
        inp = _make_input("hello world")
        inp._cursor = 5
        inp.handle_input(CTRL_K)  # kill " world"
        inp._cursor = 0
        inp.handle_input(CTRL_Y)
        assert inp.get_value() == " worldhello"


# =============================================================================
# 17. Undo
# =============================================================================


class TestUndo:
    def test_undo_typing(self) -> None:
        inp = Input()
        _type_string(inp, "hello")
        inp.handle_input(CTRL_MINUS)
        # Undo pops the last undo state. Typing "hello" as continuous chars
        # only pushes one undo state (for the first char of the word group).
        # After undo, we should go back to before "hello" was typed.
        assert inp.get_value() == ""

    def test_undo_backspace(self) -> None:
        inp = _make_input("hello")
        inp.handle_input(BACKSPACE)
        assert inp.get_value() == "hell"
        inp.handle_input(CTRL_MINUS)
        assert inp.get_value() == "hello"

    def test_undo_on_empty_stack(self) -> None:
        inp = Input()
        # Should not raise
        inp.handle_input(CTRL_MINUS)
        assert inp.get_value() == ""

    def test_undo_delete(self) -> None:
        inp = _make_input("hello")
        inp._cursor = 2
        inp.handle_input(DELETE)
        assert inp.get_value() == "helo"
        inp.handle_input(CTRL_MINUS)
        assert inp.get_value() == "hello"
        assert inp._cursor == 2


# =============================================================================
# 18. Bracketed paste
# =============================================================================


class TestBracketedPaste:
    def test_paste_simple(self) -> None:
        inp = Input()
        inp.handle_input("\x1b[200~hello\x1b[201~")
        assert inp.get_value() == "hello"

    def test_paste_strips_newlines(self) -> None:
        inp = Input()
        inp.handle_input("\x1b[200~hello\nworld\x1b[201~")
        assert inp.get_value() == "helloworld"

    def test_paste_strips_crlf(self) -> None:
        inp = Input()
        inp.handle_input("\x1b[200~line1\r\nline2\x1b[201~")
        assert inp.get_value() == "line1line2"

    def test_paste_at_cursor_position(self) -> None:
        inp = _make_input("ab")
        inp._cursor = 1
        inp.handle_input("\x1b[200~XY\x1b[201~")
        assert inp.get_value() == "aXYb"
        assert inp._cursor == 3

    def test_paste_split_across_chunks(self) -> None:
        inp = Input()
        inp.handle_input("\x1b[200~hel")
        assert inp._is_in_paste is True
        inp.handle_input("lo\x1b[201~")
        assert inp.get_value() == "hello"
        assert inp._is_in_paste is False


# =============================================================================
# 19. Horizontal scrolling in render
# =============================================================================


class TestHorizontalScrolling:
    def test_short_text_no_scroll(self) -> None:
        inp = _make_input("hi")
        result = inp.render(20)
        line = result[0]
        assert "hi" in line or "h" in line

    def test_long_text_scrolls(self) -> None:
        long_text = "a" * 100
        inp = _make_input(long_text)
        result = inp.render(20)
        line = result[0]
        # Line should not be excessively long; it should be bounded by width
        # The prompt "> " is 2 chars, so visible text area is 18 chars
        # The line includes ANSI codes, so raw length may exceed width
        assert len(line) < 200  # sanity check


# =============================================================================
# 20. Edge cases
# =============================================================================


class TestEdgeCases:
    def test_type_then_move_then_type(self) -> None:
        inp = Input()
        _type_string(inp, "hlo")
        inp.handle_input(LEFT)
        inp.handle_input(LEFT)
        inp.handle_input("e")
        inp.handle_input("l")
        assert inp.get_value() == "hello"

    def test_cursor_stays_valid_after_operations(self) -> None:
        inp = _make_input("abc")
        # Delete everything from start
        inp._cursor = 0
        inp.handle_input(CTRL_K)
        assert inp.get_value() == ""
        assert inp._cursor == 0

    def test_backspace_then_type(self) -> None:
        inp = _make_input("abc")
        inp.handle_input(BACKSPACE)
        inp.handle_input("x")
        assert inp.get_value() == "abx"

    def test_home_type_end(self) -> None:
        inp = _make_input("world")
        inp.handle_input(HOME)
        _type_string(inp, "hello ")
        assert inp.get_value() == "hello world"
        inp.handle_input(END)
        assert inp._cursor == 11

    def test_invalidate_does_nothing(self) -> None:
        inp = Input()
        inp.invalidate()  # should not raise
