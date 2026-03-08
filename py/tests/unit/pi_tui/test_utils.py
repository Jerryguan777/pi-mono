"""Comprehensive tests for pi_tui.utils."""

from __future__ import annotations

import pytest

from pi_tui.utils import (
    AnsiCode,
    AnsiCodeTracker,
    ExtractSegmentsResult,
    SliceResult,
    extract_ansi_code,
    extract_segments,
    get_segmenter,
    slice_by_column,
    slice_with_width,
    truncate_to_width,
    visible_width,
    wrap_text_with_ansi,
)


# =========================================================================
# visible_width
# =========================================================================


class TestVisibleWidth:
    def test_empty_string(self) -> None:
        assert visible_width("") == 0

    def test_ascii_text(self) -> None:
        assert visible_width("hello") == 5

    def test_ascii_with_spaces(self) -> None:
        assert visible_width("hello world") == 11

    def test_pure_ascii_fast_path(self) -> None:
        # All printable ASCII should use the fast path (len)
        s = "abcdefghijklmnopqrstuvwxyz0123456789"
        assert visible_width(s) == len(s)

    def test_ansi_escape_stripped(self) -> None:
        # Bold "hi" - ANSI codes should not count toward width
        assert visible_width("\x1b[1mhi\x1b[0m") == 2

    def test_multiple_ansi_codes(self) -> None:
        s = "\x1b[31m\x1b[1mred bold\x1b[0m"
        assert visible_width(s) == 8

    def test_ansi_sgr_with_params(self) -> None:
        # 256-color foreground
        s = "\x1b[38;5;196mcolored\x1b[0m"
        assert visible_width(s) == 7

    def test_osc_hyperlink_stripped(self) -> None:
        s = "\x1b]8;;https://example.com\x07link text\x1b]8;;\x07"
        assert visible_width(s) == 9

    def test_wide_characters_cjk(self) -> None:
        # CJK characters are typically 2 columns wide
        assert visible_width("\u4e16\u754c") == 4  # "world" in Chinese

    def test_single_wide_char(self) -> None:
        assert visible_width("\u5168") == 2  # fullwidth CJK char

    def test_mixed_ascii_and_wide(self) -> None:
        assert visible_width("a\u4e16b") == 4  # 1 + 2 + 1

    def test_tab_handling(self) -> None:
        # Tabs are replaced with 3 spaces
        assert visible_width("\t") == 3

    def test_multiple_tabs(self) -> None:
        assert visible_width("\t\t") == 6

    def test_tab_mixed_with_text(self) -> None:
        assert visible_width("a\tb") == 5  # 1 + 3 + 1

    def test_combining_characters(self) -> None:
        # 'e' + combining acute accent should be width 1
        s = "e\u0301"  # e followed by combining acute
        assert visible_width(s) == 1


# =========================================================================
# extract_ansi_code
# =========================================================================


