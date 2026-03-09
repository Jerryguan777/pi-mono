"""Reusable countdown timer for dialog components."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pi_tui.tui import TUI


class CountdownTimer:
    """Fires a callback every second, counting down from a timeout duration.

    On each tick, ``on_tick`` is called with the remaining seconds.
    When the counter reaches zero, ``on_expire`` is called.
    """

    def __init__(
        self,
        timeout_ms: float,
        tui: TUI | None,
        on_tick: Callable[[int], None],
        on_expire: Callable[[], None],
    ) -> None:
        self._tui = tui
        self._on_tick = on_tick
        self._on_expire = on_expire
        self._remaining_seconds = max(1, int(timeout_ms / 1000 + 0.999))
        self._timer: threading.Timer | None = None
        self._disposed = False

        # Fire the initial tick immediately
        self._on_tick(self._remaining_seconds)
        self._schedule_next()

    def _schedule_next(self) -> None:
        if self._disposed:
            return
        self._timer = threading.Timer(1.0, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self) -> None:
        if self._disposed:
            return
        self._remaining_seconds -= 1
        self._on_tick(self._remaining_seconds)
        if self._tui is not None and hasattr(self._tui, "request_render"):
            self._tui.request_render()

        if self._remaining_seconds <= 0:
            self.dispose()
            self._on_expire()
        else:
            self._schedule_next()

    def dispose(self) -> None:
        """Cancel the timer."""
        self._disposed = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
