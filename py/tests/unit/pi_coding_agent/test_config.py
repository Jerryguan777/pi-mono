"""Tests for pi_coding_agent.config."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from pi_coding_agent.config import (
    APP_NAME,
    CONFIG_DIR_NAME,
    ENV_AGENT_DIR,
    VERSION,
    detect_install_method,
    get_agent_dir,
    get_auth_path,
    get_bin_dir,
    get_custom_themes_dir,
    get_debug_log_path,
    get_models_path,
    get_package_dir,
    get_prompts_dir,
    get_sessions_dir,
    get_settings_path,
    get_share_viewer_url,
    get_themes_dir,
    get_tools_dir,
    get_update_instruction,
)


def test_constants() -> None:
    assert APP_NAME == "pi"
    assert CONFIG_DIR_NAME == ".pi"
    assert isinstance(VERSION, str)
    assert ENV_AGENT_DIR == "PI_CODING_AGENT_DIR"


def test_detect_install_method() -> None:
    assert detect_install_method() == "pip"


def test_get_update_instruction() -> None:
    instruction = get_update_instruction("pi-coding-agent")
    assert "pi-coding-agent" in instruction
    assert "pip" in instruction.lower() or "install" in instruction.lower()


def test_get_package_dir_default() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PI_PACKAGE_DIR", None)
        pkg_dir = get_package_dir()
        assert isinstance(pkg_dir, Path)
        assert pkg_dir.exists()


def test_get_package_dir_env_override(tmp_path: Path) -> None:
    with patch.dict(os.environ, {"PI_PACKAGE_DIR": str(tmp_path)}):
        assert get_package_dir() == tmp_path


def test_get_package_dir_env_tilde() -> None:
    with patch.dict(os.environ, {"PI_PACKAGE_DIR": "~"}):
        assert get_package_dir() == Path.home()


def test_get_package_dir_env_tilde_subdir() -> None:
    with patch.dict(os.environ, {"PI_PACKAGE_DIR": "~/somedir"}):
        result = get_package_dir()
        assert result == Path.home() / "somedir"


def test_get_themes_dir() -> None:
    themes_dir = get_themes_dir()
    assert isinstance(themes_dir, Path)
    # Built-in themes should be in data/
    assert "data" in str(themes_dir)


def test_get_agent_dir_default() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop(ENV_AGENT_DIR, None)
        agent_dir = get_agent_dir()
        assert agent_dir == Path.home() / ".pi" / "agent"


def test_get_agent_dir_env_override(tmp_path: Path) -> None:
    with patch.dict(os.environ, {ENV_AGENT_DIR: str(tmp_path)}):
        assert get_agent_dir() == tmp_path


def test_get_agent_dir_env_tilde() -> None:
    with patch.dict(os.environ, {ENV_AGENT_DIR: "~"}):
        assert get_agent_dir() == Path.home()


def test_get_agent_dir_env_tilde_subdir() -> None:
    with patch.dict(os.environ, {ENV_AGENT_DIR: "~/myagent"}):
        assert get_agent_dir() == Path.home() / "myagent"


def test_path_helpers() -> None:
    # All path helpers should return Path objects under agent_dir
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop(ENV_AGENT_DIR, None)
        agent_dir = get_agent_dir()

        assert get_custom_themes_dir() == agent_dir / "themes"
        assert get_models_path() == agent_dir / "models.json"
        assert get_auth_path() == agent_dir / "auth.json"
        assert get_settings_path() == agent_dir / "settings.json"
        assert get_tools_dir() == agent_dir / "tools"
        assert get_bin_dir() == agent_dir / "bin"
        assert get_prompts_dir() == agent_dir / "prompts"
        assert get_sessions_dir() == agent_dir / "sessions"
        assert get_debug_log_path() == agent_dir / f"{APP_NAME}-debug.log"


def test_get_share_viewer_url_default() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PI_SHARE_VIEWER_URL", None)
        url = get_share_viewer_url("abc123")
        assert url == "https://pi.dev/session/#abc123"


def test_get_share_viewer_url_custom() -> None:
    with patch.dict(os.environ, {"PI_SHARE_VIEWER_URL": "https://example.com/s/"}):
        url = get_share_viewer_url("xyz")
        assert url == "https://example.com/s/#xyz"
