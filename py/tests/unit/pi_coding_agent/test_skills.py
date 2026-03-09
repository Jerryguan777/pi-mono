"""Tests for skill loading and formatting."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pi_coding_agent.core._frontmatter import parse_frontmatter as _parse_frontmatter
from pi_coding_agent.core.skills import (
    Skill,
    format_skills_for_prompt,
    load_skills_from_dir,
)


class TestParseFrontmatter:
    def test_no_frontmatter(self) -> None:
        fm, body = _parse_frontmatter("Hello world")
        assert fm == {}
        assert body == "Hello world"

    def test_with_frontmatter(self) -> None:
        content = "---\nname: my-skill\ndescription: Does things\n---\nBody text"
        fm, body = _parse_frontmatter(content)
        assert fm.get("name") == "my-skill"
        assert fm.get("description") == "Does things"
        assert "Body text" in body

    def test_missing_closing_delimiter(self) -> None:
        content = "---\nname: my-skill\nNo closing delimiter"
        fm, body = _parse_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_empty_frontmatter(self) -> None:
        content = "---\n---\nBody"
        _fm, body = _parse_frontmatter(content)
        assert "Body" in body


class TestLoadSkillsFromDir:
    def test_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_skills_from_dir(tmpdir, "test")
            assert result.skills == []
            assert result.diagnostics == []

    def test_nonexistent_directory(self) -> None:
        result = load_skills_from_dir("/nonexistent/path", "test")
        assert result.skills == []

    def test_loads_root_md_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("---\nname: my-skill\ndescription: A test skill\n---\n# My Skill\nDoes something.")
            result = load_skills_from_dir(tmpdir, "test")
            assert len(result.skills) == 1
            assert result.skills[0].name == "my-skill"
            assert result.skills[0].description == "A test skill"

    def test_loads_skill_md_from_subdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "my-skill"
            subdir.mkdir()
            skill_file = subdir / "SKILL.md"
            skill_file.write_text("---\nname: my-skill\ndescription: Subdirectory skill\n---\n# Skill")
            result = load_skills_from_dir(tmpdir, "test")
            assert len(result.skills) == 1
            assert result.skills[0].name == "my-skill"

    def test_skill_without_description_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("---\nname: my-skill\n---\n# Just a header")
            result = load_skills_from_dir(tmpdir, "test")
            assert result.skills == []
            assert len(result.diagnostics) > 0

    def test_dotfiles_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            hidden = Path(tmpdir) / ".hidden.md"
            hidden.write_text("---\nname: hidden\ndescription: Should not load\n---\n")
            result = load_skills_from_dir(tmpdir, "test")
            assert result.skills == []

    def test_disable_model_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("---\nname: my-skill\ndescription: A skill\ndisable-model-invocation: true\n---\n")
            result = load_skills_from_dir(tmpdir, "test")
            assert len(result.skills) == 1
            assert result.skills[0].disable_model_invocation is True

    def test_source_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("---\nname: my-skill\ndescription: A skill\n---\n")
            result = load_skills_from_dir(tmpdir, "custom-source")
            assert result.skills[0].source == "custom-source"


class TestFormatSkillsForPrompt:
    def _make_skill(
        self,
        name: str = "my-skill",
        description: str = "Does things",
        file_path: str = "/path/to/SKILL.md",
        disable_model_invocation: bool = False,
    ) -> Skill:
        return Skill(
            name=name,
            description=description,
            file_path=file_path,
            base_dir="/path/to",
            source="test",
            disable_model_invocation=disable_model_invocation,
        )

    def test_empty_returns_empty(self) -> None:
        assert format_skills_for_prompt([]) == ""

    def test_all_disabled_returns_empty(self) -> None:
        skill = self._make_skill(disable_model_invocation=True)
        assert format_skills_for_prompt([skill]) == ""

    def test_basic_format(self) -> None:
        skill = self._make_skill()
        result = format_skills_for_prompt([skill])
        assert "<available_skills>" in result
        assert "<skill>" in result
        assert "<name>my-skill</name>" in result
        assert "<description>Does things</description>" in result
        assert "/path/to/SKILL.md" in result

    def test_xml_escaping(self) -> None:
        skill = self._make_skill(description="Handles <tags> & things")
        result = format_skills_for_prompt([skill])
        assert "&lt;tags&gt;" in result
        assert "&amp;" in result

    def test_disabled_skills_excluded(self) -> None:
        skills = [
            self._make_skill(name="visible", disable_model_invocation=False),
            self._make_skill(name="hidden", disable_model_invocation=True),
        ]
        result = format_skills_for_prompt(skills)
        assert "visible" in result
        assert "hidden" not in result

    def test_multiple_skills(self) -> None:
        skills = [
            self._make_skill(name="skill-a"),
            self._make_skill(name="skill-b"),
        ]
        result = format_skills_for_prompt(skills)
        assert result.count("<skill>") == 2
        assert "skill-a" in result
        assert "skill-b" in result
