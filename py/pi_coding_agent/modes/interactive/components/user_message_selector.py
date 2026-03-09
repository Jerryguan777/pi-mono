"""User message selector for branching from a previous message."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.tui import Container
from pi_tui.utils import truncate_to_width


@dataclass
class UserMessageItem:
    id: str
    text: str
    timestamp: str | None = None


class _UserMessageList:
    def __init__(self, messages: list[UserMessageItem]) -> None:
        self._messages = messages
        self._selected_index = max(0, len(messages) - 1)
        self._max_visible = 10

        self.on_select: Callable[[str], None] | None = None
        self.on_cancel: Callable[[], None] | None = None

    def invalidate(self) -> None:
        pass

    def render(self, width: int) -> list[str]:
        lines: list[str] = []
        if not self._messages:
            lines.append(theme.fg("muted", "  No user messages found"))
            return lines

        start = max(0, min(self._selected_index - self._max_visible // 2, len(self._messages) - self._max_visible))
        end = min(start + self._max_visible, len(self._messages))

        for i in range(start, end):
            msg = self._messages[i]
            is_selected = i == self._selected_index
            normalized = msg.text.replace("\n", " ").strip()
            cursor = theme.fg("accent", "\u203a ") if is_selected else "  "
            max_msg_width = width - 2
            truncated = truncate_to_width(normalized, max_msg_width)
            msg_line = cursor + (theme.bold(truncated) if is_selected else truncated)
            lines.append(msg_line)
            lines.append(theme.fg("muted", f"  Message {i + 1} of {len(self._messages)}"))
            lines.append("")

        if start > 0 or end < len(self._messages):
            lines.append(theme.fg("muted", f"  ({self._selected_index + 1}/{len(self._messages)})"))

        return lines

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()
        if kb.matches(data, "selectUp"):
            self._selected_index = (self._selected_index - 1) % max(1, len(self._messages))
        elif kb.matches(data, "selectDown"):
            self._selected_index = (self._selected_index + 1) % max(1, len(self._messages))
        elif kb.matches(data, "selectConfirm"):
            if self._messages and self.on_select:
                self.on_select(self._messages[self._selected_index].id)
        elif kb.matches(data, "selectCancel") and self.on_cancel:
            self.on_cancel()


class UserMessageSelectorComponent(Container):
    """Renders a user message list for selecting a branch point."""

    def __init__(
        self,
        messages: list[UserMessageItem],
        on_select: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__()

        self.add_child(Spacer(1))
        self.add_child(Text(theme.bold("Branch from Message"), 1, 0))
        self.add_child(Text(theme.fg("muted", "Select a message to create a new branch from that point"), 1, 0))
        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())
        self.add_child(Spacer(1))

        self._message_list = _UserMessageList(messages)
        self._message_list.on_select = on_select
        self._message_list.on_cancel = on_cancel
        self.add_child(self._message_list)

        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())

        if not messages:
            t = threading.Timer(0.1, on_cancel)
            t.daemon = True
            t.start()

    def get_message_list(self) -> _UserMessageList:
        return self._message_list
