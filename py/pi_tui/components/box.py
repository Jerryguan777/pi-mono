"""Box container component with padding and background."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pi_tui.utils import apply_background_to_line, visible_width


class Box:
    """Container that applies padding and background color to all children.

    Rendered output is cached and invalidated when children or background
    change.
    """

    def __init__(
        self,
        padding_x: int = 1,
        padding_y: int = 1,
        bg_fn: Callable[[str], str] | None = None,
    ) -> None:
        self.children: list[Any] = []
        self._padding_x = padding_x
        self._padding_y = padding_y
        self._bg_fn = bg_fn

        # Cache
        self._cache_child_lines: list[str] | None = None
        self._cache_width: int | None = None
        self._cache_bg_sample: str | None = None
        self._cache_lines: list[str] | None = None

    def add_child(self, component: Any) -> None:
        self.children.append(component)
        self._invalidate_cache()

    def remove_child(self, component: Any) -> None:
        try:
            self.children.remove(component)
            self._invalidate_cache()
        except ValueError:
            pass

    def clear(self) -> None:
        self.children = []
        self._invalidate_cache()

    def set_bg_fn(self, bg_fn: Callable[[str], str] | None = None) -> None:
        self._bg_fn = bg_fn

    def _invalidate_cache(self) -> None:
        self._cache_child_lines = None
        self._cache_width = None
        self._cache_bg_sample = None
        self._cache_lines = None

    def _match_cache(self, width: int, child_lines: list[str], bg_sample: str | None) -> bool:
        cache_cl = self._cache_child_lines
        return (
            cache_cl is not None
            and self._cache_width == width
            and self._cache_bg_sample == bg_sample
            and len(cache_cl) == len(child_lines)
            and all(a == b for a, b in zip(cache_cl, child_lines, strict=True))
        )

    def invalidate(self) -> None:
        self._invalidate_cache()
        for child in self.children:
            inv = getattr(child, "invalidate", None)
            if callable(inv):
                inv()

    def render(self, width: int) -> list[str]:
        if not self.children:
            return []

        content_width = max(1, width - self._padding_x * 2)
        left_pad = " " * self._padding_x

        # Render all children
        child_lines: list[str] = []
        for child in self.children:
            lines = child.render(content_width)
            for line in lines:
                child_lines.append(left_pad + line)

        if not child_lines:
            return []

        # Check if bg_fn output changed by sampling
        bg_sample = self._bg_fn("test") if self._bg_fn else None

        # Check cache validity
        if self._match_cache(width, child_lines, bg_sample) and self._cache_lines is not None:
            return self._cache_lines

        # Apply background and padding
        result: list[str] = []

        # Top padding
        for _ in range(self._padding_y):
            result.append(self._apply_bg("", width))

        # Content
        for line in child_lines:
            result.append(self._apply_bg(line, width))

        # Bottom padding
        for _ in range(self._padding_y):
            result.append(self._apply_bg("", width))

        # Update cache
        self._cache_child_lines = child_lines
        self._cache_width = width
        self._cache_bg_sample = bg_sample
        self._cache_lines = result

        return result

    def _apply_bg(self, line: str, width: int) -> str:
        vis_len = visible_width(line)
        pad_needed = max(0, width - vis_len)
        padded = line + " " * pad_needed

        if self._bg_fn:
            return apply_background_to_line(padded, width, self._bg_fn)
        return padded
