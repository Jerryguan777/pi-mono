"""Component that renders a user message."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pi_coding_agent.modes.interactive.components._theme import get_markdown_theme
from pi_tui.components.markdown import Markdown, MarkdownTheme
from pi_tui.components.spacer import Spacer
from pi_tui.tui import Container

if TYPE_CHECKING:
    pass


class UserMessageComponent(Container):
    """Renders a user message with markdown formatting and user message background."""

    def __init__(
        self,
        text: str,
        markdown_theme: MarkdownTheme | None = None,
    ) -> None:
        super().__init__()
        md_theme = markdown_theme if markdown_theme is not None else get_markdown_theme()
        self.add_child(Spacer(1))
        self.add_child(
            Markdown(
                text,
                1,
                1,
                md_theme,
                default_text_style=None,
            )
        )
