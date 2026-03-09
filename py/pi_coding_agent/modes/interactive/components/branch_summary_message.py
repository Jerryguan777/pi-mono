"""Component that renders a branch summary message with collapsed/expanded state."""

from __future__ import annotations

from pi_coding_agent.modes.interactive.components._theme import get_markdown_theme, theme
from pi_coding_agent.modes.interactive.components.keybinding_hints import editor_key
from pi_tui.components.box import Box
from pi_tui.components.markdown import Markdown, MarkdownTheme
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text


class BranchSummaryMessageComponent(Box):
    """Renders a branch summary message with collapsed/expanded state.

    Uses the same background as custom messages for visual consistency.
    """

    def __init__(
        self,
        message: object,
        markdown_theme: MarkdownTheme | None = None,
    ) -> None:
        super().__init__(1, 1, lambda t: theme.bg("customMessageBg", t))
        self._message = message
        self._markdown_theme: MarkdownTheme = markdown_theme if markdown_theme is not None else get_markdown_theme()
        self._expanded = False
        self._update_display()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._update_display()

    def invalidate(self) -> None:
        super().invalidate()
        self._update_display()

    def _update_display(self) -> None:
        self.clear()

        label = theme.fg("customMessageLabel", "\x1b[1m[branch]\x1b[22m")
        self.add_child(Text(label, 0, 0))
        self.add_child(Spacer(1))

        summary = getattr(self._message, "summary", "")

        if self._expanded:
            header = "**Branch Summary**\n\n"
            self.add_child(
                Markdown(
                    header + summary,
                    0,
                    0,
                    self._markdown_theme,
                )
            )
        else:
            hint_key = editor_key("expandTools")
            line = (
                theme.fg("customMessageText", "Branch summary (")
                + theme.fg("dim", hint_key)
                + theme.fg("customMessageText", " to expand)")
            )
            self.add_child(Text(line, 0, 0))
