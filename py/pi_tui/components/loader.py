"""Spinner animation component that updates at 80ms intervals."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, ClassVar

from pi_tui.components.text import Text


class Loader(Text):
    """Animated spinner with a message, rendered as a Text component.

    Uses ``threading.Timer`` for periodic updates. The *tui* parameter
    must expose a ``request_render()`` method so the loader can trigger
    re-draws.
    """

    _FRAMES: ClassVar[list[str]] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(
        self,
        tui: Any,
        spinner_color_fn: Callable[[str], str],
        message_color_fn: Callable[[str], str],
        message: str = "Loading...",
    ) -> None:
        super().__init__("", padding_x=1, padding_y=0)
        self._tui = tui
        self._spinner_color_fn = spinner_color_fn
        self._message_color_fn = message_color_fn
        self._message = message
        self._current_frame = 0
        self._timer: threading.Timer | None = None
        self.start()

    def render(self, width: int) -> list[str]:
        return ["", *super().render(width)]

    def start(self) -> None:
        self._update_display()
        self._schedule_next()

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def set_message(self, message: str) -> None:
        self._message = message
        self._update_display()

    def _schedule_next(self) -> None:
        def _tick() -> None:
            self._current_frame = (self._current_frame + 1) % len(self._FRAMES)
            self._update_display()
            self._schedule_next()

        self._timer = threading.Timer(0.08, _tick)
        self._timer.daemon = True
        self._timer.start()

    def _update_display(self) -> None:
        frame = self._FRAMES[self._current_frame]
        self.set_text(f"{self._spinner_color_fn(frame)} {self._message_color_fn(self._message)}")
        if self._tui is not None:
            request_render = getattr(self._tui, "request_render", None)
            if callable(request_render):
                request_render()
