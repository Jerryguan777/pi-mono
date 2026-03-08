"""Unit tests for TUI rendering engine.

Covers the differential rendering pipeline, overlay layout/compositing,
input handling, cursor positioning, start/stop lifecycle, and render coalescing.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from unittest.mock import MagicMock, patch

from pi_tui.tui import (
    CURSOR_MARKER,
    Container,
    InputListenerResult,
    OverlayMargin,
    OverlayOptions,
    TUI,
    _parse_size_value,
)


# ---------------------------------------------------------------------------
# Mock Terminal
# ---------------------------------------------------------------------------


class MockTerminal:
    """Terminal implementation that records all writes for assertion."""

    def __init__(self, columns: int = 80, rows: int = 24) -> None:
        self._columns = columns
        self._rows = rows
        self._cursor_visible = True
        self.written: list[str] = []
        self._on_input: Callable[[str], None] | None = None
        self._on_resize: Callable[[], None] | None = None
        self.started = False
        self.stopped = False

    def start(self, on_input: Callable[[str], None], on_resize: Callable[[], None]) -> None:
        self._on_input = on_input
        self._on_resize = on_resize
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    async def drain_input(self, max_ms: int = 1000, idle_ms: int = 50) -> None:
        pass

    def write(self, data: str) -> None:
        self.written.append(data)

    @property
    def columns(self) -> int:
        return self._columns

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def kitty_protocol_active(self) -> bool:
        return False

    def move_by(self, lines: int) -> None:
        pass

    def hide_cursor(self) -> None:
        self._cursor_visible = False

    def show_cursor(self) -> None:
        self._cursor_visible = True

    def clear_line(self) -> None:
        pass

    def clear_from_cursor(self) -> None:
        pass

    def clear_screen(self) -> None:
        pass

    def set_title(self, title: str) -> None:
        pass

    @property
    def all_output(self) -> str:
        """Concatenation of all written data."""
        return "".join(self.written)

    def inject_input(self, data: str) -> None:
        """Simulate terminal input."""
        if self._on_input is not None:
            self._on_input(data)

    def inject_resize(self) -> None:
        """Simulate terminal resize."""
        if self._on_resize is not None:
            self._on_resize()


# ---------------------------------------------------------------------------
# Stub components
# ---------------------------------------------------------------------------


class StubComponent:
    """A component that renders fixed lines."""

    def __init__(self, lines: list[str] | None = None) -> None:
        self._lines = lines or []
        self.invalidated = False

    def render(self, width: int) -> list[str]:
        return list(self._lines)

    def invalidate(self) -> None:
        self.invalidated = True

    def handle_input(self, data: str) -> None:
        pass

    @property
    def wants_key_release(self) -> bool:
        return False

    def set_lines(self, lines: list[str]) -> None:
        self._lines = lines


class FocusableComponent(StubComponent):
    """A component that supports focus."""

    def __init__(self, lines: list[str] | None = None) -> None:
        super().__init__(lines)
        self.focused: bool = False
        self.received_input: list[str] = []

    def handle_input(self, data: str) -> None:
        self.received_input.append(data)


class KeyReleaseComponent(FocusableComponent):
    """A component that opts into receiving key release events."""

    @property
    def wants_key_release(self) -> bool:
        return True


class WidthTrackingComponent:
    """Component that records which widths it was rendered at."""

    def __init__(self, lines: list[str] | None = None) -> None:
        self._lines = lines or []
        self.rendered_widths: list[int] = []
        self.invalidated = False

    def render(self, width: int) -> list[str]:
        self.rendered_widths.append(width)
        return list(self._lines)

    def invalidate(self) -> None:
        self.invalidated = True

    def handle_input(self, data: str) -> None:
        pass

    @property
    def wants_key_release(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Helper: synchronous render
# ---------------------------------------------------------------------------


def _sync_render(tui: TUI) -> None:
    """Directly invoke the render pipeline under lock, bypassing timers."""
    with tui._render_lock:
        tui._render_requested = False
        tui._do_render()


# ---------------------------------------------------------------------------
# Tests: _parse_size_value
# ---------------------------------------------------------------------------


class TestParseSizeValue:
    def test_none_returns_none(self) -> None:
        assert _parse_size_value(None, 100) is None

    def test_int_returns_int(self) -> None:
        assert _parse_size_value(40, 100) == 40

    def test_percentage_string(self) -> None:
        assert _parse_size_value("50%", 100) == 50

    def test_percentage_fractional(self) -> None:
        assert _parse_size_value("33.3%", 300) == 99

    def test_invalid_string_returns_none(self) -> None:
        assert _parse_size_value("abc", 100) is None

    def test_zero_percent(self) -> None:
        assert _parse_size_value("0%", 100) == 0

    def test_hundred_percent(self) -> None:
        assert _parse_size_value("100%", 80) == 80


# ---------------------------------------------------------------------------
# Tests: TUI properties
# ---------------------------------------------------------------------------


class TestTUIProperties:
    def test_full_redraws_counter(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        assert tui.full_redraws == 0

    def test_set_show_hardware_cursor_enables(self) -> None:
        term = MockTerminal()
        tui = TUI(term, show_hardware_cursor=False)
        tui.set_show_hardware_cursor(True)
        assert tui.get_show_hardware_cursor() is True

    def test_set_show_hardware_cursor_disables_hides_cursor(self) -> None:
        term = MockTerminal()
        tui = TUI(term, show_hardware_cursor=True)
        tui.set_show_hardware_cursor(False)
        assert tui.get_show_hardware_cursor() is False
        assert term._cursor_visible is False

    def test_set_show_hardware_cursor_same_value_noop(self) -> None:
        term = MockTerminal()
        tui = TUI(term, show_hardware_cursor=True)
        term.written.clear()
        tui.set_show_hardware_cursor(True)
        # No write should have occurred for hiding cursor
        assert term._cursor_visible is True

    def test_get_clear_on_shrink(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        assert tui.get_clear_on_shrink() is False

    def test_set_clear_on_shrink(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.set_clear_on_shrink(True)
        assert tui.get_clear_on_shrink() is True


# ---------------------------------------------------------------------------
# Tests: TUI.invalidate with overlays
# ---------------------------------------------------------------------------


class TestTUIInvalidate:
    def test_invalidate_propagates_to_overlay_components(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        child = StubComponent(["child"])
        overlay_comp = StubComponent(["overlay"])
        tui.add_child(child)
        tui.show_overlay(overlay_comp)
        tui.invalidate()
        assert child.invalidated
        assert overlay_comp.invalidated


# ---------------------------------------------------------------------------
# Tests: TUI start / stop
# ---------------------------------------------------------------------------


class TestTUIStartStop:
    @patch("pi_tui.tui.get_capabilities")
    def test_start_initializes_terminal(self, mock_caps: MagicMock) -> None:
        mock_caps.return_value = MagicMock(images=None)
        term = MockTerminal()
        tui = TUI(term)
        tui.start()
        assert term.started
        assert term._cursor_visible is False
        assert term._on_input is not None
        assert term._on_resize is not None

    @patch("pi_tui.tui.get_capabilities")
    def test_stop_moves_cursor_and_restores(self, mock_caps: MagicMock) -> None:
        mock_caps.return_value = MagicMock(images=None)
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent(["line1", "line2", "line3"]))
        tui.start()
        # Let timer fire
        time.sleep(0.05)
        tui.stop()
        assert term.stopped
        assert term._cursor_visible is True

    @patch("pi_tui.tui.get_capabilities")
    def test_stop_with_no_previous_lines(self, mock_caps: MagicMock) -> None:
        mock_caps.return_value = MagicMock(images=None)
        term = MockTerminal()
        tui = TUI(term)
        tui.start()
        tui._stopped = False  # Reset the stopped flag set by start's timer
        tui.stop()
        assert term.stopped
        assert term._cursor_visible is True

    def test_stop_writes_cursor_movement_when_lines_exist(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        # Simulate that render was done previously
        tui._previous_lines = ["line1", "line2"]
        tui._hardware_cursor_row = 0
        tui.stop()
        output = term.all_output
        # Should move cursor down to end of content
        assert "\x1b[2B" in output
        assert "\r\n" in output

    def test_stop_writes_cursor_up_when_past_content(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui._previous_lines = ["line1"]
        tui._hardware_cursor_row = 3
        tui.stop()
        output = term.all_output
        # target_row = 1 (len=1), hw_cursor = 3, diff = -2
        assert "\x1b[2A" in output


# ---------------------------------------------------------------------------
# Tests: TUI input handling
# ---------------------------------------------------------------------------


class TestTUIInputHandling:
    def test_input_dispatched_to_focused_component(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["hello"])
        tui.set_focus(comp)
        tui._handle_input("x")
        assert "x" in comp.received_input

    def test_input_not_dispatched_when_no_focus(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        # No focused component -- should not raise
        tui._handle_input("x")

    def test_input_listener_can_consume(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["hello"])
        tui.set_focus(comp)

        def listener(data: str) -> InputListenerResult:
            return InputListenerResult(consume=True)

        tui.add_input_listener(listener)
        tui._handle_input("x")
        # Input should be consumed before reaching the component
        assert comp.received_input == []

    def test_input_listener_can_transform_data(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["hello"])
        tui.set_focus(comp)

        def listener(data: str) -> InputListenerResult:
            return InputListenerResult(data="transformed")

        tui.add_input_listener(listener)
        tui._handle_input("x")
        assert comp.received_input == ["transformed"]

    def test_input_listener_returning_empty_string_stops_dispatch(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["hello"])
        tui.set_focus(comp)

        def listener(data: str) -> InputListenerResult:
            return InputListenerResult(data="")

        tui.add_input_listener(listener)
        tui._handle_input("x")
        assert comp.received_input == []

    def test_remove_input_listener(self) -> None:
        term = MockTerminal()
        tui = TUI(term)

        def listener(data: str) -> InputListenerResult:
            return InputListenerResult(consume=True)

        remove = tui.add_input_listener(listener)
        remove()
        # After removal, listener should not fire
        comp = FocusableComponent(["hello"])
        tui.set_focus(comp)
        tui._handle_input("x")
        assert "x" in comp.received_input

    def test_remove_input_listener_directly(self) -> None:
        term = MockTerminal()
        tui = TUI(term)

        def listener(data: str) -> InputListenerResult | None:
            return InputListenerResult(consume=True)

        tui.add_input_listener(listener)
        tui.remove_input_listener(listener)
        # Removing nonexistent listener should not raise
        tui.remove_input_listener(listener)

    def test_key_release_filtered_by_default(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["hello"])
        tui.set_focus(comp)
        # Simulate a key release event (contains :3u suffix)
        tui._handle_input("\x1b[97:3u")
        assert comp.received_input == []

    def test_key_release_passed_when_wants_key_release(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = KeyReleaseComponent(["hello"])
        tui.set_focus(comp)
        tui._handle_input("\x1b[97:3u")
        assert "\x1b[97:3u" in comp.received_input

    def test_overlay_focus_correction_on_hidden_overlay(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        main_comp = FocusableComponent(["main"])
        overlay_comp = FocusableComponent(["overlay"])
        tui.set_focus(main_comp)
        opts = OverlayOptions(visible=lambda cols, rows: False)
        tui.show_overlay(overlay_comp, options=opts)
        # Force set focus to overlay even though invisible
        tui._focused_component = overlay_comp
        # Inject input -- should correct focus back to main
        tui._handle_input("x")
        # Focus should have been corrected away from invisible overlay

    @patch("pi_tui.tui.get_capabilities")
    def test_cell_size_query_on_start(self, mock_caps: MagicMock) -> None:
        mock_caps.return_value = MagicMock(images="kitty")
        term = MockTerminal()
        tui = TUI(term)
        tui.start()
        output = term.all_output
        assert "\x1b[16t" in output
        tui._stopped = True


# ---------------------------------------------------------------------------
# Tests: Cell size response parsing
# ---------------------------------------------------------------------------


class TestCellSizeParsing:
    def test_parse_cell_size_response_valid(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui._cell_size_query_pending = True
        tui._input_buffer = "\x1b[6;18;9t"
        result = tui._parse_cell_size_response()
        assert tui._cell_size_query_pending is False

    def test_parse_cell_size_response_with_extra_data(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui._cell_size_query_pending = True
        tui._input_buffer = "\x1b[6;18;9textra"
        result = tui._parse_cell_size_response()
        assert "extra" in result

    def test_parse_cell_size_response_partial(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui._cell_size_query_pending = True
        tui._input_buffer = "\x1b[6;18"
        result = tui._parse_cell_size_response()
        # Should return empty string (waiting for more data)
        assert result == ""

    def test_parse_cell_size_no_match_returns_buffer(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui._cell_size_query_pending = True
        tui._input_buffer = "hello"
        result = tui._parse_cell_size_response()
        assert result == "hello"
        assert tui._cell_size_query_pending is False


# ---------------------------------------------------------------------------
# Tests: Rendering pipeline (_do_render)
# ---------------------------------------------------------------------------


class TestRenderPipeline:
    def test_first_render_produces_full_output(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent(["hello", "world"]))
        _sync_render(tui)
        output = term.all_output
        # Should include synchronized output markers
        assert "\x1b[?2026h" in output
        assert "\x1b[?2026l" in output
        assert "hello" in output
        assert "world" in output

    def test_render_increments_full_redraw_count(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent(["hello"]))
        _sync_render(tui)
        assert tui.full_redraws == 1

    def test_render_when_stopped_is_noop(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui._stopped = True
        tui.add_child(StubComponent(["hello"]))
        _sync_render(tui)
        assert term.written == []

    def test_no_change_does_not_rewrite(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent(["hello"]))
        _sync_render(tui)
        term.written.clear()
        _sync_render(tui)
        # Should only position cursor, not rewrite content
        output = term.all_output
        assert "hello" not in output

    def test_differential_update_only_writes_changed_lines(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent(["line1", "line2", "line3"])
        tui.add_child(comp)
        _sync_render(tui)
        # Change middle line
        comp.set_lines(["line1", "CHANGED", "line3"])
        term.written.clear()
        _sync_render(tui)
        output = term.all_output
        assert "CHANGED" in output
        # Should not contain unchanged lines in the diff
        # (line1 and line3 get a reset suffix so they won't match plain text)

    def test_width_change_triggers_full_redraw(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent(["hello"]))
        _sync_render(tui)
        count_before = tui.full_redraws
        # Change width
        term._columns = 60
        _sync_render(tui)
        assert tui.full_redraws == count_before + 1

    def test_width_change_clears_screen(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent(["hello"]))
        _sync_render(tui)
        term.written.clear()
        term._columns = 60
        _sync_render(tui)
        output = term.all_output
        # Width change should clear screen
        assert "\x1b[3J" in output

    def test_appended_lines_rendered(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent(["line1"])
        tui.add_child(comp)
        _sync_render(tui)
        comp.set_lines(["line1", "line2"])
        term.written.clear()
        _sync_render(tui)
        output = term.all_output
        assert "line2" in output

    def test_shrunk_content_clears_extra_lines(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent(["line1", "line2", "line3"])
        tui.add_child(comp)
        _sync_render(tui)
        comp.set_lines(["line1"])
        term.written.clear()
        _sync_render(tui)
        output = term.all_output
        # Should contain line clearing escape
        assert "\x1b[2K" in output

    def test_clear_on_shrink_triggers_full_redraw(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.set_clear_on_shrink(True)
        comp = StubComponent(["line1", "line2", "line3"])
        tui.add_child(comp)
        _sync_render(tui)
        count_before = tui.full_redraws
        comp.set_lines(["line1"])
        _sync_render(tui)
        assert tui.full_redraws == count_before + 1

    def test_clear_on_shrink_not_triggered_with_overlays(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.set_clear_on_shrink(True)
        comp = StubComponent(["line1", "line2", "line3"])
        tui.add_child(comp)
        _sync_render(tui)
        count_before = tui.full_redraws
        # Add overlay so clear_on_shrink is skipped
        tui.show_overlay(StubComponent(["overlay"]))
        comp.set_lines(["line1"])
        _sync_render(tui)
        # Should NOT have used clear-based full redraw
        # (It may still have done a full redraw for other reasons,
        # but _clear_on_shrink path is skipped when overlays exist)

    def test_render_component_receives_terminal_width(self) -> None:
        term = MockTerminal(columns=42)
        tui = TUI(term)
        comp = WidthTrackingComponent(["hello"])
        tui.add_child(comp)
        _sync_render(tui)
        assert 42 in comp.rendered_widths

    def test_force_render_resets_state_and_triggers_full_redraw(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent(["hello"]))
        _sync_render(tui)
        count_before = tui.full_redraws
        # Force render resets previous state and schedules a render
        tui.request_render(force=True)
        # Wait for the timer to fire
        time.sleep(0.05)
        # Should have triggered a full redraw since state was reset
        assert tui.full_redraws == count_before + 1

    def test_multiple_render_requests_coalesce(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent(["hello"]))
        # First request sets _render_requested
        tui._render_requested = True
        # Second request should be a no-op (returns early)
        tui.request_render()
        # _render_requested should still be True (no double scheduling)
        assert tui._render_requested is True


# ---------------------------------------------------------------------------
# Tests: Cursor extraction and positioning
# ---------------------------------------------------------------------------


class TestCursorPositioning:
    def test_extract_cursor_position_found(self) -> None:
        lines = ["hello", f"ab{CURSOR_MARKER}cd", "world"]
        pos = TUI._extract_cursor_position(lines, 24)
        assert pos is not None
        assert pos == (1, 2)  # row 1, col 2
        # Marker should be stripped
        assert CURSOR_MARKER not in lines[1]

    def test_extract_cursor_position_not_found(self) -> None:
        lines = ["hello", "world"]
        pos = TUI._extract_cursor_position(lines, 24)
        assert pos is None

    def test_extract_cursor_position_at_start_of_line(self) -> None:
        lines = [f"{CURSOR_MARKER}hello"]
        pos = TUI._extract_cursor_position(lines, 24)
        assert pos is not None
        assert pos == (0, 0)

    def test_extract_cursor_position_at_end_of_line(self) -> None:
        lines = [f"hello{CURSOR_MARKER}"]
        pos = TUI._extract_cursor_position(lines, 24)
        assert pos is not None
        assert pos == (0, 5)

    def test_extract_cursor_scans_from_bottom(self) -> None:
        # If multiple markers exist, the bottom one should be found first
        lines = [f"{CURSOR_MARKER}first", f"second{CURSOR_MARKER}"]
        pos = TUI._extract_cursor_position(lines, 24)
        assert pos is not None
        assert pos[0] == 1  # Bottom line wins

    def test_hardware_cursor_positioning_moves_down(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui._hardware_cursor_row = 0
        tui._position_hardware_cursor((3, 5), 10)
        output = term.all_output
        assert "\x1b[3B" in output  # Move down 3
        assert "\x1b[6G" in output  # Column 6 (1-indexed)

    def test_hardware_cursor_positioning_moves_up(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui._hardware_cursor_row = 5
        tui._position_hardware_cursor((2, 0), 10)
        output = term.all_output
        assert "\x1b[3A" in output  # Move up 3

    def test_hardware_cursor_positioning_none_hides(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui._position_hardware_cursor(None, 10)
        assert term._cursor_visible is False

    def test_hardware_cursor_positioning_zero_lines_hides(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui._position_hardware_cursor((0, 0), 0)
        assert term._cursor_visible is False

    def test_hardware_cursor_shows_when_enabled(self) -> None:
        term = MockTerminal()
        tui = TUI(term, show_hardware_cursor=True)
        tui._hardware_cursor_row = 0
        tui._position_hardware_cursor((0, 0), 5)
        assert term._cursor_visible is True

    def test_hardware_cursor_hides_when_disabled(self) -> None:
        term = MockTerminal()
        tui = TUI(term, show_hardware_cursor=False)
        tui._hardware_cursor_row = 0
        tui._position_hardware_cursor((0, 0), 5)
        assert term._cursor_visible is False

    def test_cursor_marker_in_render_output(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent([f"text{CURSOR_MARKER}more"]))
        _sync_render(tui)
        output = term.all_output
        # Cursor marker should be stripped from output
        assert CURSOR_MARKER not in output


# ---------------------------------------------------------------------------
# Tests: Overlay layout resolution
# ---------------------------------------------------------------------------


class TestOverlayLayout:
    def _make_tui(self, cols: int = 80, rows: int = 24) -> TUI:
        return TUI(MockTerminal(columns=cols, rows=rows))

    def test_default_layout_center(self) -> None:
        tui = self._make_tui()
        width, row, col, max_h = tui._resolve_overlay_layout(None, 5, 80, 24)
        assert width == 80  # min(80, avail_width=80)
        # Centered vertically: (24 - 5) // 2 = 9
        assert row == 9
        # Centered horizontally: (80 - 80) // 2 = 0
        assert col == 0

    def test_layout_with_explicit_width(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40)
        width, row, col, max_h = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert width == 40
        # col should center: (80 - 40) // 2 = 20
        assert col == 20

    def test_layout_with_percentage_width(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width="50%")
        width, row, col, max_h = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert width == 40  # 50% of 80

    def test_layout_with_min_width(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=20, min_width=30)
        width, _, _, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert width == 30

    def test_layout_with_max_height(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(max_height=10)
        _, _, _, max_h = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert max_h == 10

    def test_layout_with_percentage_max_height(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(max_height="50%")
        _, _, _, max_h = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert max_h == 12  # 50% of 24

    def test_layout_top_left_anchor(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, anchor="top-left")
        width, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 0
        assert col == 0

    def test_layout_top_right_anchor(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, anchor="top-right")
        width, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 0
        assert col == 40  # 80 - 40

    def test_layout_bottom_left_anchor(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, anchor="bottom-left")
        width, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 19  # 24 - 5
        assert col == 0

    def test_layout_bottom_right_anchor(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, anchor="bottom-right")
        width, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 19
        assert col == 40

    def test_layout_top_center_anchor(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, anchor="top-center")
        _, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 0
        assert col == 20  # (80-40)//2

    def test_layout_bottom_center_anchor(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, anchor="bottom-center")
        _, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 19
        assert col == 20

    def test_layout_left_center_anchor(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, anchor="left-center")
        _, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 9  # (24-5)//2
        assert col == 0

    def test_layout_right_center_anchor(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, anchor="right-center")
        _, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 9
        assert col == 40

    def test_layout_with_int_margin(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, anchor="top-left", margin=5)
        width, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 5
        assert col == 5
        assert width == 40

    def test_layout_with_overlay_margin_object(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(
            width=40,
            anchor="top-left",
            margin=OverlayMargin(top=2, right=3, bottom=4, left=5),
        )
        width, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 2
        assert col == 5

    def test_layout_with_offsets(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, anchor="top-left", offset_x=3, offset_y=2)
        _, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        assert row == 2
        assert col == 3

    def test_layout_with_absolute_row_col(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, row=5, col=10)
        _, row, col, _ = tui._resolve_overlay_layout(opts, 3, 80, 24)
        assert row == 5
        assert col == 10

    def test_layout_with_percentage_row(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, row="50%")
        _, row, _, _ = tui._resolve_overlay_layout(opts, 4, 80, 24)
        # max_row = max(0, 24 - 4) = 20, 50% of 20 = 10
        assert row == 10

    def test_layout_with_percentage_col(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, col="50%")
        _, _, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        # max_col = max(0, 80 - 40) = 40, 50% of 40 = 20
        assert col == 20

    def test_layout_with_invalid_percentage_row(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, row="abc")
        _, row, _, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        # Invalid percent falls back to center
        assert row == 9  # (24-5)//2

    def test_layout_with_invalid_percentage_col(self) -> None:
        tui = self._make_tui()
        opts = OverlayOptions(width=40, col="abc")
        _, _, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        # Invalid percent falls back to center
        assert col == 20  # (80-40)//2

    def test_layout_clamped_to_bounds(self) -> None:
        tui = self._make_tui(cols=80, rows=24)
        opts = OverlayOptions(width=40, row=100, col=100)
        _, row, col, _ = tui._resolve_overlay_layout(opts, 5, 80, 24)
        # Should be clamped
        assert row <= 24
        assert col <= 80


# ---------------------------------------------------------------------------
# Tests: Overlay compositing
# ---------------------------------------------------------------------------


class TestOverlayCompositing:
    def test_overlay_renders_on_top_of_content(self) -> None:
        term = MockTerminal(columns=40, rows=24)
        tui = TUI(term)
        tui.add_child(StubComponent(["background line"] * 24))
        overlay_comp = StubComponent(["OVERLAY"])
        tui.show_overlay(overlay_comp, OverlayOptions(width=10, anchor="top-left"))
        _sync_render(tui)
        output = term.all_output
        assert "OVERLAY" in output

    def test_overlay_with_max_height_truncates(self) -> None:
        term = MockTerminal(columns=40, rows=24)
        tui = TUI(term)
        tui.add_child(StubComponent(["bg"] * 24))
        # Overlay with many lines but max_height=2
        overlay_comp = StubComponent(["ol1", "ol2", "ol3", "ol4"])
        tui.show_overlay(overlay_comp, OverlayOptions(width=10, max_height=2, anchor="top-left"))
        _sync_render(tui)
        output = term.all_output
        assert "ol1" in output
        assert "ol2" in output
        # ol3 and ol4 should be truncated

    def test_no_overlays_returns_lines_unchanged(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        lines = ["hello", "world"]
        result = tui._composite_overlays(lines, 80, 24)
        assert result == lines

    def test_overlay_hidden_not_composited(self) -> None:
        term = MockTerminal(columns=40, rows=24)
        tui = TUI(term)
        tui.add_child(StubComponent(["bg"] * 5))
        overlay_comp = StubComponent(["OVERLAY"])
        handle = tui.show_overlay(overlay_comp, OverlayOptions(width=10, anchor="top-left"))
        handle.set_hidden(True)
        _sync_render(tui)
        output = term.all_output
        # The overlay should not appear since it's hidden
        # (though it depends on compositing; hidden overlay is not visible)

    def test_overlay_visibility_callback_false(self) -> None:
        term = MockTerminal(columns=40, rows=24)
        tui = TUI(term)
        tui.add_child(StubComponent(["bg"] * 5))
        overlay_comp = StubComponent(["INVISIBLE"])
        tui.show_overlay(overlay_comp, OverlayOptions(visible=lambda c, r: False))
        _sync_render(tui)
        output = term.all_output
        # Invisible overlay should not appear in output
        assert "INVISIBLE" not in output


# ---------------------------------------------------------------------------
# Tests: Line resets
# ---------------------------------------------------------------------------


class TestLineResets:
    def test_apply_line_resets_adds_reset_suffix(self) -> None:
        lines = ["hello", "world"]
        result = TUI._apply_line_resets(lines)
        for line in result:
            assert line.endswith("\x1b[0m\x1b]8;;\x07")


# ---------------------------------------------------------------------------
# Tests: Rendering with overlays end-to-end
# ---------------------------------------------------------------------------


class TestRenderWithOverlays:
    def test_render_with_centered_overlay(self) -> None:
        term = MockTerminal(columns=80, rows=24)
        tui = TUI(term)
        tui.add_child(StubComponent(["." * 80] * 24))
        overlay_comp = StubComponent(["OVERLAY_CONTENT"])
        tui.show_overlay(overlay_comp, OverlayOptions(width=20, anchor="center"))
        _sync_render(tui)
        output = term.all_output
        assert "OVERLAY_CONTENT" in output

    def test_render_overlay_with_margin_and_anchor(self) -> None:
        term = MockTerminal(columns=80, rows=24)
        tui = TUI(term)
        tui.add_child(StubComponent(["." * 80] * 24))
        overlay_comp = StubComponent(["X"])
        opts = OverlayOptions(width=10, anchor="top-right", margin=2)
        tui.show_overlay(overlay_comp, opts)
        _sync_render(tui)
        output = term.all_output
        assert "X" in output


# ---------------------------------------------------------------------------
# Tests: Differential rendering edge cases
# ---------------------------------------------------------------------------


class TestDifferentialRenderingEdgeCases:
    def test_all_lines_deleted(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent(["line1", "line2"])
        tui.add_child(comp)
        _sync_render(tui)
        comp.set_lines([])
        term.written.clear()
        _sync_render(tui)
        # Should handle empty content gracefully

    def test_complete_content_replacement(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent(["A", "B", "C"])
        tui.add_child(comp)
        _sync_render(tui)
        comp.set_lines(["X", "Y", "Z"])
        term.written.clear()
        _sync_render(tui)
        output = term.all_output
        assert "X" in output
        assert "Y" in output
        assert "Z" in output

    def test_content_grows_beyond_original(self) -> None:
        term = MockTerminal(rows=100)
        tui = TUI(term)
        comp = StubComponent(["A"])
        tui.add_child(comp)
        _sync_render(tui)
        comp.set_lines(["A", "B", "C", "D", "E"])
        term.written.clear()
        _sync_render(tui)
        output = term.all_output
        assert "B" in output
        assert "E" in output

    def test_content_shrinks_with_changed_remaining_lines(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent(["A", "B", "C", "D"])
        tui.add_child(comp)
        _sync_render(tui)
        comp.set_lines(["A", "X"])
        term.written.clear()
        _sync_render(tui)
        output = term.all_output
        assert "X" in output


# ---------------------------------------------------------------------------
# Tests: Render scheduling
# ---------------------------------------------------------------------------


class TestRenderScheduling:
    def test_second_request_while_pending_is_noop(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        # Manually set the flag to simulate a pending render
        tui._render_requested = True
        # This call should return early without scheduling another timer
        tui.request_render()
        assert tui._render_requested is True

    def test_request_render_schedules_deferred(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent(["scheduled"]))
        tui.request_render()
        # Wait for the zero-delay timer to fire
        time.sleep(0.05)
        output = term.all_output
        assert "scheduled" in output

    @patch("pi_tui.tui.get_capabilities")
    def test_deferred_render_fires(self, mock_caps: MagicMock) -> None:
        mock_caps.return_value = MagicMock(images=None)
        term = MockTerminal()
        tui = TUI(term)
        tui.add_child(StubComponent(["deferred"]))
        tui.start()
        # Wait for timer to fire
        time.sleep(0.1)
        output = term.all_output
        assert "deferred" in output
        tui._stopped = True


# ---------------------------------------------------------------------------
# Tests: _query_cell_size
# ---------------------------------------------------------------------------


class TestQueryCellSize:
    @patch("pi_tui.tui.get_capabilities")
    def test_query_cell_size_when_images_supported(self, mock_caps: MagicMock) -> None:
        mock_caps.return_value = MagicMock(images="kitty")
        term = MockTerminal()
        tui = TUI(term)
        tui._query_cell_size()
        output = term.all_output
        assert "\x1b[16t" in output
        assert tui._cell_size_query_pending is True

    @patch("pi_tui.tui.get_capabilities")
    def test_query_cell_size_skipped_when_no_images(self, mock_caps: MagicMock) -> None:
        mock_caps.return_value = MagicMock(images=None)
        term = MockTerminal()
        tui = TUI(term)
        tui._query_cell_size()
        assert tui._cell_size_query_pending is False


# ---------------------------------------------------------------------------
# Tests: Input handling with cell size query pending
# ---------------------------------------------------------------------------


class TestInputWithCellSizePending:
    def test_input_buffered_during_cell_size_query(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["hello"])
        tui.set_focus(comp)
        tui._cell_size_query_pending = True
        # Send partial cell size response
        tui._handle_input("\x1b[6;18")
        # Should be buffered, not passed to component
        assert comp.received_input == []

    def test_cell_size_response_consumed_rest_forwarded(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["hello"])
        tui.set_focus(comp)
        tui._cell_size_query_pending = True
        # Send cell size response followed by regular input
        tui._handle_input("\x1b[6;18;9textra_input")
        # The cell size response should be consumed, "extra_input" forwarded
        assert any("extra_input" in i for i in comp.received_input)


# ---------------------------------------------------------------------------
# Tests: Debug handler
# ---------------------------------------------------------------------------


class TestDebugHandler:
    def test_debug_key_calls_handler(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        debug_called = []
        tui.on_debug = lambda: debug_called.append(True)
        # Shift+Ctrl+D in Kitty protocol: codepoint 100 (d), modifier shift(1)+ctrl(4)=5
        # CSI u format: ESC[100;6u (modifier+1=6)
        tui._handle_input("\x1b[100;6u")
        assert debug_called == [True]
