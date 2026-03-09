"""Tests for pi_coding_agent.migrations."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from pi_coding_agent.migrations import (
    MigrationResult,
    _check_deprecated_extension_dirs,
    _migrate_commands_to_prompts,
    migrate_auth_to_auth_json,
    migrate_sessions_from_agent_root,
    run_migrations,
)


def test_migration_result_defaults() -> None:
    result = MigrationResult()
    assert result.migrated_auth_providers == []
    assert result.deprecation_warnings == []


def test_migrate_auth_skipped_when_auth_exists(tmp_path: Path) -> None:
    """If auth.json already exists, no migration is performed."""
    (tmp_path / "auth.json").write_text("{}", encoding="utf-8")

    with patch("pi_coding_agent.migrations.get_agent_dir", return_value=tmp_path):
        providers = migrate_auth_to_auth_json()

    assert providers == []


def test_migrate_auth_from_oauth_json(tmp_path: Path) -> None:
    """Migrate oauth.json into auth.json."""
    oauth_data = {"anthropic": {"token": "abc", "expires_at": 999}}
    (tmp_path / "oauth.json").write_text(json.dumps(oauth_data), encoding="utf-8")

    with patch("pi_coding_agent.migrations.get_agent_dir", return_value=tmp_path):
        providers = migrate_auth_to_auth_json()

    assert "anthropic" in providers
    auth_path = tmp_path / "auth.json"
    assert auth_path.exists()
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    assert auth["anthropic"]["type"] == "oauth"
    assert auth["anthropic"]["token"] == "abc"
    # oauth.json should be renamed
    assert not (tmp_path / "oauth.json").exists()
    assert (tmp_path / "oauth.json.migrated").exists()


def test_migrate_auth_from_settings_json(tmp_path: Path) -> None:
    """Migrate settings.json apiKeys into auth.json."""
    settings = {"apiKeys": {"openai": "sk-abc", "gemini": "key-xyz"}, "theme": "dark"}
    (tmp_path / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    with patch("pi_coding_agent.migrations.get_agent_dir", return_value=tmp_path):
        providers = migrate_auth_to_auth_json()

    assert set(providers) == {"openai", "gemini"}
    auth = json.loads((tmp_path / "auth.json").read_text(encoding="utf-8"))
    assert auth["openai"]["type"] == "api_key"
    assert auth["openai"]["key"] == "sk-abc"

    # apiKeys removed from settings
    updated_settings = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "apiKeys" not in updated_settings
    assert updated_settings["theme"] == "dark"


def test_migrate_auth_no_sources(tmp_path: Path) -> None:
    """No auth.json created if nothing to migrate."""
    with patch("pi_coding_agent.migrations.get_agent_dir", return_value=tmp_path):
        providers = migrate_auth_to_auth_json()

    assert providers == []
    assert not (tmp_path / "auth.json").exists()


def test_migrate_sessions_from_agent_root(tmp_path: Path) -> None:
    """Move .jsonl files from agent root to sessions/<encoded-cwd>/."""
    header = {"type": "session", "cwd": "/home/user/myproject"}
    jsonl_content = json.dumps(header) + "\n" + json.dumps({"type": "msg"})
    session_file = tmp_path / "session-abc.jsonl"
    session_file.write_text(jsonl_content, encoding="utf-8")

    with patch("pi_coding_agent.migrations.get_agent_dir", return_value=tmp_path):
        migrate_sessions_from_agent_root()

    # File should have moved
    assert not session_file.exists()
    # Check it's somewhere under sessions/
    sessions_dir = tmp_path / "sessions"
    assert sessions_dir.exists()
    found = list(sessions_dir.rglob("session-abc.jsonl"))
    assert len(found) == 1


def test_migrate_sessions_skips_empty_agent_dir(tmp_path: Path) -> None:
    """No error if agent dir has no .jsonl files."""
    with patch("pi_coding_agent.migrations.get_agent_dir", return_value=tmp_path):
        migrate_sessions_from_agent_root()  # Should not raise


def test_migrate_commands_to_prompts(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    (commands_dir / "test.md").write_text("cmd", encoding="utf-8")

    result = _migrate_commands_to_prompts(tmp_path, "Test")

    assert result is True
    assert not commands_dir.exists()
    assert (tmp_path / "prompts").exists()
    assert (tmp_path / "prompts" / "test.md").exists()


def test_migrate_commands_to_prompts_skips_if_prompts_exists(tmp_path: Path) -> None:
    (tmp_path / "commands").mkdir()
    (tmp_path / "prompts").mkdir()

    result = _migrate_commands_to_prompts(tmp_path, "Test")

    assert result is False
    assert (tmp_path / "commands").exists()
    assert (tmp_path / "prompts").exists()


def test_migrate_commands_to_prompts_no_commands(tmp_path: Path) -> None:
    result = _migrate_commands_to_prompts(tmp_path, "Test")
    assert result is False


def test_check_deprecated_hooks_dir(tmp_path: Path) -> None:
    (tmp_path / "hooks").mkdir()
    warnings = _check_deprecated_extension_dirs(tmp_path, "Global")
    assert any("hooks" in w for w in warnings)


def test_check_deprecated_tools_dir_with_custom(tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "my-tool.sh").write_text("#!/bin/sh", encoding="utf-8")
    warnings = _check_deprecated_extension_dirs(tmp_path, "Global")
    assert any("tools" in w for w in warnings)


def test_check_deprecated_tools_dir_only_managed(tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    # Only managed binaries — should not warn
    (tools_dir / "fd").write_text("bin", encoding="utf-8")
    (tools_dir / "rg").write_text("bin", encoding="utf-8")
    warnings = _check_deprecated_extension_dirs(tmp_path, "Global")
    assert not any("tools" in w for w in warnings)


def test_check_no_deprecated_dirs(tmp_path: Path) -> None:
    warnings = _check_deprecated_extension_dirs(tmp_path, "Global")
    assert warnings == []


def test_run_migrations(tmp_path: Path) -> None:
    """run_migrations should return a MigrationResult."""
    with (
        patch("pi_coding_agent.migrations.get_agent_dir", return_value=tmp_path),
        patch("pi_coding_agent.migrations.get_bin_dir", return_value=tmp_path / "bin"),
    ):
        result = run_migrations(str(tmp_path))

    assert isinstance(result, MigrationResult)
    assert isinstance(result.migrated_auth_providers, list)
    assert isinstance(result.deprecation_warnings, list)
