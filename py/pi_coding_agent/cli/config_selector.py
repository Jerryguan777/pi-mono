"""TUI config selector for the `pi config` command.

Python port of packages/coding-agent/src/cli/config-selector.ts.
"""

from __future__ import annotations

import asyncio
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
    """Show a TUI config selector and return when closed.

    Initializes the theme, creates a TUI with a ConfigSelectorComponent,
    and blocks until the user closes or exits the selector.
    """
    from pi_coding_agent.modes.interactive.components.config_selector import (
        ConfigSelectorComponent,
    )
    from pi_coding_agent.modes.interactive.theme import init_theme, stop_theme_watcher
    from pi_tui.terminal import ProcessTerminal
    from pi_tui.tui import TUI

    # Initialize theme from settings
    theme_name: str | None = None
    if options.settings_manager is not None and hasattr(options.settings_manager, "get_theme"):
        theme_name = options.settings_manager.get_theme()
    init_theme(theme_name, True)

    done_event = asyncio.Event()
    ui = TUI(ProcessTerminal())
    resolved = False

    def on_close() -> None:
        nonlocal resolved
        if not resolved:
            resolved = True
            ui.stop()
            stop_theme_watcher()
            done_event.set()

    def on_exit() -> None:
        ui.stop()
        stop_theme_watcher()
        raise SystemExit(0)

    selector = ConfigSelectorComponent(
        options.resolved_paths,
        options.settings_manager,
        options.cwd,
        options.agent_dir,
        on_close,
        on_exit,
        lambda: ui.request_render(),
    )

    ui.add_child(selector)
    ui.set_focus(selector.get_resource_list())
    ui.start()

    # Wait until the selector signals done (non-blocking for asyncio)
    await done_event.wait()
