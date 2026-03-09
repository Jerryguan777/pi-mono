"""Configuration constants and paths for pi_coding_agent.

Port of packages/coding-agent/src/core/config.ts.
"""

from __future__ import annotations

from pathlib import Path

CONFIG_DIR_NAME = ".pi"


def get_agent_dir() -> Path:
    """Return the global agent config directory (~/.pi/agent)."""
    return Path.home() / CONFIG_DIR_NAME / "agent"


def get_prompts_dir() -> Path:
    """Return the global prompts directory (~/.pi/agent/prompts)."""
    return get_agent_dir() / "prompts"
