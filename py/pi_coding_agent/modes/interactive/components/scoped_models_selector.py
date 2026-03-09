"""Model enable/disable selector for Ctrl+P cycling (session-scoped, optional persist)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_tui.components.input import Input
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.fuzzy import fuzzy_filter
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.keys import matches_key
from pi_tui.tui import Container

# EnabledIds: None = all enabled (no filter); list[str] = explicit ordered list
EnabledIds = list[str] | None


def _is_enabled(enabled_ids: EnabledIds, id_: str) -> bool:
    return enabled_ids is None or id_ in enabled_ids


def _toggle(enabled_ids: EnabledIds, id_: str) -> EnabledIds:
    if enabled_ids is None:
        return [id_]  # First toggle: start with only this one
    result = list(enabled_ids)
    if id_ in result:
        result.remove(id_)
        return result
    result.append(id_)
    return result


def _enable_all(enabled_ids: EnabledIds, all_ids: list[str], target_ids: list[str] | None = None) -> EnabledIds:
    if enabled_ids is None:
        return None  # Already all enabled
    targets = target_ids if target_ids is not None else all_ids
    result = list(enabled_ids)
    for id_ in targets:
        if id_ not in result:
            result.append(id_)
    return None if len(result) == len(all_ids) else result


def _clear_all(enabled_ids: EnabledIds, all_ids: list[str], target_ids: list[str] | None = None) -> EnabledIds:
    if enabled_ids is None:
        return [id_ for id_ in all_ids if target_ids is None or id_ not in target_ids]
    targets = set(target_ids if target_ids is not None else enabled_ids)
    return [id_ for id_ in enabled_ids if id_ not in targets]


def _move(enabled_ids: EnabledIds, all_ids: list[str], id_: str, delta: int) -> EnabledIds:
    lst = list(enabled_ids) if enabled_ids is not None else list(all_ids)
    if id_ not in lst:
        return lst
    idx = lst.index(id_)
    new_idx = idx + delta
    if new_idx < 0 or new_idx >= len(lst):
        return lst
    lst[idx], lst[new_idx] = lst[new_idx], lst[idx]
    return lst


def _get_sorted_ids(enabled_ids: EnabledIds, all_ids: list[str]) -> list[str]:
    if enabled_ids is None:
        return list(all_ids)
    enabled_set = set(enabled_ids)
    return list(enabled_ids) + [id_ for id_ in all_ids if id_ not in enabled_set]


@dataclass
class ModelsConfig:
    all_models: list[Any]
    enabled_model_ids: set[str]
    has_enabled_models_filter: bool  # True if enabledModels setting is defined


@dataclass
class ModelsCallbacks:
    on_model_toggle: Callable[[str, bool], None]
    on_persist: Callable[[list[str]], None]
    on_enable_all: Callable[[list[str]], None]
    on_clear_all: Callable[[], None]
    on_toggle_provider: Callable[[str, list[str], bool], None]
    on_cancel: Callable[[], None]


@dataclass
class _ModelItem:
    full_id: str
    model: Any
    enabled: bool


class ScopedModelsSelectorComponent(Container):
    """Enable/disable models for Ctrl+P cycling. Changes are session-only until Ctrl+S."""

    def __init__(self, config: ModelsConfig, callbacks: ModelsCallbacks) -> None:
        super().__init__()
        self._callbacks = callbacks
        self._models_by_id: dict[str, Any] = {}
        self._all_ids: list[str] = []
        self._enabled_ids: EnabledIds = None
        self._filtered_items: list[_ModelItem] = []
        self._selected_index = 0
        self._max_visible = 15
        self._is_dirty = False
        self._focused = False

        for model in config.all_models:
            full_id = f"{getattr(model, 'provider', '')}/{getattr(model, 'id', model)}"
            self._models_by_id[full_id] = model
            self._all_ids.append(full_id)

        # Preserve catalog order for enabled models (set has non-deterministic iteration order)
        if config.has_enabled_models_filter:
            self._enabled_ids = [id_ for id_ in self._all_ids if id_ in config.enabled_model_ids]
        else:
            self._enabled_ids = None
        self._filtered_items = self._build_items()

        self.add_child(DynamicBorder())
        self.add_child(Spacer(1))
        self.add_child(Text(theme.fg("accent", theme.bold("Model Configuration")), 0, 0))
        self.add_child(Text(theme.fg("muted", "Session-only. Ctrl+S to save to settings."), 0, 0))
        self.add_child(Spacer(1))

        self._search_input = Input()
        self.add_child(self._search_input)
        self.add_child(Spacer(1))

        self._list_container = Container()
        self.add_child(self._list_container)

        self.add_child(Spacer(1))
        self._footer_text = Text(self._get_footer_text(), 0, 0)
        self.add_child(self._footer_text)
        self.add_child(DynamicBorder())

        self._update_list()

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value
        self._search_input.focused = value

    def _build_items(self) -> list[_ModelItem]:
        return [
            _ModelItem(
                full_id=id_,
                model=self._models_by_id[id_],
                enabled=_is_enabled(self._enabled_ids, id_),
            )
            for id_ in _get_sorted_ids(self._enabled_ids, self._all_ids)
            if id_ in self._models_by_id
        ]

    def _get_footer_text(self) -> str:
        enabled_count = len(self._enabled_ids) if self._enabled_ids is not None else len(self._all_ids)
        all_enabled = self._enabled_ids is None
        count_text = "all enabled" if all_enabled else f"{enabled_count}/{len(self._all_ids)} enabled"
        parts = ["Enter toggle", "^A all", "^X clear", "^P provider", "Alt+\u2191\u2193 reorder", "^S save", count_text]
        combined = "  " + " \u00b7 ".join(parts) + " "
        if self._is_dirty:
            return theme.fg("dim", combined) + theme.fg("warning", "(unsaved)")
        return theme.fg("dim", combined)

    def _refresh(self) -> None:
        query = self._search_input.get_value()
        items = self._build_items()
        if query:
            self._filtered_items = fuzzy_filter(
                items,
                query,
                lambda i: f"{getattr(i.model, 'id', '')} {getattr(i.model, 'provider', '')}",
            )
        else:
            self._filtered_items = items
        self._selected_index = min(self._selected_index, max(0, len(self._filtered_items) - 1))
        self._update_list()
        self._footer_text.set_text(self._get_footer_text())

    def _update_list(self) -> None:
        self._list_container.clear()
        if not self._filtered_items:
            self._list_container.add_child(Text(theme.fg("muted", "  No matching models"), 0, 0))
            return

        scroll_max = len(self._filtered_items) - self._max_visible
        start = max(0, min(self._selected_index - self._max_visible // 2, scroll_max))
        end = min(start + self._max_visible, len(self._filtered_items))
        all_enabled = self._enabled_ids is None

        for i in range(start, end):
            item = self._filtered_items[i]
            is_selected = i == self._selected_index
            prefix = theme.fg("accent", "\u2192 ") if is_selected else "  "
            model_text = theme.fg("accent", item.model.id) if is_selected else getattr(item.model, "id", item.full_id)
            provider_badge = theme.fg("muted", f" [{getattr(item.model, 'provider', '')}]")
            if all_enabled:
                status = ""
            elif item.enabled:
                status = theme.fg("success", " \u2713")
            else:
                status = theme.fg("dim", " \u2717")
            self._list_container.add_child(Text(f"{prefix}{model_text}{provider_badge}{status}", 0, 0))

        if start > 0 or end < len(self._filtered_items):
            self._list_container.add_child(
                Text(theme.fg("muted", f"  ({self._selected_index + 1}/{len(self._filtered_items)})"), 0, 0)
            )

        if self._filtered_items:
            selected = self._filtered_items[self._selected_index]
            self._list_container.add_child(Spacer(1))
            model_name = getattr(selected.model, "name", getattr(selected.model, "id", ""))
            self._list_container.add_child(Text(theme.fg("muted", f"  Model Name: {model_name}"), 0, 0))

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()

        if kb.matches(data, "selectUp"):
            if self._filtered_items:
                self._selected_index = (self._selected_index - 1) % len(self._filtered_items)
                self._update_list()
            return
        if kb.matches(data, "selectDown"):
            if self._filtered_items:
                self._selected_index = (self._selected_index + 1) % len(self._filtered_items)
                self._update_list()
            return

        # Alt+Up/Down: reorder enabled models
        if matches_key(data, "alt+up") or matches_key(data, "alt+down"):
            item = self._filtered_items[self._selected_index] if self._filtered_items else None
            if item and _is_enabled(self._enabled_ids, item.full_id):
                delta = -1 if matches_key(data, "alt+up") else 1
                enabled_list = self._enabled_ids if self._enabled_ids is not None else self._all_ids
                current_idx = enabled_list.index(item.full_id) if item.full_id in enabled_list else -1
                new_idx = current_idx + delta
                if 0 <= new_idx < len(enabled_list):
                    self._enabled_ids = _move(self._enabled_ids, self._all_ids, item.full_id, delta)
                    self._is_dirty = True
                    self._selected_index += delta
                    self._refresh()
            return

        if matches_key(data, "enter"):
            if self._filtered_items:
                item = self._filtered_items[self._selected_index]
                was_all = self._enabled_ids is None
                self._enabled_ids = _toggle(self._enabled_ids, item.full_id)
                self._is_dirty = True
                if was_all:
                    self._callbacks.on_clear_all()
                self._callbacks.on_model_toggle(item.full_id, _is_enabled(self._enabled_ids, item.full_id))
                self._refresh()
            return

        if matches_key(data, "ctrl+a"):
            target_ids = [i.full_id for i in self._filtered_items] if self._search_input.get_value() else None
            self._enabled_ids = _enable_all(self._enabled_ids, self._all_ids, target_ids)
            self._is_dirty = True
            self._callbacks.on_enable_all(target_ids if target_ids is not None else self._all_ids)
            self._refresh()
            return

        if matches_key(data, "ctrl+x"):
            target_ids = [i.full_id for i in self._filtered_items] if self._search_input.get_value() else None
            self._enabled_ids = _clear_all(self._enabled_ids, self._all_ids, target_ids)
            self._is_dirty = True
            self._callbacks.on_clear_all()
            self._refresh()
            return

        if matches_key(data, "ctrl+p"):
            if self._filtered_items:
                item = self._filtered_items[self._selected_index]
                provider = getattr(item.model, "provider", "")
                provider_ids = [
                    id_ for id_ in self._all_ids if getattr(self._models_by_id.get(id_), "provider", "") == provider
                ]
                all_enabled = all(_is_enabled(self._enabled_ids, id_) for id_ in provider_ids)
                if all_enabled:
                    self._enabled_ids = _clear_all(self._enabled_ids, self._all_ids, provider_ids)
                else:
                    self._enabled_ids = _enable_all(self._enabled_ids, self._all_ids, provider_ids)
                self._is_dirty = True
                self._callbacks.on_toggle_provider(provider, provider_ids, not all_enabled)
                self._refresh()
            return

        if matches_key(data, "ctrl+s"):
            persist_ids = list(self._enabled_ids) if self._enabled_ids is not None else list(self._all_ids)
            self._callbacks.on_persist(persist_ids)
            self._is_dirty = False
            self._footer_text.set_text(self._get_footer_text())
            return

        if matches_key(data, "ctrl+c"):
            if self._search_input.get_value():
                self._search_input.set_value("")
                self._refresh()
            else:
                self._callbacks.on_cancel()
            return

        if matches_key(data, "escape"):
            self._callbacks.on_cancel()
            return

        self._search_input.handle_input(data)
        self._refresh()

    def get_search_input(self) -> Input:
        return self._search_input
