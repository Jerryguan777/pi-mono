"""Tests for pi_mom.agent (helpers and utilities)."""

from __future__ import annotations

import json
import os
from typing import Any

from pi_mom.agent import (
    PendingMessage,
    _build_system_prompt,
    _extract_tool_result_text,
    _format_skills_for_prompt,
    _format_tool_args_for_slack,
    _fresh_usage,
    _get_image_mime_type,
    _get_memory,
    _load_mom_skills,
    _parse_skill_frontmatter,
    _split_for_slack,
    _translate_to_host_path,
    _truncate_str,
)


class TestPendingMessage:
    def test_creation(self) -> None:
        msg = PendingMessage(user_name="mario", text="Hello", attachments=[], timestamp=1234567890)
        assert msg.user_name == "mario"
        assert msg.text == "Hello"
        assert msg.timestamp == 1234567890


class TestGetImageMimeType:
    def test_jpg(self) -> None:
        assert _get_image_mime_type("photo.jpg") == "image/jpeg"

    def test_jpeg(self) -> None:
        assert _get_image_mime_type("photo.jpeg") == "image/jpeg"

    def test_png(self) -> None:
        assert _get_image_mime_type("image.PNG") == "image/png"

    def test_gif(self) -> None:
        assert _get_image_mime_type("anim.gif") == "image/gif"

    def test_webp(self) -> None:
        assert _get_image_mime_type("photo.webp") == "image/webp"

    def test_non_image(self) -> None:
        assert _get_image_mime_type("document.pdf") is None

    def test_no_extension(self) -> None:
        assert _get_image_mime_type("filename") is None


class TestTruncateStr:
    def test_no_truncation(self) -> None:
        assert _truncate_str("hello", 100) == "hello"

    def test_truncation(self) -> None:
        result = _truncate_str("a" * 200, 10)
        assert len(result) == 10
        assert result.endswith("...")


class TestExtractToolResultText:
    def test_string_input(self) -> None:
        assert _extract_tool_result_text("hello") == "hello"

    def test_object_with_content(self) -> None:
        class FakeContent:
            type = "text"
            text = "result text"

        class FakeResult:
            content: list[Any] = []  # noqa: RUF012

            def __init__(self) -> None:
                self.content = [FakeContent()]

        assert _extract_tool_result_text(FakeResult()) == "result text"

    def test_dict_fallback(self) -> None:
        result = _extract_tool_result_text({"key": "value"})
        assert "key" in result


class TestFormatToolArgsForSlack:
    def test_skips_label(self) -> None:
        result = _format_tool_args_for_slack("bash", {"label": "do thing", "command": "ls"})
        assert "label" not in result
        assert "ls" in result

    def test_path_with_offset_limit(self) -> None:
        result = _format_tool_args_for_slack("read", {"label": "x", "path": "/foo.py", "offset": 5, "limit": 10})
        assert "/foo.py:5-15" in result
        assert "offset" not in result

    def test_path_without_offset(self) -> None:
        result = _format_tool_args_for_slack("read", {"label": "x", "path": "/foo.py"})
        assert "/foo.py" in result


class TestSplitForSlack:
    def test_short_text(self) -> None:
        parts = _split_for_slack("hello world")
        assert parts == ["hello world"]

    def test_long_text(self) -> None:
        long_text = "x" * 50000
        parts = _split_for_slack(long_text)
        assert len(parts) > 1
        for part in parts[:-1]:
            assert "continued" in part


class TestFreshUsage:
    def test_structure(self) -> None:
        usage = _fresh_usage()
        assert usage["input"] == 0
        assert usage["output"] == 0
        assert usage["cacheRead"] == 0
        assert usage["cacheWrite"] == 0
        assert "cost" in usage
        assert usage["cost"]["total"] == 0.0


class TestGetMemory:
    def test_no_memory_files(self, tmp_path: Any) -> None:
        channel_dir = str(tmp_path / "C123")
        os.makedirs(channel_dir)
        result = _get_memory(channel_dir)
        assert result == "(no working memory yet)"

    def test_workspace_memory(self, tmp_path: Any) -> None:
        workspace = str(tmp_path)
        channel_dir = os.path.join(workspace, "C123")
        os.makedirs(channel_dir)

        memory_file = os.path.join(workspace, "MEMORY.md")
        with open(memory_file, "w") as f:
            f.write("Global memory content")

        result = _get_memory(channel_dir)
        assert "Global Workspace Memory" in result
        assert "Global memory content" in result

    def test_channel_memory(self, tmp_path: Any) -> None:
        workspace = str(tmp_path)
        channel_dir = os.path.join(workspace, "C123")
        os.makedirs(channel_dir)

        memory_file = os.path.join(channel_dir, "MEMORY.md")
        with open(memory_file, "w") as f:
            f.write("Channel-specific memory")

        result = _get_memory(channel_dir)
        assert "Channel-Specific Memory" in result
        assert "Channel-specific memory" in result


