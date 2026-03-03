"""Skills — .md files with YAML frontmatter for system prompt injection."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass
class Skill:
    name: str
    description: str
    file_path: str
    source: str
    disable_model_invocation: bool = False


def load_skills(paths: list[str]) -> list[Skill]:
    """Load skills from directories or individual .md files.

    Each skill is a .md file with YAML frontmatter containing:
    - name: Skill name
    - description: Short description
    - disable-model-invocation: bool (optional, default False)
    """
    skills: list[Skill] = []
    seen_names: set[str] = set()

    for path in paths:
        if os.path.isfile(path) and path.endswith(".md"):
            skill = _load_skill_file(path)
            if skill and skill.name not in seen_names:
                skills.append(skill)
                seen_names.add(skill.name)
        elif os.path.isdir(path):
            for entry in sorted(os.listdir(path)):
                if entry.endswith(".md"):
                    file_path = os.path.join(path, entry)
                    skill = _load_skill_file(file_path)
                    if skill and skill.name not in seen_names:
                        skills.append(skill)
                        seen_names.add(skill.name)

    return skills


def _load_skill_file(path: str) -> Skill | None:
    """Load a single skill from a .md file with YAML frontmatter."""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    # Parse YAML frontmatter (between --- markers)
    frontmatter, body = _parse_frontmatter(content)
    if frontmatter is None:
        return None

    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")

    if not name:
        # Fall back to filename
        name = os.path.splitext(os.path.basename(path))[0]

    disable_model = frontmatter.get("disable-model-invocation", False)
    if isinstance(disable_model, str):
        disable_model = disable_model.lower() in ("true", "yes", "1")

    return Skill(
        name=name,
        description=description,
        file_path=path,
        source=body,
        disable_model_invocation=bool(disable_model),
    )


def _parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Parse YAML frontmatter from markdown content.

    Returns (frontmatter_dict, body) or (None, content) if no frontmatter.
    Uses simple key: value parsing (no full YAML parser dependency).
    """
    if not content.startswith("---"):
        return None, content

    # Find the closing ---
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return None, content

    fm_text = content[3:end_match.start() + 3]
    body = content[end_match.end() + 3:]

    # Simple YAML-like parsing (key: value per line)
    frontmatter: dict = {}
    for line in fm_text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            # Remove quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            # Handle booleans
            if value.lower() in ("true", "yes"):
                frontmatter[key] = True
            elif value.lower() in ("false", "no"):
                frontmatter[key] = False
            else:
                frontmatter[key] = value

    return frontmatter, body


def format_skills_for_prompt(skills: list[Skill]) -> str:
    """Format skills list as XML for inclusion in system prompt."""
    if not skills:
        return ""

    lines: list[str] = ["<available-skills>"]
    for skill in skills:
        if skill.disable_model_invocation:
            lines.append(f'  <skill name="{skill.name}" user-invocable-only="true">')
        else:
            lines.append(f'  <skill name="{skill.name}">')
        if skill.description:
            lines.append(f"    <description>{skill.description}</description>")
        lines.append("  </skill>")
    lines.append("</available-skills>")
    return "\n".join(lines)
