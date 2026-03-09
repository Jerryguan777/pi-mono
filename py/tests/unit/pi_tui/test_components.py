"""Unit tests for simpler pi_tui components."""

from __future__ import annotations

from unittest.mock import MagicMock

from pi_tui.components.box import Box
from pi_tui.components.loader import Loader
from pi_tui.components.select_list import SelectItem, SelectList, SelectListTheme
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.components.truncated_text import TruncatedText
from pi_tui.utils import visible_width

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity(s: str) -> str:
    return s


def _make_theme() -> SelectListTheme:
    return SelectListTheme(
        selected_prefix=_identity,
        selected_text=_identity,
        description=_identity,
        scroll_info=_identity,
        no_match=_identity,
    )


# Terminal escape sequences for arrow keys (legacy)
KEY_UP = "\x1b[A"
KEY_DOWN = "\x1b[B"
KEY_ENTER = "\r"
KEY_ESCAPE = "\x1b"


# =========================================================================
# Spacer
# =========================================================================


class TestSpacer:
    def test_default_one_line(self) -> None:
        spacer = Spacer()
        lines = spacer.render(80)
        assert lines == [""]

    def test_multiple_lines(self) -> None:
        spacer = Spacer(lines=3)
        lines = spacer.render(80)
        assert len(lines) == 3
        assert all(line == "" for line in lines)

    def test_zero_lines(self) -> None:
        spacer = Spacer(lines=0)
        lines = spacer.render(80)
        assert lines == []

    def test_set_lines(self) -> None:
        spacer = Spacer(lines=1)
        spacer.set_lines(5)
        lines = spacer.render(80)
        assert len(lines) == 5

    def test_width_is_ignored(self) -> None:
        spacer = Spacer(lines=2)
        lines_narrow = spacer.render(10)
        lines_wide = spacer.render(200)
        assert lines_narrow == lines_wide


# =========================================================================
# Text
# =========================================================================


class TestText:
    def test_empty_text_returns_empty(self) -> None:
        text = Text("")
        assert text.render(80) == []

    def test_whitespace_only_returns_empty(self) -> None:
        text = Text("   ")
        assert text.render(80) == []

    def test_simple_text_renders_with_padding(self) -> None:
        text = Text("hello", padding_x=1, padding_y=0)
        lines = text.render(40)
        assert len(lines) >= 1
        # The content line should contain "hello" with left padding
        content_line = lines[0]
        assert "hello" in content_line

    def test_vertical_padding_adds_empty_lines(self) -> None:
        text = Text("hello", padding_x=0, padding_y=2)
        lines = text.render(40)
        # 2 empty lines top + at least 1 content + 2 empty lines bottom
        assert len(lines) >= 5

    def test_text_wraps_at_width(self) -> None:
        long_text = "word " * 20  # 100 chars
        text = Text(long_text.strip(), padding_x=0, padding_y=0)
        lines = text.render(20)
        # Should have multiple lines since content exceeds width
        assert len(lines) > 1

    def test_text_with_ansi_styles(self) -> None:
        styled = "\x1b[31mred text\x1b[0m"
        text = Text(styled, padding_x=0, padding_y=0)
        lines = text.render(80)
        assert len(lines) >= 1
        # ANSI codes should be preserved in output
        assert "\x1b[31m" in lines[0]

    def test_custom_bg_fn_applied(self) -> None:
        called_with: list[str] = []

        def bg_fn(s: str) -> str:
            called_with.append(s)
            return f"[BG]{s}[/BG]"

        text = Text("hello", padding_x=0, padding_y=0, custom_bg_fn=bg_fn)
        lines = text.render(40)
        assert len(lines) >= 1
        assert len(called_with) > 0

    def test_set_text_invalidates_cache(self) -> None:
        text = Text("first", padding_x=0, padding_y=0)
        lines1 = text.render(40)
        text.set_text("second")
        lines2 = text.render(40)
        assert "first" in lines1[0]
        assert "second" in lines2[0]

    def test_cache_returns_same_result(self) -> None:
        text = Text("hello", padding_x=0, padding_y=0)
        lines1 = text.render(40)
        lines2 = text.render(40)
        assert lines1 is lines2  # Same object reference = cache hit

    def test_tab_replaced_with_spaces(self) -> None:
        text = Text("a\tb", padding_x=0, padding_y=0)
        lines = text.render(80)
        assert "\t" not in lines[0]
        assert "a   b" in lines[0]


# =========================================================================
# TruncatedText
# =========================================================================