class TestExtractAnsiCode:
    def test_csi_sgr_sequence(self) -> None:
        s = "\x1b[1m"
        result = extract_ansi_code(s, 0)
        assert result is not None
        assert result.code == "\x1b[1m"
        assert result.length == 4

    def test_csi_with_params(self) -> None:
        s = "\x1b[38;5;196m"
        result = extract_ansi_code(s, 0)
        assert result is not None
        assert result.code == "\x1b[38;5;196m"
        assert result.length == len("\x1b[38;5;196m")

    def test_csi_cursor_code(self) -> None:
        s = "\x1b[2J"  # clear screen
        result = extract_ansi_code(s, 0)
        assert result is not None
        assert result.code == "\x1b[2J"

    def test_osc_sequence_bel_terminated(self) -> None:
        s = "\x1b]8;;https://example.com\x07"
        result = extract_ansi_code(s, 0)
        assert result is not None
        assert result.code == s
        assert result.length == len(s)

    def test_osc_sequence_st_terminated(self) -> None:
        s = "\x1b]8;;https://example.com\x1b\\"
        result = extract_ansi_code(s, 0)
        assert result is not None
        assert result.code == s
        assert result.length == len(s)

    def test_apc_sequence_bel_terminated(self) -> None:
        s = "\x1b_some data\x07"
        result = extract_ansi_code(s, 0)
        assert result is not None
        assert result.code == s

    def test_apc_sequence_st_terminated(self) -> None:
        s = "\x1b_some data\x1b\\"
        result = extract_ansi_code(s, 0)
        assert result is not None
        assert result.code == s

    def test_non_ansi_returns_none(self) -> None:
        assert extract_ansi_code("hello", 0) is None

    def test_non_escape_char_returns_none(self) -> None:
        assert extract_ansi_code("abc", 1) is None

    def test_pos_out_of_bounds(self) -> None:
        assert extract_ansi_code("abc", 10) is None

    def test_pos_at_escape_in_middle(self) -> None:
        s = "abc\x1b[31mdef"
        result = extract_ansi_code(s, 3)
        assert result is not None
        assert result.code == "\x1b[31m"

    def test_incomplete_csi_returns_none(self) -> None:
        # ESC [ with no terminator
        s = "\x1b[123"
        result = extract_ansi_code(s, 0)
        assert result is None

    def test_incomplete_osc_returns_none(self) -> None:
        # No BEL or ST terminator
        s = "\x1b]8;;https://example.com"
        result = extract_ansi_code(s, 0)
        assert result is None

    def test_bare_escape_returns_none(self) -> None:
        # Just ESC with nothing after
        s = "\x1b"
        result = extract_ansi_code(s, 0)
        assert result is None

    def test_escape_with_unknown_follows_returns_none(self) -> None:
        s = "\x1bX"
        result = extract_ansi_code(s, 0)
        assert result is None

    def test_returns_namedtuple(self) -> None:
        result = extract_ansi_code("\x1b[0m", 0)
        assert result is not None
        assert isinstance(result, AnsiCode)
        assert result.code == "\x1b[0m"
        assert result.length == 4


# =========================================================================
# AnsiCodeTracker
# =========================================================================


