"""Loader wrapped with borders for extension UI."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.keybinding_hints import key_hint
from pi_tui.components.cancellable_loader import CancellableLoader
from pi_tui.components.loader import Loader
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.tui import Container

if TYPE_CHECKING:
    from pi_coding_agent.modes.interactive.components._theme import Theme
    from pi_tui.tui import TUI


class BorderedLoader(Container):
    """A loader component wrapped with dynamic borders.

    Optionally shows a cancel hint and integrates with :class:`CancellableLoader`.
    """

    def __init__(
        self,
        tui: TUI,
        the_theme: Theme,
        message: str,
        options: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        cancellable = (options or {}).get("cancellable", True)
        self._cancellable = cancellable

        def border_color(s: str) -> str:
            return the_theme.fg("border", s)

        self.add_child(DynamicBorder(border_color))

        if cancellable:
            self._loader: CancellableLoader | Loader = CancellableLoader(
                tui,
                lambda s: the_theme.fg("accent", s),
                lambda s: the_theme.fg("muted", s),
                message,
            )
        else:
            self._loader = Loader(
                tui,
                lambda s: the_theme.fg("accent", s),
                lambda s: the_theme.fg("muted", s),
                message,
            )

        self.add_child(self._loader)

        if cancellable:
            self.add_child(Spacer(1))
            self.add_child(Text(key_hint("selectCancel", "cancel"), 1, 0))

        self.add_child(Spacer(1))
        self.add_child(DynamicBorder(border_color))

    @property
    def signal(self) -> Any:
        """Return the abort event if using a CancellableLoader."""
        if self._cancellable and isinstance(self._loader, CancellableLoader):
            return self._loader.abort_event
        return None

    def set_on_abort(self, fn: Callable[[], None] | None) -> None:
        if self._cancellable and isinstance(self._loader, CancellableLoader):
            self._loader.on_abort = fn

    def handle_input(self, data: str) -> None:
        if self._cancellable and isinstance(self._loader, CancellableLoader):
            self._loader.handle_input(data)

    def dispose(self) -> None:
        if hasattr(self._loader, "dispose"):
            self._loader.dispose()
