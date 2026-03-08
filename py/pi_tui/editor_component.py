"""Protocol for custom editor components.

Port of editor-component.ts. Allows extensions to provide their own editor
implementation (e.g., vim mode, emacs mode, custom keybindings) while
maintaining compatibility with the core application.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EditorComponent(Protocol):
    """Interface for custom editor components.

    Extends the base Component protocol with text editing capabilities,
    callbacks, history, autocomplete, and appearance configuration.
    """

    # =========================================================================
    # Core text access (required)
    # =========================================================================

    def get_text(self) -> str:
        """Get the current text content."""
        ...

    def set_text(self, text: str) -> None:
        """Set the text content."""
        ...

    def handle_input(self, data: str) -> None:
        """Handle raw terminal input (key presses, paste sequences, etc.)."""
        ...

    def render(self, width: int) -> list[str]:
        """Render the component to lines for the given viewport width."""
        ...

    def invalidate(self) -> None:
        """Mark the component as needing re-render."""
        ...

    # =========================================================================
    # Callbacks (required)
    # =========================================================================

    on_submit: Callable[[str], None] | None
    """Called when user submits (e.g., Enter key)."""

    on_change: Callable[[str], None] | None
    """Called when text changes."""

    # =========================================================================
    # History support (optional)
    # =========================================================================

    def add_to_history(self, text: str) -> None:
        """Add text to history for up/down navigation."""
        ...

    # =========================================================================
    # Advanced text manipulation (optional)
    # =========================================================================

    def insert_text_at_cursor(self, text: str) -> None:
        """Insert text at current cursor position."""
        ...

    def get_expanded_text(self) -> str:
        """Get text with any markers expanded (e.g., paste markers).

        Falls back to get_text() if not implemented.
        """
        ...

    # =========================================================================
    # Autocomplete support (optional)
    # =========================================================================

    def set_autocomplete_provider(self, provider: Any) -> None:
        """Set the autocomplete provider."""
        ...

    # =========================================================================
    # Appearance (optional)
    # =========================================================================

    border_color: Callable[[str], str] | None
    """Border color function."""

    def set_padding_x(self, padding: int) -> None:
        """Set horizontal padding."""
        ...

    def set_autocomplete_max_visible(self, max_visible: int) -> None:
        """Set max visible items in autocomplete dropdown."""
        ...
