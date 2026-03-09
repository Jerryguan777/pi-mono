"""Generic selector component for extensions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.countdown_timer import CountdownTimer
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.keybinding_hints import key_hint, raw_key_hint
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.tui import Container

if TYPE_CHECKING:
    from pi_tui.tui import TUI


class ExtensionSelectorComponent(Container):
    """Keyboard-navigable list of string options for extension-driven selection prompts."""

    def __init__(
        self,
        title: str,
        options: list[str],
        on_select: Callable[[str], None],
        on_cancel: Callable[[], None],
        tui: TUI | None = None,
        timeout: int = 0,
    ) -> None:
        super().__init__()
        self._options = options
        self._on_select = on_select
        self._on_cancel = on_cancel
        self._base_title = title
        self._selected_index = 0

        self.add_child(DynamicBorder())
        self.add_child(Spacer(1))

        self._title_text = Text(theme.fg("accent", title), 1, 0)
        self.add_child(self._title_text)
        self.add_child(Spacer(1))

        self._countdown: CountdownTimer | None = None
        if timeout > 0 and tui is not None:
            self._countdown = CountdownTimer(
                timeout,
                tui,
                lambda s: self._title_text.set_text(theme.fg("accent", f"{self._base_title} ({s}s)")),
                on_cancel,
            )

        self._list_container = Container()
        self.add_child(self._list_container)
        self.add_child(Spacer(1))
        self.add_child(
            Text(
                raw_key_hint("\u2191\u2193", "navigate")
                + "  "
                + key_hint("selectConfirm", "select")
                + "  "
                + key_hint("selectCancel", "cancel"),
                1,
                0,
            )
        )
        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())

        self._update_list()

    def _update_list(self) -> None:
        self._list_container.clear()
        for i, option in enumerate(self._options):
            is_selected = i == self._selected_index
            if is_selected:
                text = theme.fg("accent", "\u2192 ") + theme.fg("accent", option)
            else:
                text = f"  {theme.fg('text', option)}"
            self._list_container.add_child(Text(text, 1, 0))

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()
        if kb.matches(data, "selectUp") or data == "k":
            self._selected_index = max(0, self._selected_index - 1)
            self._update_list()
        elif kb.matches(data, "selectDown") or data == "j":
            self._selected_index = min(len(self._options) - 1, self._selected_index + 1)
            self._update_list()
        elif kb.matches(data, "selectConfirm") or data == "\n":
            if self._options:
                self._on_select(self._options[self._selected_index])
        elif kb.matches(data, "selectCancel"):
            self._on_cancel()

    def dispose(self) -> None:
        if self._countdown is not None:
            self._countdown.dispose()
