"""Dynamic border component that adjusts to viewport width."""

from __future__ import annotations

from collections.abc import Callable

from pi_coding_agent.modes.interactive.components._theme import theme


class DynamicBorder:
    """Renders a full-width horizontal rule.

    The color function is applied to the border character string. A default
    color of ``theme.fg("border", ...)`` is used when none is provided.

    When used from extension code that may run in an isolated module cache
    (e.g. via import hooks), always pass an explicit color function to avoid
    stale references to the global ``theme``.
    """

    def __init__(self, color: Callable[[str], str] | None = None) -> None:
        if color is None:
            self._color: Callable[[str], str] = lambda s: theme.fg("border", s)
        else:
            self._color = color

    def invalidate(self) -> None:
        """No cached state to invalidate."""

    def render(self, width: int) -> list[str]:
        return [self._color("\u2500" * max(1, width))]