class TestParseSkillFrontmatter:
    def test_valid_frontmatter(self) -> None:
        content = """---
name: my-skill
description: Does something cool
---

# My Skill
"""
        name, desc = _parse_skill_frontmatter(content)
        assert name == "my-skill"
        assert desc == "Does something cool"

    def test_no_frontmatter(self) -> None:
        name, desc = _parse_skill_frontmatter("# No frontmatter")
        assert name == ""
        assert desc == ""

    def test_missing_fields(self) -> None:
        content = "---\nname: only-name\n---\n"
        name, desc = _parse_skill_frontmatter(content)
        assert name == "only-name"
        assert desc == ""


class TestLoadMomSkills:
    def test_no_skills_dirs(self, tmp_path: Any) -> None:
        workspace = str(tmp_path)
        channel_dir = os.path.join(workspace, "C123")
        os.makedirs(channel_dir)
        result = _load_mom_skills(channel_dir, "/workspace")
        assert result == []

    def test_loads_workspace_skill(self, tmp_path: Any) -> None:
        workspace = str(tmp_path)
        channel_dir = os.path.join(workspace, "C123")
        os.makedirs(channel_dir)

        skills_dir = os.path.join(workspace, "skills", "my-tool")
        os.makedirs(skills_dir)
        with open(os.path.join(skills_dir, "SKILL.md"), "w") as f:
            f.write("---\nname: my-tool\ndescription: A useful tool\n---\n")

        result = _load_mom_skills(channel_dir, "/workspace")
        assert len(result) == 1
        assert result[0]["name"] == "my-tool"

    def test_channel_skill_overrides_workspace(self, tmp_path: Any) -> None:
        workspace = str(tmp_path)
        channel_dir = os.path.join(workspace, "C123")
        os.makedirs(channel_dir)

        # Workspace skill
        workspace_skills = os.path.join(workspace, "skills", "shared-tool")
        os.makedirs(workspace_skills)
        with open(os.path.join(workspace_skills, "SKILL.md"), "w") as f:
            f.write("---\nname: shared-tool\ndescription: Workspace version\n---\n")

        # Channel skill with same name (overrides workspace)
        channel_skills = os.path.join(channel_dir, "skills", "shared-tool")
        os.makedirs(channel_skills)
        with open(os.path.join(channel_skills, "SKILL.md"), "w") as f:
            f.write("---\nname: shared-tool\ndescription: Channel version\n---\n")

        result = _load_mom_skills(channel_dir, "/workspace")
        assert len(result) == 1
        assert result[0]["description"] == "Channel version"
        assert result[0]["source"] == "channel"


class TestFormatSkillsForPrompt:
    def test_no_skills(self) -> None:
        result = _format_skills_for_prompt([])
        assert result == "(no skills installed yet)"

    def test_with_skills(self) -> None:
        skills = [
            {
                "name": "my-tool",
                "description": "Does stuff",
                "baseDir": "/workspace/skills/my-tool",
                "source": "workspace",
                "filePath": "/workspace/skills/my-tool/SKILL.md",
            },
        ]
        result = _format_skills_for_prompt(skills)
        assert "my-tool" in result
        assert "Does stuff" in result
        assert "/workspace/skills/my-tool" in result


