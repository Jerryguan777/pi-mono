"""Tests for system prompt builder.

Ported from python-superpowers. The rewrite uses BuildSystemPromptOptions
dataclass instead of positional cwd argument.
"""

from __future__ import annotations

import platform
from datetime import datetime

from pi_coding_agent.core.system_prompt import BuildSystemPromptOptions, build_system_prompt


class TestBuildSystemPrompt:
    """Tests for build_system_prompt."""

    def test_contains_cwd(self) -> None:
        prompt = build_system_prompt(BuildSystemPromptOptions(cwd="/home/user/project"))
        assert "/home/user/project" in prompt

    def test_contains_agent_identity(self) -> None:
        prompt = build_system_prompt(BuildSystemPromptOptions(cwd="/tmp"))
        # Should mention pi or coding agent
        lower = prompt.lower()
        assert "pi" in lower or "coding" in lower or "agent" in lower

    def test_contains_current_date(self) -> None:
        prompt = build_system_prompt(BuildSystemPromptOptions(cwd="/tmp"))
        today = datetime.now().strftime("%Y")
        assert today in prompt

    def test_contains_tools_section(self) -> None:
        prompt = build_system_prompt(BuildSystemPromptOptions(cwd="/tmp"))
        lower = prompt.lower()
        # Should mention the core tools
        assert "read" in lower
        assert "bash" in lower
        assert "edit" in lower
        assert "write" in lower

    def test_contains_custom_instructions(self) -> None:
        prompt = build_system_prompt(
            BuildSystemPromptOptions(
                cwd="/tmp",
                append_system_prompt="Always use snake_case.",
            )
        )
        assert "Always use snake_case." in prompt

    def test_working_directory_label(self) -> None:
        prompt = build_system_prompt(BuildSystemPromptOptions(cwd="/home/user/code"))
        lower = prompt.lower()
        assert "working directory" in lower or "/home/user/code" in prompt
