"""Armin says hi! A fun easter egg with animated XBM art."""

from __future__ import annotations

import math
import random
import threading
from typing import TYPE_CHECKING, Any, Literal

from pi_coding_agent.modes.interactive.components._theme import theme

if TYPE_CHECKING:
    from pi_tui.tui import TUI

# XBM image: 31x36 pixels, LSB first, 1=background, 0=foreground
_WIDTH = 31
_HEIGHT = 36
_BITS = [
    0xFF,
    0xFF,
    0xFF,
    0x7F,
    0xFF,
    0xF0,
    0xFF,
    0x7F,
    0xFF,
    0xED,
    0xFF,
    0x7F,
    0xFF,
    0xDB,
    0xFF,
    0x7F,
    0xFF,
    0xB7,
    0xFF,
    0x7F,
    0xFF,
    0x77,
    0xFE,
    0x7F,
    0x3F,
    0xF8,
    0xFE,
    0x7F,
    0xDF,
    0xFF,
    0xFE,
    0x7F,
    0xDF,
    0x3F,
    0xFC,
    0x7F,
    0x9F,
    0xC3,
    0xFB,
    0x7F,
    0x6F,
    0xFC,
    0xF4,
    0x7F,
    0xF7,
    0x0F,
    0xF7,
    0x7F,
    0xF7,
    0xFF,
    0xF7,
    0x7F,
    0xF7,
    0xFF,
    0xE3,
    0x7F,
    0xF7,
    0x07,
    0xE8,
    0x7F,
    0xEF,
    0xF8,
    0x67,
    0x70,
    0x0F,
    0xFF,
    0xBB,
    0x6F,
    0xF1,
    0x00,
    0xD0,
    0x5B,
    0xFD,
    0x3F,
    0xEC,
    0x53,
    0xC1,
    0xFF,
    0xEF,
    0x57,
    0x9F,
    0xFD,
    0xEE,
    0x5F,
    0x9F,
    0xFC,
    0xAE,
    0x5F,
    0x1F,
    0x78,
    0xAC,
    0x5F,
    0x3F,
    0x00,
    0x50,
    0x6C,
    0x7F,
    0x00,
    0xDC,
    0x77,
    0xFF,
    0xC0,
    0x3F,
    0x78,
    0xFF,
    0x01,
    0xF8,
    0x7F,
    0xFF,
    0x03,
    0x9C,
    0x78,
    0xFF,
    0x07,
    0x8C,
    0x7C,
    0xFF,
    0x0F,
    0xCE,
    0x78,
    0xFF,
    0xFF,
    0xCF,
    0x7F,
    0xFF,
    0xFF,
    0xCF,
    0x78,
    0xFF,
    0xFF,
    0xDF,
    0x78,
    0xFF,
    0xFF,
    0xDF,
    0x7D,
    0xFF,
    0xFF,
    0x3F,
    0x7E,
    0xFF,
    0xFF,
    0xFF,
    0x7F,
]

_BYTES_PER_ROW = math.ceil(_WIDTH / 8)
_DISPLAY_HEIGHT = math.ceil(_HEIGHT / 2)

Effect = Literal["typewriter", "scanline", "rain", "fade", "crt", "glitch", "dissolve"]
_EFFECTS: list[Effect] = ["typewriter", "scanline", "rain", "fade", "crt", "glitch", "dissolve"]


def _get_pixel(x: int, y: int) -> bool:
    """Return True if pixel (x, y) is foreground (0-bit in XBM)."""
    if y >= _HEIGHT:
        return False
    byte_index = y * _BYTES_PER_ROW + x // 8
    bit_index = x % 8
    return ((_BITS[byte_index] >> bit_index) & 1) == 0


def _get_char(x: int, row: int) -> str:
    """Return half-block character for two vertically packed pixels."""
    upper = _get_pixel(x, row * 2)
    lower = _get_pixel(x, row * 2 + 1)
    if upper and lower:
        return "\u2588"
    if upper:
        return "\u2580"
    if lower:
        return "\u2584"
    return " "


