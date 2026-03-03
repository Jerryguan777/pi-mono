"""Extension lifecycle management — load, setup, and event dispatch."""

from __future__ import annotations

import importlib.util
import os
import sys
from typing import Any

from pi_agent.types import AgentEvent, AgentTool

from pi_coding_agent.extensions.types import ExtensionContext, ExtensionRuntime
from pi_coding_agent.slash_commands import SlashCommand


class ExtensionRunner:
    """Manages extension lifecycle: loading, setup, and event dispatch."""

    def __init__(self, context: ExtensionContext):
        self._context = context
        self._runtimes: list[ExtensionRuntime] = []
        self._loaded_paths: list[str] = []

    def load(self, extension_paths: list[str]) -> None:
        """Load extensions from Python module paths.

        Each extension module must have a `setup(context, runtime)` function.
        """
        for path in extension_paths:
            try:
                runtime = ExtensionRuntime()
                module = self._load_module(path)

                if hasattr(module, "setup"):
                    result = module.setup(self._context, runtime)
                    # Support async setup
                    if hasattr(result, "__await__"):
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Can't await in sync context during running loop
                            asyncio.ensure_future(result)
                        else:
                            loop.run_until_complete(result)

                self._runtimes.append(runtime)
                self._loaded_paths.append(path)
            except Exception as e:
                # Log but don't crash on extension load failure
                sys.stderr.write(f"Warning: Failed to load extension {path}: {e}\n")

    async def emit_event(self, event: AgentEvent) -> None:
        """Dispatch an event to all registered extension handlers."""
        for runtime in self._runtimes:
            for handler in runtime.event_handlers:
                try:
                    await handler(event)
                except Exception:
                    pass  # Don't let extension errors crash the agent

    def get_tools(self) -> list[AgentTool]:
        """Get all tools registered by extensions."""
        tools: list[AgentTool] = []
        for runtime in self._runtimes:
            tools.extend(runtime.tools)
        return tools

    def get_commands(self) -> list[SlashCommand]:
        """Get all commands registered by extensions."""
        commands: list[SlashCommand] = []
        for runtime in self._runtimes:
            for cmd_data in runtime.commands:
                commands.append(SlashCommand(
                    name=cmd_data["name"],
                    description=cmd_data["description"],
                    handler=cmd_data["handler"],
                    source="extension",
                ))
        return commands

    @property
    def loaded_paths(self) -> list[str]:
        return list(self._loaded_paths)

    @staticmethod
    def _load_module(path: str) -> Any:
        """Load a Python module from a file path."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Extension not found: {path}")

        module_name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from: {path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