class TestAnsiCodeTracker:
    def test_initial_state_no_active_codes(self) -> None:
        tracker = AnsiCodeTracker()
        assert not tracker.has_active_codes()
        assert tracker.get_active_codes() == ""

    def test_bold(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[1m")
        assert tracker.has_active_codes()
        assert "1" in tracker.get_active_codes()

    def test_italic(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[3m")
        assert tracker.has_active_codes()
        assert "3" in tracker.get_active_codes()

    def test_foreground_color(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[31m")  # red
        assert tracker.has_active_codes()
        assert "31" in tracker.get_active_codes()

    def test_background_color(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[42m")  # green bg
        assert tracker.has_active_codes()
        assert "42" in tracker.get_active_codes()

    def test_reset_clears_all(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[1m")
        tracker.process("\x1b[31m")
        tracker.process("\x1b[0m")
        assert not tracker.has_active_codes()
        assert tracker.get_active_codes() == ""

    def test_empty_params_is_reset(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[1m")
        tracker.process("\x1b[m")  # empty params = reset
        assert not tracker.has_active_codes()

    def test_multiple_attributes(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[1;3;31m")  # bold + italic + red
        assert tracker.has_active_codes()
        codes = tracker.get_active_codes()
        assert "1" in codes
        assert "3" in codes
        assert "31" in codes

    def test_specific_attribute_removal(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[1m")  # bold on
        tracker.process("\x1b[21m")  # bold off
        assert not tracker.has_active_codes()

    def test_dim_and_bold_removal_with_22(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[1m")  # bold
        tracker.process("\x1b[2m")  # dim
        tracker.process("\x1b[22m")  # removes both bold and dim
        assert not tracker.has_active_codes()

    def test_256_color_foreground(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[38;5;196m")
        assert tracker.has_active_codes()
        codes = tracker.get_active_codes()
        assert "38;5;196" in codes

    def test_256_color_background(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[48;5;22m")
        assert tracker.has_active_codes()
        codes = tracker.get_active_codes()
        assert "48;5;22" in codes

    def test_rgb_foreground(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[38;2;255;0;128m")
        assert tracker.has_active_codes()
        codes = tracker.get_active_codes()
        assert "38;2;255;0;128" in codes

    def test_rgb_background(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[48;2;0;128;255m")
        assert tracker.has_active_codes()
        assert "48;2;0;128;255" in tracker.get_active_codes()

    def test_fg_reset_with_39(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[31m")
        tracker.process("\x1b[39m")  # default fg
        assert not tracker.has_active_codes()

    def test_bg_reset_with_49(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[42m")
        tracker.process("\x1b[49m")  # default bg
        assert not tracker.has_active_codes()

    def test_bright_fg_color(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[91m")  # bright red
        assert tracker.has_active_codes()
        assert "91" in tracker.get_active_codes()

    def test_bright_bg_color(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[101m")  # bright red bg
        assert tracker.has_active_codes()
        assert "101" in tracker.get_active_codes()

    def test_clear_resets_all(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[1;3;31m")
        tracker.clear()
        assert not tracker.has_active_codes()

    def test_non_sgr_code_ignored(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[2J")  # clear screen, not SGR
        assert not tracker.has_active_codes()

    def test_line_end_reset_for_underline(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[4m")  # underline
        assert tracker.get_line_end_reset() == "\x1b[24m"

    def test_line_end_reset_no_underline(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[1m")  # bold, no underline
        assert tracker.get_line_end_reset() == ""

    def test_all_attribute_flags(self) -> None:
        tracker = AnsiCodeTracker()
        # Set all boolean flags
        tracker.process("\x1b[1;2;3;4;5;7;8;9m")
        codes = tracker.get_active_codes()
        for expected in ["1", "2", "3", "4", "5", "7", "8", "9"]:
            assert expected in codes

    def test_strikethrough_removal(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[9m")
        tracker.process("\x1b[29m")
        assert not tracker.has_active_codes()

    def test_underline_removal(self) -> None:
        tracker = AnsiCodeTracker()
        tracker.process("\x1b[4m")
        tracker.process("\x1b[24m")
        assert not tracker.has_active_codes()


# =========================================================================
# wrap_text_with_ansi
# =========================================================================


class TestWrapTextWithAnsi:
    def test_empty_string(self) -> None:
        assert wrap_text_with_ansi("", 80) == [""]

    def test_single_line_no_wrap(self) -> None:
        assert wrap_text_with_ansi("hello", 80) == ["hello"]

    def test_exact_width_no_wrap(self) -> None:
        assert wrap_text_with_ansi("hello", 5) == ["hello"]

    def test_wrapping_at_word_boundary(self) -> None:
        result = wrap_text_with_ansi("hello world", 5)
        assert len(result) == 2
        assert result[0] == "hello"
        assert result[1] == "world"

    def test_wrapping_multiple_words(self) -> None:
        result = wrap_text_with_ansi("one two three four", 8)
        # "one two" = 7, "three" = 5, "four" = 4
        assert result[0] == "one two"
        assert "three" in result[1]

    def test_preserves_ansi_codes_across_wrap(self) -> None:
        # Bold text wrapping - ANSI code should persist
        s = "\x1b[1mhello world\x1b[0m"
        result = wrap_text_with_ansi(s, 5)
        assert len(result) >= 2
        # First line should have bold
        assert "\x1b[1m" in result[0]

    def test_hard_break_long_word(self) -> None:
        result = wrap_text_with_ansi("abcdefghij", 5)
        assert len(result) == 2
        assert visible_width(result[0]) <= 5
        assert visible_width(result[1]) <= 5

    def test_preserves_newlines(self) -> None:
        result = wrap_text_with_ansi("hello\nworld", 80)
        assert result == ["hello", "world"]

    def test_wrapping_with_existing_newlines(self) -> None:
        result = wrap_text_with_ansi("hello world\nfoo bar", 5)
        assert len(result) >= 3  # at least 2 from first line + 1 from second

    def test_all_lines_within_width(self) -> None:
        text = "The quick brown fox jumps over the lazy dog"
        width = 10
        result = wrap_text_with_ansi(text, width)
        for line in result:
            assert visible_width(line) <= width

    def test_ansi_color_preserved_on_continuation(self) -> None:
        # Red text that wraps - color should carry over
        s = "\x1b[31mhello world\x1b[0m"
        result = wrap_text_with_ansi(s, 5)
        assert len(result) >= 2


# =========================================================================
# truncate_to_width
# =========================================================================


class TestTruncateToWidth:
    def test_no_truncation_needed(self) -> None:
        assert truncate_to_width("hello", 10) == "hello"

    def test_exact_width(self) -> None:
        assert truncate_to_width("hello", 5) == "hello"

    def test_basic_truncation(self) -> None:
        result = truncate_to_width("hello world", 8)
        assert visible_width(result) <= 8
        assert result.endswith("...")

    def test_truncation_with_custom_ellipsis(self) -> None:
        result = truncate_to_width("hello world", 8, ellipsis="..")
        assert result.endswith("..")

    def test_truncation_with_empty_ellipsis(self) -> None:
        result = truncate_to_width("hello world", 5, ellipsis="")
        assert visible_width(result) <= 5
        assert not result.endswith("...")

    def test_truncation_with_padding(self) -> None:
        result = truncate_to_width("hello", 10, pad=True)
        assert visible_width(result) == 10

    def test_truncation_and_padding(self) -> None:
        result = truncate_to_width("hello world", 8, pad=True)
        assert visible_width(result) == 8

    def test_wide_characters_truncation(self) -> None:
        # Two CJK chars = 4 columns, try truncating to 3
        result = truncate_to_width("\u4e16\u754c\u4e16", 5)
        assert visible_width(result) <= 5

    def test_very_small_width(self) -> None:
        result = truncate_to_width("hello", 2)
        assert visible_width(result) <= 2

    def test_width_zero(self) -> None:
        result = truncate_to_width("hello", 0)
        assert visible_width(result) <= 3  # just ellipsis possibly

    def test_no_pad_short_string(self) -> None:
        result = truncate_to_width("hi", 10, pad=False)
        assert result == "hi"

    def test_pad_short_string(self) -> None:
        result = truncate_to_width("hi", 10, pad=True)
        assert result == "hi" + " " * 8

    def test_ansi_preserved_after_truncation(self) -> None:
        s = "\x1b[31mhello world\x1b[0m"
        result = truncate_to_width(s, 8)
        # Should contain the red code at the start
        assert "\x1b[31m" in result


# =========================================================================
# slice_by_column
# =========================================================================


class TestSliceByColumn:
    def test_ascii_slice(self) -> None:
        assert slice_by_column("hello world", 0, 5) == "hello"

    def test_ascii_middle_slice(self) -> None:
        assert slice_by_column("hello world", 6, 5) == "world"

    def test_full_string(self) -> None:
        assert slice_by_column("hello", 0, 5) == "hello"

    def test_zero_length(self) -> None:
        assert slice_by_column("hello", 0, 0) == ""

    def test_slice_with_wide_chars(self) -> None:
        # "AB" where A and B are CJK (2 cols each), total 4 cols
        s = "\u4e16\u754c"  # 2 + 2 = 4 columns
        result = slice_by_column(s, 0, 2)
        assert result == "\u4e16"

    def test_slice_past_end(self) -> None:
        result = slice_by_column("hi", 0, 10)
        assert result == "hi"

    def test_slice_with_ansi(self) -> None:
        s = "\x1b[31mhello\x1b[0m"
        result = slice_by_column(s, 0, 3)
        # Should include the ANSI code and first 3 chars
        assert "hel" in result

    def test_strict_excludes_wide_at_boundary(self) -> None:
        # Wide char at boundary with strict mode
        s = "a\u4e16b"  # 1 + 2 + 1 = 4 columns
        # Strict slice of cols 0-1: "a" (wide char at col 1-2 extends past)
        result_strict = slice_by_column(s, 0, 2, strict=True)
        result_non_strict = slice_by_column(s, 0, 2, strict=False)
        # In strict mode, the wide char starting at col 1 extends to col 3,
        # which is past length 2, so it should be excluded
        assert visible_width(result_strict) <= 2


# =========================================================================
# slice_with_width
# =========================================================================


class TestSliceWithWidth:
    def test_basic_ascii(self) -> None:
        result = slice_with_width("hello", 0, 3)
        assert isinstance(result, SliceResult)
        assert result.text == "hel"
        assert result.width == 3

    def test_zero_length(self) -> None:
        result = slice_with_width("hello", 0, 0)
        assert result.text == ""
        assert result.width == 0

    def test_negative_length(self) -> None:
        result = slice_with_width("hello", 0, -1)
        assert result.text == ""
        assert result.width == 0

    def test_wide_character_width(self) -> None:
        s = "\u4e16\u754c"  # 2 + 2 = 4 columns
        result = slice_with_width(s, 0, 4)
        assert result.text == s
        assert result.width == 4

    def test_partial_wide_character(self) -> None:
        s = "\u4e16\u754c"  # 2 + 2 = 4 columns
        result = slice_with_width(s, 0, 2)
        assert result.text == "\u4e16"
        assert result.width == 2

    def test_with_ansi_codes(self) -> None:
        s = "\x1b[1mhello\x1b[0m"
        result = slice_with_width(s, 0, 3)
        assert "hel" in result.text
        assert result.width == 3


# =========================================================================
# get_segmenter
# =========================================================================


class TestGetSegmenter:
    def test_returns_callable(self) -> None:
        segmenter = get_segmenter()
        assert callable(segmenter)

    def test_ascii_iteration(self) -> None:
        segmenter = get_segmenter()
        result = segmenter("abc")
        assert result == ["a", "b", "c"]

    def test_empty_string(self) -> None:
        segmenter = get_segmenter()
        assert segmenter("") == []

    def test_combining_characters_grouped(self) -> None:
        segmenter = get_segmenter()
        # e + combining acute accent should be one cluster
        s = "e\u0301"
        result = segmenter(s)
        assert len(result) == 1
        assert result[0] == "e\u0301"

    def test_multiple_combining_chars(self) -> None:
        segmenter = get_segmenter()
        # a + combining tilde + combining acute
        s = "a\u0303\u0301"
        result = segmenter(s)
        assert len(result) == 1

    def test_mixed_text(self) -> None:
        segmenter = get_segmenter()
        result = segmenter("ae\u0301b")
        assert len(result) == 3
        assert result[0] == "a"
        assert result[1] == "e\u0301"
        assert result[2] == "b"

    def test_variation_selector_grouped(self) -> None:
        segmenter = get_segmenter()
        # Text presentation selector
        s = "\u2603\ufe0f"  # snowman + VS16
        result = segmenter(s)
        assert len(result) == 1

    def test_regional_indicator_flag(self) -> None:
        segmenter = get_segmenter()
        # US flag = regional indicator U + S
        s = "\U0001F1FA\U0001F1F8"
        result = segmenter(s)
        assert len(result) == 1


# =========================================================================
# extract_segments
# =========================================================================


class TestExtractSegments:
    def test_basic_before_segment(self) -> None:
        result = extract_segments("hello world", before_end=5, after_start=6, after_len=5)
        assert isinstance(result, ExtractSegmentsResult)
        assert result.before == "hello"
        assert result.before_width == 5

    def test_basic_after_segment(self) -> None:
        result = extract_segments("hello world", before_end=5, after_start=6, after_len=5)
        assert result.after == "world"
        assert result.after_width == 5

    def test_no_after_segment(self) -> None:
        result = extract_segments("hello world", before_end=5, after_start=6, after_len=0)
        assert result.after == ""
        assert result.after_width == 0

    def test_with_ansi_styling_preserved_in_after(self) -> None:
        # Style set in the overlay gap should carry into after segment
        s = "\x1b[31mhello world"
        result = extract_segments(s, before_end=3, after_start=6, after_len=5)
        # The after segment should include restored styling
        assert result.after_width == 5

    def test_before_width_matches_content(self) -> None:
        result = extract_segments("abcdefghij", before_end=4, after_start=6, after_len=4)
        assert result.before == "abcd"
        assert result.before_width == 4

    def test_empty_line(self) -> None:
        result = extract_segments("", before_end=0, after_start=0, after_len=0)
        assert result.before == ""
        assert result.after == ""

    def test_before_only(self) -> None:
        result = extract_segments("hello", before_end=5, after_start=5, after_len=0)
        assert result.before == "hello"
        assert result.before_width == 5
        assert result.after == ""
