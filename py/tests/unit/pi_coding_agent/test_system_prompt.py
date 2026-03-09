"""Tests for pi_coding_agent.core.system_prompt."""

from __future__ import annotations

from pi_coding_agent.core.system_prompt import (
    BuildSystemPromptOptions,
    Skill,
    _format_skills_for_prompt,
    build_system_prompt,
)


class TestBuildSystemPrompt:
    def test_default_prompt_contains_tools(self) -> None:
        prompt = build_system_prompt()
        assert "read" in prompt
        assert "bash" in prompt
        assert "edit" in prompt
        assert "write" in prompt

    def test_default_prompt_has_guidelines(self) -> None:
        prompt = build_system_prompt()
        assert "Guidelines" in prompt

    def test_custom_prompt_used(self) -> None:
        opts = BuildSystemPromptOptions(custom_prompt="My custom prompt")
        prompt = build_system_prompt(opts)
        assert prompt.startswith("My custom prompt")

    def test_append_system_prompt(self) -> None:
        opts = BuildSystemPromptOptions(append_system_prompt="Additional instructions.")
        prompt = build_system_prompt(opts)
        assert "Additional instructions." in prompt

    def test_selected_tools_filters(self) -> None:
        opts = BuildSystemPromptOptions(selected_tools=["read", "bash"])
        prompt = build_system_prompt(opts)
        assert "read" in prompt
        assert "bash" in prompt
        # edit and write should not appear in the tools section
        # (they may appear in guidelines text but not the tool list)

    def test_context_files_included(self) -> None:
        opts = BuildSystemPromptOptions(
            context_files=[{"path": "/project/README.md", "content": "Project guide content"}]
        )
        prompt = build_system_prompt(opts)
        assert "Project guide content" in prompt
        assert "/project/README.md" in prompt

    def test_cwd_in_prompt(self) -> None:
        opts = BuildSystemPromptOptions(cwd="/custom/working/dir")
        prompt = build_system_prompt(opts)
        assert "/custom/working/dir" in prompt

    def test_date_time_in_prompt(self) -> None:
        prompt = build_system_prompt()
        assert "Current date and time:" in prompt

    def test_skills_included_when_read_available(self) -> None:
        skill = Skill(
            name="my-skill",
            description="Does something",
            file_path="/skills/my-skill/SKILL.md",
            base_dir="/skills/my-skill",
            source="user",
        )
        opts = BuildSystemPromptOptions(skills=[skill], selected_tools=["read", "bash"])
        prompt = build_system_prompt(opts)
        assert "my-skill" in prompt
        assert "Does something" in prompt

    def test_skills_excluded_when_no_read(self) -> None:
        skill = Skill(
            name="my-skill",
            description="Does something",
            file_path="/skills/my-skill/SKILL.md",
            base_dir="/skills/my-skill",
            source="user",
        )
        opts = BuildSystemPromptOptions(skills=[skill], selected_tools=["bash"])
        prompt = build_system_prompt(opts)
        assert "available_skills" not in prompt

    def test_no_options_returns_string(self) -> None:
        prompt = build_system_prompt(None)
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestFormatSkillsForPrompt:
    def test_empty_skills(self) -> None:
        result = _format_skills_for_prompt([])
        assert result == ""

    def test_skill_with_disable_model_invocation(self) -> None:
        skill = Skill(
            name="hidden",
            description="Secret",
            file_path="/x/SKILL.md",
            base_dir="/x",
            source="user",
            disable_model_invocation=True,
        )
        result = _format_skills_for_prompt([skill])
        assert result == ""

    def test_skill_formatted_as_xml(self) -> None:
        skill = Skill(
            name="test-skill",
            description="Test description",
            file_path="/skills/test-skill/SKILL.md",
            base_dir="/skills/test-skill",
            source="user",
        )
        result = _format_skills_for_prompt([skill])
        assert "<available_skills>" in result
        assert "<name>test-skill</name>" in result
        assert "<description>Test description</description>" in result

    def test_xml_escape_in_skill_fields(self) -> None:
        skill = Skill(
            name="test-skill",
            description="Has <special> & chars",
            file_path="/x/SKILL.md",
            base_dir="/x",
            source="user",
        )
        result = _format_skills_for_prompt([skill])
        assert "&lt;special&gt;" in result
        assert "&amp;" in result
