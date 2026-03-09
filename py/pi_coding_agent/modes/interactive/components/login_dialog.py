"""Login dialog component for OAuth authentication flows."""

from __future__ import annotations

import contextlib
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import Future
from typing import TYPE_CHECKING

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.keybinding_hints import key_hint
from pi_tui.components.input import Input
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.tui import Container

if TYPE_CHECKING:
    from pi_tui.tui import TUI


class LoginDialogComponent(Container):
    """Replaces the editor during OAuth login flows.

    Implements the Focusable protocol by propagating focus to the inner Input.
    """

    def __init__(
        self,
        tui: TUI,
        provider_id: str,
        on_complete: Callable[[bool, str | None], None],
        provider_name: str | None = None,
    ) -> None:
        super().__init__()
        self._tui = tui
        self._on_complete = on_complete
        self._focused = False
        self._cancelled = False

        self._input_resolver: Callable[[str], None] | None = None
        self._input_rejecter: Callable[[Exception], None] | None = None

        display_name = provider_name or provider_id

        self.add_child(DynamicBorder())
        self.add_child(Text(theme.fg("warning", f"Login to {display_name}"), 1, 0))

        self._content_container = Container()
        self.add_child(self._content_container)

        self._input = Input()
        self._input.on_submit = self._on_input_submit
        self._input.on_escape = self._cancel

        self.add_child(DynamicBorder())

    # --- Focusable protocol ---

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value
        self._input.focused = value

    # --- Public API (called from OAuth flow callbacks) ---

    def show_auth(self, url: str, instructions: str | None = None) -> None:
        """Show the auth URL and optional instructions; attempt to open a browser."""
        self._content_container.clear()
        self._content_container.add_child(Spacer(1))
        self._content_container.add_child(Text(theme.fg("accent", url), 1, 0))

        click_hint = "Cmd+click to open" if sys.platform == "darwin" else "Ctrl+click to open"
        hyperlink = f"\x1b]8;;{url}\x07{click_hint}\x1b]8;;\x07"
        self._content_container.add_child(Text(theme.fg("dim", hyperlink), 1, 0))

        if instructions:
            self._content_container.add_child(Spacer(1))
            self._content_container.add_child(Text(theme.fg("warning", instructions), 1, 0))

        open_cmd = "open" if sys.platform == "darwin" else ("start" if sys.platform == "win32" else "xdg-open")
        with contextlib.suppress(OSError):
            subprocess.Popen([open_cmd, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self._tui.request_render()

    def show_manual_input(self, prompt: str) -> Future[str]:
        """Show input for manual code/URL entry. Returns a Future resolved when submitted."""
        self._content_container.add_child(Spacer(1))
        self._content_container.add_child(Text(theme.fg("dim", prompt), 1, 0))
        self._content_container.add_child(self._input)
        self._content_container.add_child(Text(f"({key_hint('selectCancel', 'to cancel')})", 1, 0))
        self._tui.request_render()
        return self._make_input_future()

    def show_prompt(self, message: str, placeholder: str | None = None) -> Future[str]:
        """Show a prompt and wait for input (appends to existing content)."""
        self._content_container.add_child(Spacer(1))
        self._content_container.add_child(Text(theme.fg("text", message), 1, 0))
        if placeholder:
            self._content_container.add_child(Text(theme.fg("dim", f"e.g., {placeholder}"), 1, 0))
        self._content_container.add_child(self._input)
        self._content_container.add_child(
            Text(
                f"({key_hint('selectCancel', 'to cancel,')} {key_hint('selectConfirm', 'to submit')})",
                1,
                0,
            )
        )
        self._input.set_value("")
        self._tui.request_render()
        return self._make_input_future()

    def show_waiting(self, message: str) -> None:
        """Show a waiting message (for polling-based providers)."""
        self._content_container.add_child(Spacer(1))
        self._content_container.add_child(Text(theme.fg("dim", message), 1, 0))
        self._content_container.add_child(Text(f"({key_hint('selectCancel', 'to cancel')})", 1, 0))
        self._tui.request_render()

    def show_progress(self, message: str) -> None:
        """Show a progress message appended to existing content."""
        self._content_container.add_child(Text(theme.fg("dim", message), 1, 0))
        self._tui.request_render()

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()
        if kb.matches(data, "selectCancel"):
            self._cancel()
            return
        self._input.handle_input(data)

    # --- Private helpers ---

    def _make_input_future(self) -> Future[str]:
        future: Future[str] = Future()

        def resolve(value: str) -> None:
            if not future.done():
                future.set_result(value)
            self._input_resolver = None
            self._input_rejecter = None

        def reject(exc: Exception) -> None:
            if not future.done():
                future.set_exception(exc)
            self._input_resolver = None
            self._input_rejecter = None

        self._input_resolver = resolve
        self._input_rejecter = reject
        return future

    def _on_input_submit(self, value: str | None = None) -> None:
        v = value if value is not None else self._input.get_value()
        if self._input_resolver is not None:
            self._input_resolver(v)

    def _cancel(self) -> None:
        if self._cancelled:
            return
        self._cancelled = True
        if self._input_rejecter is not None:
            self._input_rejecter(RuntimeError("Login cancelled"))
        self._on_complete(False, "Login cancelled")
