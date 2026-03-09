"""Component that renders a custom message entry from extensions."""

from __future__ import annotations

from typing import Any

from pi_coding_agent.modes.interactive.components._theme import get_markdown_theme, theme
from pi_tui.components.box import Box
from pi_tui.components.markdown import Markdown, MarkdownTheme
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.tui import Container


class CustomMessageComponent(Container):
    """Renders a custom message from an extension.

    If a custom renderer is provided it is called first. The renderer may
    return a component (which is used directly) or ``None`` (falls back to
    the default box-based layout).
    """

    def __init__(
        self,
        message: Any,
        custom_renderer: Any | None = None,
        markdown_theme: MarkdownTheme | None = None,
    ) -> None:
        super().__init__()
        self._message = message
        self._custom_renderer = custom_renderer
        self._markdown_theme: MarkdownTheme = markdown_theme if markdown_theme is not None else get_markdown_theme()
        self._expanded = False

        self.add_child(Spacer(1))

        self._box = Box(1, 1, lambda t: theme.bg("customMessageBg", t))
        self._custom_component: Any | None = None

        self._rebuild()

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded != expanded:
            self._expanded = expanded
            self._rebuild()

    def invalidate(self) -> None:
        super().invalidate()
        self._rebuild()

    def _rebuild(self) -> None:
        if self._custom_component is not None:
            self.remove_child(self._custom_component)
            self._custom_component = None
        self.remove_child(self._box)

        # Try custom renderer first
        if self._custom_renderer is not None:
            try:
                component = self._custom_renderer(self._message, {"expanded": self._expanded}, theme)
                if component is not None:
                    self._custom_component = component
                    self.add_child(component)
                    return
            except Exception:
                pass

        # Default rendering
        self.add_child(self._box)
        self._box.clear()

        custom_type = getattr(self._message, "custom_type", getattr(self._message, "customType", "custom"))
        label = theme.fg("customMessageLabel", f"\x1b[1m[{custom_type}]\x1b[22m")
        self._box.add_child(Text(label, 0, 0))
        self._box.add_child(Spacer(1))

        content = getattr(self._message, "content", "")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "\n".join(
                c.get("text", "") if isinstance(c, dict) else getattr(c, "text", "")
                for c in content
                if (isinstance(c, dict) and c.get("type") == "text") or (hasattr(c, "type") and c.type == "text")
            )
        else:
            text = str(content)

        self._box.add_child(Markdown(text, 0, 0, self._markdown_theme))