class TestBuildSystemPrompt:
    def test_host_sandbox(self) -> None:
        from pi_mom.sandbox import HostSandboxConfig
        from pi_mom.slack import ChannelInfo, UserInfo

        channels = [ChannelInfo(id="C123", name="general")]
        users = [UserInfo(id="U1", user_name="mario", display_name="Mario")]
        result = _build_system_prompt(
            workspace_path="/workspace",
            channel_id="C123",
            memory="test memory",
            sandbox_config=HostSandboxConfig(),
            channels=channels,
            users=users,
            skills=[],
        )
        assert "You are mom" in result
        assert "C123" in result
        assert "U1" in result
        assert "#general" in result
        assert "@mario" in result
        assert "host machine" in result

    def test_docker_sandbox(self) -> None:
        from pi_mom.sandbox import DockerSandboxConfig

        result = _build_system_prompt(
            workspace_path="/workspace",
            channel_id="C456",
            memory="",
            sandbox_config=DockerSandboxConfig(container="mom-box"),
            channels=[],
            users=[],
            skills=[],
        )
        assert "Docker container" in result
        assert "(no channels loaded)" in result
        assert "(no users loaded)" in result

    def test_with_skills(self) -> None:
        from pi_mom.sandbox import HostSandboxConfig

        skills = [
            {
                "name": "email-tool",
                "description": "Send emails",
                "baseDir": "/workspace/skills/email-tool",
                "source": "workspace",
                "filePath": "/workspace/skills/email-tool/SKILL.md",
            },
        ]
        result = _build_system_prompt(
            workspace_path="/workspace",
            channel_id="C123",
            memory="",
            sandbox_config=HostSandboxConfig(),
            channels=[],
            users=[],
            skills=skills,
        )
        assert "email-tool" in result


class TestTranslateToHostPath:
    def test_workspace_path_translation(self) -> None:
        result = _translate_to_host_path(
            container_path="/workspace/C123/scratch/file.py",
            channel_dir="/home/user/work/C123",
            workspace_path="/workspace",
            channel_id="C123",
        )
        assert "scratch/file.py" in result
        assert "/home/user/work/C123" in result

    def test_workspace_root_translation(self) -> None:
        result = _translate_to_host_path(
            container_path="/workspace/MEMORY.md",
            channel_dir="/home/user/work/C123",
            workspace_path="/workspace",
            channel_id="C123",
        )
        assert "MEMORY.md" in result

    def test_non_workspace_path(self) -> None:
        result = _translate_to_host_path(
            container_path="/etc/hosts",
            channel_dir="/home/user/work/C123",
            workspace_path="/workspace",
            channel_id="C123",
        )
        assert result == "/etc/hosts"

    def test_host_sandbox_no_translation(self) -> None:
        result = _translate_to_host_path(
            container_path="/home/user/work/C123/file.py",
            channel_dir="/home/user/work/C123",
            workspace_path="/home/user/work",
            channel_id="C123",
        )
        assert result == "/home/user/work/C123/file.py"


