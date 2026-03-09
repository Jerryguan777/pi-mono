"""Session tree selector with ASCII art visualization and filter modes."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.keybinding_hints import key_hint
from pi_tui.components.input import Input
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.components.truncated_text import TruncatedText
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.keys import matches_key
from pi_tui.tui import Container
from pi_tui.utils import truncate_to_width

FilterMode = Literal["default", "no-tools", "user-only", "labeled-only", "all"]


@dataclass
class _GutterInfo:
    position: int
    show: bool


@dataclass
class _FlatNode:
    node: Any
    indent: int
    show_connector: bool
    is_last: bool
    gutters: list[_GutterInfo]
    is_virtual_root_child: bool


def _shorten_path(p: str) -> str:
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or ""
    if home and p.startswith(home):
        return f"~{p[len(home) :]}"
    return p


class _TreeList:
    def __init__(
        self,
        tree: list[Any],
        current_leaf_id: str | None,
        max_visible_lines: int,
        initial_selected_id: str | None = None,
    ) -> None:
        self._current_leaf_id = current_leaf_id
        self._max_visible_lines = max_visible_lines
        self._filter_mode: FilterMode = "default"
        self._search_query = ""
        self._tool_call_map: dict[str, dict[str, Any]] = {}
        self._multiple_roots = len(tree) > 1
        self._active_path_ids: set[str] = set()
        self._last_selected_id: str | None = None
        self._flat_nodes: list[_FlatNode] = []
        self._filtered_nodes: list[_FlatNode] = []
        self._selected_index = 0

        self.on_select: Callable[[str], None] | None = None
        self.on_cancel: Callable[[], None] | None = None
        self.on_label_edit: Callable[[str, str | None], None] | None = None

        self._flat_nodes = self._flatten_tree(tree)
        self._build_active_path()
        self._apply_filter()

        target_id = initial_selected_id or current_leaf_id
        self._selected_index = self._find_nearest_visible_index(target_id)
        if self._filtered_nodes:
            selected_entry = self._filtered_nodes[self._selected_index].node.entry
            self._last_selected_id = getattr(selected_entry, "id", None) if self._filtered_nodes else None

    def _find_nearest_visible_index(self, entry_id: str | None) -> int:
        if not self._filtered_nodes:
            return 0
        entry_map = {getattr(n.node.entry, "id", None): n for n in self._flat_nodes}
        visible_id_to_index = {getattr(n.node.entry, "id", None): i for i, n in enumerate(self._filtered_nodes)}

        current_id = entry_id
        while current_id is not None:
            idx = visible_id_to_index.get(current_id)
            if idx is not None:
                return idx
            node = entry_map.get(current_id)
            if node is None:
                break
            current_id = getattr(getattr(node.node, "entry", None), "parent_id", None)
        return max(0, len(self._filtered_nodes) - 1)

    def _build_active_path(self) -> None:
        self._active_path_ids.clear()
        if not self._current_leaf_id:
            return
        entry_map = {getattr(n.node.entry, "id", None): n for n in self._flat_nodes}
        current_id: str | None = self._current_leaf_id
        while current_id:
            self._active_path_ids.add(current_id)
            node = entry_map.get(current_id)
            if node is None:
                break
            current_id = getattr(getattr(node.node, "entry", None), "parent_id", None)

    def _flatten_tree(self, roots: list[Any]) -> list[_FlatNode]:
        result: list[_FlatNode] = []
        self._tool_call_map.clear()

        # Pre-compute which subtrees contain the active leaf
        contains_active: dict[int, bool] = {}
        all_nodes: list[Any] = []
        pre_stack = list(roots)
        while pre_stack:
            node = pre_stack.pop()
            all_nodes.append(node)
            pre_stack.extend(reversed(node.children))

        leaf_id = self._current_leaf_id
        for node in reversed(all_nodes):
            entry_id = getattr(getattr(node, "entry", None), "id", None)
            has = leaf_id is not None and entry_id == leaf_id
            for child in node.children:
                if contains_active.get(id(child)):
                    has = True
            contains_active[id(node)] = has

        multiple_roots = len(roots) > 1
        ordered_roots = sorted(roots, key=lambda n: 0 if contains_active.get(id(n)) else 1)
        stack: list[tuple[Any, int, bool, bool, bool, list[_GutterInfo], bool]] = []
        for i in range(len(ordered_roots) - 1, -1, -1):
            is_last = i == len(ordered_roots) - 1
            init_indent = 1 if multiple_roots else 0
            stack.append((ordered_roots[i], init_indent, multiple_roots, multiple_roots, is_last, [], multiple_roots))

        while stack:
            node, indent, just_branched, show_connector, is_last, gutters, is_virtual_root_child = stack.pop()

            entry = getattr(node, "entry", None)
            if entry and getattr(entry, "type", None) == "message":
                msg = getattr(entry, "message", None)
                if msg and getattr(msg, "role", None) == "assistant":
                    content = getattr(msg, "content", []) or []
                    if isinstance(content, list):
                        for block in content:
                            if getattr(block, "type", None) == "toolCall":
                                tc_id = getattr(block, "id", None)
                                if tc_id:
                                    self._tool_call_map[tc_id] = {
                                        "name": getattr(block, "name", ""),
                                        "arguments": getattr(block, "arguments", {}),
                                    }

            result.append(
                _FlatNode(
                    node=node,
                    indent=indent,
                    show_connector=show_connector,
                    is_last=is_last,
                    gutters=list(gutters),
                    is_virtual_root_child=is_virtual_root_child,
                )
            )

            children = list(node.children)
            multiple_children = len(children) > 1
            ordered_children = sorted(children, key=lambda c: 0 if contains_active.get(id(c)) else 1)

            child_indent = indent + 1 if multiple_children or (just_branched and indent > 0) else indent

            connector_displayed = show_connector and not is_virtual_root_child
            current_display_indent = max(0, indent - 1) if self._multiple_roots else indent
            connector_position = max(0, current_display_indent - 1)
            gutter_extra = [_GutterInfo(position=connector_position, show=not is_last)] if connector_displayed else []
            child_gutters = list(gutters) + gutter_extra

            for i in range(len(ordered_children) - 1, -1, -1):
                child_is_last = i == len(ordered_children) - 1
                stack.append(
                    (
                        ordered_children[i],
                        child_indent,
                        multiple_children,
                        multiple_children,
                        child_is_last,
                        child_gutters,
                        False,
                    )
                )

        return result

    def _apply_filter(self) -> None:
        if self._filtered_nodes:
            sel_entry = self._filtered_nodes[self._selected_index].node.entry
            lid = getattr(sel_entry, "id", None) if self._filtered_nodes else None
            if lid:
                self._last_selected_id = lid

        search_tokens = [t for t in self._search_query.lower().split() if t]

        def passes(flat_node: _FlatNode) -> bool:
            entry = flat_node.node.entry
            entry_id = getattr(entry, "id", None)
            is_current_leaf = entry_id == self._current_leaf_id

            if getattr(entry, "type", None) == "message":
                msg = getattr(entry, "message", None)
                if msg and getattr(msg, "role", None) == "assistant" and not is_current_leaf:
                    content = getattr(msg, "content", None)
                    has_text = self._has_text_content(content)
                    stop_reason = getattr(msg, "stop_reason", None)
                    is_error = stop_reason and stop_reason not in ("stop", "toolUse")
                    if not has_text and not is_error:
                        return False

            entry_type = getattr(entry, "type", None)
            is_settings = entry_type in ("label", "custom", "model_change", "thinking_level_change")

            if self._filter_mode == "user-only":
                ok = entry_type == "message" and getattr(getattr(entry, "message", None), "role", None) == "user"
            elif self._filter_mode == "no-tools":
                msg_role = getattr(getattr(entry, "message", None), "role", None)
                ok = not is_settings and not (entry_type == "message" and msg_role == "toolResult")
            elif self._filter_mode == "labeled-only":
                ok = flat_node.node.label is not None
            elif self._filter_mode == "all":
                ok = True
            else:
                ok = not is_settings

            if not ok:
                return False

            if search_tokens:
                node_text = self._get_searchable_text(flat_node.node).lower()
                return all(t in node_text for t in search_tokens)
            return True

        self._filtered_nodes = [n for n in self._flat_nodes if passes(n)]
        self._recalculate_visual_structure()

        if self._last_selected_id:
            self._selected_index = self._find_nearest_visible_index(self._last_selected_id)
        elif self._selected_index >= len(self._filtered_nodes):
            self._selected_index = max(0, len(self._filtered_nodes) - 1)

        if self._filtered_nodes:
            final_entry = self._filtered_nodes[self._selected_index].node.entry
            lid = getattr(final_entry, "id", None)
            if lid:
                self._last_selected_id = lid

    def _recalculate_visual_structure(self) -> None:
        if not self._filtered_nodes:
            return
        visible_ids = {getattr(n.node.entry, "id", None) for n in self._filtered_nodes}
        entry_map = {getattr(n.node.entry, "id", None): n for n in self._flat_nodes}

        def find_visible_ancestor(node_id: str) -> str | None:
            # Walk parent chain via entry_map
            n = entry_map.get(node_id)
            n_entry = getattr(getattr(n, "node", None), "entry", None) if n else None
            current_id: str | None = getattr(n_entry, "parent_id", None)
            while current_id is not None:
                if current_id in visible_ids:
                    return str(current_id)
                n2 = entry_map.get(current_id)
                n2_entry = getattr(getattr(n2, "node", None), "entry", None) if n2 else None
                current_id = getattr(n2_entry, "parent_id", None)
            return None

        visible_children: dict[str | None, list[str]] = {None: []}
        for flat_node in self._filtered_nodes:
            node_id: str | None = getattr(flat_node.node.entry, "id", None)
            if node_id is None:
                continue
            ancestor_id = find_visible_ancestor(node_id)
            if ancestor_id not in visible_children:
                visible_children[ancestor_id] = []
            visible_children[ancestor_id].append(node_id)

        visible_root_ids = visible_children.get(None, [])
        self._multiple_roots = len(visible_root_ids) > 1
        filtered_node_map = {getattr(n.node.entry, "id", None): n for n in self._filtered_nodes}

        stack: list[tuple[str, int, bool, bool, bool, list[_GutterInfo], bool]] = []
        for i in range(len(visible_root_ids) - 1, -1, -1):
            is_last = i == len(visible_root_ids) - 1
            r_indent = 1 if self._multiple_roots else 0
            stack.append(
                (
                    visible_root_ids[i],
                    r_indent,
                    self._multiple_roots,
                    self._multiple_roots,
                    is_last,
                    [],
                    self._multiple_roots,
                )
            )

        while stack:
            node_id, indent, just_branched, show_connector, is_last, gutters, is_vrc = stack.pop()
            fn: _FlatNode | None = filtered_node_map.get(node_id)
            if fn is None:
                continue
            fn.indent = indent
            fn.show_connector = show_connector
            fn.is_last = is_last
            fn.gutters = list(gutters)
            fn.is_virtual_root_child = is_vrc

            children = visible_children.get(node_id, [])
            multiple_children = len(children) > 1
            child_indent = indent + 1 if multiple_children else (indent + 1 if just_branched and indent > 0 else indent)
            connector_displayed = show_connector and not is_vrc
            cur_display = max(0, indent - 1) if self._multiple_roots else indent
            connector_pos = max(0, cur_display - 1)
            gutter_extra = [_GutterInfo(position=connector_pos, show=not is_last)] if connector_displayed else []
            child_gutters = list(gutters) + gutter_extra

            for i in range(len(children) - 1, -1, -1):
                child_is_last = i == len(children) - 1
                stack.append(
                    (
                        children[i],
                        child_indent,
                        multiple_children,
                        multiple_children,
                        child_is_last,
                        child_gutters,
                        False,
                    )
                )

    def _get_searchable_text(self, node: Any) -> str:
        entry = getattr(node, "entry", None)
        parts: list[str] = []
        label = getattr(node, "label", None)
        if label:
            parts.append(label)
        entry_type = getattr(entry, "type", None)
        if entry_type == "message":
            msg = getattr(entry, "message", None)
            role = getattr(msg, "role", "")
            parts.append(role)
            content = getattr(msg, "content", None)
            if content:
                parts.append(self._extract_content(content))
        elif entry_type == "custom_message":
            parts.append(getattr(entry, "custom_type", ""))
            parts.append(self._extract_content(getattr(entry, "content", "")))
        elif entry_type == "compaction":
            parts.append("compaction")
        elif entry_type == "branch_summary":
            parts.extend(["branch summary", getattr(entry, "summary", "")])
        elif entry_type == "model_change":
            parts.extend(["model", getattr(entry, "model_id", "")])
        elif entry_type == "thinking_level_change":
            parts.extend(["thinking", getattr(entry, "thinking_level", "")])
        elif entry_type == "custom":
            parts.extend(["custom", getattr(entry, "custom_type", "")])
        elif entry_type == "label":
            parts.extend(["label", getattr(entry, "label", "") or ""])
        return " ".join(parts)

    def _extract_content(self, content: Any, max_len: int = 200) -> str:
        if isinstance(content, str):
            return content[:max_len]
        if isinstance(content, list):
            result = ""
            for c in content:
                if getattr(c, "type", None) == "text" or (isinstance(c, dict) and c.get("type") == "text"):
                    text = str(c.get("text", "") if isinstance(c, dict) else getattr(c, "text", ""))
                    result += text
                    if len(result) >= max_len:
                        return result[:max_len]
            return result
        return ""

    def _has_text_content(self, content: Any) -> bool:
        if isinstance(content, str):
            return bool(content.strip())
        if isinstance(content, list):
            for c in content:
                t = c.get("text", "") if isinstance(c, dict) else getattr(c, "text", "")
                if t and t.strip():
                    return True
        return False

    def _get_filter_label(self) -> str:
        labels = {"no-tools": " [no-tools]", "user-only": " [user]", "labeled-only": " [labeled]", "all": " [all]"}
        return labels.get(self._filter_mode, "")

    def invalidate(self) -> None:
        pass

    def get_search_query(self) -> str:
        return self._search_query

    def get_selected_node(self) -> Any | None:
        if self._filtered_nodes and self._selected_index < len(self._filtered_nodes):
            return self._filtered_nodes[self._selected_index].node
        return None

    def update_node_label(self, entry_id: str, label: str | None) -> None:
        for flat_node in self._flat_nodes:
            if getattr(flat_node.node.entry, "id", None) == entry_id:
                flat_node.node.label = label
                break

    def render(self, width: int) -> list[str]:
        lines: list[str] = []
        if not self._filtered_nodes:
            lines.append(truncate_to_width(theme.fg("muted", "  No entries found"), width))
            lines.append(truncate_to_width(theme.fg("muted", f"  (0/0){self._get_filter_label()}"), width))
            return lines

        scroll_max = len(self._filtered_nodes) - self._max_visible_lines
        start = max(0, min(self._selected_index - self._max_visible_lines // 2, scroll_max))
        end = min(start + self._max_visible_lines, len(self._filtered_nodes))

        for i in range(start, end):
            flat_node = self._filtered_nodes[i]
            entry = flat_node.node.entry
            is_selected = i == self._selected_index
            cursor = theme.fg("accent", "\u203a ") if is_selected else "  "
            display_indent = max(0, flat_node.indent - 1) if self._multiple_roots else flat_node.indent
            connector = ""
            if flat_node.show_connector and not flat_node.is_virtual_root_child:
                connector = "\u2514\u2500 " if flat_node.is_last else "\u251c\u2500 "
            connector_position = display_indent - 1 if connector else -1
            total_chars = display_indent * 3
            prefix_chars: list[str] = []
            for j in range(total_chars):
                level = j // 3
                pos_in_level = j % 3
                gutter = next((g for g in flat_node.gutters if g.position == level), None)
                if gutter:
                    prefix_chars.append("\u2502" if pos_in_level == 0 and gutter.show else " ")
                elif connector and level == connector_position:
                    if pos_in_level == 0:
                        prefix_chars.append("\u2514" if flat_node.is_last else "\u251c")
                    elif pos_in_level == 1:
                        prefix_chars.append("\u2500")
                    else:
                        prefix_chars.append(" ")
                else:
                    prefix_chars.append(" ")
            prefix = "".join(prefix_chars)

            is_on_active = getattr(entry, "id", None) in self._active_path_ids
            path_marker = theme.fg("accent", "\u2022 ") if is_on_active else ""
            node_label = getattr(flat_node.node, "label", None)
            label_text = theme.fg("warning", f"[{node_label}] ") if node_label else ""
            content = self._get_entry_display_text(flat_node.node, is_selected)

            line = cursor + theme.fg("dim", prefix) + path_marker + label_text + content
            if is_selected:
                line = theme.bg("selectedBg", line)
            lines.append(truncate_to_width(line, width))

        page_info = f"  ({self._selected_index + 1}/{len(self._filtered_nodes)}){self._get_filter_label()}"
        lines.append(truncate_to_width(theme.fg("muted", page_info), width))
        return lines

    def _get_entry_display_text(self, node: Any, is_selected: bool) -> str:
        entry = getattr(node, "entry", None)
        entry_type = getattr(entry, "type", None)

        def normalize(s: str) -> str:
            return s.replace("\n", " ").replace("\t", " ").strip()

        result = ""
        if entry_type == "message":
            msg = getattr(entry, "message", None)
            role = getattr(msg, "role", "")
            if role == "user":
                content = normalize(self._extract_content(getattr(msg, "content", "")))
                result = theme.fg("accent", "user: ") + content
            elif role == "assistant":
                asst_content = getattr(msg, "content", None)
                text = normalize(self._extract_content(asst_content))
                stop_reason = getattr(msg, "stop_reason", None)
                error_msg = getattr(msg, "error_message", None)
                if text:
                    result = theme.fg("success", "assistant: ") + text
                elif stop_reason == "aborted":
                    result = theme.fg("success", "assistant: ") + theme.fg("muted", "(aborted)")
                elif error_msg:
                    result = theme.fg("success", "assistant: ") + theme.fg("error", normalize(error_msg)[:80])
                else:
                    result = theme.fg("success", "assistant: ") + theme.fg("muted", "(no content)")
            elif role == "toolResult":
                tool_call_id = getattr(msg, "tool_call_id", None)
                tool_name = getattr(msg, "tool_name", None)
                tc = self._tool_call_map.get(tool_call_id) if tool_call_id else None
                if tc:
                    result = theme.fg("muted", self._format_tool_call(tc["name"], tc["arguments"]))
                else:
                    result = theme.fg("muted", f"[{tool_name or 'tool'}]")
            elif role == "bashExecution":
                cmd = normalize(getattr(msg, "command", "") or "")
                result = theme.fg("dim", f"[bash]: {cmd}")
            else:
                result = theme.fg("dim", f"[{role}]")
        elif entry_type == "custom_message":
            content = getattr(entry, "content", "")
            if isinstance(content, str):
                text = content
            else:
                text = "".join(
                    getattr(c, "text", "") or c.get("text", "")
                    for c in (content or [])
                    if getattr(c, "type", None) == "text" or (isinstance(c, dict) and c.get("type") == "text")
                )
            custom_type = getattr(entry, "custom_type", "custom")
            result = theme.fg("customMessageLabel", f"[{custom_type}]: ") + normalize(text)
        elif entry_type == "compaction":
            tokens = round(getattr(entry, "tokens_before", 0) / 1000)
            result = theme.fg("borderAccent", f"[compaction: {tokens}k tokens]")
        elif entry_type == "branch_summary":
            summary = normalize(getattr(entry, "summary", ""))
            result = theme.fg("warning", "[branch summary]: ") + summary
        elif entry_type == "model_change":
            result = theme.fg("dim", f"[model: {getattr(entry, 'model_id', '')}]")
        elif entry_type == "thinking_level_change":
            result = theme.fg("dim", f"[thinking: {getattr(entry, 'thinking_level', '')}]")
        elif entry_type == "custom":
            result = theme.fg("dim", f"[custom: {getattr(entry, 'custom_type', '')}]")
        elif entry_type == "label":
            lbl = getattr(entry, "label", None)
            result = theme.fg("dim", f"[label: {lbl or '(cleared)'}]")

        return theme.bold(result) if is_selected else result

    def _format_tool_call(self, name: str, args: dict[str, Any]) -> str:
        def sp(p: str) -> str:
            return _shorten_path(p)

        if name == "read":
            path = sp(str(args.get("path") or args.get("file_path") or ""))
            offset = args.get("offset")
            limit = args.get("limit")
            display = path
            if offset is not None or limit is not None:
                start = offset or 1
                end = start + limit - 1 if limit is not None else ""
                display += f":{start}{f'-{end}' if end else ''}"
            return f"[read: {display}]"
        if name == "write":
            return f"[write: {sp(str(args.get('path') or args.get('file_path') or ''))}]"
        if name == "edit":
            return f"[edit: {sp(str(args.get('path') or args.get('file_path') or ''))}]"
        if name == "bash":
            raw_cmd = str(args.get("command") or "")
            cmd = raw_cmd.replace("\n", " ").replace("\t", " ").strip()[:50]
            return f"[bash: {cmd}{'...' if len(raw_cmd) > 50 else ''}]"
        if name == "grep":
            pattern = str(args.get("pattern") or "")
            path = sp(str(args.get("path") or "."))
            return f"[grep: /{pattern}/ in {path}]"
        if name == "find":
            pattern = str(args.get("pattern") or "")
            path = sp(str(args.get("path") or "."))
            return f"[find: {pattern} in {path}]"
        if name == "ls":
            return f"[ls: {sp(str(args.get('path') or '.'))}]"
        import json

        args_str = json.dumps(args)[:40]
        return f"[{name}: {args_str}{'...' if len(json.dumps(args)) > 40 else ''}]"

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()
        modes: list[FilterMode] = ["default", "no-tools", "user-only", "labeled-only", "all"]

        if kb.matches(data, "selectUp"):
            self._selected_index = (self._selected_index - 1) % max(1, len(self._filtered_nodes))
        elif kb.matches(data, "selectDown"):
            self._selected_index = (self._selected_index + 1) % max(1, len(self._filtered_nodes))
        elif kb.matches(data, "cursorLeft"):
            self._selected_index = max(0, self._selected_index - self._max_visible_lines)
        elif kb.matches(data, "cursorRight"):
            self._selected_index = min(len(self._filtered_nodes) - 1, self._selected_index + self._max_visible_lines)
        elif kb.matches(data, "selectConfirm"):
            if self._filtered_nodes and self.on_select:
                entry_id = getattr(self._filtered_nodes[self._selected_index].node.entry, "id", None)
                if entry_id:
                    self.on_select(entry_id)
        elif kb.matches(data, "selectCancel"):
            if self._search_query:
                self._search_query = ""
                self._apply_filter()
            elif self.on_cancel:
                self.on_cancel()
        elif matches_key(data, "ctrl+d"):
            self._filter_mode = "default"
            self._apply_filter()
        elif matches_key(data, "ctrl+t"):
            self._filter_mode = "default" if self._filter_mode == "no-tools" else "no-tools"
            self._apply_filter()
        elif matches_key(data, "ctrl+u"):
            self._filter_mode = "default" if self._filter_mode == "user-only" else "user-only"
            self._apply_filter()
        elif matches_key(data, "ctrl+l"):
            self._filter_mode = "default" if self._filter_mode == "labeled-only" else "labeled-only"
            self._apply_filter()
        elif matches_key(data, "ctrl+a"):
            self._filter_mode = "default" if self._filter_mode == "all" else "all"
            self._apply_filter()
        elif matches_key(data, "shift+ctrl+o"):
            idx = modes.index(self._filter_mode)
            self._filter_mode = modes[(idx - 1) % len(modes)]
            self._apply_filter()
        elif matches_key(data, "ctrl+o"):
            idx = modes.index(self._filter_mode)
            self._filter_mode = modes[(idx + 1) % len(modes)]
            self._apply_filter()
        elif kb.matches(data, "deleteCharBackward"):
            if self._search_query:
                self._search_query = self._search_query[:-1]
                self._apply_filter()
        elif matches_key(data, "shift+l"):
            if self._filtered_nodes and self.on_label_edit:
                node = self._filtered_nodes[self._selected_index].node
                self.on_label_edit(getattr(node.entry, "id", ""), getattr(node, "label", None))
        else:
            has_control = any(ord(ch) < 32 or ord(ch) == 0x7F or 0x80 <= ord(ch) <= 0x9F for ch in data)
            if not has_control and data:
                self._search_query += data
                self._apply_filter()


class _SearchLine:
    def __init__(self, tree_list: _TreeList) -> None:
        self._tree_list = tree_list

    def invalidate(self) -> None:
        pass

    def render(self, width: int) -> list[str]:
        query = self._tree_list.get_search_query()
        base = f"  {theme.fg('muted', 'Type to search:')}"
        if query:
            return [truncate_to_width(f"{base} {theme.fg('accent', query)}", width)]
        return [truncate_to_width(base, width)]

    def handle_input(self, _data: str) -> None:
        pass


class _LabelInput:
    def __init__(self, entry_id: str, current_label: str | None) -> None:
        self._entry_id = entry_id
        self._input = Input()
        if current_label:
            self._input.set_value(current_label)
        self._focused = False
        self.on_submit: Callable[[str, str | None], None] | None = None
        self.on_cancel: Callable[[], None] | None = None

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value
        self._input.focused = value

    def invalidate(self) -> None:
        pass

    def render(self, width: int) -> list[str]:
        indent = "  "
        available = width - len(indent)
        lines = [truncate_to_width(f"{indent}{theme.fg('muted', 'Label (empty to remove):')}", width)]
        lines.extend(truncate_to_width(f"{indent}{ln}", width) for ln in self._input.render(available))
        hints = f"{key_hint('selectConfirm', 'save')}  {key_hint('selectCancel', 'cancel')}"
        lines.append(truncate_to_width(f"{indent}{hints}", width))
        return lines

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()
        if kb.matches(data, "selectConfirm"):
            value = self._input.get_value().strip()
            if self.on_submit:
                self.on_submit(self._entry_id, value or None)
        elif kb.matches(data, "selectCancel"):
            if self.on_cancel:
                self.on_cancel()
        else:
            self._input.handle_input(data)


class TreeSelectorComponent(Container):
    """Session tree selector with ASCII art, filter modes, search, and label editing."""

    def __init__(
        self,
        tree: list[Any],
        current_leaf_id: str | None,
        terminal_height: int,
        on_select: Callable[[str], None],
        on_cancel: Callable[[], None],
        on_label_change: Callable[[str, str | None], None] | None = None,
        initial_selected_id: str | None = None,
    ) -> None:
        super().__init__()
        self._on_label_change = on_label_change
        self._focused = False
        self._label_input: _LabelInput | None = None

        max_visible = max(5, terminal_height // 2)
        self._tree_list = _TreeList(tree, current_leaf_id, max_visible, initial_selected_id)
        self._tree_list.on_select = on_select
        self._tree_list.on_cancel = on_cancel
        self._tree_list.on_label_edit = lambda eid, lbl: self._show_label_input(eid, lbl)

        self._tree_container = Container()
        self._tree_container.add_child(self._tree_list)

        self._label_input_container = Container()

        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())
        self.add_child(Text(theme.bold("  Session Tree"), 1, 0))
        self.add_child(
            TruncatedText(
                theme.fg("muted", "  \u2191/\u2193: move. \u2190/\u2192: page. Shift+L: label. ")
                + theme.fg("muted", "^D/^T/^U/^L/^A: filters (^O/\u21e7^O cycle)"),
                0,
                0,
            )
        )
        self.add_child(_SearchLine(self._tree_list))
        self.add_child(DynamicBorder())
        self.add_child(Spacer(1))
        self.add_child(self._tree_container)
        self.add_child(self._label_input_container)
        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())

        if not tree:
            t = threading.Timer(0.1, on_cancel)
            t.daemon = True
            t.start()

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value
        if self._label_input:
            self._label_input.focused = value

    def _show_label_input(self, entry_id: str, current_label: str | None) -> None:
        self._label_input = _LabelInput(entry_id, current_label)

        def _on_label_submit(eid: str, lbl: str | None) -> None:
            self._tree_list.update_node_label(eid, lbl)
            if self._on_label_change:
                self._on_label_change(eid, lbl)
            self._hide_label_input()

        self._label_input.on_submit = _on_label_submit
        self._label_input.on_cancel = self._hide_label_input
        self._label_input.focused = self._focused
        self._tree_container.clear()
        self._label_input_container.clear()
        self._label_input_container.add_child(self._label_input)

    def _hide_label_input(self) -> None:
        self._label_input = None
        self._label_input_container.clear()
        self._tree_container.clear()
        self._tree_container.add_child(self._tree_list)

    def handle_input(self, data: str) -> None:
        if self._label_input:
            self._label_input.handle_input(data)
        else:
            self._tree_list.handle_input(data)

    def get_tree_list(self) -> _TreeList:
        return self._tree_list
