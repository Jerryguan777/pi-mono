"""Editor keybindings for TUI applications.

Port of keybindings.ts. Provides configurable key-to-action mapping
with defaults matching the original TypeScript implementation.
"""

from __future__ import annotations

from typing import Literal

from pi_tui.keys import matches_key

EditorAction = Literal[
    # Cursor movement
    "cursorUp",
    "cursorDown",
    "cursorLeft",
    "cursorRight",
    "cursorWordLeft",
    "cursorWordRight",
    "cursorLineStart",
    "cursorLineEnd",
    "jumpForward",
    "jumpBackward",
    "pageUp",
    "pageDown",
    # Deletion
    "deleteCharBackward",
    "deleteCharForward",
    "deleteWordBackward",
    "deleteWordForward",
    "deleteToLineStart",
    "deleteToLineEnd",
    # Text input
    "newLine",
    "submit",
    "tab",
    # Selection/autocomplete
    "selectUp",
    "selectDown",
    "selectPageUp",
    "selectPageDown",
    "selectConfirm",
    "selectCancel",
    # Clipboard
    "copy",
    # Kill ring
    "yank",
    "yankPop",
    # Undo
    "undo",
    # Tool output
    "expandTools",
    # Session
    "toggleSessionPath",
    "toggleSessionSort",
    "renameSession",
    "deleteSession",
    "deleteSessionNoninvasive",
]

EditorKeybindingsConfig = dict[str, str | list[str]]
"""Configuration mapping action names to key identifiers.
Values can be a single key ID string or a list of key ID strings."""

DEFAULT_EDITOR_KEYBINDINGS: dict[str, str | list[str]] = {
    # Cursor movement
    "cursorUp": "up",
    "cursorDown": "down",
    "cursorLeft": ["left", "ctrl+b"],
    "cursorRight": ["right", "ctrl+f"],
    "cursorWordLeft": ["alt+left", "ctrl+left", "alt+b"],
    "cursorWordRight": ["alt+right", "ctrl+right", "alt+f"],
    "cursorLineStart": ["home", "ctrl+a"],
    "cursorLineEnd": ["end", "ctrl+e"],
    "jumpForward": "ctrl+]",
    "jumpBackward": "ctrl+alt+]",
    "pageUp": "pageUp",
    "pageDown": "pageDown",
    # Deletion
    "deleteCharBackward": "backspace",
    "deleteCharForward": ["delete", "ctrl+d"],
    "deleteWordBackward": ["ctrl+w", "alt+backspace"],
    "deleteWordForward": ["alt+d", "alt+delete"],
    "deleteToLineStart": "ctrl+u",
    "deleteToLineEnd": "ctrl+k",
    # Text input
    "newLine": "shift+enter",
    "submit": "enter",
    "tab": "tab",
    # Selection/autocomplete
    "selectUp": "up",
    "selectDown": "down",
    "selectPageUp": "pageUp",
    "selectPageDown": "pageDown",
    "selectConfirm": "enter",
    "selectCancel": ["escape", "ctrl+c"],
    # Clipboard
    "copy": "ctrl+c",
    # Kill ring
    "yank": "ctrl+y",
    "yankPop": "alt+y",
    # Undo
    "undo": "ctrl+-",
    # Tool output
    "expandTools": "ctrl+o",
    # Session
    "toggleSessionPath": "ctrl+p",
    "toggleSessionSort": "ctrl+s",
    "renameSession": "ctrl+r",
    "deleteSession": "ctrl+d",
    "deleteSessionNoninvasive": "ctrl+backspace",
}


class EditorKeybindingsManager:
    """Manages keybindings for the editor.

    Starts with DEFAULT_EDITOR_KEYBINDINGS and allows overriding via
    a user-supplied config dict.
    """

    def __init__(self, config: EditorKeybindingsConfig | None = None) -> None:
        self._action_to_keys: dict[str, list[str]] = {}
        self._build_maps(config or {})

    def _build_maps(self, config: EditorKeybindingsConfig) -> None:
        """Build the action-to-keys mapping from defaults + overrides."""
        self._action_to_keys.clear()

        # Start with defaults
        for action, keys in DEFAULT_EDITOR_KEYBINDINGS.items():
            if isinstance(keys, list):
                self._action_to_keys[action] = list(keys)
            else:
                self._action_to_keys[action] = [keys]

        # Override with user config
        for action, keys in config.items():
            if isinstance(keys, list):
                self._action_to_keys[action] = list(keys)
            else:
                self._action_to_keys[action] = [keys]

    def matches(self, data: str, action: str) -> bool:
        """Check if input data matches a specific editor action.

        Args:
            data: Raw input data from terminal.
            action: The editor action name to check against.

        Returns:
            True if the input matches any key bound to the action.
        """
        keys = self._action_to_keys.get(action)
        if keys is None:
            return False
        return any(matches_key(data, key) for key in keys)

    def get_keys(self, action: str) -> list[str]:
        """Get the key identifiers bound to an action.

        Args:
            action: The editor action name.

        Returns:
            List of key identifier strings, or empty list if action not found.
        """
        return list(self._action_to_keys.get(action, []))

    def set_config(self, config: EditorKeybindingsConfig) -> None:
        """Update configuration, rebuilding all mappings.

        Args:
            config: New keybindings configuration to apply on top of defaults.
        """
        self._build_maps(config)


# Global instance
_global_editor_keybindings: EditorKeybindingsManager | None = None


def get_editor_keybindings() -> EditorKeybindingsManager:
    """Get the global EditorKeybindingsManager instance.

    Creates one with default keybindings on first access.
    """
    global _global_editor_keybindings
    if _global_editor_keybindings is None:
        _global_editor_keybindings = EditorKeybindingsManager()
    return _global_editor_keybindings


def set_editor_keybindings(manager: EditorKeybindingsManager) -> None:
    """Set the global EditorKeybindingsManager instance.

    Args:
        manager: The manager to use globally.
    """
    global _global_editor_keybindings
    _global_editor_keybindings = manager
