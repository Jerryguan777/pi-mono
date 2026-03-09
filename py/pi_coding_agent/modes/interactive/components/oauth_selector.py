"""OAuth provider selector for login/logout flows."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_tui.components.spacer import Spacer
from pi_tui.components.truncated_text import TruncatedText
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.tui import Container


class OAuthSelectorComponent(Container):
    """Renders a list of OAuth providers for login or logout selection."""

    def __init__(
        self,
        mode: str,  # "login" | "logout"
        auth_storage: Any,
        on_select: Callable[[str], None],
        on_cancel: Callable[[], None],
        oauth_providers: list[Any] | None = None,
    ) -> None:
        super().__init__()
        self._mode = mode
        self._auth_storage = auth_storage
        self._on_select = on_select
        self._on_cancel = on_cancel
        self._selected_index = 0
        self._all_providers: list[Any] = oauth_providers or []

        self.add_child(DynamicBorder())
        self.add_child(Spacer(1))

        title = "Select provider to login:" if mode == "login" else "Select provider to logout:"
        self.add_child(TruncatedText(theme.bold(title)))
        self.add_child(Spacer(1))

        self._list_container = Container()
        self.add_child(self._list_container)
        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())

        self._update_list()

    def _update_list(self) -> None:
        self._list_container.clear()

        for i, provider in enumerate(self._all_providers):
            is_selected = i == self._selected_index
            provider_id = getattr(provider, "id", str(provider))
            provider_name = getattr(provider, "name", provider_id)

            credentials = self._auth_storage.get(provider_id) if hasattr(self._auth_storage, "get") else None
            is_logged_in = getattr(credentials, "type", None) == "oauth"
            status = theme.fg("success", " \u2713 logged in") if is_logged_in else ""

            if is_selected:
                line = theme.fg("accent", "\u2192 ") + theme.fg("accent", provider_name) + status
            else:
                line = f"  {provider_name}{status}"

            self._list_container.add_child(TruncatedText(line, 0, 0))

        if not self._all_providers:
            msg = (
                "No OAuth providers available"
                if self._mode == "login"
                else "No OAuth providers logged in. Use /login first."
            )
            self._list_container.add_child(TruncatedText(theme.fg("muted", f"  {msg}"), 0, 0))

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()
        if kb.matches(data, "selectUp"):
            self._selected_index = max(0, self._selected_index - 1)
            self._update_list()
        elif kb.matches(data, "selectDown"):
            self._selected_index = min(len(self._all_providers) - 1, self._selected_index + 1)
            self._update_list()
        elif kb.matches(data, "selectConfirm"):
            if self._all_providers:
                provider = self._all_providers[self._selected_index]
                self._on_select(getattr(provider, "id", str(provider)))
        elif kb.matches(data, "selectCancel"):
            self._on_cancel()
