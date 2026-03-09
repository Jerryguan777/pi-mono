"""Component that renders a complete assistant message."""

from __future__ import annotations

from pi_coding_agent.modes.interactive.components._theme import get_markdown_theme, theme
from pi_tui.components.markdown import DefaultTextStyle, Markdown, MarkdownTheme
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.tui import Container


class AssistantMessageComponent(Container):
    """Renders a complete assistant message with text and thinking blocks."""

    def __init__(
        self,
        message: object | None = None,
        hide_thinking_block: bool = False,
        markdown_theme: MarkdownTheme | None = None,
    ) -> None:
        super().__init__()
        self._hide_thinking_block = hide_thinking_block
        self._markdown_theme: MarkdownTheme = markdown_theme if markdown_theme is not None else get_markdown_theme()
        self._last_message: object | None = None

        self._content_container = Container()
        self.add_child(self._content_container)

        if message is not None:
            self.update_content(message)

    def invalidate(self) -> None:
        super().invalidate()
        if self._last_message is not None:
            self.update_content(self._last_message)

    def set_hide_thinking_block(self, hide: bool) -> None:
        self._hide_thinking_block = hide

    def update_content(self, message: object) -> None:
        """Rebuild the content container from an assistant message."""
        self._last_message = message
        self._content_container.clear()

        content_blocks: list[object] = getattr(message, "content", [])

        has_visible_content = any(
            (getattr(b, "type", None) == "text" and str(getattr(b, "text", "")).strip())
            or (getattr(b, "type", None) == "thinking" and str(getattr(b, "thinking", "")).strip())
            for b in content_blocks
        )

        if has_visible_content:
            self._content_container.add_child(Spacer(1))

        for i, block in enumerate(content_blocks):
            btype = getattr(block, "type", None)
            if btype == "text":
                text_val = str(getattr(block, "text", "")).strip()
                if text_val:
                    self._content_container.add_child(Markdown(text_val, 1, 0, self._markdown_theme))
            elif btype == "thinking":
                thinking_val = str(getattr(block, "thinking", "")).strip()
                if thinking_val:
                    has_visible_after = any(
                        (getattr(c, "type", None) == "text" and str(getattr(c, "text", "")).strip())
                        or (getattr(c, "type", None) == "thinking" and str(getattr(c, "thinking", "")).strip())
                        for c in content_blocks[i + 1 :]
                    )
                    if self._hide_thinking_block:
                        self._content_container.add_child(
                            Text(theme.italic(theme.fg("thinkingText", "Thinking...")), 1, 0)
                        )
                        if has_visible_after:
                            self._content_container.add_child(Spacer(1))
                    else:
                        thinking_style = DefaultTextStyle(
                            color=lambda t: theme.fg("thinkingText", t),
                            italic=True,
                        )
                        self._content_container.add_child(
                            Markdown(thinking_val, 1, 0, self._markdown_theme, thinking_style)
                        )
                        if has_visible_after:
                            self._content_container.add_child(Spacer(1))

        # Show abort/error status if there are no tool calls
        has_tool_calls = any(getattr(b, "type", None) == "toolCall" for b in content_blocks)
        if not has_tool_calls:
            stop_reason = getattr(message, "stop_reason", None)
            error_msg = getattr(message, "error_message", None)
            if stop_reason == "aborted":
                abort_message = error_msg if error_msg and error_msg != "Request was aborted" else "Operation aborted"
                self._content_container.add_child(Spacer(1))
                self._content_container.add_child(Text(theme.fg("error", abort_message), 1, 0))
            elif stop_reason == "error":
                err = error_msg or "Unknown error"
                self._content_container.add_child(Spacer(1))
                self._content_container.add_child(Text(theme.fg("error", f"Error: {err}"), 1, 0))
