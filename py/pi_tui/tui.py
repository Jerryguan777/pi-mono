"""Minimal TUI implementation with differential rendering.

Port of tui.ts. Provides Component/Focusable protocols, Container,
overlay system, and the main TUI class with a differential rendering engine.
"""

from __future__ import annotations

import contextlib
import math
import os
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from pi_tui.keys import is_key_release, matches_key
from pi_tui.terminal import Terminal
from pi_tui.terminal_image import CellDimensions, get_capabilities, is_image_line, set_cell_dimensions
from pi_tui.utils import extract_segments, slice_by_column, slice_with_width, visible_width

# ---------------------------------------------------------------------------
# Component protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Component(Protocol):
    """All TUI components must implement this protocol."""

    def render(self, width: int) -> list[str]:
        """Render the component to lines for the given viewport width."""
        ...

    def invalidate(self) -> None:
        """Invalidate any cached rendering state."""
        ...

    def handle_input(self, data: str) -> None:
        """Optional handler for keyboard input when component has focus."""
        ...

    @property
    def wants_key_release(self) -> bool:
        """If True, component receives key release events (Kitty protocol).
        Default is False - release events are filtered out.
        """
        ...


# ---------------------------------------------------------------------------
# Input listener types
# ---------------------------------------------------------------------------


class InputListenerResult:
    """Result from an input listener."""

    __slots__ = ("consume", "data")

    def __init__(self, *, consume: bool = False, data: str | None = None) -> None:
        self.consume = consume
        self.data = data


InputListener = Callable[[str], InputListenerResult | None]


# ---------------------------------------------------------------------------
# Focusable protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Focusable(Protocol):
    """Interface for components that can receive focus and display a hardware cursor."""

    focused: bool


def is_focusable(component: Any) -> bool:
    """Type guard to check if a component implements Focusable."""
    return component is not None and hasattr(component, "focused")


# ---------------------------------------------------------------------------
# Cursor marker
# ---------------------------------------------------------------------------

CURSOR_MARKER = "\x1b_pi:c\x07"
"""Zero-width APC sequence for cursor positioning.
Components emit this at the cursor position when focused.
TUI finds and strips this marker, then positions the hardware cursor there.
"""


# ---------------------------------------------------------------------------
# Re-export visible_width
# ---------------------------------------------------------------------------

# visible_width is already imported above; re-export for consumers
__all__ = [
    "CURSOR_MARKER",
    "TUI",
    "Component",
    "Container",
    "Focusable",
    "InputListener",
    "InputListenerResult",
    "OverlayAnchor",
    "OverlayHandle",
    "OverlayMargin",
    "OverlayOptions",
    "SizeValue",
    "is_focusable",
    "visible_width",
]


# ---------------------------------------------------------------------------
# Overlay types
# ---------------------------------------------------------------------------

OverlayAnchor = Literal[
    "center",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "top-center",
    "bottom-center",
    "left-center",
    "right-center",
]

SizeValue = int | str
"""A size value: absolute int or percentage string like ``"50%"``."""


@dataclass
class OverlayMargin:
    """Margin configuration for overlays."""

    top: int | None = None
    right: int | None = None
    bottom: int | None = None
    left: int | None = None


@dataclass
class OverlayOptions:
    """Options for overlay positioning and sizing."""

    # Sizing
    width: SizeValue | None = None
    min_width: int | None = None
    max_height: SizeValue | None = None

    # Positioning - anchor-based
    anchor: OverlayAnchor | None = None
    offset_x: int | None = None
    offset_y: int | None = None

    # Positioning - percentage or absolute
    row: SizeValue | None = None
    col: SizeValue | None = None

    # Margin from terminal edges (int applies to all sides)
    margin: OverlayMargin | int | None = None

    # Visibility callback
    visible: Callable[[int, int], bool] | None = None


