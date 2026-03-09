"""Component that renders a skill invocation message with collapsed/expanded state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pi_coding_agent.modes.interactive.components._theme import get_markdown_theme, theme
from pi_coding_agent.modes.interactive.components.keybinding_hints import editor_key
from pi_tui.components.box import Box
from pi_tui.components.markdown import Markdown, MarkdownTheme
from pi_tui.components.text import Text

if TYPE_CHECKING:
    pass


class SkillInvocationMessageComponent(Box):
    """Renders a skill invocation message with collapsed/expanded states.

    Uses the same background as custom messages for visual consistency.
    """

    def __init__(
        self,
        skill_block: Any,
        markdown_theme: MarkdownTheme | None = None,
    ) -> None:
        super().__init__(1, 1, lambda t: theme.bg("customMessageBg", t))
        self._skill_block = skill_block
        self._markdown_theme = markdown_theme if markdown_theme is not None else get_markdown_theme()
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
        name = getattr(self._skill_block, "name", "")
        content = getattr(self._skill_block, "content", "")

        if self._expanded:
            label = theme.fg("customMessageLabel", "\x1b[1m[skill]\x1b[22m")
            self.add_child(Text(label, 0, 0))
            header = f"**{name}**\n\n"
            self.add_child(
                Markdown(
                    header + content,
                    0,
                    0,
                    self._markdown_theme,
                    default_text_style=None,
                )
            )
        else:
            hint_key = editor_key("expandTools")
            line = (
                theme.fg("customMessageLabel", "\x1b[1m[skill]\x1b[22m ")
                + theme.fg("customMessageText", name)
                + theme.fg("dim", f" ({hint_key} to expand)")
            )
            self.add_child(Text(line, 0, 0))