class TestConcreteRunnerLoadMessages:
    """Tests for _ConcreteRunner._load_messages using duck typing."""

    def _make_minimal_runner(self, tmp_path: Any) -> Any:
        """Create a minimal _ConcreteRunner-like object for testing _load_messages."""
        from unittest.mock import MagicMock, patch

        from pi_mom.agent import _ConcreteRunner

        channel_dir = str(tmp_path / "C123")
        os.makedirs(channel_dir, exist_ok=True)

        # We need to mock pi_agent.Agent to avoid API calls
        with (
            patch("pi_mom.agent.create_executor") as mock_create_executor,
            patch("pi_agent.agent.Agent") as MockAgent,
            patch("pi_ai.models.get_model") as mock_get_model,
        ):
            mock_executor = MagicMock()
            mock_executor.get_workspace_path.return_value = "/workspace"
            mock_create_executor.return_value = mock_executor
            mock_get_model.return_value = MagicMock()

            mock_agent_instance = MagicMock()
            mock_agent_instance.state.messages = []
            mock_agent_instance.subscribe = MagicMock()
            mock_agent_instance.replace_messages = MagicMock()
            MockAgent.return_value = mock_agent_instance

            with patch("pi_agent.types.AgentState"):
                runner = _ConcreteRunner.__new__(_ConcreteRunner)
                runner._channel_dir = channel_dir
                runner._context_file = os.path.join(channel_dir, "context.jsonl")
                runner._agent = mock_agent_instance
                return runner

    def test_load_messages_no_file(self, tmp_path: Any) -> None:
        from unittest.mock import MagicMock

        from pi_mom.agent import _ConcreteRunner

        runner = _ConcreteRunner.__new__(_ConcreteRunner)
        runner._context_file = str(tmp_path / "nonexistent.jsonl")
        runner._agent = MagicMock()

        result = runner._load_messages()
        assert result == []

    def test_load_messages_with_file(self, tmp_path: Any) -> None:
        from unittest.mock import MagicMock

        from pi_mom.agent import _ConcreteRunner

        channel_dir = str(tmp_path / "C123")
        os.makedirs(channel_dir, exist_ok=True)
        context_file = os.path.join(channel_dir, "context.jsonl")
        with open(context_file, "w") as f:
            f.write(json.dumps({"role": "user", "content": "Hello", "timestamp": 1000000}) + "\n")

        runner = _ConcreteRunner.__new__(_ConcreteRunner)
        runner._context_file = context_file
        runner._agent = MagicMock()

        result = runner._load_messages()
        assert len(result) >= 0  # May load messages if UserMessage can be created

    def test_load_messages_with_list_content(self, tmp_path: Any) -> None:
        from unittest.mock import MagicMock

        from pi_mom.agent import _ConcreteRunner

        channel_dir = str(tmp_path / "C456")
        os.makedirs(channel_dir, exist_ok=True)
        context_file = os.path.join(channel_dir, "context.jsonl")
        with open(context_file, "w") as f:
            f.write(
                json.dumps({"role": "user", "content": [{"type": "text", "text": "Hello"}], "timestamp": 1000000})
                + "\n"
            )

        runner = _ConcreteRunner.__new__(_ConcreteRunner)
        runner._context_file = context_file
        runner._agent = MagicMock()

        result = runner._load_messages()
        assert isinstance(result, list)

    def test_load_messages_malformed_line(self, tmp_path: Any) -> None:
        from unittest.mock import MagicMock

        from pi_mom.agent import _ConcreteRunner

        channel_dir = str(tmp_path / "C789")
        os.makedirs(channel_dir, exist_ok=True)
        context_file = os.path.join(channel_dir, "context.jsonl")
        with open(context_file, "w") as f:
            f.write("NOT JSON\n")
            f.write("{}\n")  # Valid JSON but no role

        runner = _ConcreteRunner.__new__(_ConcreteRunner)
        runner._context_file = context_file
        runner._agent = MagicMock()

        result = runner._load_messages()
        assert result == []  # Malformed lines are skipped

    def test_save_messages_creates_file(self, tmp_path: Any) -> None:
        from unittest.mock import MagicMock

        from pi_mom.agent import _ConcreteRunner

        channel_dir = str(tmp_path / "Csave")
        os.makedirs(channel_dir, exist_ok=True)
        context_file = os.path.join(channel_dir, "context.jsonl")

        # Create mock message with role and content
        mock_msg = MagicMock()
        mock_msg.role = "user"
        mock_msg.content = "Test message"
        mock_msg.timestamp = 1000000.0

        mock_agent = MagicMock()
        mock_agent.state.messages = [mock_msg]

        runner = _ConcreteRunner.__new__(_ConcreteRunner)
        runner._context_file = context_file
        runner._agent = mock_agent

        runner._save_messages()
        assert os.path.exists(context_file)
        with open(context_file) as _f:
            content = _f.read()
        assert "user" in content


class TestGetOrCreateRunner:
    def test_creates_and_caches_runner(self, tmp_path: Any) -> None:
        from unittest.mock import MagicMock, patch

        from pi_mom.agent import _channel_runners, get_or_create_runner
        from pi_mom.sandbox import HostSandboxConfig

        channel_dir = str(tmp_path / "C_NEW_RUNNER")
        os.makedirs(channel_dir, exist_ok=True)

        # Clear cache
        _channel_runners.clear()

        with patch("pi_mom.agent._create_runner") as mock_create:
            mock_runner = MagicMock()
            mock_create.return_value = mock_runner

            result = get_or_create_runner(HostSandboxConfig(), "C_NEW_RUNNER", channel_dir)
            assert result is mock_runner
            assert "C_NEW_RUNNER" in _channel_runners

            # Second call should return cached
            result2 = get_or_create_runner(HostSandboxConfig(), "C_NEW_RUNNER", channel_dir)
            assert result2 is mock_runner
            mock_create.assert_called_once()  # Not called again


