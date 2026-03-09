"""Loader with abort support via asyncio.Event."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from pi_tui.components.loader import Loader
from pi_tui.keybindings import get_editor_keybindings


class CancellableLoader(Loader):
    """Loader that can be cancelled with Escape.

    Exposes an ``asyncio.Event`` as the abort signal and an ``on_abort``
    callback that is invoked when the user presses the cancel key.
    """

    def __init__(
        self,
        tui: Any,
        spinner_color_fn: Callable[[str], str],
        message_color_fn: Callable[[str], str],
        message: str = "Loading...",
    ) -> None:
        super().__init__(tui, spinner_color_fn, message_color_fn, message)
        self._abort_event = asyncio.Event()
        self.on_abort: Callable[[], None] | None = None

    @property
    def abort_event(self) -> asyncio.Event:
        """Event that is set when the user aborts."""
        return self._abort_event

    @property
    def aborted(self) -> bool:
        return self._abort_event.is_set()

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()
        if kb.matches(data, "selectCancel"):
            self._abort_event.set()
            if self.on_abort is not None:
                self.on_abort()

    def dispose(self) -> None:
        self.stop()
