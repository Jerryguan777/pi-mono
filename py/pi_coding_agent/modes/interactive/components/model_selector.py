"""Model selector component with search and scoped/all toggle."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.keybinding_hints import key_hint
from pi_tui.components.input import Input
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.fuzzy import fuzzy_filter
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.tui import Container

if TYPE_CHECKING:
    from pi_tui.tui import TUI


def _models_are_equal(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    return getattr(a, "id", None) == getattr(b, "id", None) and getattr(a, "provider", None) == getattr(
        b, "provider", None
    )


class ModelSelectorComponent(Container):
    """Model selector with fuzzy search, scope toggle (all/scoped), and keybindings."""

    def __init__(
        self,
        tui: TUI,
        current_model: Any,
        settings_manager: Any,
        model_registry: Any,
        scoped_models: list[Any],
        on_select: Callable[[Any], None],
        on_cancel: Callable[[], None],
        initial_search_input: str | None = None,
    ) -> None:
        super().__init__()
        self._tui = tui
        self._current_model = current_model
        self._settings_manager = settings_manager
        self._model_registry = model_registry
        self._scoped_models = scoped_models
        self._on_select = on_select
        self._on_cancel = on_cancel
        self._focused = False

        self._scope: str = "scoped" if scoped_models else "all"
        self._all_models: list[Any] = []
        self._scoped_model_items: list[Any] = []
        self._active_models: list[Any] = []
        self._filtered_models: list[Any] = []
        self._selected_index = 0
        self._error_message: str | None = None

        self.add_child(DynamicBorder())
        self.add_child(Spacer(1))

        self._scope_text: Text | None = None
        self._scope_hint_text: Text | None = None

        if scoped_models:
            self._scope_text = Text(self._get_scope_text(), 0, 0)
            self.add_child(self._scope_text)
            self._scope_hint_text = Text(self._get_scope_hint_text(), 0, 0)
            self.add_child(self._scope_hint_text)
        else:
            self.add_child(
                Text(
                    theme.fg("warning", "Only showing models with configured API keys (see README for details)"),
                    0,
                    0,
                )
            )

        self.add_child(Spacer(1))

        self._search_input = Input()
        if initial_search_input:
            self._search_input.set_value(initial_search_input)
        self._search_input.on_submit = self._on_search_submit
        self.add_child(self._search_input)
        self.add_child(Spacer(1))

        self._list_container = Container()
        self.add_child(self._list_container)
        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())

        self._load_models(initial_search_input)

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value
        self._search_input.focused = value

    def _get_scope_text(self) -> str:
        all_text = theme.fg("accent", "all") if self._scope == "all" else theme.fg("muted", "all")
        scoped_text = theme.fg("accent", "scoped") if self._scope == "scoped" else theme.fg("muted", "scoped")
        return f"{theme.fg('muted', 'Scope: ')}{all_text}{theme.fg('muted', ' | ')}{scoped_text}"

    def _get_scope_hint_text(self) -> str:
        return key_hint("tab", "scope") + theme.fg("muted", " (all/scoped)")

    def _load_models(self, initial_query: str | None = None) -> None:
        """Load models synchronously (async not available in Python port)."""
        if hasattr(self._model_registry, "refresh"):
            self._model_registry.refresh()

        load_error = self._model_registry.get_error() if hasattr(self._model_registry, "get_error") else None
        if load_error:
            self._error_message = load_error

        try:
            if hasattr(self._model_registry, "get_available"):
                available = self._model_registry.get_available()
                if hasattr(available, "__await__"):
                    # Fallback: skip async
                    available = []
            else:
                available = []

            self._all_models = self._sort_models(list(available))
            self._scoped_model_items = self._sort_models([getattr(s, "model", s) for s in self._scoped_models])
            self._active_models = self._scoped_model_items if self._scope == "scoped" else self._all_models
            self._filtered_models = list(self._active_models)
            self._selected_index = min(self._selected_index, max(0, len(self._filtered_models) - 1))
        except Exception as exc:
            self._error_message = str(exc)
            self._all_models = []
            self._scoped_model_items = []
            self._active_models = []
            self._filtered_models = []

        if initial_query:
            self._filter_models(initial_query)
        else:
            self._update_list()

        self._tui.request_render()

    def _sort_models(self, models: list[Any]) -> list[Any]:
        def key(m: Any) -> tuple[int, str]:
            is_current = _models_are_equal(self._current_model, m)
            return (0 if is_current else 1, getattr(m, "provider", ""))

        return sorted(models, key=key)

    def _set_scope(self, scope: str) -> None:
        if self._scope == scope:
            return
        self._scope = scope
        self._active_models = self._scoped_model_items if scope == "scoped" else self._all_models
        self._selected_index = 0
        self._filter_models(self._search_input.get_value())
        if self._scope_text is not None:
            self._scope_text.set_text(self._get_scope_text())

    def _filter_models(self, query: str) -> None:
        if query:
            self._filtered_models = fuzzy_filter(
                self._active_models,
                query,
                lambda m: f"{getattr(m, 'id', '')} {getattr(m, 'provider', '')}",
            )
        else:
            self._filtered_models = list(self._active_models)
        self._selected_index = min(self._selected_index, max(0, len(self._filtered_models) - 1))
        self._update_list()

    def _update_list(self) -> None:
        self._list_container.clear()
        max_visible = 10
        start = max(0, min(self._selected_index - max_visible // 2, len(self._filtered_models) - max_visible))
        end = min(start + max_visible, len(self._filtered_models))

        for i in range(start, end):
            item = self._filtered_models[i]
            is_selected = i == self._selected_index
            is_current = _models_are_equal(self._current_model, item)
            checkmark = theme.fg("success", " \u2713") if is_current else ""
            model_id = getattr(item, "id", str(item))
            provider = getattr(item, "provider", "")
            provider_badge = theme.fg("muted", f"[{provider}]")
            if is_selected:
                arrow = theme.fg("accent", chr(8594) + " ")
                line = f"{arrow}{theme.fg('accent', model_id)} {provider_badge}{checkmark}"
            else:
                line = f"  {model_id} {provider_badge}{checkmark}"
            self._list_container.add_child(Text(line, 0, 0))

        if start > 0 or end < len(self._filtered_models):
            self._list_container.add_child(
                Text(theme.fg("muted", f"  ({self._selected_index + 1}/{len(self._filtered_models)})"), 0, 0)
            )

        if self._error_message:
            for line in self._error_message.split("\n"):
                self._list_container.add_child(Text(theme.fg("error", line), 0, 0))
        elif not self._filtered_models:
            self._list_container.add_child(Text(theme.fg("muted", "  No matching models"), 0, 0))
        elif self._filtered_models:
            selected = self._filtered_models[self._selected_index]
            self._list_container.add_child(Spacer(1))
            self._list_container.add_child(
                Text(theme.fg("muted", f"  Model Name: {getattr(selected, 'name', getattr(selected, 'id', ''))}"), 0, 0)
            )

    def _on_search_submit(self, _value: str | None = None) -> None:
        if self._filtered_models:
            self._handle_select(self._filtered_models[self._selected_index])

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()
        if kb.matches(data, "tab"):
            if self._scoped_model_items:
                next_scope = "all" if self._scope == "scoped" else "scoped"
                self._set_scope(next_scope)
                if self._scope_hint_text is not None:
                    self._scope_hint_text.set_text(self._get_scope_hint_text())
            return
        if kb.matches(data, "selectUp"):
            if self._filtered_models:
                self._selected_index = (self._selected_index - 1) % len(self._filtered_models)
                self._update_list()
        elif kb.matches(data, "selectDown"):
            if self._filtered_models:
                self._selected_index = (self._selected_index + 1) % len(self._filtered_models)
                self._update_list()
        elif kb.matches(data, "selectConfirm"):
            if self._filtered_models:
                self._handle_select(self._filtered_models[self._selected_index])
        elif kb.matches(data, "selectCancel"):
            self._on_cancel()
        else:
            self._search_input.handle_input(data)
            self._filter_models(self._search_input.get_value())

    def _handle_select(self, model: Any) -> None:
        if hasattr(self._settings_manager, "set_default_model_and_provider"):
            self._settings_manager.set_default_model_and_provider(
                getattr(model, "provider", ""),
                getattr(model, "id", ""),
            )
        self._on_select(model)

    def get_search_input(self) -> Input:
        return self._search_input