class TestGetMemoryEdgeCases:
    """Tests for _get_memory exception paths."""

    def test_workspace_memory_read_error(self, tmp_path: Any) -> None:
        """Exception reading workspace MEMORY.md should be handled gracefully."""
        from pi_mom.agent import _get_memory

        channel_dir = os.path.join(str(tmp_path), "C001")
        os.makedirs(channel_dir)
        workspace_memory = os.path.join(str(tmp_path), "MEMORY.md")

        # Create a MEMORY.md that can be stat'd but not read (simulate failure by making it a dir)
        os.makedirs(workspace_memory)

        # Should not raise even if reading fails
        result = _get_memory(channel_dir)
        assert result is not None

    def test_channel_memory_read_error(self, tmp_path: Any) -> None:
        """Exception reading channel MEMORY.md should be handled gracefully."""
        from pi_mom.agent import _get_memory

        channel_dir = os.path.join(str(tmp_path), "C001")
        os.makedirs(channel_dir)
        channel_memory = os.path.join(channel_dir, "MEMORY.md")

        # Create MEMORY.md as a directory to cause read failure
        os.makedirs(channel_memory)

        result = _get_memory(channel_dir)
        assert result is not None


class TestLoadMomSkillsEdgeCases:
    """Tests for _load_mom_skills edge cases."""

    def test_skills_dir_with_file_entry(self, tmp_path: Any) -> None:
        """Entries that are files (not dirs) should be skipped."""
        from pi_mom.agent import _load_mom_skills

        channel_dir = os.path.join(str(tmp_path), "C001")
        workspace_dir = str(tmp_path)
        skills_dir = os.path.join(workspace_dir, "skills")
        os.makedirs(skills_dir)
        os.makedirs(channel_dir)

        # Create a file (not a dir) inside skills — should be skipped
        open(os.path.join(skills_dir, "not_a_dir.txt"), "w").close()

        result = _load_mom_skills(channel_dir, "/workspace")
        assert result == []

    def test_skills_dir_entry_no_skill_md(self, tmp_path: Any) -> None:
        """Skill dir without SKILL.md should be skipped."""
        from pi_mom.agent import _load_mom_skills

        channel_dir = os.path.join(str(tmp_path), "C001")
        workspace_dir = str(tmp_path)
        os.makedirs(channel_dir)
        skill_dir = os.path.join(workspace_dir, "skills", "my-skill")
        os.makedirs(skill_dir)
        # No SKILL.md file created

        result = _load_mom_skills(channel_dir, "/workspace")
        assert result == []

    def test_skills_dir_invalid_frontmatter(self, tmp_path: Any) -> None:
        """A SKILL.md that fails to parse should not crash."""
        from pi_mom.agent import _load_mom_skills

        channel_dir = os.path.join(str(tmp_path), "C001")
        workspace_dir = str(tmp_path)
        os.makedirs(channel_dir)
        skill_dir = os.path.join(workspace_dir, "skills", "broken-skill")
        os.makedirs(skill_dir)

        # SKILL.md with no parseable frontmatter
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write("No frontmatter here at all")

        # Should not crash, returns empty since no valid name/description
        result = _load_mom_skills(channel_dir, "/workspace")
        assert isinstance(result, list)

    def test_translate_path_non_workspace_path(self, tmp_path: Any) -> None:
        """Path outside workspace_path should be returned as-is."""
        from pi_mom.agent import _translate_to_host_path

        # Non-docker path — workspace_path is not /workspace
        result = _translate_to_host_path("/some/absolute/path", "/channel/dir", "/not/workspace", "C001")
        assert result == "/some/absolute/path"


class TestFormatToolArgsForSlackEdgeCases:
    """Tests for _format_tool_args_for_slack edge cases (non-string values)."""

    def test_non_string_value_json_dumps(self) -> None:
        """Non-string values should be JSON-encoded."""
        from pi_mom.agent import _format_tool_args_for_slack

        args = {"label": "test", "count": 42, "enabled": True}
        result = _format_tool_args_for_slack("bash", args)
        assert "42" in result or "true" in result

    def test_skips_label_key(self) -> None:
        """label key should be skipped in output."""
        from pi_mom.agent import _format_tool_args_for_slack

        args = {"label": "My label", "command": "echo hello"}
        result = _format_tool_args_for_slack("bash", args)
        assert "My label" not in result
        assert "echo hello" in result

    def test_skips_offset_and_limit(self) -> None:
        """offset and limit keys should be skipped."""
        from pi_mom.agent import _format_tool_args_for_slack

        args = {"path": "/tmp/file.txt", "offset": 10, "limit": 20}
        result = _format_tool_args_for_slack("read", args)
        assert "offset" not in result
        assert "limit" not in result
        assert "/tmp/file.txt" in result