def _build_final_grid() -> list[list[str]]:
    """Build the full target image grid."""
    grid: list[list[str]] = []
    for row in range(_DISPLAY_HEIGHT):
        line = [_get_char(x, row) for x in range(_WIDTH)]
        grid.append(line)
    return grid


class ArminComponent:
    """Animated ASCII art easter egg — Armin says hi!"""

    def __init__(self, ui: TUI) -> None:
        self._ui = ui
        self._effect: Effect = random.choice(_EFFECTS)
        self._final_grid = _build_final_grid()
        self._current_grid: list[list[str]] = self._create_empty_grid()
        self._effect_state: dict[str, Any] = {}
        self._cached_lines: list[str] = []
        self._cached_width = 0
        self._grid_version = 0
        self._cached_version = -1
        self._interval: threading.Timer | None = None

        self._init_effect()
        self._start_animation()

    def invalidate(self) -> None:
        self._cached_width = 0

    def render(self, width: int) -> list[str]:
        if width == self._cached_width and self._cached_version == self._grid_version:
            return self._cached_lines

        padding = 1
        available_width = width - padding

        lines: list[str] = []
        for row in self._current_grid:
            clipped = "".join(row[:available_width])
            pad_right = max(0, width - padding - len(clipped))
            lines.append(f" {theme.fg('accent', clipped)}{' ' * pad_right}")

        message = "ARMIN SAYS HI"
        msg_pad = max(0, width - padding - len(message))
        lines.append(f" {theme.fg('accent', message)}{' ' * msg_pad}")

        self._cached_lines = lines
        self._cached_width = width
        self._cached_version = self._grid_version
        return self._cached_lines

    def dispose(self) -> None:
        self._stop_animation()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_empty_grid(self) -> list[list[str]]:
        return [[" "] * _WIDTH for _ in range(_DISPLAY_HEIGHT)]

    def _init_effect(self) -> None:
        effect = self._effect
        if effect == "typewriter":
            self._effect_state = {"pos": 0}
        elif effect == "scanline":
            self._effect_state = {"row": 0}
        elif effect == "rain":
            self._effect_state = {
                "drops": [{"y": -random.randint(0, _DISPLAY_HEIGHT * 2 - 1), "settled": 0} for _ in range(_WIDTH)]
            }
        elif effect == "fade":
            positions = [(r, x) for r in range(_DISPLAY_HEIGHT) for x in range(_WIDTH)]
            random.shuffle(positions)
            self._effect_state = {"positions": positions, "idx": 0}
        elif effect == "crt":
            self._effect_state = {"expansion": 0}
        elif effect == "glitch":
            self._effect_state = {"phase": 0, "glitch_frames": 8}
        elif effect == "dissolve":
            chars = [" ", "\u2591", "\u2592", "\u2593", "\u2588", "\u2580", "\u2584"]
            self._current_grid = [[random.choice(chars) for _ in range(_WIDTH)] for _ in range(_DISPLAY_HEIGHT)]
            positions = [(r, x) for r in range(_DISPLAY_HEIGHT) for x in range(_WIDTH)]
            random.shuffle(positions)
            self._effect_state = {"positions": positions, "idx": 0}

    def _start_animation(self) -> None:
        fps = 60 if self._effect == "glitch" else 30
        interval = 1.0 / fps
        self._schedule_tick(interval)

    def _schedule_tick(self, interval: float) -> None:
        self._interval = threading.Timer(interval, self._animation_tick, args=(interval,))
        self._interval.daemon = True
        self._interval.start()

    def _animation_tick(self, interval: float) -> None:
        done = self._tick_effect()
        self._grid_version += 1
        if hasattr(self._ui, "request_render"):
            self._ui.request_render()
        if done:
            self._stop_animation()
        else:
            self._schedule_tick(interval)

    def _stop_animation(self) -> None:
        if self._interval is not None:
            self._interval.cancel()
            self._interval = None

    def _tick_effect(self) -> bool:
        effect = self._effect
        if effect == "typewriter":
            return self._tick_typewriter()
        if effect == "scanline":
            return self._tick_scanline()
        if effect == "rain":
            return self._tick_rain()
        if effect == "fade":
            return self._tick_fade()
        if effect == "crt":
            return self._tick_crt()
        if effect == "glitch":
            return self._tick_glitch()
        if effect == "dissolve":
            return self._tick_dissolve()
        return True

    def _tick_typewriter(self) -> bool:
        state = self._effect_state
        pos = int(state["pos"])
        pixels_per_frame = 3
        for _ in range(pixels_per_frame):
            row = pos // _WIDTH
            x = pos % _WIDTH
            if row >= _DISPLAY_HEIGHT:
                return True
            self._current_grid[row][x] = self._final_grid[row][x]
            pos += 1
        state["pos"] = pos
        return False

    def _tick_scanline(self) -> bool:
        state = self._effect_state
        row = int(state["row"])
        if row >= _DISPLAY_HEIGHT:
            return True
        for x in range(_WIDTH):
            self._current_grid[row][x] = self._final_grid[row][x]
        state["row"] = row + 1
        return False

    def _tick_rain(self) -> bool:
        drops = self._effect_state["drops"]
        all_settled = True
        self._current_grid = self._create_empty_grid()

        for x in range(_WIDTH):
            drop = drops[x]
            # Draw settled pixels
            for row in range(_DISPLAY_HEIGHT - 1, _DISPLAY_HEIGHT - 1 - drop["settled"] - 1, -1):
                if row >= 0:
                    self._current_grid[row][x] = self._final_grid[row][x]

            if drop["settled"] >= _DISPLAY_HEIGHT:
                continue

            all_settled = False

            # Find target row
            target_row = -1
            for row in range(_DISPLAY_HEIGHT - 1 - drop["settled"], -1, -1):
                if self._final_grid[row][x] != " ":
                    target_row = row
                    break

            drop["y"] += 1

            if 0 <= drop["y"] < _DISPLAY_HEIGHT:
                if target_row >= 0 and drop["y"] >= target_row:
                    drop["settled"] = _DISPLAY_HEIGHT - target_row
                    drop["y"] = -random.randint(1, 5)
                else:
                    self._current_grid[drop["y"]][x] = "\u2593"

        return all_settled

    def _tick_fade(self) -> bool:
        state = self._effect_state
        positions = state["positions"]
        idx = int(state["idx"])
        pixels_per_frame = 15
        for _ in range(pixels_per_frame):
            if idx >= len(positions):
                return True
            row, x = positions[idx]
            self._current_grid[row][x] = self._final_grid[row][x]
            idx += 1
        state["idx"] = idx
        return False

    def _tick_crt(self) -> bool:
        state = self._effect_state
        expansion = int(state["expansion"])
        mid_row = _DISPLAY_HEIGHT // 2
        self._current_grid = self._create_empty_grid()
        top = mid_row - expansion
        bottom = mid_row + expansion
        for row in range(max(0, top), min(_DISPLAY_HEIGHT - 1, bottom) + 1):
            for x in range(_WIDTH):
                self._current_grid[row][x] = self._final_grid[row][x]
        state["expansion"] = expansion + 1
        return expansion > _DISPLAY_HEIGHT

    def _tick_glitch(self) -> bool:
        state = self._effect_state
        phase = int(state["phase"])
        glitch_frames = int(state["glitch_frames"])

        if phase < glitch_frames:
            new_grid: list[list[str]] = []
            for row in self._final_grid:
                r = random.random()
                if r < 0.3:
                    offset = random.randint(-3, 3)
                    shifted = row[offset:] + row[:offset]
                    new_grid.append(shifted[:_WIDTH])
                elif r < 0.5:
                    swap_row_idx = random.randint(0, _DISPLAY_HEIGHT - 1)
                    new_grid.append(list(self._final_grid[swap_row_idx]))
                else:
                    new_grid.append(list(row))
            self._current_grid = new_grid
            state["phase"] = phase + 1
            return False

        self._current_grid = [list(row) for row in self._final_grid]
        return True

    def _tick_dissolve(self) -> bool:
        state = self._effect_state
        positions = state["positions"]
        idx = int(state["idx"])
        pixels_per_frame = 20
        for _ in range(pixels_per_frame):
            if idx >= len(positions):
                return True
            row, x = positions[idx]
            self._current_grid[row][x] = self._final_grid[row][x]
            idx += 1
        state["idx"] = idx
        return False
