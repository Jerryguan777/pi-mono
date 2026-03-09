"""Session selector component with search, scope toggle, sort modes, and rename/delete."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.keybinding_hints import app_key, app_key_hint, key_hint
from pi_coding_agent.modes.interactive.components.session_selector_search import (
    NameFilter,
    SortMode,
    filter_and_sort_sessions,
    has_session_name,
)
from pi_tui.components.input import Input
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.keys import matches_key
from pi_tui.tui import Container
from pi_tui.utils import truncate_to_width, visible_width

SessionScope = Literal["current", "all"]


def _shorten_path(path: str) -> str:
    home = os.path.expanduser("~")
    if path.startswith(home):
        return f"~{path[len(home) :]}"
    return path


def _format_session_date(dt: datetime) -> str:
    now = datetime.now()
    diff = now - dt
    mins = int(diff.total_seconds() // 60)
    hours = mins // 60
    days = hours // 24

    if mins < 1:
        return "now"
    if mins < 60:
        return f"{mins}m"
    if hours < 24:
        return f"{hours}h"
    if days < 7:
        return f"{days}d"
    if days < 30:
        return f"{days // 7}w"
    if days < 365:
        return f"{days // 30}mo"
    return f"{days // 365}y"


@dataclass
class _SessionTreeNode:
    session: Any
    children: list[_SessionTreeNode] = field(default_factory=list)


@dataclass
class _FlatSessionNode:
    session: Any
    depth: int
    is_last: bool
    ancestor_continues: list[bool]


def _build_session_tree(sessions: list[Any]) -> list[_SessionTreeNode]:
    by_path: dict[str, _SessionTreeNode] = {}
    for s in sessions:
        by_path[s.path] = _SessionTreeNode(session=s)

    roots: list[_SessionTreeNode] = []
    for s in sessions:
        node = by_path[s.path]
        parent_path = getattr(s, "parent_session_path", None)
        if parent_path and parent_path in by_path:
            by_path[parent_path].children.append(node)
        else:
            roots.append(node)

    def sort_nodes(nodes: list[_SessionTreeNode]) -> None:
        nodes.sort(key=lambda n: getattr(n.session, "modified", datetime.min), reverse=True)
        for n in nodes:
            sort_nodes(n.children)

    sort_nodes(roots)
    return roots


def _flatten_session_tree(roots: list[_SessionTreeNode]) -> list[_FlatSessionNode]:
    result: list[_FlatSessionNode] = []

    def walk(node: _SessionTreeNode, depth: int, ancestor_continues: list[bool], is_last: bool) -> None:
        result.append(
            _FlatSessionNode(
                session=node.session,
                depth=depth,
                is_last=is_last,
                ancestor_continues=list(ancestor_continues),
            )
        )
        for i, child in enumerate(node.children):
            child_is_last = i == len(node.children) - 1
            continues = not is_last if depth > 0 else False
            walk(child, depth + 1, [*ancestor_continues, continues], child_is_last)

    for i, root in enumerate(roots):
        walk(root, 0, [], i == len(roots) - 1)
    return result


class _SessionSelectorHeader:
    def __init__(
        self,
        scope: SessionScope,
        sort_mode: SortMode,
        name_filter: NameFilter,
        keybindings: Any,
        request_render: Callable[[], None],
    ) -> None:
        self._scope = scope
        self._sort_mode = sort_mode
        self._name_filter = name_filter
        self._keybindings = keybindings
        self._request_render = request_render
        self._loading = False
        self._load_progress: tuple[int, int] | None = None
        self._show_path = False
        self._confirming_delete_path: str | None = None
        self._status_message: dict[str, str] | None = None
        self._status_timer: threading.Timer | None = None
        self._show_rename_hint = False

    def set_scope(self, scope: SessionScope) -> None:
        self._scope = scope

    def set_sort_mode(self, sort_mode: SortMode) -> None:
        self._sort_mode = sort_mode

    def set_name_filter(self, name_filter: NameFilter) -> None:
        self._name_filter = name_filter

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        self._load_progress = None

    def set_progress(self, loaded: int, total: int) -> None:
        self._load_progress = (loaded, total)

    def set_show_path(self, show_path: bool) -> None:
        self._show_path = show_path

    def set_show_rename_hint(self, show: bool) -> None:
        self._show_rename_hint = show

    def set_confirming_delete_path(self, path: str | None) -> None:
        self._confirming_delete_path = path

    def set_status_message(self, msg: dict[str, str] | None, auto_hide_ms: int | None = None) -> None:
        if self._status_timer is not None:
            self._status_timer.cancel()
            self._status_timer = None
        self._status_message = msg
        if msg and auto_hide_ms:

            def clear() -> None:
                self._status_message = None
                self._request_render()

            self._status_timer = threading.Timer(auto_hide_ms / 1000, clear)
            self._status_timer.daemon = True
            self._status_timer.start()

    def invalidate(self) -> None:
        pass

    def render(self, width: int) -> list[str]:
        title = "Resume Session (Current Folder)" if self._scope == "current" else "Resume Session (All)"
        left_text = theme.bold(title)

        sort_labels = {"threaded": "Threaded", "recent": "Recent", "relevance": "Fuzzy"}
        sort_label = sort_labels.get(self._sort_mode, self._sort_mode)
        sort_text = theme.fg("muted", "Sort: ") + theme.fg("accent", sort_label)

        name_label = "All" if self._name_filter == "all" else "Named"
        name_text = theme.fg("muted", "Name: ") + theme.fg("accent", name_label)

        if self._loading:
            progress_text = f"{self._load_progress[0]}/{self._load_progress[1]}" if self._load_progress else "..."
            loading_text = theme.fg("accent", f"Loading {progress_text}")
            scope_text = f"{theme.fg('muted', chr(0x25CB) + ' Current Folder | ')}{loading_text}"
        elif self._scope == "current":
            scope_text = theme.fg("accent", "\u25c9 Current Folder") + theme.fg("muted", " | \u25cb All")
        else:
            scope_text = theme.fg("muted", "\u25cb Current Folder | ") + theme.fg("accent", "\u25c9 All")

        right_text = truncate_to_width(f"{scope_text}  {name_text}  {sort_text}", width, "")
        available_left = max(0, width - visible_width(right_text) - 1)
        left = truncate_to_width(left_text, available_left, "")
        spacing = max(0, width - visible_width(left) - visible_width(right_text))

        sep = theme.fg("muted", " \u00b7 ")
        if self._confirming_delete_path is not None:
            delete_msg = "Delete session? [Enter] confirm \u00b7 [Esc/Ctrl+C] cancel"
            hint_line1 = theme.fg("error", truncate_to_width(delete_msg, width, "\u2026"))
            hint_line2 = ""
        elif self._status_message:
            color = "error" if self._status_message.get("type") == "error" else "accent"
            hint_line1 = theme.fg(color, truncate_to_width(self._status_message.get("message", ""), width, "\u2026"))
            hint_line2 = ""
        else:
            path_state = "(on)" if self._show_path else "(off)"
            hint1 = key_hint("tab", "scope") + sep + theme.fg("muted", 're:<pattern> regex \u00b7 "phrase" exact')
            hint2_parts = [
                key_hint("toggleSessionSort", "sort"),
                app_key_hint(self._keybindings, "toggleSessionNamedFilter", "named"),
                key_hint("deleteSession", "delete"),
                key_hint("toggleSessionPath", f"path {path_state}"),
            ]
            if self._show_rename_hint:
                hint2_parts.append(key_hint("renameSession", "rename"))
            hint2 = sep.join(hint2_parts)
            hint_line1 = truncate_to_width(hint1, width, "\u2026")
            hint_line2 = truncate_to_width(hint2, width, "\u2026")

        return [f"{left}{' ' * spacing}{right_text}", hint_line1, hint_line2]


class _SessionList:
    def __init__(
        self,
        sessions: list[Any],
        show_cwd: bool,
        sort_mode: SortMode,
        name_filter: NameFilter,
        keybindings: Any,
        current_session_file_path: str | None = None,
    ) -> None:
        self._all_sessions = sessions
        self._filtered_sessions: list[_FlatSessionNode] = []
        self._selected_index = 0
        self._search_input = Input()
        self._show_cwd = show_cwd
        self._sort_mode = sort_mode
        self._name_filter = name_filter
        self._keybindings = keybindings
        self._current_session_file_path = current_session_file_path
        self._show_path = False
        self._confirming_delete_path: str | None = None
        self._max_visible = 10
        self._focused = False

        self.on_select: Callable[[str], None] | None = None
        self.on_cancel: Callable[[], None] | None = None
        self.on_exit: Callable[[], None] = lambda: None
        self.on_toggle_scope: Callable[[], None] | None = None
        self.on_toggle_sort: Callable[[], None] | None = None
        self.on_toggle_name_filter: Callable[[], None] | None = None
        self.on_toggle_path: Callable[[bool], None] | None = None
        self.on_delete_confirmation_change: Callable[[str | None], None] | None = None
        self.on_delete_session: Callable[[str], None] | None = None
        self.on_rename_session: Callable[[str], None] | None = None
        self.on_error: Callable[[str], None] | None = None

        self._search_input.on_submit = self._on_search_submit
        self._filter_sessions("")

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value
        self._search_input.focused = value

    def get_selected_session_path(self) -> str | None:
        if self._filtered_sessions and self._selected_index < len(self._filtered_sessions):
            return str(self._filtered_sessions[self._selected_index].session.path)
        return None

    def set_sort_mode(self, sort_mode: SortMode) -> None:
        self._sort_mode = sort_mode
        self._filter_sessions(self._search_input.get_value())

    def set_name_filter(self, name_filter: NameFilter) -> None:
        self._name_filter = name_filter
        self._filter_sessions(self._search_input.get_value())

    def set_sessions(self, sessions: list[Any], show_cwd: bool) -> None:
        self._all_sessions = sessions
        self._show_cwd = show_cwd
        self._filter_sessions(self._search_input.get_value())

    def _filter_sessions(self, query: str) -> None:
        trimmed = query.strip()
        name_filtered = [s for s in self._all_sessions if self._name_filter == "all" or has_session_name(s)]

        if self._sort_mode == "threaded" and not trimmed:
            roots = _build_session_tree(name_filtered)
            self._filtered_sessions = _flatten_session_tree(roots)
        else:
            filtered = filter_and_sort_sessions(name_filtered, query, self._sort_mode, "all")
            self._filtered_sessions = [_FlatSessionNode(s, 0, True, []) for s in filtered]

        self._selected_index = min(self._selected_index, max(0, len(self._filtered_sessions) - 1))

    def _set_confirming_delete_path(self, path: str | None) -> None:
        self._confirming_delete_path = path
        if self.on_delete_confirmation_change:
            self.on_delete_confirmation_change(path)

    def _start_delete_confirmation(self) -> None:
        if not self._filtered_sessions:
            return
        selected = self._filtered_sessions[self._selected_index]
        if self._current_session_file_path and selected.session.path == self._current_session_file_path:
            if self.on_error:
                self.on_error("Cannot delete the currently active session")
            return
        self._set_confirming_delete_path(selected.session.path)

    def _on_search_submit(self, _value: str | None = None) -> None:
        if self._filtered_sessions and self.on_select:
            self.on_select(self._filtered_sessions[self._selected_index].session.path)

    def invalidate(self) -> None:
        pass

    def render(self, width: int) -> list[str]:
        lines: list[str] = []
        lines.extend(self._search_input.render(width))
        lines.append("")

        if not self._filtered_sessions:
            toggle_key = app_key(self._keybindings, "toggleSessionNamedFilter")
            if self._name_filter == "named":
                if self._show_cwd:
                    msg = f"  No named sessions found. Press {toggle_key} to show all."
                else:
                    msg = f"  No named sessions in current folder. Press {toggle_key} to show all, or Tab to view all."
            elif self._show_cwd:
                msg = "  No sessions found"
            else:
                msg = "  No sessions in current folder. Press Tab to view all."
            lines.append(theme.fg("muted", truncate_to_width(msg, width, "\u2026")))
            return lines

        scroll_max = len(self._filtered_sessions) - self._max_visible
        start = max(0, min(self._selected_index - self._max_visible // 2, scroll_max))
        end = min(start + self._max_visible, len(self._filtered_sessions))

        for i in range(start, end):
            node = self._filtered_sessions[i]
            session = node.session
            is_selected = i == self._selected_index
            is_confirming = session.path == self._confirming_delete_path
            is_current = self._current_session_file_path == session.path

            prefix = self._build_tree_prefix(node)
            has_name = bool(getattr(session, "name", None))
            display_text = getattr(session, "name", None) or getattr(session, "first_message", "")
            normalized = str(display_text or "").replace("\n", " ").strip()

            modified = getattr(session, "modified", datetime.min)
            age = _format_session_date(modified) if isinstance(modified, datetime) else ""
            msg_count = str(getattr(session, "message_count", 0))
            right_part = f"{msg_count} {age}"
            if self._show_cwd and getattr(session, "cwd", None):
                right_part = f"{_shorten_path(session.cwd)} {right_part}"
            if self._show_path:
                right_part = f"{_shorten_path(session.path)} {right_part}"

            cursor = theme.fg("accent", "\u203a ") if is_selected else "  "
            prefix_width = visible_width(prefix)
            right_width = visible_width(right_part) + 2
            available_for_msg = width - 2 - prefix_width - right_width
            truncated_msg = truncate_to_width(normalized, max(10, available_for_msg), "\u2026")

            if is_confirming:
                msg_color = "error"
            elif is_current:
                msg_color = "accent"
            elif has_name:
                msg_color = "warning"
            else:
                msg_color = None

            styled_msg = theme.fg(msg_color, truncated_msg) if msg_color else truncated_msg
            if is_selected:
                styled_msg = theme.bold(styled_msg)

            left_part = cursor + theme.fg("dim", prefix) + styled_msg
            left_width = visible_width(left_part)
            spacing = max(1, width - left_width - visible_width(right_part))
            styled_right = theme.fg("error" if is_confirming else "dim", right_part)

            line = left_part + " " * spacing + styled_right
            if is_selected:
                line = theme.bg("selectedBg", line)
            lines.append(truncate_to_width(line, width))

        if start > 0 or end < len(self._filtered_sessions):
            page_info = f"  ({self._selected_index + 1}/{len(self._filtered_sessions)})"
            lines.append(theme.fg("muted", truncate_to_width(page_info, width, "")))

        return lines

    def _build_tree_prefix(self, node: _FlatSessionNode) -> str:
        if node.depth == 0:
            return ""
        parts = ["\u2502  " if c else "   " for c in node.ancestor_continues]
        branch = "\u2514\u2500 " if node.is_last else "\u251c\u2500 "
        return "".join(parts) + branch

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()

        if self._confirming_delete_path is not None:
            if kb.matches(data, "selectConfirm"):
                path = self._confirming_delete_path
                self._set_confirming_delete_path(None)
                if self.on_delete_session:
                    self.on_delete_session(path)
                return
            if kb.matches(data, "selectCancel") or matches_key(data, "ctrl+c"):
                self._set_confirming_delete_path(None)
                return
            return

        if kb.matches(data, "tab"):
            if self.on_toggle_scope:
                self.on_toggle_scope()
            return
        if kb.matches(data, "toggleSessionSort"):
            if self.on_toggle_sort:
                self.on_toggle_sort()
            return
        if hasattr(self._keybindings, "matches") and self._keybindings.matches(data, "toggleSessionNamedFilter"):
            if self.on_toggle_name_filter:
                self.on_toggle_name_filter()
            return
        if kb.matches(data, "toggleSessionPath"):
            self._show_path = not self._show_path
            if self.on_toggle_path:
                self.on_toggle_path(self._show_path)
            return
        if kb.matches(data, "deleteSession"):
            self._start_delete_confirmation()
            return
        if matches_key(data, "ctrl+r"):
            if self._filtered_sessions and self.on_rename_session:
                self.on_rename_session(self._filtered_sessions[self._selected_index].session.path)
            return
        if kb.matches(data, "deleteSessionNoninvasive"):
            if self._search_input.get_value():
                self._search_input.handle_input(data)
                self._filter_sessions(self._search_input.get_value())
                return
            self._start_delete_confirmation()
            return

        if kb.matches(data, "selectUp"):
            self._selected_index = max(0, self._selected_index - 1)
        elif kb.matches(data, "selectDown"):
            self._selected_index = min(len(self._filtered_sessions) - 1, self._selected_index + 1)
        elif kb.matches(data, "selectPageUp"):
            self._selected_index = max(0, self._selected_index - self._max_visible)
        elif kb.matches(data, "selectPageDown"):
            self._selected_index = min(len(self._filtered_sessions) - 1, self._selected_index + self._max_visible)
        elif kb.matches(data, "selectConfirm"):
            if self._filtered_sessions and self.on_select:
                self.on_select(self._filtered_sessions[self._selected_index].session.path)
        elif kb.matches(data, "selectCancel"):
            if self.on_cancel:
                self.on_cancel()
        else:
            self._search_input.handle_input(data)
            self._filter_sessions(self._search_input.get_value())


def _delete_session_file(session_path: str) -> dict[str, Any]:
    """Try `trash` first, fall back to os.unlink."""
    args = ["--", session_path] if session_path.startswith("-") else [session_path]
    try:
        result = subprocess.run(["trash", *args], capture_output=True, text=True)
        if result.returncode == 0 or not os.path.exists(session_path):
            return {"ok": True, "method": "trash"}
    except FileNotFoundError:
        pass

    try:
        os.unlink(session_path)
        return {"ok": True, "method": "unlink"}
    except OSError as exc:
        return {"ok": False, "method": "unlink", "error": str(exc)}


class SessionSelectorComponent(Container):
    """Full session selector with search, scope toggle, sort, rename and delete."""

    def __init__(
        self,
        current_sessions_loader: Callable[..., list[Any]],
        all_sessions_loader: Callable[..., list[Any]],
        on_select: Callable[[str], None],
        on_cancel: Callable[[], None],
        on_exit: Callable[[], None],
        request_render: Callable[[], None],
        keybindings: Any | None = None,
        rename_session: Callable[[str, str | None], None] | None = None,
        show_rename_hint: bool | None = None,
        current_session_file_path: str | None = None,
    ) -> None:
        super().__init__()
        from pi_coding_agent.modes.interactive.components.keybinding_hints import _create_default_keybindings

        self._keybindings = keybindings or _create_default_keybindings()
        self._current_sessions_loader = current_sessions_loader
        self._all_sessions_loader = all_sessions_loader
        self._on_cancel = on_cancel
        self._request_render = request_render
        self._scope: SessionScope = "current"
        self._sort_mode: SortMode = "threaded"
        self._name_filter: NameFilter = "all"
        self._current_sessions: list[Any] | None = None
        self._all_sessions: list[Any] | None = None
        self._current_loading = False
        self._all_loading = False
        self._all_load_seq = 0
        self._sessions_lock = threading.Lock()
        self._mode: str = "list"
        self._rename_target_path: str | None = None
        self._focused = False

        self._header = _SessionSelectorHeader(
            self._scope, self._sort_mode, self._name_filter, self._keybindings, request_render
        )
        can_rename = rename_session is not None
        self._header.set_show_rename_hint(show_rename_hint if show_rename_hint is not None else can_rename)

        self._session_list = _SessionList(
            [], False, self._sort_mode, self._name_filter, self._keybindings, current_session_file_path
        )
        self._rename_input = Input()

        self._build_base_layout(self._session_list)

        self._rename_input.on_submit = lambda v: self._confirm_rename(v or "")

        def clear_status() -> None:
            self._header.set_status_message(None)

        def _on_select(path: str) -> None:
            clear_status()
            on_select(path)

        def _on_cancel() -> None:
            clear_status()
            on_cancel()

        def _on_exit() -> None:
            clear_status()
            on_exit()

        def _on_toggle_path(show: bool) -> None:
            self._header.set_show_path(show)
            request_render()

        def _on_delete_confirmation_change(path: str | None) -> None:
            self._header.set_confirming_delete_path(path)
            request_render()

        def _on_error(msg: str) -> None:
            self._header.set_status_message({"type": "error", "message": msg}, 3000)
            request_render()

        self._session_list.on_select = _on_select
        self._session_list.on_cancel = _on_cancel
        self._session_list.on_exit = _on_exit
        self._session_list.on_toggle_scope = self._toggle_scope
        self._session_list.on_toggle_sort = self._toggle_sort_mode
        self._session_list.on_toggle_name_filter = self._toggle_name_filter
        self._session_list.on_toggle_path = _on_toggle_path
        self._session_list.on_delete_confirmation_change = _on_delete_confirmation_change
        self._session_list.on_error = _on_error

        if rename_session is not None:

            def _on_rename(session_path: str) -> None:
                with self._sessions_lock:
                    if self._scope == "current" and self._current_loading:
                        return
                    if self._scope == "all" and self._all_loading:
                        return
                    sessions = self._all_sessions or self._current_sessions or []
                session = next((s for s in sessions if s.path == session_path), None)
                self._enter_rename_mode(session_path, getattr(session, "name", None))

            self._session_list.on_rename_session = _on_rename

        def _on_delete(session_path: str) -> None:
            result = _delete_session_file(session_path)
            if result["ok"]:
                with self._sessions_lock:
                    if self._current_sessions:
                        self._current_sessions = [s for s in self._current_sessions if s.path != session_path]
                    if self._all_sessions:
                        self._all_sessions = [s for s in self._all_sessions if s.path != session_path]
                    sessions = self._all_sessions or [] if self._scope == "all" else self._current_sessions or []
                self._session_list.set_sessions(sessions, self._scope == "all")
                msg = "Session moved to trash" if result["method"] == "trash" else "Session deleted"
                self._header.set_status_message({"type": "info", "message": msg}, 2000)
                self._load_scope(self._scope, "refresh")
            else:
                error_msg = result.get("error", "Unknown error")
                self._header.set_status_message({"type": "error", "message": f"Failed to delete: {error_msg}"}, 3000)
            request_render()

        self._session_list.on_delete_session = _on_delete
        self._load_current_sessions()

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value
        self._session_list.focused = value
        self._rename_input.focused = value

    def _build_base_layout(self, content: Any, show_header: bool = True) -> None:
        self.clear()
        self.add_child(Spacer(1))
        self.add_child(DynamicBorder(lambda s: theme.fg("accent", s)))
        self.add_child(Spacer(1))
        if show_header:
            self.add_child(self._header)
            self.add_child(Spacer(1))
        self.add_child(content)
        self.add_child(Spacer(1))
        self.add_child(DynamicBorder(lambda s: theme.fg("accent", s)))

    def _load_current_sessions(self) -> None:
        self._load_scope("current", "initial")

    def _load_scope(self, scope: SessionScope, reason: str) -> None:
        show_cwd = scope == "all"

        with self._sessions_lock:
            if scope == "current":
                self._current_loading = True
            else:
                self._all_loading = True
                self._all_load_seq += 1
            seq = self._all_load_seq if scope == "all" else None

        self._header.set_scope(scope)
        self._header.set_loading(True)
        self._request_render()

        def do_load() -> None:
            try:
                loader = self._all_sessions_loader if scope == "all" else self._current_sessions_loader
                sessions = loader()

                with self._sessions_lock:
                    if scope == "current":
                        self._current_sessions = sessions
                        self._current_loading = False
                    else:
                        if seq != self._all_load_seq:
                            return
                        self._all_sessions = sessions
                        self._all_loading = False
                    current_scope = self._scope
                    current_sessions_snapshot = self._current_sessions

                if current_scope != scope:
                    return

                self._header.set_loading(False)
                self._session_list.set_sessions(sessions, show_cwd)
                self._request_render()

                if scope == "all" and not sessions and not (current_sessions_snapshot or []):
                    self._on_cancel()
            except Exception as exc:
                with self._sessions_lock:
                    if scope == "current":
                        self._current_loading = False
                    else:
                        self._all_loading = False
                    current_scope = self._scope

                if current_scope != scope:
                    return

                msg = str(exc)
                self._header.set_loading(False)
                self._header.set_status_message({"type": "error", "message": f"Failed to load sessions: {msg}"}, 4000)

                if reason == "initial":
                    self._session_list.set_sessions([], show_cwd)
                self._request_render()

        t = threading.Thread(target=do_load, daemon=True)
        t.start()

    def _toggle_sort_mode(self) -> None:
        modes: list[SortMode] = ["threaded", "recent", "relevance"]
        self._sort_mode = modes[(modes.index(self._sort_mode) + 1) % len(modes)]
        self._header.set_sort_mode(self._sort_mode)
        self._session_list.set_sort_mode(self._sort_mode)
        self._request_render()

    def _toggle_name_filter(self) -> None:
        self._name_filter = "named" if self._name_filter == "all" else "all"
        self._header.set_name_filter(self._name_filter)
        self._session_list.set_name_filter(self._name_filter)
        self._request_render()

    def _toggle_scope(self) -> None:
        if self._scope == "current":
            self._scope = "all"
            self._header.set_scope(self._scope)
            with self._sessions_lock:
                all_sessions_snapshot = self._all_sessions
                all_loading = self._all_loading
            if all_sessions_snapshot is not None:
                self._header.set_loading(False)
                self._session_list.set_sessions(all_sessions_snapshot, True)
                self._request_render()
                return
            if not all_loading:
                self._load_scope("all", "toggle")
            return

        self._scope = "current"
        self._header.set_scope(self._scope)
        with self._sessions_lock:
            current_loading = self._current_loading
            current_sessions_snapshot = self._current_sessions
        self._header.set_loading(current_loading)
        self._session_list.set_sessions(current_sessions_snapshot or [], False)
        self._request_render()

    def _enter_rename_mode(self, session_path: str, current_name: str | None) -> None:
        self._mode = "rename"
        self._rename_target_path = session_path
        self._rename_input.set_value(current_name or "")
        self._rename_input.focused = self._focused

        panel = Container()
        panel.add_child(Text(theme.bold("Rename Session"), 1, 0))
        panel.add_child(Spacer(1))
        panel.add_child(self._rename_input)
        panel.add_child(Spacer(1))
        panel.add_child(Text(theme.fg("muted", "Enter to save \u00b7 Esc/Ctrl+C to cancel"), 1, 0))

        self._build_base_layout(panel, show_header=False)
        self._request_render()

    def _exit_rename_mode(self) -> None:
        self._mode = "list"
        self._rename_target_path = None
        self._build_base_layout(self._session_list)
        self._request_render()

    def _confirm_rename(self, value: str) -> None:
        name = value.strip()
        if not name or not self._rename_target_path:
            self._exit_rename_mode()
            return
        self._exit_rename_mode()

    def handle_input(self, data: str) -> None:
        if self._mode == "rename":
            kb = get_editor_keybindings()
            if kb.matches(data, "selectCancel") or matches_key(data, "ctrl+c"):
                self._exit_rename_mode()
                return
            self._rename_input.handle_input(data)
            return
        self._session_list.handle_input(data)

    def get_session_list(self) -> _SessionList:
        return self._session_list
