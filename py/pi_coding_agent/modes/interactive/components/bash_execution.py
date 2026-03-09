"""Component for displaying bash command execution with streaming output."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.keybinding_hints import editor_key, key_hint
from pi_coding_agent.modes.interactive.components.visual_truncate import truncate_to_visual_lines
from pi_tui.components.loader import Loader
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.tui import Container

if TYPE_CHECKING:
    from pi_tui.tui import TUI

# Preview line limit when not expanded
_PREVIEW_LINES = 20
_DEFAULT_MAX_LINES = 32_768
_DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)


def _truncate_tail(text: str, max_lines: int, max_bytes: int) -> tuple[str, bool]:
    """Truncate to the tail of output within line and byte limits."""
    if len(text.encode()) <= max_bytes:
        lines = text.split("\n")
        if len(lines) <= max_lines:
            return text, False
        return "\n".join(lines[-max_lines:]), True
    # Byte-limit truncation
    encoded = text.encode()[-max_bytes:]
    truncated = encoded.decode("utf-8", errors="replace")
    return truncated, True


class BashExecutionComponent(Container):
    """Displays a bash command execution with streaming output."""

    def __init__(self, command: str, ui: TUI, exclude_from_context: bool = False) -> None:
        super().__init__()
        self._command = command
        self._ui = ui
        self._output_lines: list[str] = []
        self._status: str = "running"
        self._exit_code: int | None = None
        self._truncation_result: tuple[str, bool] | None = None
        self._full_output_path: str | None = None
        self._expanded = False

        color_key = "dim" if exclude_from_context else "bashMode"
        border_color = lambda s: theme.fg(color_key, s)  # noqa: E731

        self.add_child(Spacer(1))
        self.add_child(DynamicBorder(border_color))

        self._content_container = Container()
        self.add_child(self._content_container)

        header = Text(theme.fg(color_key, theme.bold(f"$ {command}")), 1, 0)
        self._content_container.add_child(header)

        self._loader = Loader(
            ui,
            lambda s: theme.fg(color_key, s),
            lambda t: theme.fg("muted", t),
            f"Running... ({editor_key('selectCancel')} to cancel)",
        )
        self._content_container.add_child(self._loader)

        self.add_child(DynamicBorder(border_color))

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._update_display()

    def invalidate(self) -> None:
        super().invalidate()
        self._update_display()

    def append_output(self, chunk: str) -> None:
        """Append a chunk of output (strips ANSI, normalises line endings)."""
        clean = _strip_ansi(chunk).replace("\r\n", "\n").replace("\r", "\n")
        new_lines = clean.split("\n")
        if self._output_lines and new_lines:
            self._output_lines[-1] += new_lines[0]
            self._output_lines.extend(new_lines[1:])
        else:
            self._output_lines.extend(new_lines)
        self._update_display()

    def set_complete(
        self,
        exit_code: int | None,
        cancelled: bool,
        truncation_result: Any | None = None,
        full_output_path: str | None = None,
    ) -> None:
        """Mark execution as complete."""
        self._exit_code = exit_code
        if cancelled:
            self._status = "cancelled"
        elif exit_code is not None and exit_code != 0:
            self._status = "error"
        else:
            self._status = "complete"
        self._truncation_result = truncation_result
        self._full_output_path = full_output_path
        self._loader.stop()
        self._update_display()

    def get_output(self) -> str:
        return "\n".join(self._output_lines)

    def get_command(self) -> str:
        return self._command

    def _update_display(self) -> None:
        full_output = "\n".join(self._output_lines)
        context_content, context_truncated = _truncate_tail(full_output, _DEFAULT_MAX_LINES, _DEFAULT_MAX_BYTES)
        available_lines = context_content.split("\n") if context_content else []

        preview_lines = available_lines[-_PREVIEW_LINES:]
        hidden_line_count = len(available_lines) - len(preview_lines)

        self._content_container.clear()

        header = Text(theme.fg("bashMode", theme.bold(f"$ {self._command}")), 1, 0)
        self._content_container.add_child(header)

        if available_lines:
            if self._expanded:
                display_text = "\n".join(theme.fg("muted", line) for line in available_lines)
                self._content_container.add_child(Text(f"\n{display_text}", 1, 0))
            else:
                styled_output = "\n".join(theme.fg("muted", line) for line in preview_lines)

                def _make_truncated_renderer(styled: str) -> object:
                    cache: dict[str, Any] = {}

                    def render(width: int) -> list[str]:
                        if cache.get("width") != width:
                            result = truncate_to_visual_lines(f"\n{styled}", _PREVIEW_LINES, width, 1)
                            cache["width"] = width
                            cache["lines"] = result.visual_lines
                            cache["skipped"] = result.skipped_count
                        return cache["lines"]  # type: ignore[no-any-return]

                    def invalidate() -> None:
                        cache.clear()

                    class _Renderer:
                        def render(self, w: int) -> list[str]:
                            return render(w)

                        def invalidate(self) -> None:
                            return invalidate()

                    return _Renderer()

                self._content_container.add_child(_make_truncated_renderer(styled_output))

        if self._status == "running":
            self._content_container.add_child(self._loader)
        else:
            status_parts: list[str] = []
            if hidden_line_count > 0:
                if self._expanded:
                    status_parts.append(f"({key_hint('expandTools', 'to collapse')})")
                else:
                    more = theme.fg("muted", f"... {hidden_line_count} more lines")
                    status_parts.append(f"{more} ({key_hint('expandTools', 'to expand')})")

            if self._status == "cancelled":
                status_parts.append(theme.fg("warning", "(cancelled)"))
            elif self._status == "error":
                status_parts.append(theme.fg("error", f"(exit {self._exit_code})"))

            was_truncated = context_truncated or (
                self._truncation_result is not None and getattr(self._truncation_result, "truncated", False)
            )
            if was_truncated and self._full_output_path:
                status_parts.append(theme.fg("warning", f"Output truncated. Full output: {self._full_output_path}"))

            if status_parts:
                self._content_container.add_child(Text(f"\n{chr(10).join(status_parts)}", 1, 0))