class TestTruncatedText:
    def test_short_text_fits(self) -> None:
        tt = TruncatedText("hello", padding_x=0, padding_y=0)
        lines = tt.render(80)
        assert len(lines) == 1
        assert "hello" in lines[0]

    def test_long_text_truncated(self) -> None:
        long = "a" * 100
        tt = TruncatedText(long, padding_x=0, padding_y=0)
        lines = tt.render(20)
        assert len(lines) == 1
        assert visible_width(lines[0]) == 20
        # Should contain ellipsis
        assert "..." in lines[0]

    def test_multiline_uses_first_line_only(self) -> None:
        tt = TruncatedText("first\nsecond\nthird", padding_x=0, padding_y=0)
        lines = tt.render(80)
        assert len(lines) == 1
        assert "first" in lines[0]
        assert "second" not in lines[0]

    def test_padding_x(self) -> None:
        tt = TruncatedText("hello", padding_x=2, padding_y=0)
        lines = tt.render(80)
        assert len(lines) == 1
        # Should start with 2 spaces of padding
        assert lines[0].startswith("  ")

    def test_padding_y(self) -> None:
        tt = TruncatedText("hello", padding_x=0, padding_y=1)
        lines = tt.render(80)
        # 1 empty top + 1 content + 1 empty bottom
        assert len(lines) == 3

    def test_output_padded_to_width(self) -> None:
        tt = TruncatedText("hi", padding_x=0, padding_y=0)
        lines = tt.render(40)
        assert len(lines) == 1
        assert visible_width(lines[0]) == 40


# =========================================================================
# Box
# =========================================================================


class TestBox:
    def test_empty_box_returns_empty(self) -> None:
        box = Box()
        assert box.render(80) == []

    def test_box_with_child(self) -> None:
        box = Box(padding_x=0, padding_y=0)
        child = Spacer(lines=1)
        box.add_child(child)
        lines = box.render(80)
        assert len(lines) >= 1

    def test_box_padding_y(self) -> None:
        box = Box(padding_x=0, padding_y=2)
        child = Spacer(lines=1)
        box.add_child(child)
        lines = box.render(80)
        # 2 top padding + 1 child line + 2 bottom padding = 5
        assert len(lines) == 5

    def test_box_padding_x(self) -> None:
        box = Box(padding_x=3, padding_y=0)
        child = Text("hi", padding_x=0, padding_y=0)
        box.add_child(child)
        lines = box.render(80)
        assert len(lines) >= 1
        # Each line should be padded to width 80
        for line in lines:
            assert visible_width(line) == 80

    def test_box_with_bg_fn(self) -> None:
        applied: list[str] = []

        def bg_fn(s: str) -> str:
            applied.append(s)
            return f"[BG]{s}[/BG]"

        box = Box(padding_x=0, padding_y=0, bg_fn=bg_fn)
        child = Spacer(lines=1)
        box.add_child(child)
        lines = box.render(40)
        assert len(lines) >= 1
        assert len(applied) > 0

    def test_box_remove_child(self) -> None:
        box = Box(padding_x=0, padding_y=0)
        child = Spacer(lines=1)
        box.add_child(child)
        assert len(box.render(80)) >= 1
        box.remove_child(child)
        assert box.render(80) == []

    def test_box_clear(self) -> None:
        box = Box(padding_x=0, padding_y=0)
        box.add_child(Spacer(lines=1))
        box.add_child(Spacer(lines=1))
        assert len(box.render(80)) >= 2
        box.clear()
        assert box.render(80) == []

    def test_box_multiple_children(self) -> None:
        box = Box(padding_x=0, padding_y=0)
        box.add_child(Spacer(lines=2))
        box.add_child(Spacer(lines=3))
        lines = box.render(80)
        # 2 + 3 = 5 lines from children
        assert len(lines) == 5

    def test_box_invalidate_propagates(self) -> None:
        box = Box(padding_x=0, padding_y=0)
        child_mock = MagicMock()
        child_mock.render.return_value = ["line"]
        box.add_child(child_mock)
        box.invalidate()
        child_mock.invalidate.assert_called_once()


# =========================================================================
# Loader
# =========================================================================


class TestLoader:
    def test_render_includes_spinner_frame(self) -> None:
        tui = MagicMock()
        loader = Loader(
            tui=tui,
            spinner_color_fn=_identity,
            message_color_fn=_identity,
            message="Loading...",
        )
        try:
            lines = loader.render(80)
            # First line is always empty (from Loader.render prepending "")
            assert lines[0] == ""
            # Should have more lines with spinner content
            assert len(lines) >= 2
            # One of the frames should appear in the content
            content = " ".join(lines[1:])
            assert any(frame in content for frame in Loader._FRAMES)
        finally:
            loader.stop()

    def test_render_includes_message(self) -> None:
        tui = MagicMock()
        loader = Loader(
            tui=tui,
            spinner_color_fn=_identity,
            message_color_fn=_identity,
            message="Please wait",
        )
        try:
            lines = loader.render(80)
            content = " ".join(lines)
            assert "Please wait" in content
        finally:
            loader.stop()

    def test_set_message(self) -> None:
        tui = MagicMock()
        loader = Loader(
            tui=tui,
            spinner_color_fn=_identity,
            message_color_fn=_identity,
            message="first",
        )
        try:
            loader.set_message("second")
            lines = loader.render(80)
            content = " ".join(lines)
            assert "second" in content
            assert "first" not in content
        finally:
            loader.stop()

    def test_stop_cancels_timer(self) -> None:
        tui = MagicMock()
        loader = Loader(
            tui=tui,
            spinner_color_fn=_identity,
            message_color_fn=_identity,
        )
        loader.stop()
        assert loader._timer is None

    def test_color_functions_applied(self) -> None:
        tui = MagicMock()

        def color_spinner(s: str) -> str:
            return f"<S>{s}</S>"

        def color_msg(s: str) -> str:
            return f"<M>{s}</M>"

        loader = Loader(
            tui=tui,
            spinner_color_fn=color_spinner,
            message_color_fn=color_msg,
            message="test",
        )
        try:
            lines = loader.render(80)
            content = " ".join(lines)
            assert "<S>" in content
            assert "<M>" in content
        finally:
            loader.stop()


