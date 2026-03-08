"""Single-line text component that truncates to fit the viewport width."""

from __future__ import annotations

from pi_tui.utils import truncate_to_width, visible_width


class TruncatedText:
    """Displays a single line of text, truncated with ellipsis if too long."""

    def __init__(
        self,
        text: str,
        padding_x: int = 0,
        padding_y: int = 0,
    ) -> None:
        self._text = text
        self._padding_x = padding_x
        self._padding_y = padding_y

    def invalidate(self) -> None:
        pass

    def render(self, width: int) -> list[str]:
        result: list[str] = []
        empty_line = " " * width

        # Vertical padding above
        for _ in range(self._padding_y):
            result.append(empty_line)

        # Available width after horizontal padding
        available_width = max(1, width - self._padding_x * 2)

        # Take only the first line
        single_line_text = self._text
        newline_index = self._text.find("\n")
        if newline_index != -1:
            single_line_text = self._text[:newline_index]

        # Truncate if needed
        display_text = truncate_to_width(single_line_text, available_width)

        # Add horizontal padding
        left_padding = " " * self._padding_x
        right_padding = " " * self._padding_x
        line_with_padding = left_padding + display_text + right_padding

        # Pad to exactly width characters
        line_visible_width = visible_width(line_with_padding)
        padding_needed = max(0, width - line_visible_width)
        final_line = line_with_padding + " " * padding_needed

        result.append(final_line)

        # Vertical padding below
        for _ in range(self._padding_y):
            result.append(empty_line)

        return result
