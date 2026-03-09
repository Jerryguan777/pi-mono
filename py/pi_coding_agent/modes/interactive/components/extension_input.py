"""Simple text input component for extensions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.countdown_timer import CountdownTimer
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.keybinding_hints import key_hint
from pi_tui.components.input import Input
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.tui import Container

if TYPE_CHECKING:
    from pi_tui.tui import TUI


@dataclass
class ExtensionInputOptions:
    """Options for creating an ExtensionInputComponent.

    Port of ExtensionInputOptions from
    packages/coding-agent/src/modes/interactive/components/extension-input.ts.
    """

    tui: TUI | None = None
    timeout: int | None = None


class ExtensionInputComponent(Container):
    """Single-line text input for extension-driven prompts.

    Supports optional countdown timer that auto-cancels on expiry.
    Implements the Focusable protocol by propagating focus to the inner Input.
    """

    def __init__(
        self,
        title: str,
        placeholder: str | None,
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
        tui: TUI | None = None,
        timeout: int = 0,
    ) -> None:
        super().__init__()
        self._on_submit = on_submit
        self._on_cancel = on_cancel
        self._base_title = title
        self._focused = False

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

        self._input = Input()
        self.add_child(self._input)
        self.add_child(Spacer(1))
        self.add_child(Text(f"{key_hint('selectConfirm', 'submit')}  {key_hint('selectCancel', 'cancel')}", 1, 0))
        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value
        self._input.focused = value

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()
        if kb.matches(data, "selectConfirm") or data == "\n":
            self._on_submit(self._input.get_value())
        elif kb.matches(data, "selectCancel"):
            self._on_cancel()
        else:
            self._input.handle_input(data)

    def dispose(self) -> None:
        if self._countdown is not None:
            self._countdown.dispose()
