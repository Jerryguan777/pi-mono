"""Interactive TUI mode for the coding agent.

Python port of packages/coding-agent/src/modes/interactive/interactive-mode.ts.
The full TUI implementation depends on parallel tasks; the public interface
is defined here with a stub run() method.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InteractiveModeOptions:
    """Options for the interactive mode."""

    migrated_providers: list[str] = field(default_factory=list)
    model_fallback_message: str | None = None
    initial_message: str | None = None
    initial_images: list[Any] | None = None
    initial_messages: list[str] = field(default_factory=list)
    verbose: bool = False


class InteractiveMode:
    """Interactive TUI mode for the coding agent.

    Wraps an AgentSession and handles TUI rendering and user interaction.
    The full implementation depends on parallel task modules; this is a stub
    that can be extended once those modules are available.
    """

    def __init__(
        self,
        session: Any,
        options: InteractiveModeOptions | None = None,
    ) -> None:
        """Initialize the interactive mode.

        Args:
            session: AgentSession instance (typed as Any at runtime).
            options: Optional mode options.
        """
        self._session = session
        self._options = options or InteractiveModeOptions()

    async def run(self) -> None:
        """Run the interactive TUI loop.

        This is a stub implementation. The full TUI loop will be added
        once parallel task modules (core.agent_session, etc.) are available.
        """
        print("Interactive mode not yet fully implemented.", file=sys.stderr)
        print("Use --print (-p) for non-interactive mode.", file=sys.stderr)
