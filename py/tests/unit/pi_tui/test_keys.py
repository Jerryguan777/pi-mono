"""Tests for pi_tui.keys module."""

from __future__ import annotations

import pytest

from pi_tui.keys import (
    Key,
    is_key_release,
    is_key_repeat,
    is_kitty_protocol_active,
    matches_key,
    parse_key,
    set_kitty_protocol_active,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_kitty_protocol() -> None:
    """Ensure Kitty protocol state is reset before each test."""
    set_kitty_protocol_active(False)


# =============================================================================
# Key class: special keys
# =============================================================================


class TestKeySpecialKeys:
    def test_escape(self) -> None:
        assert Key.escape == "escape"
        assert Key.esc == "esc"

    def test_enter(self) -> None:
        assert Key.enter == "enter"
        assert Key.return_ == "return"

    def test_tab(self) -> None:
        assert Key.tab == "tab"

    def test_space(self) -> None:
        assert Key.space == "space"

    def test_backspace(self) -> None:
        assert Key.backspace == "backspace"

    def test_delete(self) -> None:
        assert Key.delete == "delete"

    def test_insert(self) -> None:
        assert Key.insert == "insert"

    def test_navigation_keys(self) -> None:
        assert Key.home == "home"
        assert Key.end == "end"
        assert Key.page_up == "pageUp"
        assert Key.page_down == "pageDown"

    def test_arrow_keys(self) -> None:
        assert Key.up == "up"
        assert Key.down == "down"
        assert Key.left == "left"
        assert Key.right == "right"

    def test_function_keys(self) -> None:
        assert Key.f1 == "f1"
        assert Key.f2 == "f2"
        assert Key.f3 == "f3"
        assert Key.f4 == "f4"
        assert Key.f5 == "f5"
        assert Key.f6 == "f6"
        assert Key.f7 == "f7"
        assert Key.f8 == "f8"
        assert Key.f9 == "f9"
        assert Key.f10 == "f10"
        assert Key.f11 == "f11"
        assert Key.f12 == "f12"

    def test_symbol_keys(self) -> None:
        assert Key.backtick == "`"
        assert Key.hyphen == "-"
        assert Key.equals == "="
        assert Key.leftbracket == "["
        assert Key.rightbracket == "]"
        assert Key.backslash == "\\"
        assert Key.semicolon == ";"
        assert Key.quote == "'"
        assert Key.comma == ","
        assert Key.period == "."
        assert Key.slash == "/"
        assert Key.exclamation == "!"
        assert Key.at == "@"
        assert Key.hash == "#"
        assert Key.dollar == "$"
        assert Key.percent == "%"
        assert Key.caret == "^"
        assert Key.ampersand == "&"
        assert Key.asterisk == "*"
        assert Key.leftparen == "("
        assert Key.rightparen == ")"
        assert Key.underscore == "_"
        assert Key.plus == "+"
        assert Key.pipe == "|"
        assert Key.tilde == "~"
        assert Key.leftbrace == "{"
        assert Key.rightbrace == "}"
        assert Key.colon == ":"
        assert Key.lessthan == "<"
        assert Key.greaterthan == ">"
        assert Key.question == "?"


# =============================================================================
# Key class: modifier methods
# =============================================================================


class TestKeyModifiers:
    def test_ctrl(self) -> None:
        assert Key.ctrl("c") == "ctrl+c"
        assert Key.ctrl("z") == "ctrl+z"
        assert Key.ctrl("a") == "ctrl+a"

    def test_alt(self) -> None:
        assert Key.alt("x") == "alt+x"
        assert Key.alt("enter") == "alt+enter"

    def test_shift(self) -> None:
        assert Key.shift("tab") == "shift+tab"
        assert Key.shift("enter") == "shift+enter"

    def test_ctrl_shift(self) -> None:
        assert Key.ctrl_shift("p") == "ctrl+shift+p"

    def test_shift_ctrl(self) -> None:
        assert Key.shift_ctrl("p") == "shift+ctrl+p"

    def test_ctrl_alt(self) -> None:
        assert Key.ctrl_alt("x") == "ctrl+alt+x"

    def test_alt_ctrl(self) -> None:
        assert Key.alt_ctrl("x") == "alt+ctrl+x"

    def test_shift_alt(self) -> None:
        assert Key.shift_alt("a") == "shift+alt+a"

    def test_alt_shift(self) -> None:
        assert Key.alt_shift("a") == "alt+shift+a"

    def test_ctrl_shift_alt(self) -> None:
        assert Key.ctrl_shift_alt("x") == "ctrl+shift+alt+x"


# =============================================================================
# parse_key: simple characters
# =============================================================================


class TestParseKeySimpleChars:
    def test_lowercase_letters(self) -> None:
        assert parse_key("a") == "a"
        assert parse_key("b") == "b"
        assert parse_key("z") == "z"

    def test_digits(self) -> None:
        assert parse_key("1") == "1"
        assert parse_key("9") == "9"
        assert parse_key("0") == "0"

    def test_printable_symbols(self) -> None:
        assert parse_key("/") == "/"
        assert parse_key(".") == "."
        assert parse_key(",") == ","

    def test_space(self) -> None:
        assert parse_key(" ") == "space"


# =============================================================================
# parse_key: control characters
# =============================================================================


class TestParseKeyControlChars:
    def test_ctrl_c(self) -> None:
        assert parse_key("\x03") == "ctrl+c"

    def test_ctrl_a(self) -> None:
        assert parse_key("\x01") == "ctrl+a"

    def test_ctrl_z(self) -> None:
        assert parse_key("\x1a") == "ctrl+z"

    def test_ctrl_d(self) -> None:
        assert parse_key("\x04") == "ctrl+d"

    def test_ctrl_l(self) -> None:
        assert parse_key("\x0c") == "ctrl+l"

    def test_ctrl_backslash(self) -> None:
        assert parse_key("\x1c") == "ctrl+\\"

    def test_ctrl_rightbracket(self) -> None:
        assert parse_key("\x1d") == "ctrl+]"

    def test_ctrl_hyphen(self) -> None:
        assert parse_key("\x1f") == "ctrl+-"

    def test_ctrl_space(self) -> None:
        assert parse_key("\x00") == "ctrl+space"


# =============================================================================
# parse_key: escape
# =============================================================================


class TestParseKeyEscape:
    def test_escape_alone(self) -> None:
        assert parse_key("\x1b") == "escape"


# =============================================================================
# parse_key: arrow key sequences
# =============================================================================


class TestParseKeyArrows:
    def test_arrow_up(self) -> None:
        assert parse_key("\x1b[A") == "up"

    def test_arrow_down(self) -> None:
        assert parse_key("\x1b[B") == "down"

    def test_arrow_right(self) -> None:
        assert parse_key("\x1b[C") == "right"

    def test_arrow_left(self) -> None:
        assert parse_key("\x1b[D") == "left"

    def test_arrow_up_ss3(self) -> None:
        assert parse_key("\x1bOA") == "up"

    def test_arrow_down_ss3(self) -> None:
        assert parse_key("\x1bOB") == "down"

    def test_arrow_right_ss3(self) -> None:
        assert parse_key("\x1bOC") == "right"

    def test_arrow_left_ss3(self) -> None:
        assert parse_key("\x1bOD") == "left"


# =============================================================================
# parse_key: home/end sequences
# =============================================================================


class TestParseKeyHomeEnd:
    def test_home_csi(self) -> None:
        assert parse_key("\x1b[H") == "home"

    def test_home_ss3(self) -> None:
        assert parse_key("\x1bOH") == "home"

    def test_end_csi(self) -> None:
        assert parse_key("\x1b[F") == "end"

    def test_end_ss3(self) -> None:
        assert parse_key("\x1bOF") == "end"


# =============================================================================
# parse_key: function keys
# =============================================================================


class TestParseKeyFunctionKeys:
    def test_f1_ss3(self) -> None:
        assert parse_key("\x1bOP") == "f1"

    def test_f2_ss3(self) -> None:
        assert parse_key("\x1bOQ") == "f2"

    def test_f3_ss3(self) -> None:
        assert parse_key("\x1bOR") == "f3"

    def test_f4_ss3(self) -> None:
        assert parse_key("\x1bOS") == "f4"

    def test_f5(self) -> None:
        assert parse_key("\x1b[15~") == "f5"

    def test_f6(self) -> None:
        assert parse_key("\x1b[17~") == "f6"

    def test_f7(self) -> None:
        assert parse_key("\x1b[18~") == "f7"

    def test_f8(self) -> None:
        assert parse_key("\x1b[19~") == "f8"

    def test_f9(self) -> None:
        assert parse_key("\x1b[20~") == "f9"

    def test_f10(self) -> None:
        assert parse_key("\x1b[21~") == "f10"

    def test_f11(self) -> None:
        assert parse_key("\x1b[23~") == "f11"

    def test_f12(self) -> None:
        assert parse_key("\x1b[24~") == "f12"

    def test_f1_alternate_csi(self) -> None:
        assert parse_key("\x1b[11~") == "f1"

    def test_f1_linux_console(self) -> None:
        assert parse_key("\x1b[[A") == "f1"

    def test_f5_linux_console(self) -> None:
        assert parse_key("\x1b[[E") == "f5"


# =============================================================================
# parse_key: special terminal sequences
# =============================================================================


class TestParseKeySpecialSequences:
    def test_tab(self) -> None:
        assert parse_key("\t") == "tab"

    def test_enter_cr(self) -> None:
        assert parse_key("\r") == "enter"

    def test_enter_lf_legacy(self) -> None:
        # In legacy mode (kitty not active), \n is enter
        assert parse_key("\n") == "enter"

    def test_enter_lf_kitty_active(self) -> None:
        # In Kitty mode, \n is shift+enter
        set_kitty_protocol_active(True)
        assert parse_key("\n") == "shift+enter"

    def test_backspace(self) -> None:
        assert parse_key("\x7f") == "backspace"

    def test_backspace_bs(self) -> None:
        assert parse_key("\x08") == "backspace"

    def test_shift_tab(self) -> None:
        assert parse_key("\x1b[Z") == "shift+tab"

    def test_delete(self) -> None:
        assert parse_key("\x1b[3~") == "delete"

    def test_page_up(self) -> None:
        assert parse_key("\x1b[5~") == "pageUp"

    def test_page_down(self) -> None:
        assert parse_key("\x1b[6~") == "pageDown"

    def test_numpad_enter(self) -> None:
        assert parse_key("\x1bOM") == "enter"

    def test_alt_backspace(self) -> None:
        assert parse_key("\x1b\x7f") == "alt+backspace"

    def test_alt_backspace_bs(self) -> None:
        assert parse_key("\x1b\x08") == "alt+backspace"

    def test_alt_enter_legacy(self) -> None:
        assert parse_key("\x1b\r") == "alt+enter"

    def test_alt_enter_kitty_active(self) -> None:
        set_kitty_protocol_active(True)
        assert parse_key("\x1b\r") == "shift+enter"

    def test_alt_space_legacy(self) -> None:
        assert parse_key("\x1b ") == "alt+space"

    def test_alt_letter_legacy(self) -> None:
        assert parse_key("\x1bb") == "alt+left"
        assert parse_key("\x1bf") == "alt+right"
        assert parse_key("\x1bp") == "alt+up"
        assert parse_key("\x1bn") == "alt+down"

    def test_ctrl_alt_letter_legacy(self) -> None:
        # ESC followed by ctrl char (ctrl+a = \x01)
        assert parse_key("\x1b\x01") == "ctrl+alt+a"
        assert parse_key("\x1b\x03") == "ctrl+alt+c"

    def test_ctrl_alt_bracket_legacy(self) -> None:
        assert parse_key("\x1b\x1b") == "ctrl+alt+["
        assert parse_key("\x1b\x1c") == "ctrl+alt+\\"
        assert parse_key("\x1b\x1d") == "ctrl+alt+]"
        assert parse_key("\x1b\x1f") == "ctrl+alt+-"

    def test_legacy_alt_letter(self) -> None:
        # ESC followed by letter
        assert parse_key("\x1ba") == "alt+a"
        assert parse_key("\x1bz") == "alt+z"

    def test_unrecognized_returns_none(self) -> None:
        assert parse_key("\x1b[999Z") is None
        assert parse_key("") is None


# =============================================================================
# parse_key: Kitty protocol CSI-u sequences
# =============================================================================


class TestParseKeyKittyCSIU:
    def test_simple_letter_a(self) -> None:
        # \x1b[97u = codepoint 97 = 'a'
        assert parse_key("\x1b[97u") == "a"

    def test_simple_letter_z(self) -> None:
        assert parse_key("\x1b[122u") == "z"

    def test_escape_csi_u(self) -> None:
        assert parse_key("\x1b[27u") == "escape"

    def test_enter_csi_u(self) -> None:
        assert parse_key("\x1b[13u") == "enter"

    def test_tab_csi_u(self) -> None:
        assert parse_key("\x1b[9u") == "tab"

    def test_space_csi_u(self) -> None:
        assert parse_key("\x1b[32u") == "space"

    def test_backspace_csi_u(self) -> None:
        assert parse_key("\x1b[127u") == "backspace"

    def test_numpad_enter_csi_u(self) -> None:
        assert parse_key("\x1b[57414u") == "enter"


# =============================================================================
# parse_key: Kitty protocol with modifiers
# =============================================================================


class TestParseKeyKittyModifiers:
    def test_ctrl_a_kitty(self) -> None:
        # modifier 5 = 4+1 (ctrl), value in sequence is modifier+1
        assert parse_key("\x1b[97;5u") == "ctrl+a"

    def test_shift_a_kitty(self) -> None:
        # modifier 2 = 1+1 (shift)
        assert parse_key("\x1b[97;2u") == "shift+a"

    def test_alt_a_kitty(self) -> None:
        # modifier 3 = 2+1 (alt)
        assert parse_key("\x1b[97;3u") == "alt+a"

    def test_ctrl_shift_a_kitty(self) -> None:
        # modifier 6 = 5+1 (ctrl+shift)
        assert parse_key("\x1b[97;6u") == "shift+ctrl+a"

    def test_ctrl_alt_a_kitty(self) -> None:
        # modifier 7 = 6+1 (ctrl+alt)
        assert parse_key("\x1b[97;7u") == "ctrl+alt+a"

    def test_shift_alt_a_kitty(self) -> None:
        # modifier 4 = 3+1 (shift+alt)
        assert parse_key("\x1b[97;4u") == "shift+alt+a"

    def test_ctrl_shift_alt_a_kitty(self) -> None:
        # modifier 8 = 7+1 (ctrl+shift+alt)
        assert parse_key("\x1b[97;8u") == "shift+ctrl+alt+a"

    def test_ctrl_enter_kitty(self) -> None:
        assert parse_key("\x1b[13;5u") == "ctrl+enter"

    def test_shift_tab_kitty(self) -> None:
        assert parse_key("\x1b[9;2u") == "shift+tab"

    def test_alt_backspace_kitty(self) -> None:
        assert parse_key("\x1b[127;3u") == "alt+backspace"

    def test_kitty_arrow_with_modifier(self) -> None:
        # \x1b[1;5A = ctrl+up (modifier 5 = ctrl+1)
        assert parse_key("\x1b[1;5A") == "ctrl+up"
        assert parse_key("\x1b[1;5B") == "ctrl+down"
        assert parse_key("\x1b[1;5C") == "ctrl+right"
        assert parse_key("\x1b[1;5D") == "ctrl+left"

    def test_kitty_arrow_shift(self) -> None:
        assert parse_key("\x1b[1;2A") == "shift+up"
        assert parse_key("\x1b[1;2D") == "shift+left"

    def test_kitty_arrow_alt(self) -> None:
        assert parse_key("\x1b[1;3A") == "alt+up"
        assert parse_key("\x1b[1;3C") == "alt+right"

    def test_kitty_home_end_with_modifier(self) -> None:
        # \x1b[1;5H = ctrl+home, \x1b[1;5F = ctrl+end
        assert parse_key("\x1b[1;5H") == "ctrl+home"
        assert parse_key("\x1b[1;5F") == "ctrl+end"
        assert parse_key("\x1b[1;2H") == "shift+home"
        assert parse_key("\x1b[1;2F") == "shift+end"

    def test_kitty_functional_with_modifier(self) -> None:
        # \x1b[3;5~ = ctrl+delete (key_num=3, modifier=5)
        assert parse_key("\x1b[3;5~") == "ctrl+delete"
        assert parse_key("\x1b[5;2~") == "shift+pageUp"
        assert parse_key("\x1b[6;2~") == "shift+pageDown"

    def test_kitty_symbol_key(self) -> None:
        # Codepoint 45 = '-'
        assert parse_key("\x1b[45u") == "-"

    def test_kitty_with_shifted_key(self) -> None:
        # CSI 97:65 u = 'a' with shifted key 'A' (65)
        assert parse_key("\x1b[97:65u") == "a"

    def test_kitty_with_base_layout_key(self) -> None:
        # CSI 1000::97 u = non-latin codepoint 1000 with base layout 'a'
        # The base layout key should be used since codepoint is not latin
        assert parse_key("\x1b[1000::97u") == "a"

    def test_kitty_latin_codepoint_ignores_base_layout(self) -> None:
        # CSI 97::122 u = 'a' with base layout 'z'
        # Should use codepoint 97 ('a') since it IS latin
        assert parse_key("\x1b[97::122u") == "a"


# =============================================================================
# parse_key: Kitty protocol event types
# =============================================================================


class TestParseKeyKittyEventTypes:
    def test_press_event(self) -> None:
        # :1 = press (default)
        assert parse_key("\x1b[97;1:1u") == "a"

    def test_repeat_event(self) -> None:
        # :2 = repeat
        assert parse_key("\x1b[97;1:2u") == "a"

    def test_release_event(self) -> None:
        # :3 = release
        assert parse_key("\x1b[97;1:3u") == "a"


# =============================================================================
# matches_key
# =============================================================================


class TestMatchesKey:
    def test_escape(self) -> None:
        assert matches_key("\x1b", "escape") is True
        assert matches_key("\x1b", "esc") is True

    def test_enter(self) -> None:
        assert matches_key("\r", "enter") is True
        assert matches_key("\r", "return") is True

    def test_tab(self) -> None:
        assert matches_key("\t", "tab") is True

    def test_space(self) -> None:
        assert matches_key(" ", "space") is True

    def test_backspace(self) -> None:
        assert matches_key("\x7f", "backspace") is True
        assert matches_key("\x08", "backspace") is True

    def test_ctrl_c(self) -> None:
        assert matches_key("\x03", "ctrl+c") is True
        assert matches_key("\x03", Key.ctrl("c")) is True

    def test_ctrl_z(self) -> None:
        assert matches_key("\x1a", "ctrl+z") is True

    def test_ctrl_a(self) -> None:
        assert matches_key("\x01", "ctrl+a") is True

    def test_shift_tab(self) -> None:
        assert matches_key("\x1b[Z", "shift+tab") is True

    def test_arrow_keys(self) -> None:
        assert matches_key("\x1b[A", "up") is True
        assert matches_key("\x1b[B", "down") is True
        assert matches_key("\x1b[C", "right") is True
        assert matches_key("\x1b[D", "left") is True

    def test_arrow_keys_ss3(self) -> None:
        assert matches_key("\x1bOA", "up") is True
        assert matches_key("\x1bOB", "down") is True

    def test_home_end(self) -> None:
        assert matches_key("\x1b[H", "home") is True
        assert matches_key("\x1b[F", "end") is True
        assert matches_key("\x1bOH", "home") is True
        assert matches_key("\x1bOF", "end") is True

    def test_delete(self) -> None:
        assert matches_key("\x1b[3~", "delete") is True

    def test_insert(self) -> None:
        assert matches_key("\x1b[2~", "insert") is True

    def test_page_up_down(self) -> None:
        assert matches_key("\x1b[5~", "pageUp") is True
        assert matches_key("\x1b[6~", "pageDown") is True

    def test_function_keys(self) -> None:
        assert matches_key("\x1bOP", "f1") is True
        assert matches_key("\x1bOQ", "f2") is True
        assert matches_key("\x1bOR", "f3") is True
        assert matches_key("\x1bOS", "f4") is True
        assert matches_key("\x1b[15~", "f5") is True
        assert matches_key("\x1b[17~", "f6") is True
        assert matches_key("\x1b[24~", "f12") is True

    def test_alt_backspace(self) -> None:
        assert matches_key("\x1b\x7f", "alt+backspace") is True
        assert matches_key("\x1b\x08", "alt+backspace") is True

    def test_alt_letter_legacy(self) -> None:
        assert matches_key("\x1ba", "alt+a") is True
        assert matches_key("\x1bz", "alt+z") is True

    def test_alt_arrow_keys(self) -> None:
        assert matches_key("\x1bb", "alt+left") is True
        assert matches_key("\x1bf", "alt+right") is True
        assert matches_key("\x1bp", "alt+up") is True
        assert matches_key("\x1bn", "alt+down") is True

    def test_ctrl_alt_letter_legacy(self) -> None:
        # ctrl+alt+a = ESC followed by ctrl+a (\x01)
        assert matches_key("\x1b\x01", "ctrl+alt+a") is True

    def test_single_letter(self) -> None:
        assert matches_key("a", "a") is True
        assert matches_key("z", "z") is True

    def test_shift_letter(self) -> None:
        # shift+a produces uppercase A
        assert matches_key("A", "shift+a") is True
        assert matches_key("Z", "shift+z") is True

    def test_no_match(self) -> None:
        assert matches_key("a", "b") is False
        assert matches_key("\x03", "ctrl+z") is False

    def test_invalid_key_id(self) -> None:
        assert matches_key("a", "") is False

    def test_kitty_csi_u_match(self) -> None:
        assert matches_key("\x1b[97u", "a") is True
        assert matches_key("\x1b[97;5u", "ctrl+a") is True

    def test_shift_enter_csi_u(self) -> None:
        assert matches_key("\x1b[13;2u", "shift+enter") is True

    def test_alt_enter_csi_u(self) -> None:
        assert matches_key("\x1b[13;3u", "alt+enter") is True

    def test_ctrl_space_legacy(self) -> None:
        assert matches_key("\x00", "ctrl+space") is True

    def test_alt_space_legacy(self) -> None:
        assert matches_key("\x1b ", "alt+space") is True

    def test_ctrl_shift_kitty(self) -> None:
        # ctrl+shift+a via Kitty CSI-u: modifier 6
        assert matches_key("\x1b[97;6u", "ctrl+shift+a") is True

    def test_legacy_shift_arrows(self) -> None:
        assert matches_key("\x1b[a", "shift+up") is True
        assert matches_key("\x1b[b", "shift+down") is True
        assert matches_key("\x1b[c", "shift+right") is True
        assert matches_key("\x1b[d", "shift+left") is True

    def test_legacy_ctrl_arrows(self) -> None:
        assert matches_key("\x1bOa", "ctrl+up") is True
        assert matches_key("\x1bOb", "ctrl+down") is True
        assert matches_key("\x1bOc", "ctrl+right") is True
        assert matches_key("\x1bOd", "ctrl+left") is True

    def test_ctrl_left_xterm(self) -> None:
        assert matches_key("\x1b[1;5D", "ctrl+left") is True

    def test_ctrl_right_xterm(self) -> None:
        assert matches_key("\x1b[1;5C", "ctrl+right") is True

    def test_alt_left_xterm(self) -> None:
        assert matches_key("\x1b[1;3D", "alt+left") is True

    def test_alt_right_xterm(self) -> None:
        assert matches_key("\x1b[1;3C", "alt+right") is True

    def test_legacy_shift_delete(self) -> None:
        assert matches_key("\x1b[3$", "shift+delete") is True

    def test_legacy_ctrl_delete(self) -> None:
        assert matches_key("\x1b[3^", "ctrl+delete") is True

    def test_legacy_shift_home(self) -> None:
        assert matches_key("\x1b[7$", "shift+home") is True

    def test_legacy_ctrl_home(self) -> None:
        assert matches_key("\x1b[7^", "ctrl+home") is True

    def test_legacy_shift_end(self) -> None:
        assert matches_key("\x1b[8$", "shift+end") is True

    def test_legacy_ctrl_end(self) -> None:
        assert matches_key("\x1b[8^", "ctrl+end") is True

    def test_enter_lf_legacy(self) -> None:
        assert matches_key("\n", "enter") is True

    def test_enter_lf_kitty_not_enter(self) -> None:
        set_kitty_protocol_active(True)
        assert matches_key("\n", "enter") is False

    def test_shift_enter_kitty_lf(self) -> None:
        set_kitty_protocol_active(True)
        assert matches_key("\n", "shift+enter") is True

    def test_shift_enter_kitty_esc_cr(self) -> None:
        set_kitty_protocol_active(True)
        assert matches_key("\x1b\r", "shift+enter") is True

    def test_alt_enter_legacy_esc_cr(self) -> None:
        # In legacy mode, \x1b\r is alt+enter
        assert matches_key("\x1b\r", "alt+enter") is True

    def test_escape_with_modifier_returns_false(self) -> None:
        assert matches_key("\x1b", "ctrl+escape") is False

    def test_symbol_key_match(self) -> None:
        assert matches_key("/", "/") is True
        assert matches_key(".", ".") is True


# =============================================================================
# is_key_release / is_key_repeat
# =============================================================================


class TestKeyEventTypes:
    def test_is_key_release_csi_u(self) -> None:
        assert is_key_release("\x1b[97;1:3u") is True

    def test_is_key_release_tilde(self) -> None:
        assert is_key_release("\x1b[3;5:3~") is True

    def test_is_key_release_arrow(self) -> None:
        assert is_key_release("\x1b[1;5:3A") is True
        assert is_key_release("\x1b[1;5:3B") is True
        assert is_key_release("\x1b[1;5:3C") is True
        assert is_key_release("\x1b[1;5:3D") is True

    def test_is_key_release_home_end(self) -> None:
        assert is_key_release("\x1b[1;5:3H") is True
        assert is_key_release("\x1b[1;5:3F") is True

    def test_is_not_key_release(self) -> None:
        assert is_key_release("\x1b[97u") is False
        assert is_key_release("\x1b[97;1:1u") is False
        assert is_key_release("a") is False

    def test_is_key_release_ignores_bracketed_paste(self) -> None:
        assert is_key_release("\x1b[200~:3u") is False

    def test_is_key_repeat_csi_u(self) -> None:
        assert is_key_repeat("\x1b[97;1:2u") is True

    def test_is_key_repeat_tilde(self) -> None:
        assert is_key_repeat("\x1b[3;5:2~") is True

    def test_is_key_repeat_arrow(self) -> None:
        assert is_key_repeat("\x1b[1;5:2A") is True

    def test_is_not_key_repeat(self) -> None:
        assert is_key_repeat("\x1b[97u") is False
        assert is_key_repeat("a") is False

    def test_is_key_repeat_ignores_bracketed_paste(self) -> None:
        assert is_key_repeat("\x1b[200~:2u") is False


# =============================================================================
# set/is_kitty_protocol_active
# =============================================================================


class TestKittyProtocolState:
    def test_default_is_false(self) -> None:
        assert is_kitty_protocol_active() is False

    def test_set_active(self) -> None:
        set_kitty_protocol_active(True)
        assert is_kitty_protocol_active() is True

    def test_set_inactive(self) -> None:
        set_kitty_protocol_active(True)
        set_kitty_protocol_active(False)
        assert is_kitty_protocol_active() is False

    def test_affects_parse_key_behavior(self) -> None:
        # \n is "enter" in legacy, "shift+enter" in Kitty
        assert parse_key("\n") == "enter"
        set_kitty_protocol_active(True)
        assert parse_key("\n") == "shift+enter"

    def test_affects_alt_enter_parsing(self) -> None:
        # \x1b\r is "alt+enter" in legacy, "shift+enter" in Kitty
        assert parse_key("\x1b\r") == "alt+enter"
        set_kitty_protocol_active(True)
        assert parse_key("\x1b\r") == "shift+enter"

    def test_affects_alt_left_legacy_sequence(self) -> None:
        # \x1bB is "alt+left" only in legacy mode
        assert parse_key("\x1bB") == "alt+left"
        set_kitty_protocol_active(True)
        # In Kitty mode, \x1bB is ESC followed by 'B' which is not alt+left
        # It falls through to the alt+letter check which is also gated
        result = parse_key("\x1bB")
        assert result != "alt+left"

    def test_affects_alt_right_legacy_sequence(self) -> None:
        assert parse_key("\x1bF") == "alt+right"
        set_kitty_protocol_active(True)
        result = parse_key("\x1bF")
        assert result != "alt+right"
