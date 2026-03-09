"""TUI component for managing package resources (enable/disable)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.keybinding_hints import raw_key_hint
from pi_tui.components.input import Input
from pi_tui.components.spacer import Spacer
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.tui import Container
from pi_tui.utils import truncate_to_width, visible_width

ResourceType = Literal["extensions", "skills", "prompts", "themes"]

_RESOURCE_TYPE_LABELS: dict[str, str] = {
    "extensions": "Extensions",
    "skills": "Skills",
    "prompts": "Prompts",
    "themes": "Themes",
}


@dataclass
class PathMetadata:
    origin: Literal["package", "top-level"]
    scope: Literal["user", "project"]
    source: str
    base_dir: str | None = None


@dataclass
class ResolvedResource:
    path: str
    enabled: bool
    metadata: PathMetadata


@dataclass
class ResolvedPaths:
    extensions: list[ResolvedResource] = field(default_factory=list)
    skills: list[ResolvedResource] = field(default_factory=list)
    prompts: list[ResolvedResource] = field(default_factory=list)
    themes: list[ResolvedResource] = field(default_factory=list)


@dataclass
class ResourceItem:
    path: str
    enabled: bool
    metadata: PathMetadata
    resource_type: ResourceType
    display_name: str
    group_key: str
    subgroup_key: str


@dataclass
class ResourceSubgroup:
    type: ResourceType
    label: str
    items: list[ResourceItem] = field(default_factory=list)


@dataclass
class ResourceGroup:
    key: str
    label: str
    scope: Literal["user", "project"]
    origin: Literal["package", "top-level"]
    source: str
    subgroups: list[ResourceSubgroup] = field(default_factory=list)


def _get_group_label(metadata: PathMetadata) -> str:
    if metadata.origin == "package":
        return f"{metadata.source} ({metadata.scope})"
    if metadata.source == "auto":
        return "User (~/.pi/agent/)" if metadata.scope == "user" else "Project (.pi/)"
    return "User settings" if metadata.scope == "user" else "Project settings"


def build_groups(resolved: ResolvedPaths) -> list[ResourceGroup]:
    """Build hierarchical resource groups from resolved paths."""
    group_map: dict[str, ResourceGroup] = {}

    def add_to_group(resources: list[ResolvedResource], resource_type: ResourceType) -> None:
        for res in resources:
            group_key = f"{res.metadata.origin}:{res.metadata.scope}:{res.metadata.source}"
            if group_key not in group_map:
                group_map[group_key] = ResourceGroup(
                    key=group_key,
                    label=_get_group_label(res.metadata),
                    scope=res.metadata.scope,
                    origin=res.metadata.origin,
                    source=res.metadata.source,
                )

            group = group_map[group_key]
            subgroup_key = f"{group_key}:{resource_type}"

            subgroup = next((sg for sg in group.subgroups if sg.type == resource_type), None)
            if subgroup is None:
                subgroup = ResourceSubgroup(
                    type=resource_type,
                    label=_RESOURCE_TYPE_LABELS[resource_type],
                )
                group.subgroups.append(subgroup)

            file_name = os.path.basename(res.path)
            parent_folder = os.path.basename(os.path.dirname(res.path))
            if resource_type == "extensions" and parent_folder != "extensions":
                display_name = f"{parent_folder}/{file_name}"
            elif resource_type == "skills" and file_name == "SKILL.md":
                display_name = parent_folder
            else:
                display_name = file_name

            subgroup.items.append(
                ResourceItem(
                    path=res.path,
                    enabled=res.enabled,
                    metadata=res.metadata,
                    resource_type=resource_type,
                    display_name=display_name,
                    group_key=group_key,
                    subgroup_key=subgroup_key,
                )
            )

    add_to_group(resolved.extensions, "extensions")
    add_to_group(resolved.skills, "skills")
    add_to_group(resolved.prompts, "prompts")
    add_to_group(resolved.themes, "themes")

    groups = list(group_map.values())
    groups.sort(key=lambda g: (0 if g.origin == "package" else 1, 0 if g.scope == "user" else 1, g.source))

    type_order = {"extensions": 0, "skills": 1, "prompts": 2, "themes": 3}
    for group in groups:
        group.subgroups.sort(key=lambda sg: type_order[sg.type])
        for sg in group.subgroups:
            sg.items.sort(key=lambda item: item.display_name)

    return groups


FlatEntry = dict[str, Any]  # {"type": "group"|"subgroup"|"item", ...}


class _ConfigSelectorHeader:
    def invalidate(self) -> None:
        pass

    def render(self, width: int) -> list[str]:
        title = theme.bold("Resource Configuration")
        sep = theme.fg("muted", " · ")
        hint = raw_key_hint("space", "toggle") + sep + raw_key_hint("esc", "close")
        hint_width = visible_width(hint)
        title_width = visible_width(title)
        spacing = max(1, width - title_width - hint_width)
        return [
            truncate_to_width(f"{title}{' ' * spacing}{hint}", width, ""),
            theme.fg("muted", "Type to filter resources"),
        ]


class _ResourceList:
    def __init__(
        self,
        groups: list[ResourceGroup],
        settings_manager: object,
        cwd: str,
        agent_dir: str,
    ) -> None:
        self._groups = groups
        self._settings_manager = settings_manager
        self._cwd = cwd
        self._agent_dir = agent_dir
        self._search_input = Input()
        self._max_visible = 15
        self._flat_items: list[FlatEntry] = []
        self._filtered_items: list[FlatEntry] = []
        self._selected_index = 0
        self._focused = False

        self.on_cancel: object = None
        self.on_exit: object = None
        self.on_toggle: object = None

        self._build_flat_list()
        self._filtered_items = list(self._flat_items)

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value
        self._search_input.focused = value

    def _build_flat_list(self) -> None:
        self._flat_items = []
        for group in self._groups:
            self._flat_items.append({"type": "group", "group": group})
            for subgroup in group.subgroups:
                self._flat_items.append({"type": "subgroup", "subgroup": subgroup, "group": group})
                for item in subgroup.items:
                    self._flat_items.append({"type": "item", "item": item})
        idx = next((i for i, e in enumerate(self._flat_items) if e["type"] == "item"), 0)
        self._selected_index = idx

    def _find_next_item(self, from_index: int, direction: int) -> int:
        idx = from_index + direction
        while 0 <= idx < len(self._filtered_items):
            if self._filtered_items[idx]["type"] == "item":
                return idx
            idx += direction
        return from_index

    def _filter_items(self, query: str) -> None:
        if not query.strip():
            self._filtered_items = list(self._flat_items)
            self._select_first_item()
            return

        lq = query.lower()
        matching_items: set[str] = set()
        for entry in self._flat_items:
            if entry["type"] == "item":
                item: ResourceItem = entry["item"]
                if lq in item.display_name.lower() or lq in item.resource_type.lower() or lq in item.path.lower():
                    matching_items.add(item.path)

        matching_subgroups: set[str] = set()
        matching_groups: set[str] = set()
        for group in self._groups:
            for subgroup in group.subgroups:
                for item in subgroup.items:
                    if item.path in matching_items:
                        matching_subgroups.add(subgroup.label + group.key)
                        matching_groups.add(group.key)

        self._filtered_items = []
        for entry in self._flat_items:
            if entry["type"] == "group" and entry["group"].key in matching_groups:
                self._filtered_items.append(entry)
            elif entry["type"] == "subgroup":
                sg: ResourceSubgroup = entry["subgroup"]
                g: ResourceGroup = entry["group"]
                if (sg.label + g.key) in matching_subgroups:
                    self._filtered_items.append(entry)
            elif entry["type"] == "item" and entry["item"].path in matching_items:
                self._filtered_items.append(entry)

        self._select_first_item()

    def _select_first_item(self) -> None:
        idx = next((i for i, e in enumerate(self._filtered_items) if e["type"] == "item"), 0)
        self._selected_index = idx

    def update_item(self, item: ResourceItem, enabled: bool) -> None:
        item.enabled = enabled

    def invalidate(self) -> None:
        pass

    def render(self, width: int) -> list[str]:
        lines: list[str] = []
        lines.extend(self._search_input.render(width))
        lines.append("")

        if not self._filtered_items:
            lines.append(theme.fg("muted", "  No resources found"))
            return lines

        start = max(
            0,
            min(
                self._selected_index - self._max_visible // 2,
                len(self._filtered_items) - self._max_visible,
            ),
        )
        end = min(start + self._max_visible, len(self._filtered_items))

        for i in range(start, end):
            entry = self._filtered_items[i]
            is_selected = i == self._selected_index
            if entry["type"] == "group":
                g: ResourceGroup = entry["group"]
                lines.append(truncate_to_width(f"  {theme.fg('accent', theme.bold(g.label))}", width, ""))
            elif entry["type"] == "subgroup":
                sg2: ResourceSubgroup = entry["subgroup"]
                lines.append(truncate_to_width(f"    {theme.fg('muted', sg2.label)}", width, ""))
            else:
                item2: ResourceItem = entry["item"]
                cursor = "> " if is_selected else "  "
                checkbox = theme.fg("success", "[x]") if item2.enabled else theme.fg("dim", "[ ]")
                name = theme.bold(item2.display_name) if is_selected else item2.display_name
                lines.append(truncate_to_width(f"{cursor}    {checkbox} {name}", width, "..."))

        if start > 0 or end < len(self._filtered_items):
            lines.append(theme.fg("dim", f"  ({self._selected_index + 1}/{len(self._filtered_items)})"))

        return lines

    def handle_input(self, data: str) -> None:
        from pi_tui.keys import matches_key

        kb = get_editor_keybindings()
        if kb.matches(data, "selectUp"):
            self._selected_index = self._find_next_item(self._selected_index, -1)
            return
        if kb.matches(data, "selectDown"):
            self._selected_index = self._find_next_item(self._selected_index, 1)
            return
        if kb.matches(data, "selectCancel"):
            if callable(self.on_cancel):
                self.on_cancel()
            return
        if matches_key(data, "ctrl+c"):
            if callable(self.on_exit):
                self.on_exit()
            return
        if data == " " or kb.matches(data, "selectConfirm"):
            entry = self._filtered_items[self._selected_index] if self._filtered_items else None
            if entry and entry["type"] == "item":
                item3: ResourceItem = entry["item"]
                new_enabled = not item3.enabled
                self.update_item(item3, new_enabled)
                if callable(self.on_toggle):
                    self.on_toggle(item3, new_enabled)
            return
        self._search_input.handle_input(data)
        self._filter_items(self._search_input.get_value())


class ConfigSelectorComponent(Container):
    """Full resource configuration selector with search and toggle support."""

    def __init__(
        self,
        resolved_paths: ResolvedPaths,
        settings_manager: object,
        cwd: str,
        agent_dir: str,
        on_close: object,
        on_exit: object,
        request_render: object,
    ) -> None:
        super().__init__()

        groups = build_groups(resolved_paths)

        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())
        self.add_child(Spacer(1))
        self.add_child(_ConfigSelectorHeader())
        self.add_child(Spacer(1))

        self._resource_list = _ResourceList(groups, settings_manager, cwd, agent_dir)
        self._resource_list.on_cancel = on_close
        self._resource_list.on_exit = on_exit
        self._resource_list.on_toggle = lambda item, enabled: request_render() if callable(request_render) else None
        self.add_child(self._resource_list)

        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())

    @property
    def focused(self) -> bool:
        return self._resource_list.focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._resource_list.focused = value

    def get_resource_list(self) -> _ResourceList:
        return self._resource_list
