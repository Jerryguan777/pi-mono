"""Tests for pi_ai.env_api_keys."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pi_ai.env_api_keys import get_env_api_key


def test_openai_key() -> None:
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
        assert get_env_api_key("openai") == "sk-test"


def test_openai_key_missing() -> None:
    with patch.dict("os.environ", {}, clear=True):
        assert get_env_api_key("openai") is None


def test_anthropic_api_key() -> None:
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant"}, clear=True):
        assert get_env_api_key("anthropic") == "sk-ant"


def test_anthropic_oauth_takes_precedence() -> None:
    with patch.dict(
        "os.environ",
        {"ANTHROPIC_OAUTH_TOKEN": "sk-ant-oat-xxx", "ANTHROPIC_API_KEY": "sk-ant"},
        clear=True,
    ):
        assert get_env_api_key("anthropic") == "sk-ant-oat-xxx"


def test_github_copilot_copilot_token() -> None:
    with patch.dict("os.environ", {"COPILOT_GITHUB_TOKEN": "ghu_copilot"}, clear=True):
        assert get_env_api_key("github-copilot") == "ghu_copilot"


def test_github_copilot_gh_token_fallback() -> None:
    with patch.dict("os.environ", {"GH_TOKEN": "ghu_gh"}, clear=True):
        assert get_env_api_key("github-copilot") == "ghu_gh"


def test_github_copilot_github_token_fallback() -> None:
    with patch.dict("os.environ", {"GITHUB_TOKEN": "ghu_github"}, clear=True):
        assert get_env_api_key("github-copilot") == "ghu_github"


def test_groq_key() -> None:
    with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_test"}, clear=True):
        assert get_env_api_key("groq") == "gsk_test"


def test_unknown_provider() -> None:
    with patch.dict("os.environ", {}, clear=True):
        assert get_env_api_key("totally-unknown-provider") is None


def test_bedrock_with_profile() -> None:
    with patch.dict("os.environ", {"AWS_PROFILE": "default"}, clear=True):
        assert get_env_api_key("amazon-bedrock") == "<authenticated>"


def test_bedrock_with_access_key() -> None:
    with patch.dict(
        "os.environ",
        {"AWS_ACCESS_KEY_ID": "AKIA", "AWS_SECRET_ACCESS_KEY": "secret"},
        clear=True,
    ):
        assert get_env_api_key("amazon-bedrock") == "<authenticated>"


def test_bedrock_no_creds() -> None:
    with patch.dict("os.environ", {}, clear=True):
        assert get_env_api_key("amazon-bedrock") is None


def test_mistral_key() -> None:
    with patch.dict("os.environ", {"MISTRAL_API_KEY": "mist-key"}, clear=True):
        assert get_env_api_key("mistral") == "mist-key"


def test_xai_key() -> None:
    with patch.dict("os.environ", {"XAI_API_KEY": "xai-key"}, clear=True):
        assert get_env_api_key("xai") == "xai-key"


def test_google_vertex_authenticated(tmp_path: Path) -> None:
    creds_file = tmp_path / "creds.json"
    creds_file.write_text("{}")
    with patch.dict(
        "os.environ",
        {
            "GOOGLE_APPLICATION_CREDENTIALS": str(creds_file),
            "GOOGLE_CLOUD_PROJECT": "my-project",
            "GOOGLE_CLOUD_LOCATION": "us-central1",
        },
        clear=True,
    ):
        assert get_env_api_key("google-vertex") == "<authenticated>"


def test_google_vertex_no_project(tmp_path: Path) -> None:
    creds_file = tmp_path / "creds.json"
    creds_file.write_text("{}")
    with patch.dict(
        "os.environ",
        {
            "GOOGLE_APPLICATION_CREDENTIALS": str(creds_file),
            "GOOGLE_CLOUD_LOCATION": "us-central1",
        },
        clear=True,
    ):
        assert get_env_api_key("google-vertex") is None
