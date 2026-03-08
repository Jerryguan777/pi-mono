"""Unit tests for pi_tui.tui module."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

from pi_tui.terminal import Terminal
from pi_tui.tui import (
    Container,
    Focusable,
    OverlayHandle,
    OverlayOptions,
    TUI,
    is_focusable,
)


# ---------------------------------------------------------------------------
# Mock Terminal
# ---------------------------------------------------------------------------


class MockTerminal:
    """Simple Terminal implementation for testing."""

    def __init__(self, columns: int = 80, rows: int = 24) -> None:
        self._columns = columns
        self._rows = rows
        self._cursor_visible = True
        self.written: list[str] = []

    def start(self, on_input: Callable[[str], None], on_resize: Callable[[], None]) -> None:
        pass

    def stop(self) -> None:
        pass

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


# ---------------------------------------------------------------------------
# Stub components
# ---------------------------------------------------------------------------


class StubComponent:
    """A simple component that renders fixed lines."""

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


class FocusableComponent(StubComponent):
    """A component that supports focus."""

    def __init__(self, lines: list[str] | None = None) -> None:
        super().__init__(lines)
        self.focused: bool = False


# ---------------------------------------------------------------------------
# Tests: MockTerminal satisfies Terminal protocol
# ---------------------------------------------------------------------------


class TestMockTerminal:
    def test_satisfies_terminal_protocol(self) -> None:
        """MockTerminal has all methods required by the Terminal protocol."""
        term = MockTerminal()
        # Terminal is not @runtime_checkable, so verify structurally
        assert hasattr(term, "start")
        assert hasattr(term, "stop")
        assert hasattr(term, "write")
        assert hasattr(term, "columns")
        assert hasattr(term, "rows")
        assert hasattr(term, "hide_cursor")
        assert hasattr(term, "show_cursor")

    def test_default_size(self) -> None:
        term = MockTerminal()
        assert term.columns == 80
        assert term.rows == 24

    def test_custom_size(self) -> None:
        term = MockTerminal(columns=120, rows=40)
        assert term.columns == 120
        assert term.rows == 40

    def test_write_records_output(self) -> None:
        term = MockTerminal()
        term.write("hello")
        term.write("world")
        assert term.written == ["hello", "world"]


# ---------------------------------------------------------------------------
# Tests: Container
# ---------------------------------------------------------------------------


class TestContainer:
    def test_add_child(self) -> None:
        container = Container()
        child = StubComponent(["line1"])
        container.add_child(child)
        assert child in container.children
        assert len(container.children) == 1

    def test_add_multiple_children(self) -> None:
        container = Container()
        c1 = StubComponent(["a"])
        c2 = StubComponent(["b"])
        container.add_child(c1)
        container.add_child(c2)
        assert len(container.children) == 2

    def test_remove_child(self) -> None:
        container = Container()
        child = StubComponent(["line1"])
        container.add_child(child)
        container.remove_child(child)
        assert child not in container.children
        assert len(container.children) == 0

    def test_remove_nonexistent_child_does_not_raise(self) -> None:
        container = Container()
        other = StubComponent()
        # Should not raise
        container.remove_child(other)

    def test_clear(self) -> None:
        container = Container()
        container.add_child(StubComponent(["a"]))
        container.add_child(StubComponent(["b"]))
        container.clear()
        assert len(container.children) == 0

    def test_render_empty(self) -> None:
        container = Container()
        assert container.render(80) == []

    def test_render_single_child(self) -> None:
        container = Container()
        container.add_child(StubComponent(["hello", "world"]))
        result = container.render(80)
        assert result == ["hello", "world"]

    def test_render_aggregates_children(self) -> None:
        container = Container()
        container.add_child(StubComponent(["line1"]))
        container.add_child(StubComponent(["line2", "line3"]))
        container.add_child(StubComponent(["line4"]))
        result = container.render(80)
        assert result == ["line1", "line2", "line3", "line4"]

    def test_invalidate_propagates_to_children(self) -> None:
        container = Container()
        c1 = StubComponent()
        c2 = StubComponent()
        container.add_child(c1)
        container.add_child(c2)
        container.invalidate()
        assert c1.invalidated
        assert c2.invalidated


# ---------------------------------------------------------------------------
# Tests: is_focusable
# ---------------------------------------------------------------------------


class TestIsFocusable:
    def test_focusable_component(self) -> None:
        comp = FocusableComponent()
        assert is_focusable(comp) is True

    def test_non_focusable_component(self) -> None:
        comp = StubComponent()
        assert is_focusable(comp) is False

    def test_none_is_not_focusable(self) -> None:
        assert is_focusable(None) is False

    def test_object_with_focused_attr_is_focusable(self) -> None:
        obj = MagicMock()
        obj.focused = False
        assert is_focusable(obj) is True

    def test_object_without_focused_attr(self) -> None:
        obj = MagicMock(spec=[])
        assert is_focusable(obj) is False


# ---------------------------------------------------------------------------
# Tests: OverlayOptions / OverlayHandle
# ---------------------------------------------------------------------------


class TestOverlayOptions:
    def test_default_values(self) -> None:
        opts = OverlayOptions()
        assert opts.width is None
        assert opts.min_width is None
        assert opts.max_height is None
        assert opts.anchor is None
        assert opts.offset_x is None
        assert opts.offset_y is None
        assert opts.row is None
        assert opts.col is None
        assert opts.margin is None
        assert opts.visible is None

    def test_custom_values(self) -> None:
        opts = OverlayOptions(
            width=60,
            anchor="top-left",
            offset_x=5,
            offset_y=2,
        )
        assert opts.width == 60
        assert opts.anchor == "top-left"
        assert opts.offset_x == 5
        assert opts.offset_y == 2

    def test_percentage_width(self) -> None:
        opts = OverlayOptions(width="50%")
        assert opts.width == "50%"

    def test_visible_callback(self) -> None:
        visible_fn = lambda cols, rows: cols > 40
        opts = OverlayOptions(visible=visible_fn)
        assert opts.visible is not None
        assert opts.visible(80, 24) is True
        assert opts.visible(30, 24) is False


# ---------------------------------------------------------------------------
# Tests: TUI construction
# ---------------------------------------------------------------------------


class TestTUIConstruction:
    def test_creates_with_mock_terminal(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        assert tui.terminal is term

    def test_inherits_container(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        assert isinstance(tui, Container)

    def test_show_hardware_cursor_override(self) -> None:
        term = MockTerminal()
        tui = TUI(term, show_hardware_cursor=True)
        assert tui.get_show_hardware_cursor() is True

        tui2 = TUI(term, show_hardware_cursor=False)
        assert tui2.get_show_hardware_cursor() is False

    def test_initial_overlay_stack_empty(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        assert tui.has_overlay() is False


# ---------------------------------------------------------------------------
# Tests: TUI.set_focus
# ---------------------------------------------------------------------------


class TestTUISetFocus:
    def test_set_focus_on_focusable(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent()
        tui.set_focus(comp)
        assert comp.focused is True

    def test_set_focus_clears_previous(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp1 = FocusableComponent()
        comp2 = FocusableComponent()
        tui.set_focus(comp1)
        assert comp1.focused is True
        tui.set_focus(comp2)
        assert comp1.focused is False
        assert comp2.focused is True

    def test_set_focus_none(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent()
        tui.set_focus(comp)
        tui.set_focus(None)
        assert comp.focused is False

    def test_set_focus_non_focusable_does_not_raise(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent()
        # Should not raise even though comp has no .focused
        tui.set_focus(comp)

    def test_set_focus_from_non_focusable_to_focusable(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        non_foc = StubComponent()
        foc = FocusableComponent()
        tui.set_focus(non_foc)
        tui.set_focus(foc)
        assert foc.focused is True


# ---------------------------------------------------------------------------
# Tests: TUI.show_overlay / hide_overlay
# ---------------------------------------------------------------------------


class TestTUIOverlay:
    def test_show_overlay_returns_handle(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["overlay content"])
        handle = tui.show_overlay(comp)
        # handle must satisfy OverlayHandle protocol
        assert hasattr(handle, "hide")
        assert hasattr(handle, "set_hidden")
        assert hasattr(handle, "is_hidden")

    def test_show_overlay_adds_to_stack(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent(["overlay"])
        tui.show_overlay(comp)
        assert tui.has_overlay() is True

    def test_show_overlay_focuses_component(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["overlay"])
        tui.show_overlay(comp)
        assert comp.focused is True

    def test_hide_overlay_removes_topmost(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent(["overlay"])
        tui.show_overlay(comp)
        tui.hide_overlay()
        assert tui.has_overlay() is False

    def test_hide_overlay_restores_previous_focus(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        main_comp = FocusableComponent(["main"])
        overlay_comp = FocusableComponent(["overlay"])

        tui.set_focus(main_comp)
        tui.show_overlay(overlay_comp)
        assert overlay_comp.focused is True
        assert main_comp.focused is False

        tui.hide_overlay()
        assert main_comp.focused is True

    def test_hide_overlay_no_overlays_does_nothing(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        # Should not raise
        tui.hide_overlay()

    def test_handle_hide_removes_overlay(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent(["overlay"])
        handle = tui.show_overlay(comp)
        handle.hide()
        assert tui.has_overlay() is False

    def test_handle_set_hidden_and_is_hidden(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["overlay"])
        handle = tui.show_overlay(comp)

        assert handle.is_hidden() is False
        handle.set_hidden(True)
        assert handle.is_hidden() is True
        handle.set_hidden(False)
        assert handle.is_hidden() is False

    def test_handle_set_hidden_unfocuses_overlay(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        main_comp = FocusableComponent(["main"])
        overlay_comp = FocusableComponent(["overlay"])
        tui.set_focus(main_comp)
        handle = tui.show_overlay(overlay_comp)
        assert overlay_comp.focused is True

        handle.set_hidden(True)
        # Focus should move back to main
        assert main_comp.focused is True

    def test_handle_set_hidden_false_refocuses_overlay(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        main_comp = FocusableComponent(["main"])
        overlay_comp = FocusableComponent(["overlay"])
        tui.set_focus(main_comp)
        handle = tui.show_overlay(overlay_comp)
        handle.set_hidden(True)
        handle.set_hidden(False)
        assert overlay_comp.focused is True

    def test_show_overlay_with_options(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = StubComponent(["overlay"])
        opts = OverlayOptions(width=40, anchor="top-left")
        handle = tui.show_overlay(comp, options=opts)
        assert tui.has_overlay() is True

    def test_multiple_overlays_stack(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp1 = FocusableComponent(["overlay1"])
        comp2 = FocusableComponent(["overlay2"])
        tui.show_overlay(comp1)
        tui.show_overlay(comp2)
        assert comp2.focused is True
        assert comp1.focused is False

        # Hiding topmost should focus next overlay
        tui.hide_overlay()
        assert comp1.focused is True
        assert tui.has_overlay() is True

        tui.hide_overlay()
        assert tui.has_overlay() is False

    def test_overlay_with_visible_callback_false(self) -> None:
        term = MockTerminal()
        tui = TUI(term)
        comp = FocusableComponent(["overlay"])
        opts = OverlayOptions(visible=lambda cols, rows: False)
        tui.show_overlay(comp, options=opts)
        # Overlay exists but is not visible
        assert tui.has_overlay() is False
        # Component should not be focused since overlay is not visible
        assert comp.focused is False
