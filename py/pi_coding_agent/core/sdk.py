"""SDK entry point for creating agent sessions.

Python port of packages/coding-agent/src/core/sdk.ts.
Provides createAgentSession() as the main high-level API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CreateAgentSessionOptions:
    """Options for create_agent_session()."""

    cwd: str | None = None
    agent_dir: str | None = None
    model: Any = None  # Model
    thinking_level: str | None = None
    continue_session: bool = False
    session_id: str | None = None
    tools: list[Any] | None = None  # list[Tool]
    custom_tools: list[Any] | None = None  # list[ToolDefinition]
    resource_loader: Any = None  # ResourceLoader
    session_manager: Any = None  # SessionManager
    settings_manager: Any = None  # SettingsManager
    auth_storage: Any = None  # AuthStorage
    model_registry: Any = None  # ModelRegistry


@dataclass
class CreateAgentSessionResult:
    """Result from create_agent_session()."""

    session: Any  # AgentSession
    extensions_result: Any  # LoadExtensionsResult
    model_fallback_message: str | None = None


async def create_agent_session(
    options: CreateAgentSessionOptions | None = None,
) -> CreateAgentSessionResult:
    """Create an AgentSession with the specified options.

    This is the main SDK entry point for programmatic usage.
    Sets up auth, model registry, settings, session management,
    resource loading, extensions, and tool registration.
    """
    raise NotImplementedError("TODO")
