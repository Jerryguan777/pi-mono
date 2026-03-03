"""System prompt builder — constructs the system prompt from base + tools + context."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from pi_agent.types import AgentTool

from pi_coding_agent.resource_loader import ContextFile


BASE_SYSTEM_PROMPT = """You are a helpful AI coding assistant. You help users with software engineering tasks including writing code, debugging, refactoring, and explaining code.

## Guidelines
- Write clean, readable, well-structured code
- Follow existing code conventions in the project
- Explain your reasoning when making changes
- Ask for clarification when requirements are ambiguous
- Prefer editing existing files over creating new ones
- Be careful not to introduce security vulnerabilities"""


TOOL_GUIDELINES = """
## Tool Usage Guidelines
- Use the read tool to examine files before modifying them
- Use grep/find to search the codebase before making assumptions
- Prefer dedicated tools (read, write, edit) over bash for file operations
- Use bash for commands that need shell execution (git, npm, pip, etc.)
- Keep tool calls focused — do one thing well per call"""


def build_system_prompt(
    custom_prompt: str | None = None,
    tools: list[AgentTool] | None = None,
    context_files: list[ContextFile] | None = None,
    skills: list | None = None,
    cwd: str | None = None,
    append_system_prompt: str | None = None,
) -> str:
    """Build the full system prompt from components.

    Sections:
    1. Base instructions (or custom prompt override)
    2. Tool descriptions + guidelines
    3. Project context (AGENTS.md/CLAUDE.md content)
    4. Skills (if available)
    5. Current date/time + working directory
    6. Appended system prompt (if any)
    """
    parts: list[str] = []

    # 1. Base instructions
    if custom_prompt:
        parts.append(custom_prompt)
    else:
        parts.append(BASE_SYSTEM_PROMPT)

    # 2. Tool descriptions
    if tools:
        parts.append(TOOL_GUIDELINES)
        parts.append("\n## Available Tools\n")
        for tool in tools:
            parts.append(f"### {tool.name}")
            if tool.description:
                parts.append(tool.description)
            parts.append("")

    # 3. Project context files
    if context_files:
        parts.append("\n## Project Context\n")
        for cf in context_files:
            parts.append(f"### {os.path.basename(cf.path)}")
            parts.append(f"*From: {cf.path}*\n")
            parts.append(cf.content)
            parts.append("")

    # 4. Skills
    if skills:
        parts.append("\n## Available Skills\n")
        parts.append(_format_skills_for_prompt(skills))

    # 5. Current info
    now = datetime.now(timezone.utc)
    effective_cwd = cwd or os.getcwd()
    parts.append(f"\n## Environment")
    parts.append(f"- Current date: {now.strftime('%Y-%m-%d')}")
    parts.append(f"- Current time: {now.strftime('%H:%M UTC')}")
    parts.append(f"- Working directory: {effective_cwd}")

    # 6. Appended system prompt
    if append_system_prompt:
        parts.append(f"\n{append_system_prompt}")

    return "\n".join(parts)


def _format_skills_for_prompt(skills: list) -> str:
    """Format skills list as XML for system prompt."""
    if not skills:
        return ""

    lines: list[str] = ["<available-skills>"]
    for skill in skills:
        name = getattr(skill, "name", str(skill))
        desc = getattr(skill, "description", "")
        lines.append(f'  <skill name="{name}">{desc}</skill>')
    lines.append("</available-skills>")
    return "\n".join(lines)