# =========================================================================
# SelectList
# =========================================================================


class TestSelectList:
    def _make_items(self) -> list[SelectItem]:
        return [
            SelectItem(value="alpha", label="Alpha"),
            SelectItem(value="beta", label="Beta"),
            SelectItem(value="gamma", label="Gamma"),
            SelectItem(value="delta", label="Delta"),
        ]

    def test_construction(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        assert sl.get_selected_item() is not None
        assert sl.get_selected_item() == items[0]

    def test_get_selected_item_default_first(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        assert sl.get_selected_item() == items[0]

    def test_get_selected_item_empty_list(self) -> None:
        sl = SelectList(items=[], max_visible=10, theme=_make_theme())
        assert sl.get_selected_item() is None

    def test_navigate_down(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        sl.handle_input(KEY_DOWN)
        assert sl.get_selected_item() == items[1]

    def test_navigate_up(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        sl.handle_input(KEY_DOWN)
        sl.handle_input(KEY_DOWN)
        sl.handle_input(KEY_UP)
        assert sl.get_selected_item() == items[1]

    def test_navigate_wraps_down(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        # Move past last item -> should wrap to first
        for _ in range(len(items)):
            sl.handle_input(KEY_DOWN)
        assert sl.get_selected_item() == items[0]

    def test_navigate_wraps_up(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        # At index 0, pressing up wraps to last
        sl.handle_input(KEY_UP)
        assert sl.get_selected_item() == items[-1]

    def test_filter_narrows_items(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        sl.set_filter("al")
        assert sl.get_selected_item() is not None
        assert sl.get_selected_item().value == "alpha"  # type: ignore[union-attr]

    def test_filter_no_match(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        sl.set_filter("zzz")
        assert sl.get_selected_item() is None

    def test_filter_resets_selection(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        sl.handle_input(KEY_DOWN)
        sl.handle_input(KEY_DOWN)
        assert sl.get_selected_item() == items[2]
        sl.set_filter("b")
        # After filter, selection resets to 0
        assert sl.get_selected_item() is not None
        assert sl.get_selected_item().value == "beta"  # type: ignore[union-attr]

    def test_filter_case_insensitive(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        sl.set_filter("ALPHA")
        assert sl.get_selected_item() is not None
        assert sl.get_selected_item().value == "alpha"  # type: ignore[union-attr]

    def test_on_select_callback(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        selected: list[SelectItem] = []
        sl.on_select = lambda item: selected.append(item)
        sl.handle_input(KEY_ENTER)
        assert len(selected) == 1
        assert selected[0] == items[0]

    def test_on_cancel_callback(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        cancelled = []
        sl.on_cancel = lambda: cancelled.append(True)
        sl.handle_input(KEY_ESCAPE)
        assert len(cancelled) == 1

    def test_on_selection_change_callback(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        changes: list[SelectItem] = []
        sl.on_selection_change = lambda item: changes.append(item)
        sl.handle_input(KEY_DOWN)
        assert len(changes) == 1
        assert changes[0] == items[1]

    def test_render_shows_items(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "Alpha" in content
        assert "Beta" in content
        assert "Gamma" in content
        assert "Delta" in content

    def test_render_no_match_message(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        sl.set_filter("zzz")
        lines = sl.render(80)
        assert len(lines) == 1
        assert "No matching" in lines[0]

    def test_render_selected_has_arrow(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        lines = sl.render(80)
        # First item should have the arrow prefix
        assert "\u2192" in lines[0]

    def test_render_scroll_indicator(self) -> None:
        items = [SelectItem(value=f"item{i}", label=f"Item {i}") for i in range(20)]
        sl = SelectList(items=items, max_visible=5, theme=_make_theme())
        lines = sl.render(80)
        # Should have a scroll indicator line
        content = "\n".join(lines)
        assert "(1/20)" in content

    def test_set_selected_index(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        sl.set_selected_index(2)
        assert sl.get_selected_item() == items[2]

    def test_set_selected_index_clamped(self) -> None:
        items = self._make_items()
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        sl.set_selected_index(100)
        assert sl.get_selected_item() == items[-1]
        sl.set_selected_index(-5)
        assert sl.get_selected_item() == items[0]

    def test_item_with_description(self) -> None:
        items = [SelectItem(value="cmd", label="Command", description="A useful command")]
        sl = SelectList(items=items, max_visible=10, theme=_make_theme())
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "Command" in content
        # Description should appear for selected item at sufficient width
        assert "A useful command" in content
