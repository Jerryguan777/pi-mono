"""TUI config selector stub for the `pi config` command.

Python port of packages/coding-agent/src/cli/config-selector.ts.
The full TUI implementation depends on parallel tasks; this is a stub.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ConfigSelectorOptions:
    """Options for the config selector."""

    resolved_paths: Any
    settings_manager: Any
    cwd: str
    agent_dir: str


async def select_config(options: ConfigSelectorOptions) -> None:
    """Show a config selector and return when closed.

    Currently a stub; prints a placeholder message.
    """
    print("Config selector not yet implemented")
