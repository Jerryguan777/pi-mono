"""Utilities for formatting keybinding hints in the UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_tui.keybindings import EditorAction, get_editor_keybindings

if TYPE_CHECKING:
    pass


def _format_keys(keys: list[str]) -> str:
    """Format a list of key IDs as a display string (e.g. 'ctrl+c/escape')."""
    if not keys:
        return ""
    if len(keys) == 1:
        return keys[0]
    return "/".join(keys)


def editor_key(action: EditorAction) -> str:
    """Return display string for an editor action."""
    kb = get_editor_keybindings()
    return _format_keys(kb.get_keys(action))


def app_key(keybindings: object, action: str) -> str:
    """Return display string for an app action."""
    if hasattr(keybindings, "get_keys"):
        return _format_keys(keybindings.get_keys(action))
    return action


def key_hint(action: EditorAction, description: str) -> str:
    """Format a keybinding hint: dim key + muted description.

    Looks up the key from editor keybindings automatically.
    """
    return theme.fg("dim", editor_key(action)) + theme.fg("muted", f" {description}")


def app_key_hint(keybindings: object, action: str, description: str) -> str:
    """Format a keybinding hint for an app-level action."""
    return theme.fg("dim", app_key(keybindings, action)) + theme.fg("muted", f" {description}")


def raw_key_hint(key: str, description: str) -> str:
    """Format a raw key string with description (for non-configurable keys like ↑↓)."""
    return theme.fg("dim", key) + theme.fg("muted", f" {description}")


def _create_default_keybindings() -> object:
    """Create a minimal default keybindings object (no-op for all app actions)."""

    class _DefaultKeybindings:
        def matches(self, _data: str, _action: str) -> bool:
            return False

        def get_keys(self, _action: str) -> list[str]:
            return []

    return _DefaultKeybindings()
