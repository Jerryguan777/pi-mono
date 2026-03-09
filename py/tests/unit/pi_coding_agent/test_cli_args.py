"""Tests for pi_coding_agent.cli.args."""

from __future__ import annotations

import pytest

from pi_coding_agent.cli.args import (
    VALID_THINKING_LEVELS,
    is_valid_thinking_level,
    parse_args,
    print_help,
)


def test_defaults() -> None:
    args = parse_args([])
    assert args.provider is None
    assert args.model is None
    assert args.api_key is None
    assert args.thinking is None
    assert args.continue_session is False
    assert args.resume is False
    assert args.help is False
    assert args.version is False
    assert args.mode is None
    assert args.no_session is False
    assert args.messages == []
    assert args.file_args == []
    assert args.unknown_flags == {}


def test_help_flag() -> None:
    assert parse_args(["--help"]).help is True
    assert parse_args(["-h"]).help is True


def test_version_flag() -> None:
    assert parse_args(["--version"]).version is True
    assert parse_args(["-v"]).version is True


def test_continue_flag() -> None:
    assert parse_args(["--continue"]).continue_session is True
    assert parse_args(["-c"]).continue_session is True


def test_resume_flag() -> None:
    assert parse_args(["--resume"]).resume is True
    assert parse_args(["-r"]).resume is True


def test_print_flag() -> None:
    assert parse_args(["--print"]).print_mode is True
    assert parse_args(["-p"]).print_mode is True


def test_verbose_flag() -> None:
    assert parse_args(["--verbose"]).verbose is True


def test_no_session_flag() -> None:
    assert parse_args(["--no-session"]).no_session is True


def test_no_tools_flag() -> None:
    assert parse_args(["--no-tools"]).no_tools is True


def test_no_extensions_flag() -> None:
    assert parse_args(["--no-extensions"]).no_extensions is True
    assert parse_args(["-ne"]).no_extensions is True


def test_no_skills_flag() -> None:
    assert parse_args(["--no-skills"]).no_skills is True
    assert parse_args(["-ns"]).no_skills is True


def test_no_prompt_templates_flag() -> None:
    assert parse_args(["--no-prompt-templates"]).no_prompt_templates is True
    assert parse_args(["-np"]).no_prompt_templates is True


def test_no_themes_flag() -> None:
    assert parse_args(["--no-themes"]).no_themes is True


def test_provider_flag() -> None:
    args = parse_args(["--provider", "openai"])
    assert args.provider == "openai"


def test_model_flag() -> None:
    args = parse_args(["--model", "gpt-4o"])
    assert args.model == "gpt-4o"


def test_api_key_flag() -> None:
    args = parse_args(["--api-key", "sk-abc"])
    assert args.api_key == "sk-abc"


def test_system_prompt_flag() -> None:
    args = parse_args(["--system-prompt", "Be helpful"])
    assert args.system_prompt == "Be helpful"


def test_append_system_prompt_flag() -> None:
    args = parse_args(["--append-system-prompt", "Extra context"])
    assert args.append_system_prompt == "Extra context"


def test_mode_flag() -> None:
    assert parse_args(["--mode", "text"]).mode == "text"
    assert parse_args(["--mode", "json"]).mode == "json"
    assert parse_args(["--mode", "rpc"]).mode == "rpc"


def test_mode_invalid_ignored() -> None:
    # Invalid mode is silently ignored
    args = parse_args(["--mode", "invalid"])
    assert args.mode is None


def test_session_flag() -> None:
    args = parse_args(["--session", "abc123"])
    assert args.session == "abc123"


def test_session_dir_flag() -> None:
    args = parse_args(["--session-dir", "/tmp/sessions"])
    assert args.session_dir == "/tmp/sessions"


def test_models_flag() -> None:
    args = parse_args(["--models", "gpt-4,claude-3,gemini"])
    assert args.models == ["gpt-4", "claude-3", "gemini"]


def test_models_flag_with_spaces() -> None:
    args = parse_args(["--models", "gpt-4, claude-3 , gemini"])
    assert args.models == ["gpt-4", "claude-3", "gemini"]


def test_tools_flag() -> None:
    args = parse_args(["--tools", "read,bash"])
    assert args.tools == ["read", "bash"]


def test_thinking_flag_valid() -> None:
    for level in VALID_THINKING_LEVELS:
        args = parse_args(["--thinking", level])
        assert args.thinking == level


def test_thinking_flag_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    args = parse_args(["--thinking", "invalid"])
    assert args.thinking is None
    captured = capsys.readouterr()
    assert "Warning" in captured.err


def test_export_flag() -> None:
    args = parse_args(["--export", "session.jsonl"])
    assert args.export == "session.jsonl"


def test_extension_flag() -> None:
    args = parse_args(["--extension", "/path/to/ext.js"])
    assert args.extensions == ["/path/to/ext.js"]
    # -e shorthand
    args2 = parse_args(["-e", "/path/a", "-e", "/path/b"])
    assert args2.extensions == ["/path/a", "/path/b"]


def test_skill_flag() -> None:
    args = parse_args(["--skill", "skill1", "--skill", "skill2"])
    assert args.skills == ["skill1", "skill2"]


def test_prompt_template_flag() -> None:
    args = parse_args(["--prompt-template", "/t/p.md"])
    assert args.prompt_templates == ["/t/p.md"]


def test_theme_flag() -> None:
    args = parse_args(["--theme", "dark"])
    assert args.themes == ["dark"]


def test_list_models_flag_no_pattern() -> None:
    args = parse_args(["--list-models"])
    assert args.list_models is True


def test_list_models_flag_with_pattern() -> None:
    args = parse_args(["--list-models", "claude"])
    assert args.list_models == "claude"


def test_list_models_flag_pattern_not_flag() -> None:
    # If next arg starts with -, treat list_models as True and leave it as a flag
    args = parse_args(["--list-models", "--verbose"])
    assert args.list_models is True
    assert args.verbose is True


def test_file_args() -> None:
    args = parse_args(["@file.txt", "@image.png"])
    assert args.file_args == ["file.txt", "image.png"]


def test_messages() -> None:
    args = parse_args(["Hello world", "Second message"])
    assert args.messages == ["Hello world", "Second message"]


def test_mixed_args() -> None:
    args = parse_args(["--model", "gpt-4", "@file.txt", "Hello", "--verbose"])
    assert args.model == "gpt-4"
    assert args.file_args == ["file.txt"]
    assert args.messages == ["Hello"]
    assert args.verbose is True


def test_extension_flags() -> None:
    ext_flags = {
        "plan": {"type": "boolean"},
        "output": {"type": "string"},
    }
    args = parse_args(["--plan", "--output", "result.txt"], extension_flags=ext_flags)
    assert args.unknown_flags["plan"] is True
    assert args.unknown_flags["output"] == "result.txt"


def test_unknown_flag_ignored_without_extension_flags() -> None:
    args = parse_args(["--unknown-flag"])
    assert "unknown-flag" not in args.unknown_flags


def test_is_valid_thinking_level() -> None:
    for level in VALID_THINKING_LEVELS:
        assert is_valid_thinking_level(level) is True
    assert is_valid_thinking_level("invalid") is False
    assert is_valid_thinking_level("") is False


def test_print_help(capsys: pytest.CaptureFixture[str]) -> None:
    print_help()
    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert "pi" in captured.out
    assert "--model" in captured.out
