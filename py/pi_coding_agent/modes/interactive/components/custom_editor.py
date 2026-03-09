"""Custom editor that handles app-level keybindings for coding-agent."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pi_tui.components.editor import Editor, EditorOptions, EditorTheme

if TYPE_CHECKING:
    from pi_tui.tui import TUI


class CustomEditor(Editor):
    """Editor subclass that intercepts app-level keybinding actions.

    App actions are registered via :meth:`on_action` and are checked before
    falling through to the base :class:`Editor` input handling.

    Special handler slots:
    * ``on_escape`` — override for the ``interrupt`` action.
    * ``on_ctrl_d`` — override for the ``exit`` action (when editor is empty).
    * ``on_paste_image`` — invoked for the ``pasteImage`` keybinding.
    * ``on_extension_shortcut`` — called first; return ``True`` to consume.
    """

    def __init__(
        self,
        tui: TUI,
        editor_theme: EditorTheme,
        keybindings: Any,
        options: EditorOptions | None = None,
    ) -> None:
        super().__init__(tui, editor_theme, options)
        self._keybindings = keybindings
        self.action_handlers: dict[str, Callable[[], None]] = {}
        self.on_escape: Callable[[], None] | None = None
        self.on_ctrl_d: Callable[[], None] | None = None
        self.on_paste_image: Callable[[], None] | None = None
        self.on_extension_shortcut: Callable[[str], bool] | None = None

    def on_action(self, action: str, handler: Callable[[], None]) -> None:
        """Register a handler for an app action."""
        self.action_handlers[action] = handler

    def handle_input(self, data: str) -> None:
        kb = self._keybindings

        # Extension-registered shortcuts have highest priority
        if self.on_extension_shortcut is not None and self.on_extension_shortcut(data):
            return

        # Paste image keybinding
        if hasattr(kb, "matches") and kb.matches(data, "pasteImage"):
            if self.on_paste_image is not None:
                self.on_paste_image()
            return

        # Escape / interrupt — only when autocomplete is not showing
        if hasattr(kb, "matches") and kb.matches(data, "interrupt"):
            if not self.is_showing_autocomplete():
                handler = self.on_escape or self.action_handlers.get("interrupt")
                if handler is not None:
                    handler()
                    return
            # Let base class handle for autocomplete cancellation
            super().handle_input(data)
            return

        # Ctrl+D / exit — only when editor is empty
        if hasattr(kb, "matches") and kb.matches(data, "exit") and len(self.get_text()) == 0:
            handler = self.on_ctrl_d or self.action_handlers.get("exit")
            if handler is not None:
                handler()
                return
            # Fall through to editor for delete-char-forward when not empty

        # Check all other app actions
        for action, handler in self.action_handlers.items():
            if action in ("interrupt", "exit"):
                continue
            if hasattr(kb, "matches") and kb.matches(data, action):
                handler()
                return

        super().handle_input(data)
