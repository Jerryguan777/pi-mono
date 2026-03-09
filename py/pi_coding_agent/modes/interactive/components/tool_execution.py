"""Component that renders a tool call with its result (updateable)."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pi_coding_agent.modes.interactive.components._theme import (
    get_language_from_path,
    highlight_code,
    theme,
)
from pi_coding_agent.modes.interactive.components.diff import render_diff
from pi_coding_agent.modes.interactive.components.keybinding_hints import key_hint
from pi_coding_agent.modes.interactive.components.visual_truncate import truncate_to_visual_lines
from pi_tui.components.box import Box
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.tui import Container
from pi_tui.utils import truncate_to_width

if TYPE_CHECKING:
    from pi_tui.tui import TUI

_BASH_PREVIEW_LINES = 5
_DEFAULT_MAX_LINES = 16000
_DEFAULT_MAX_BYTES = 5 * 1024 * 1024


def _shorten_path(path: Any) -> str:
    if not isinstance(path, str):
        return ""
    home = os.path.expanduser("~")
    if path.startswith(home):
        return f"~{path[len(home) :]}"
    return path


def _replace_tabs(text: str) -> str:
    return text.replace("\t", "   ")


def _str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return None  # Invalid type


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n // 1024}KB"
    return f"{n // (1024 * 1024)}MB"


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[mK]", "", text)


class ToolExecutionComponent(Container):
    """Renders a tool call with its result; supports expand/collapse and image display."""

    def __init__(
        self,
        tool_name: str,
        args: Any,
        show_images: bool = True,
        tool_definition: Any | None = None,
        ui: TUI | None = None,
        cwd: str | None = None,
    ) -> None:
        super().__init__()
        self._tool_name = tool_name
        self._args = args
        self._show_images = show_images
        self._tool_definition = tool_definition
        self._ui = ui
        self._cwd = cwd or os.getcwd()
        self._expanded = False
        self._is_partial = True
        self._result: Any | None = None
        self._edit_diff_preview: Any | None = None
        self._edit_diff_args_key: str | None = None

        self.add_child(Spacer(1))

        self._content_box = Box(1, 1, lambda t: theme.bg("toolPendingBg", t))
        self._content_text = Text("", 1, 1, lambda t: theme.bg("toolPendingBg", t))

        # Use box for bash or custom tools; text for built-in tools
        if tool_name == "bash" or (tool_definition and not self._should_use_built_in()):
            self.add_child(self._content_box)
        else:
            self.add_child(self._content_text)

        self._update_display()

    def _should_use_built_in(self) -> bool:
        built_in_names = {"bash", "read", "write", "edit", "ls", "find", "grep"}
        is_built_in = self._tool_name in built_in_names
        has_custom = self._tool_definition is not None and (
            getattr(self._tool_definition, "render_call", None) or getattr(self._tool_definition, "render_result", None)
        )
        return is_built_in and not has_custom

    def update_args(self, args: Any) -> None:
        self._args = args
        self._update_display()

    def set_args_complete(self) -> None:
        self._maybe_compute_edit_diff()

    def _maybe_compute_edit_diff(self) -> None:
        if self._tool_name != "edit":
            return
        path = self._args.get("path") if isinstance(self._args, dict) else None
        old_text = self._args.get("oldText") if isinstance(self._args, dict) else None
        new_text = self._args.get("newText") if isinstance(self._args, dict) else None
        if not path or old_text is None or new_text is None:
            return

        args_key = f"{path}:{hash(old_text)}:{hash(new_text)}"
        if self._edit_diff_args_key == args_key:
            return
        self._edit_diff_args_key = args_key

        # Compute diff synchronously (simplified, no async)
        try:
            import difflib

            old_lines = old_text.splitlines(keepends=True)
            new_lines = new_text.splitlines(keepends=True)
            diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=path, tofile=path))
            self._edit_diff_preview = {"diff": "".join(diff)}
        except Exception:
            self._edit_diff_preview = {"error": "Could not compute diff"}

    def update_result(self, result: Any, is_partial: bool = False) -> None:
        self._result = result
        self._is_partial = is_partial
        self._update_display()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._update_display()

    def set_show_images(self, show: bool) -> None:
        self._show_images = show
        self._update_display()

    def invalidate(self) -> None:
        super().invalidate()
        self._update_display()

    def _get_bg_fn(self) -> Callable[[str], str]:
        if self._is_partial:
            return lambda t: theme.bg("toolPendingBg", t)
        if self._result is not None and getattr(self._result, "is_error", False):
            return lambda t: theme.bg("toolErrorBg", t)
        return lambda t: theme.bg("toolSuccessBg", t)

    def _update_display(self) -> None:
        bg_fn = self._get_bg_fn()

        if self._should_use_built_in():
            if self._tool_name == "bash":
                self._content_box.set_bg_fn(bg_fn)
                self._content_box.clear()
                self._render_bash_content()
            else:
                self._content_text.set_custom_bg_fn(bg_fn)
                self._content_text.set_text(self._format_tool_execution())
        elif self._tool_definition is not None:
            self._content_box.set_bg_fn(bg_fn)
            self._content_box.clear()

            render_call = getattr(self._tool_definition, "render_call", None)
            render_result = getattr(self._tool_definition, "render_result", None)

            if render_call:
                try:
                    call_component = render_call(self._args, theme)
                    if call_component is not None:
                        self._content_box.add_child(call_component)
                except Exception:
                    self._content_box.add_child(Text(theme.fg("toolTitle", theme.bold(self._tool_name)), 0, 0))
            else:
                self._content_box.add_child(Text(theme.fg("toolTitle", theme.bold(self._tool_name)), 0, 0))

            if self._result is not None and render_result:
                try:
                    result_data = {
                        "content": getattr(self._result, "content", []),
                        "details": getattr(self._result, "details", None),
                    }
                    result_component = render_result(
                        result_data,
                        {"expanded": self._expanded, "is_partial": self._is_partial},
                        theme,
                    )
                    if result_component is not None:
                        self._content_box.add_child(result_component)
                except Exception:
                    output = self._get_text_output()
                    if output:
                        self._content_box.add_child(Text(theme.fg("toolOutput", output), 0, 0))
            elif self._result is not None:
                output = self._get_text_output()
                if output:
                    self._content_box.add_child(Text(theme.fg("toolOutput", output), 0, 0))

    def _render_bash_content(self) -> None:
        command = _str(self._args.get("command") if isinstance(self._args, dict) else None)
        timeout = self._args.get("timeout") if isinstance(self._args, dict) else None

        timeout_suffix = theme.fg("muted", f" (timeout {timeout}s)") if timeout else ""
        invalid_arg = theme.fg("error", "[invalid arg]")
        if command is None:
            cmd_display = invalid_arg
        elif command:
            cmd_display = command
        else:
            cmd_display = theme.fg("toolOutput", "...")

        self._content_box.add_child(Text(theme.fg("toolTitle", theme.bold(f"$ {cmd_display}")) + timeout_suffix, 0, 0))

        if self._result is not None:
            output = self._get_text_output().strip()
            if output:
                styled_output = "\n".join(theme.fg("toolOutput", line) for line in output.split("\n"))

                if self._expanded:
                    self._content_box.add_child(Text(f"\n{styled_output}", 0, 0))
                else:
                    cached: dict[str, Any] = {}

                    class _BashTruncatedView:
                        def render(self, width: int) -> list[str]:
                            if cached.get("width") != width:
                                result = truncate_to_visual_lines(styled_output, _BASH_PREVIEW_LINES, width)
                                cached["lines"] = result.visual_lines
                                cached["skipped"] = result.skipped_count
                                cached["width"] = width
                            lines: list[str] = cached.get("lines", [])
                            skipped: int = cached.get("skipped", 0)
                            if skipped > 0:
                                hint = (
                                    theme.fg("muted", f"... ({skipped} earlier lines,")
                                    + f" {key_hint('expandTools', 'to expand')})"
                                )
                                return ["", truncate_to_width(hint, width, "..."), *lines]
                            return ["", *lines]

                        def invalidate(self) -> None:
                            cached.clear()

                        def handle_input(self, data: str) -> None:
                            pass

                        @property
                        def wants_key_release(self) -> bool:
                            return False

                    self._content_box.add_child(_BashTruncatedView())

            if self._result is not None:
                details = getattr(self._result, "details", None) or {}
                if isinstance(details, dict):
                    truncation = details.get("truncation")
                    full_output_path = details.get("fullOutputPath")
                else:
                    truncation = getattr(details, "truncation", None)
                    full_output_path = getattr(details, "full_output_path", None)

                warnings: list[str] = []
                if full_output_path:
                    warnings.append(f"Full output: {full_output_path}")
                if truncation and getattr(truncation, "truncated", False):
                    if getattr(truncation, "truncated_by", None) == "lines":
                        out_lines = getattr(truncation, "output_lines", 0)
                        total_lines = getattr(truncation, "total_lines", 0)
                        warnings.append(f"Truncated: showing {out_lines} of {total_lines} lines")
                    else:
                        out_lines = getattr(truncation, "output_lines", 0)
                        max_b = _format_size(getattr(truncation, "max_bytes", _DEFAULT_MAX_BYTES))
                        warnings.append(f"Truncated: {out_lines} lines shown ({max_b} limit)")
                if warnings:
                    self._content_box.add_child(Text(f"\n{theme.fg('warning', f'[{chr(46).join(warnings)}]')}", 0, 0))

    def _get_text_output(self) -> str:
        if self._result is None:
            return ""
        content = getattr(self._result, "content", []) or []
        text_blocks = [
            c
            for c in content
            if (isinstance(c, dict) and c.get("type") == "text") or (hasattr(c, "type") and c.type == "text")
        ]
        return "\n".join(
            _strip_ansi(c.get("text", "") if isinstance(c, dict) else getattr(c, "text", "")).replace("\r", "")
            for c in text_blocks
        )

    def _format_tool_execution(self) -> str:
        invalid_arg = theme.fg("error", "[invalid arg]")
        text = ""

        if self._tool_name == "read":
            args_dict = self._args if isinstance(self._args, dict) else {}
            raw_path = _str(args_dict.get("file_path") or args_dict.get("path"))
            path = _shorten_path(raw_path) if raw_path is not None else None
            offset = args_dict.get("offset")
            limit = args_dict.get("limit")

            if path is None:
                path_display = invalid_arg
            elif path:
                path_display = theme.fg("accent", path)
            else:
                path_display = theme.fg("toolOutput", "...")

            if offset is not None or limit is not None:
                start_line = offset or 1
                end_line = start_line + limit - 1 if limit is not None else ""
                path_display += theme.fg("warning", f":{start_line}{f'-{end_line}' if end_line else ''}")

            text = f"{theme.fg('toolTitle', theme.bold('read'))} {path_display}"

            if self._result is not None:
                output = self._get_text_output()
                lang = get_language_from_path(raw_path) if raw_path else None
                lines = highlight_code(_replace_tabs(output), lang) if lang else output.split("\n")
                max_lines = len(lines) if self._expanded else 10
                display_lines = lines[:max_lines]
                remaining = len(lines) - max_lines
                text += "\n\n" + "\n".join(
                    _replace_tabs(ln) if lang else theme.fg("toolOutput", _replace_tabs(ln)) for ln in display_lines
                )
                if remaining > 0:
                    more = theme.fg("muted", f"... ({remaining} more lines,")
                    text += f"{more} {key_hint('expandTools', 'to expand')})"

        elif self._tool_name == "write":
            args_dict = self._args if isinstance(self._args, dict) else {}
            raw_path = _str(args_dict.get("file_path") or args_dict.get("path"))
            file_content = _str(args_dict.get("content"))
            path = _shorten_path(raw_path) if raw_path is not None else None

            if path is None:
                path_display = invalid_arg
            elif path:
                path_display = theme.fg("accent", path)
            else:
                path_display = theme.fg("toolOutput", "...")
            text = f"{theme.fg('toolTitle', theme.bold('write'))} {path_display}"

            if file_content is None:
                text += f"\n\n{theme.fg('error', '[invalid content arg - expected string]')}"
            elif file_content:
                lang = get_language_from_path(raw_path) if raw_path else None
                lines = highlight_code(_replace_tabs(file_content), lang) if lang else file_content.split("\n")
                max_lines = len(lines) if self._expanded else 10
                remaining = len(lines) - max_lines
                text += "\n\n" + "\n".join(
                    _replace_tabs(ln) if lang else theme.fg("toolOutput", _replace_tabs(ln)) for ln in lines[:max_lines]
                )
                if remaining > 0:
                    more = theme.fg("muted", f"\n... ({remaining} more lines, {len(lines)} total,")
                    text += more + f" {key_hint('expandTools', 'to expand')})"

            if self._result is not None and getattr(self._result, "is_error", False):
                error_text = self._get_text_output()
                if error_text:
                    text += f"\n\n{theme.fg('error', error_text)}"

        elif self._tool_name == "edit":
            args_dict = self._args if isinstance(self._args, dict) else {}
            raw_path = _str(args_dict.get("file_path") or args_dict.get("path"))
            path = _shorten_path(raw_path) if raw_path is not None else None
            if path is None:
                path_display = invalid_arg
            elif path:
                path_display = theme.fg("accent", path)
            else:
                path_display = theme.fg("toolOutput", "...")

            first_changed_line = None
            if self._edit_diff_preview and "firstChangedLine" in (self._edit_diff_preview or {}):
                first_changed_line = self._edit_diff_preview.get("firstChangedLine")
            if first_changed_line:
                path_display += theme.fg("warning", f":{first_changed_line}")

            text = f"{theme.fg('toolTitle', theme.bold('edit'))} {path_display}"

            if self._result is not None and getattr(self._result, "is_error", False):
                error_text = self._get_text_output()
                if error_text:
                    text += f"\n\n{theme.fg('error', error_text)}"
            elif (
                self._result is not None
                and isinstance(getattr(self._result, "details", None), dict)
                and self._result.details.get("diff")
            ):
                text += f"\n\n{render_diff(self._result.details['diff'], raw_path)}"
            elif self._edit_diff_preview:
                if "error" in self._edit_diff_preview:
                    text += f"\n\n{theme.fg('error', self._edit_diff_preview['error'])}"
                elif self._edit_diff_preview.get("diff"):
                    text += f"\n\n{render_diff(self._edit_diff_preview['diff'], raw_path)}"

        elif self._tool_name == "ls":
            args_dict = self._args if isinstance(self._args, dict) else {}
            raw_path = _str(args_dict.get("path"))
            path = _shorten_path(raw_path or ".") if raw_path is not None else None
            limit = args_dict.get("limit")

            path_display = invalid_arg if path is None else theme.fg("accent", path)
            text = f"{theme.fg('toolTitle', theme.bold('ls'))} {path_display}"
            if limit is not None:
                text += theme.fg("toolOutput", f" (limit {limit})")

            if self._result is not None:
                output = self._get_text_output().strip()
                if output:
                    lines = output.split("\n")
                    max_lines = len(lines) if self._expanded else 20
                    remaining = len(lines) - max_lines
                    text += "\n\n" + "\n".join(theme.fg("toolOutput", ln) for ln in lines[:max_lines])
                    if remaining > 0:
                        more = theme.fg("muted", f"... ({remaining} more lines,")
                        text += f"{more} {key_hint('expandTools', 'to expand')})"

        elif self._tool_name in ("find", "grep"):
            args_dict = self._args if isinstance(self._args, dict) else {}
            pattern = _str(args_dict.get("pattern"))
            raw_path = _str(args_dict.get("path"))
            path = _shorten_path(raw_path or ".") if raw_path is not None else None
            glob = _str(args_dict.get("glob"))
            limit = args_dict.get("limit")

            if self._tool_name == "grep":
                pattern_display = invalid_arg if pattern is None else theme.fg("accent", f"/{pattern or ''}/")
            else:
                pattern_display = invalid_arg if pattern is None else theme.fg("accent", pattern or "")

            path_display = invalid_arg if path is None else path
            in_text = theme.fg("toolOutput", f" in {path_display}")
            text = f"{theme.fg('toolTitle', theme.bold(self._tool_name))} {pattern_display}{in_text}"
            if glob:
                text += theme.fg("toolOutput", f" ({glob})")
            if limit is not None:
                text += theme.fg("toolOutput", f" limit {limit}")

            if self._result is not None:
                output = self._get_text_output().strip()
                if output:
                    lines = output.split("\n")
                    max_lines = len(lines) if self._expanded else 15
                    remaining = len(lines) - max_lines
                    text += "\n\n" + "\n".join(theme.fg("toolOutput", ln) for ln in lines[:max_lines])
                    if remaining > 0:
                        more = theme.fg("muted", f"... ({remaining} more lines,")
                        text += f"{more} {key_hint('expandTools', 'to expand')})"

        else:
            text = theme.fg("toolTitle", theme.bold(self._tool_name))
            import json

            try:
                content = json.dumps(self._args, indent=2)
            except Exception:
                content = str(self._args)
            text += f"\n\n{content}"
            output = self._get_text_output()
            if output:
                text += f"\n{output}"

        return text