class OverlayHandle(Protocol):
    """Handle returned by show_overlay for controlling the overlay."""

    def hide(self) -> None:
        """Permanently remove the overlay."""
        ...

    def set_hidden(self, hidden: bool) -> None:
        """Temporarily hide or show the overlay."""
        ...

    def is_hidden(self) -> bool:
        """Check if overlay is temporarily hidden."""
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PERCENT_RE = re.compile(r"^(\d+(?:\.\d+)?)%$")


def _parse_size_value(value: SizeValue | None, reference_size: int) -> int | None:
    """Parse a SizeValue into absolute value given a reference size."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    m = _PERCENT_RE.match(value)
    if m:
        return math.floor(reference_size * float(m.group(1)) / 100)
    return None


# ---------------------------------------------------------------------------
# Overlay entry (internal)
# ---------------------------------------------------------------------------


@dataclass
class _OverlayEntry:
    component: Any  # Component
    options: OverlayOptions | None
    pre_focus: Any  # Component | None
    hidden: bool = False


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class Container:
    """A component that contains other components."""

    def __init__(self) -> None:
        self.children: list[Any] = []  # list[Component]

    def add_child(self, component: Any) -> None:
        self.children.append(component)

    def remove_child(self, component: Any) -> None:
        with contextlib.suppress(ValueError):
            self.children.remove(component)

    def clear(self) -> None:
        self.children = []

    def invalidate(self) -> None:
        for child in self.children:
            if hasattr(child, "invalidate"):
                child.invalidate()

    def render(self, width: int) -> list[str]:
        lines: list[str] = []
        for child in self.children:
            lines.extend(child.render(width))
        return lines


# ---------------------------------------------------------------------------
# TUI
# ---------------------------------------------------------------------------

_SEGMENT_RESET = "\x1b[0m\x1b]8;;\x07"


class TUI(Container):
    """Main class for managing terminal UI with differential rendering."""

    def __init__(self, terminal: Terminal, show_hardware_cursor: bool | None = None) -> None:
        super().__init__()
        self.terminal: Terminal = terminal
        self.on_debug: Callable[[], None] | None = None

        self._previous_lines: list[str] = []
        self._previous_width: int = 0
        self._focused_component: Any | None = None  # Component | None
        self._input_listeners: list[InputListener] = []

        self._render_requested: bool = False
        self._cursor_row: int = 0
        self._hardware_cursor_row: int = 0
        self._input_buffer: str = ""
        self._cell_size_query_pending: bool = False
        self._show_hardware_cursor: bool = os.environ.get("PI_HARDWARE_CURSOR") == "1"
        self._clear_on_shrink: bool = os.environ.get("PI_CLEAR_ON_SHRINK") == "1"
        self._max_lines_rendered: int = 0
        self._previous_viewport_top: int = 0
        self._full_redraw_count: int = 0
        self._stopped: bool = False
        self._render_lock: threading.Lock = threading.Lock()

        self._overlay_stack: list[_OverlayEntry] = []

        if show_hardware_cursor is not None:
            self._show_hardware_cursor = show_hardware_cursor

    # -- Properties ----------------------------------------------------------

    @property
    def full_redraws(self) -> int:
        return self._full_redraw_count

    def get_show_hardware_cursor(self) -> bool:
        return self._show_hardware_cursor

    def set_show_hardware_cursor(self, enabled: bool) -> None:
        if self._show_hardware_cursor == enabled:
            return
        self._show_hardware_cursor = enabled
        if not enabled:
            self.terminal.hide_cursor()
        self.request_render()

    def get_clear_on_shrink(self) -> bool:
        return self._clear_on_shrink

    def set_clear_on_shrink(self, enabled: bool) -> None:
        """Set whether to trigger full re-render when content shrinks."""
        self._clear_on_shrink = enabled

    # -- Focus management ----------------------------------------------------

    def set_focus(self, component: Any | None) -> None:
        # Clear focused flag on old component
        old = self._focused_component
        if old is not None and is_focusable(old):
            old.focused = False

        self._focused_component = component

        # Set focused flag on new component
        if component is not None and is_focusable(component):
            component.focused = True

    # -- Overlay system ------------------------------------------------------

    def show_overlay(self, component: Any, options: OverlayOptions | None = None) -> OverlayHandle:
        """Show an overlay component with configurable positioning and sizing."""
        entry = _OverlayEntry(
            component=component,
            options=options,
            pre_focus=self._focused_component,
            hidden=False,
        )
        self._overlay_stack.append(entry)
        # Only focus if overlay is actually visible
        if self._is_overlay_visible(entry):
            self.set_focus(component)
        self.terminal.hide_cursor()
        self.request_render()

        # Build handle
        tui = self

        class _Handle:
            def hide(self) -> None:
                if entry in tui._overlay_stack:
                    tui._overlay_stack.remove(entry)
                    # Restore focus if this overlay had focus
                    if tui._focused_component is component:
                        top_visible = tui._get_topmost_visible_overlay()
                        tui.set_focus(top_visible.component if top_visible else entry.pre_focus)
                    if not tui._overlay_stack:
                        tui.terminal.hide_cursor()
                    tui.request_render()

            def set_hidden(self, hidden: bool) -> None:
                if entry.hidden == hidden:
                    return
                entry.hidden = hidden
                if hidden:
                    if tui._focused_component is component:
                        top_visible = tui._get_topmost_visible_overlay()
                        tui.set_focus(top_visible.component if top_visible else entry.pre_focus)
                else:
                    if tui._is_overlay_visible(entry):
                        tui.set_focus(component)
                tui.request_render()

            def is_hidden(self) -> bool:
                return entry.hidden

        return _Handle()

    def hide_overlay(self) -> None:
        """Hide the topmost overlay and restore previous focus."""
        if not self._overlay_stack:
            return
        overlay = self._overlay_stack.pop()
        top_visible = self._get_topmost_visible_overlay()
        self.set_focus(top_visible.component if top_visible else overlay.pre_focus)
        if not self._overlay_stack:
            self.terminal.hide_cursor()
        self.request_render()

    def has_overlay(self) -> bool:
        """Check if there are any visible overlays."""
        return any(self._is_overlay_visible(o) for o in self._overlay_stack)

    def _is_overlay_visible(self, entry: _OverlayEntry) -> bool:
        """Check if an overlay entry is currently visible."""
        if entry.hidden:
            return False
        if entry.options is not None and entry.options.visible is not None:
            return entry.options.visible(self.terminal.columns, self.terminal.rows)
        return True

    def _get_topmost_visible_overlay(self) -> _OverlayEntry | None:
        """Find the topmost visible overlay, if any."""
        for i in range(len(self._overlay_stack) - 1, -1, -1):
            if self._is_overlay_visible(self._overlay_stack[i]):
                return self._overlay_stack[i]
        return None

    # -- Invalidate ----------------------------------------------------------

    def invalidate(self) -> None:
        super().invalidate()
        for overlay in self._overlay_stack:
            if hasattr(overlay.component, "invalidate"):
                overlay.component.invalidate()

    # -- Start / Stop -------------------------------------------------------

    def start(self) -> None:
        self._stopped = False
        self.terminal.start(
            lambda data: self._handle_input(data),
            lambda: self.request_render(),
        )
        self.terminal.hide_cursor()
        self._query_cell_size()
        self.request_render()

    def stop(self) -> None:
        self._stopped = True
        # Move cursor to end of content
        if self._previous_lines:
            target_row = len(self._previous_lines)
            line_diff = target_row - self._hardware_cursor_row
            if line_diff > 0:
                self.terminal.write(f"\x1b[{line_diff}B")
            elif line_diff < 0:
                self.terminal.write(f"\x1b[{-line_diff}A")
            self.terminal.write("\r\n")

        self.terminal.show_cursor()
        self.terminal.stop()

    # -- Input listeners -----------------------------------------------------

    def add_input_listener(self, listener: InputListener) -> Callable[[], None]:
        self._input_listeners.append(listener)

        def remove() -> None:
            self.remove_input_listener(listener)

        return remove

    def remove_input_listener(self, listener: InputListener) -> None:
        with contextlib.suppress(ValueError):
            self._input_listeners.remove(listener)

    # -- Cell size query -----------------------------------------------------

    def _query_cell_size(self) -> None:
        """Query terminal for cell size in pixels (only if images are supported)."""
        if not get_capabilities().images:
            return
        self._cell_size_query_pending = True
        self.terminal.write("\x1b[16t")

    # -- Render request ------------------------------------------------------

    def request_render(self, force: bool = False) -> None:
        if force:
            self._previous_lines = []
            self._previous_width = -1
            self._cursor_row = 0
            self._hardware_cursor_row = 0
            self._max_lines_rendered = 0
            self._previous_viewport_top = 0
        if self._render_requested:
            return
        self._render_requested = True
        # Use a zero-delay timer for deferred rendering (like process.nextTick).
        # This coalesces multiple request_render calls in the same tick.
        threading.Timer(0, self._deferred_render).start()

    def _deferred_render(self) -> None:
        """Called from timer thread; perform render under lock."""
        with self._render_lock:
            self._render_requested = False
            self._do_render()

    # -- Input handling ------------------------------------------------------

    def _handle_input(self, data: str) -> None:
        if self._input_listeners:
            current = data
            for listener in list(self._input_listeners):
                result = listener(current)
                if result is not None and result.consume:
                    return
                if result is not None and result.data is not None:
                    current = result.data
            if not current:
                return
            data = current

        # Buffer for cell size response parsing
        if self._cell_size_query_pending:
            self._input_buffer += data
            filtered = self._parse_cell_size_response()
            if not filtered:
                return
            data = filtered

        # Global debug key handler (Shift+Ctrl+D)
        if matches_key(data, "shift+ctrl+d") and self.on_debug:
            self.on_debug()
            return

        # If focused component is an overlay, verify it is still visible
        focused_overlay: _OverlayEntry | None = None
        for o in self._overlay_stack:
            if o.component is self._focused_component:
                focused_overlay = o
                break

        if focused_overlay and not self._is_overlay_visible(focused_overlay):
            top_visible = self._get_topmost_visible_overlay()
            if top_visible:
                self.set_focus(top_visible.component)
            else:
                self.set_focus(focused_overlay.pre_focus)

        # Pass input to focused component
        if self._focused_component is not None and hasattr(self._focused_component, "handle_input"):
            # Filter out key release events unless component opts in
            wants_release = getattr(self._focused_component, "wants_key_release", False)
            if is_key_release(data) and not wants_release:
                return
            self._focused_component.handle_input(data)
            self.request_render()

    def _parse_cell_size_response(self) -> str:
        """Parse cell size response from input buffer."""
        response_pattern = re.compile(r"\x1b\[6;(\d+);(\d+)t")
        match = response_pattern.search(self._input_buffer)

        if match:
            height_px = int(match.group(1))
            width_px = int(match.group(2))

            if height_px > 0 and width_px > 0:
                set_cell_dimensions(CellDimensions(width_px=width_px, height_px=height_px))
                self.invalidate()
                self.request_render()

            self._input_buffer = response_pattern.sub("", self._input_buffer)
            self._cell_size_query_pending = False

        # Check for partial response (wait for more data)
        partial_pattern = re.compile(r"\x1b(\[6?;?[\d;]*)?$")
        if partial_pattern.search(self._input_buffer):
            last_char = self._input_buffer[-1] if self._input_buffer else ""
            if not re.match(r"[a-zA-Z~]", last_char):
                return ""

        # No cell size response found, return buffered data
        result = self._input_buffer
        self._input_buffer = ""
        self._cell_size_query_pending = False
        return result

    # -- Overlay layout resolution -------------------------------------------

    def _resolve_overlay_layout(
        self,
        options: OverlayOptions | None,
        overlay_height: int,
        term_width: int,
        term_height: int,
    ) -> tuple[int, int, int, int | None]:
        """Resolve overlay layout.

        Returns (width, row, col, max_height).
        """
        opt = options if options is not None else OverlayOptions()

        # Parse margin
        if isinstance(opt.margin, int):
            margin_top = max(0, opt.margin)
            margin_right = max(0, opt.margin)
            margin_bottom = max(0, opt.margin)
            margin_left = max(0, opt.margin)
        elif isinstance(opt.margin, OverlayMargin):
            margin_top = max(0, opt.margin.top or 0)
            margin_right = max(0, opt.margin.right or 0)
            margin_bottom = max(0, opt.margin.bottom or 0)
            margin_left = max(0, opt.margin.left or 0)
        else:
            margin_top = margin_right = margin_bottom = margin_left = 0

        # Available space after margins
        avail_width = max(1, term_width - margin_left - margin_right)
        avail_height = max(1, term_height - margin_top - margin_bottom)

        # Resolve width
        width = _parse_size_value(opt.width, term_width)
        if width is None:
            width = min(80, avail_width)
        if opt.min_width is not None:
            width = max(width, opt.min_width)
        width = max(1, min(width, avail_width))

        # Resolve max_height
        max_height = _parse_size_value(opt.max_height, term_height)
        if max_height is not None:
            max_height = max(1, min(max_height, avail_height))

        # Effective overlay height
        effective_height = min(overlay_height, max_height) if max_height is not None else overlay_height

        # Resolve row position
        row: int
        if opt.row is not None:
            if isinstance(opt.row, str):
                m = _PERCENT_RE.match(opt.row)
                if m:
                    max_row = max(0, avail_height - effective_height)
                    percent = float(m.group(1)) / 100
                    row = margin_top + math.floor(max_row * percent)
                else:
                    row = self._resolve_anchor_row("center", effective_height, avail_height, margin_top)
            else:
                row = opt.row
        else:
            anchor: OverlayAnchor = opt.anchor if opt.anchor is not None else "center"
            row = self._resolve_anchor_row(anchor, effective_height, avail_height, margin_top)

        # Resolve col position
        col: int
        if opt.col is not None:
            if isinstance(opt.col, str):
                m = _PERCENT_RE.match(opt.col)
                if m:
                    max_col = max(0, avail_width - width)
                    percent = float(m.group(1)) / 100
                    col = margin_left + math.floor(max_col * percent)
                else:
                    col = self._resolve_anchor_col("center", width, avail_width, margin_left)
            else:
                col = opt.col
        else:
            anchor = opt.anchor if opt.anchor is not None else "center"
            col = self._resolve_anchor_col(anchor, width, avail_width, margin_left)

        # Apply offsets
        if opt.offset_y is not None:
            row += opt.offset_y
        if opt.offset_x is not None:
            col += opt.offset_x

        # Clamp to terminal bounds
        row = max(margin_top, min(row, term_height - margin_bottom - effective_height))
        col = max(margin_left, min(col, term_width - margin_right - width))

        return width, row, col, max_height

    def _resolve_anchor_row(self, anchor: OverlayAnchor, height: int, avail_height: int, margin_top: int) -> int:
        if anchor in ("top-left", "top-center", "top-right"):
            return margin_top
        if anchor in ("bottom-left", "bottom-center", "bottom-right"):
            return margin_top + avail_height - height
        # center, left-center, right-center
        return margin_top + (avail_height - height) // 2

    def _resolve_anchor_col(self, anchor: OverlayAnchor, width: int, avail_width: int, margin_left: int) -> int:
        if anchor in ("top-left", "left-center", "bottom-left"):
            return margin_left
        if anchor in ("top-right", "right-center", "bottom-right"):
            return margin_left + avail_width - width
        # top-center, center, bottom-center
        return margin_left + (avail_width - width) // 2

    # -- Overlay compositing -------------------------------------------------

    def _composite_overlays(self, lines: list[str], term_width: int, term_height: int) -> list[str]:
        """Composite all overlays into content lines."""
        if not self._overlay_stack:
            return lines
        result = list(lines)

        # Pre-render all visible overlays
        rendered: list[tuple[list[str], int, int, int]] = []  # (lines, row, col, width)
        min_lines_needed = len(result)

        for entry in self._overlay_stack:
            if not self._is_overlay_visible(entry):
                continue

            component = entry.component
            options = entry.options

            # Get layout with height=0 to determine width and max_height
            width, _, _, max_height = self._resolve_overlay_layout(options, 0, term_width, term_height)

            # Render component at calculated width
            overlay_lines = component.render(width)

            # Apply max_height
            if max_height is not None and len(overlay_lines) > max_height:
                overlay_lines = overlay_lines[:max_height]

            # Get final row/col with actual height
            _, row, col, _ = self._resolve_overlay_layout(options, len(overlay_lines), term_width, term_height)

            rendered.append((overlay_lines, row, col, width))
            min_lines_needed = max(min_lines_needed, row + len(overlay_lines))

        # Ensure result covers the terminal working area
        working_height = max(self._max_lines_rendered, min_lines_needed)
        while len(result) < working_height:
            result.append("")

        viewport_start = max(0, working_height - term_height)

        modified_lines: set[int] = set()

        # Composite each overlay
        for overlay_lines, row, col, w in rendered:
            for i, overlay_line in enumerate(overlay_lines):
                idx = viewport_start + row + i
                if 0 <= idx < len(result):
                    # Truncate overlay line to declared width
                    if visible_width(overlay_line) > w:
                        overlay_line = slice_by_column(overlay_line, 0, w, True)
                    result[idx] = self._composite_line_at(result[idx], overlay_line, col, w, term_width)
                    modified_lines.add(idx)

        # Final verification: ensure no composited line exceeds terminal width
        for idx in modified_lines:
            if visible_width(result[idx]) > term_width:
                result[idx] = slice_by_column(result[idx], 0, term_width, True)

        return result

    def _composite_line_at(
        self,
        base_line: str,
        overlay_line: str,
        start_col: int,
        overlay_width: int,
        total_width: int,
    ) -> str:
        """Splice overlay content into a base line at a specific column."""
        if is_image_line(base_line):
            return base_line

        after_start = start_col + overlay_width
        base = extract_segments(base_line, start_col, after_start, total_width - after_start, True)

        overlay = slice_with_width(overlay_line, 0, overlay_width, True)

        before_pad = max(0, start_col - base.before_width)
        overlay_pad = max(0, overlay_width - overlay.width)
        actual_before_width = max(start_col, base.before_width)
        actual_overlay_width = max(overlay_width, overlay.width)
        after_target = max(0, total_width - actual_before_width - actual_overlay_width)
        after_pad = max(0, after_target - base.after_width)

        r = _SEGMENT_RESET
        result = (
            base.before + " " * before_pad + r + overlay.text + " " * overlay_pad + r + base.after + " " * after_pad
        )

        result_width = visible_width(result)
        if result_width <= total_width:
            return result
        return slice_by_column(result, 0, total_width, True)

    # -- Line resets ---------------------------------------------------------

    @staticmethod
    def _apply_line_resets(lines: list[str]) -> list[str]:
        for i in range(len(lines)):
            if not is_image_line(lines[i]):
                lines[i] = lines[i] + _SEGMENT_RESET
        return lines

    # -- Cursor position extraction ------------------------------------------

    @staticmethod
    def _extract_cursor_position(lines: list[str], height: int) -> tuple[int, int] | None:
        """Find and extract cursor position from rendered lines.

        Returns (row, col) or None if no marker found.
        """
        viewport_top = max(0, len(lines) - height)
        for row in range(len(lines) - 1, viewport_top - 1, -1):
            line = lines[row]
            marker_index = line.find(CURSOR_MARKER)
            if marker_index != -1:
                before_marker = line[:marker_index]
                col = visible_width(before_marker)
                lines[row] = line[:marker_index] + line[marker_index + len(CURSOR_MARKER) :]
                return (row, col)
        return None

    # -- Hardware cursor positioning -----------------------------------------

    def _position_hardware_cursor(self, cursor_pos: tuple[int, int] | None, total_lines: int) -> None:
        """Position the hardware cursor for IME candidate window."""
        if cursor_pos is None or total_lines <= 0:
            self.terminal.hide_cursor()
            return

        target_row = max(0, min(cursor_pos[0], total_lines - 1))
        target_col = max(0, cursor_pos[1])

        row_delta = target_row - self._hardware_cursor_row
        buf = ""
        if row_delta > 0:
            buf += f"\x1b[{row_delta}B"
        elif row_delta < 0:
            buf += f"\x1b[{-row_delta}A"
        # Move to absolute column (1-indexed)
        buf += f"\x1b[{target_col + 1}G"

        if buf:
            self.terminal.write(buf)

        self._hardware_cursor_row = target_row
        if self._show_hardware_cursor:
            self.terminal.show_cursor()
        else:
            self.terminal.hide_cursor()

    # -- Differential rendering engine ---------------------------------------

    def _do_render(self) -> None:
        if self._stopped:
            return

        width = self.terminal.columns
        height = self.terminal.rows
        viewport_top = max(0, self._max_lines_rendered - height)
        prev_viewport_top = self._previous_viewport_top
        hardware_cursor_row = self._hardware_cursor_row

        def compute_line_diff(target_row: int) -> int:
            current_screen_row = hardware_cursor_row - prev_viewport_top
            target_screen_row = target_row - viewport_top
            return target_screen_row - current_screen_row

        # Render all components
        new_lines = self.render(width)

        # Composite overlays
        if self._overlay_stack:
            new_lines = self._composite_overlays(new_lines, width, height)

        # Extract cursor position before line resets
        cursor_pos = self._extract_cursor_position(new_lines, height)

        new_lines = self._apply_line_resets(new_lines)

        # Width changed?
        width_changed = self._previous_width != 0 and self._previous_width != width

        def full_render(clear: bool) -> None:
            nonlocal viewport_top, prev_viewport_top, hardware_cursor_row
            self._full_redraw_count += 1
            buf = "\x1b[?2026h"  # Begin synchronized output
            if clear:
                buf += "\x1b[3J\x1b[2J\x1b[H"  # Clear scrollback, screen, home
            for i, line in enumerate(new_lines):
                if i > 0:
                    buf += "\r\n"
                buf += line
            buf += "\x1b[?2026l"  # End synchronized output
            self.terminal.write(buf)
            self._cursor_row = max(0, len(new_lines) - 1)
            self._hardware_cursor_row = self._cursor_row
            if clear:
                self._max_lines_rendered = len(new_lines)
            else:
                self._max_lines_rendered = max(self._max_lines_rendered, len(new_lines))
            self._previous_viewport_top = max(0, self._max_lines_rendered - height)
            self._position_hardware_cursor(cursor_pos, len(new_lines))
            self._previous_lines = new_lines
            self._previous_width = width

        # First render
        if not self._previous_lines and not width_changed:
            full_render(False)
            return

        # Width changed
        if width_changed:
            full_render(True)
            return

        # Content shrunk + clearOnShrink
        if self._clear_on_shrink and len(new_lines) < self._max_lines_rendered and not self._overlay_stack:
            full_render(True)
            return

        # Find first and last changed lines
        first_changed = -1
        last_changed = -1
        max_lines = max(len(new_lines), len(self._previous_lines))
        for i in range(max_lines):
            old_line = self._previous_lines[i] if i < len(self._previous_lines) else ""
            new_line = new_lines[i] if i < len(new_lines) else ""
            if old_line != new_line:
                if first_changed == -1:
                    first_changed = i
                last_changed = i

        appended_lines = len(new_lines) > len(self._previous_lines)
        if appended_lines:
            if first_changed == -1:
                first_changed = len(self._previous_lines)
            last_changed = len(new_lines) - 1

        append_start = appended_lines and first_changed == len(self._previous_lines) and first_changed > 0

        # No changes
        if first_changed == -1:
            self._position_hardware_cursor(cursor_pos, len(new_lines))
            self._previous_viewport_top = max(0, self._max_lines_rendered - height)
            return

        # All changes are in deleted lines
        if first_changed >= len(new_lines):
            if len(self._previous_lines) > len(new_lines):
                buf = "\x1b[?2026h"
                target_row = max(0, len(new_lines) - 1)
                line_diff = compute_line_diff(target_row)
                if line_diff > 0:
                    buf += f"\x1b[{line_diff}B"
                elif line_diff < 0:
                    buf += f"\x1b[{-line_diff}A"
                buf += "\r"
                extra_lines = len(self._previous_lines) - len(new_lines)
                if extra_lines > height:
                    full_render(True)
                    return
                if extra_lines > 0:
                    buf += "\x1b[1B"
                for i in range(extra_lines):
                    buf += "\r\x1b[2K"
                    if i < extra_lines - 1:
                        buf += "\x1b[1B"
                if extra_lines > 0:
                    buf += f"\x1b[{extra_lines}A"
                buf += "\x1b[?2026l"
                self.terminal.write(buf)
                self._cursor_row = target_row
                self._hardware_cursor_row = target_row
            self._position_hardware_cursor(cursor_pos, len(new_lines))
            self._previous_lines = new_lines
            self._previous_width = width
            self._previous_viewport_top = max(0, self._max_lines_rendered - height)
            return

        # Check if first change is above previous viewport
        previous_content_viewport_top = max(0, len(self._previous_lines) - height)
        if first_changed < previous_content_viewport_top:
            full_render(True)
            return

        # Build differential update buffer
        buf = "\x1b[?2026h"
        prev_viewport_bottom = prev_viewport_top + height - 1
        move_target_row = first_changed - 1 if append_start else first_changed

        if move_target_row > prev_viewport_bottom:
            current_screen_row = max(0, min(height - 1, hardware_cursor_row - prev_viewport_top))
            move_to_bottom = height - 1 - current_screen_row
            if move_to_bottom > 0:
                buf += f"\x1b[{move_to_bottom}B"
            scroll = move_target_row - prev_viewport_bottom
            buf += "\r\n" * scroll
            prev_viewport_top += scroll
            viewport_top += scroll
            hardware_cursor_row = move_target_row

        line_diff = compute_line_diff(move_target_row)
        if line_diff > 0:
            buf += f"\x1b[{line_diff}B"
        elif line_diff < 0:
            buf += f"\x1b[{-line_diff}A"

        buf += "\r\n" if append_start else "\r"

        render_end = min(last_changed, len(new_lines) - 1)
        for i in range(first_changed, render_end + 1):
            if i > first_changed:
                buf += "\r\n"
            buf += "\x1b[2K"  # Clear current line
            line = new_lines[i]
            is_img = is_image_line(line)
            if not is_img and visible_width(line) > width:
                # Width overflow - stop and clean up
                self.stop()
                raise RuntimeError(
                    f"Rendered line {i} exceeds terminal width "
                    f"({visible_width(line)} > {width}). "
                    "Use visible_width() to measure and truncate_to_width() to truncate lines."
                )
            buf += line

        # Track where cursor ended up
        final_cursor_row = render_end

        # Clear extra lines if content shrunk
        if len(self._previous_lines) > len(new_lines):
            if render_end < len(new_lines) - 1:
                move_down = len(new_lines) - 1 - render_end
                buf += f"\x1b[{move_down}B"
                final_cursor_row = len(new_lines) - 1
            extra_lines = len(self._previous_lines) - len(new_lines)
            for _ in range(extra_lines):
                buf += "\r\n\x1b[2K"
            buf += f"\x1b[{extra_lines}A"

        buf += "\x1b[?2026l"  # End synchronized output

        self.terminal.write(buf)

        self._cursor_row = max(0, len(new_lines) - 1)
        self._hardware_cursor_row = final_cursor_row
        self._max_lines_rendered = max(self._max_lines_rendered, len(new_lines))
        self._previous_viewport_top = max(0, self._max_lines_rendered - height)

        self._position_hardware_cursor(cursor_pos, len(new_lines))

        self._previous_lines = new_lines
        self._previous_width = width
