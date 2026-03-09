"""Thinking level selector component."""

from __future__ import annotations

from collections.abc import Callable

from pi_coding_agent.modes.interactive.components._theme import get_select_list_theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_tui.components.select_list import SelectItem, SelectList
from pi_tui.tui import Container

_LEVEL_DESCRIPTIONS: dict[str, str] = {
    "off": "No reasoning",
    "minimal": "Very brief reasoning (~1k tokens)",
    "low": "Light reasoning (~2k tokens)",
    "medium": "Moderate reasoning (~8k tokens)",
    "high": "Deep reasoning (~16k tokens)",
    "xhigh": "Maximum reasoning (~32k tokens)",
}


class ThinkingSelectorComponent(Container):
    """Selector for reasoning depth levels (off/minimal/low/medium/high/xhigh)."""

    def __init__(
        self,
        current_level: str,
        available_levels: list[str],
        on_select: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__()

        thinking_levels = [
            SelectItem(
                value=level,
                label=level,
                description=_LEVEL_DESCRIPTIONS.get(level, ""),
            )
            for level in available_levels
        ]

        self.add_child(DynamicBorder())

        self._select_list = SelectList(thinking_levels, len(thinking_levels), get_select_list_theme())
        current_idx = next((i for i, item in enumerate(thinking_levels) if item.value == current_level), -1)
        if current_idx >= 0:
            self._select_list.set_selected_index(current_idx)

        self._select_list.on_select = lambda item: on_select(item.value)
        self._select_list.on_cancel = on_cancel

        self.add_child(self._select_list)
        self.add_child(DynamicBorder())

    def get_select_list(self) -> SelectList:
        return self._select_list
