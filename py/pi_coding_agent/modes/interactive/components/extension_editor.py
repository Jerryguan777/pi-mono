"""Multi-line editor component for extensions with optional external editor support."""

from __future__ import annotations

import contextlib
import os
import shlex
import subprocess
import tempfile
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pi_coding_agent.modes.interactive.components._theme import get_editor_theme, theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.keybinding_hints import app_key_hint, key_hint
from pi_tui.components.editor import Editor, EditorOptions
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.keybindings import get_editor_keybindings
from pi_tui.tui import Container

if TYPE_CHECKING:
    from pi_tui.tui import TUI


class ExtensionEditorComponent(Container):
    """Multi-line editor for extension-driven text input.

    Supports Ctrl+G (or configured externalEditor keybinding) to open an external
    editor. Submit via Enter; cancel via Escape.
    """

    def __init__(
        self,
        tui: TUI,
        keybindings: Any,
        title: str,
        prefill: str | None,
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
        options: EditorOptions | None = None,
    ) -> None:
        super().__init__()
        self._tui = tui
        self._keybindings = keybindings
        self._on_submit = on_submit
        self._on_cancel = on_cancel

        self.add_child(DynamicBorder())
        self.add_child(Spacer(1))
        self.add_child(Text(theme.fg("accent", title), 1, 0))
        self.add_child(Spacer(1))

        self._editor = Editor(tui, get_editor_theme(), options)
        if prefill:
            self._editor.set_text(prefill)

        self._editor.on_submit = lambda text: self._on_submit(text)
        self.add_child(self._editor)
        self.add_child(Spacer(1))

        has_external = bool(os.environ.get("VISUAL") or os.environ.get("EDITOR"))
        hint = (
            key_hint("selectConfirm", "submit")
            + "  "
            + key_hint("newLine", "newline")
            + "  "
            + key_hint("selectCancel", "cancel")
        )
        if has_external:
            hint += "  " + app_key_hint(keybindings, "externalEditor", "external editor")
        self.add_child(Text(hint, 1, 0))
        self.add_child(Spacer(1))
        self.add_child(DynamicBorder())

    def handle_input(self, data: str) -> None:
        kb = get_editor_keybindings()
        if kb.matches(data, "selectCancel"):
            self._on_cancel()
            return
        if hasattr(self._keybindings, "matches") and self._keybindings.matches(data, "externalEditor"):
            self._open_external_editor()
            return
        self._editor.handle_input(data)

    def _open_external_editor(self) -> None:
        editor_cmd = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if not editor_cmd:
            return

        current_text = self._editor.get_text()
        with tempfile.NamedTemporaryFile(
            suffix=".md", prefix="pi-extension-editor-", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(current_text)
            tmp_path = f.name

        try:
            self._tui.stop()
            parts = shlex.split(editor_cmd)
            result = subprocess.run([*parts, tmp_path], check=False)
            if result.returncode == 0:
                with open(tmp_path, encoding="utf-8") as f:
                    new_content = f.read().rstrip("\n")
                self._editor.set_text(new_content)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            self._tui.start()
            self._tui.request_render(True)
