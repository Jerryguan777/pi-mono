"""Theme selector component with live preview on selection change."""

from __future__ import annotations

from collections.abc import Callable

from pi_coding_agent.modes.interactive.components._theme import get_available_themes, get_select_list_theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_tui.components.select_list import SelectItem, SelectList
from pi_tui.tui import Container


class ThemeSelectorComponent(Container):
    """Keyboard-navigable theme list with live preview on cursor movement."""

    def __init__(
        self,
        current_theme: str,
        on_select: Callable[[str], None],
        on_cancel: Callable[[], None],
        on_preview: Callable[[str], None],
    ) -> None:
        super().__init__()
        self._on_preview = on_preview

        themes = get_available_themes()
        theme_items = [
            SelectItem(
                value=name,
                label=name,
                description="(current)" if name == current_theme else None,
            )
            for name in themes
        ]

        self.add_child(DynamicBorder())

        self._select_list = SelectList(theme_items, 10, get_select_list_theme())
        current_idx = themes.index(current_theme) if current_theme in themes else -1
        if current_idx >= 0:
            self._select_list.set_selected_index(current_idx)

        self._select_list.on_select = lambda item: on_select(item.value)
        self._select_list.on_cancel = on_cancel
        self._select_list.on_selection_change = lambda item: on_preview(item.value)

        self.add_child(self._select_list)
        self.add_child(DynamicBorder())

    def get_select_list(self) -> SelectList:
        return self._select_list
