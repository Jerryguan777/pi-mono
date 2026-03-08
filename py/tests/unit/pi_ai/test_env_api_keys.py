"""Tests for pi_ai.env_api_keys."""

from __future__ import annotations

import os
from unittest.mock import patch

from pi_ai.env_api_keys import get_env_api_key, reset_vertex_adc_cache


class TestGetEnvApiKey:
    def test_openai(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            assert get_env_api_key("openai") == "sk-test"

    def test_openai_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert get_env_api_key("openai") is None

    def test_anthropic_api_key(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "ant-key"}, clear=True):
            assert get_env_api_key("anthropic") == "ant-key"

    def test_anthropic_oauth_takes_precedence(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_OAUTH_TOKEN": "oauth-tok", "ANTHROPIC_API_KEY": "api-key"}, clear=True):
            assert get_env_api_key("anthropic") == "oauth-tok"

    def test_github_copilot_token_priority(self) -> None:
        with patch.dict(os.environ, {"COPILOT_GITHUB_TOKEN": "copilot-tok"}, clear=True):
            assert get_env_api_key("github-copilot") == "copilot-tok"

    def test_github_copilot_fallback(self) -> None:
        with patch.dict(os.environ, {"GH_TOKEN": "gh-tok"}, clear=True):
            assert get_env_api_key("github-copilot") == "gh-tok"

    def test_bedrock_profile(self) -> None:
        with patch.dict(os.environ, {"AWS_PROFILE": "my-profile"}, clear=True):
            assert get_env_api_key("amazon-bedrock") == "<authenticated>"

    def test_bedrock_iam_keys(self) -> None:
        with patch.dict(
            os.environ,
            {"AWS_ACCESS_KEY_ID": "AKID", "AWS_SECRET_ACCESS_KEY": "secret"},
            clear=True,
        ):
            assert get_env_api_key("amazon-bedrock") == "<authenticated>"

    def test_bedrock_no_creds(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert get_env_api_key("amazon-bedrock") is None

    def test_vertex_authenticated(self) -> None:
        reset_vertex_adc_cache()
        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/test-creds.json",
                    "GOOGLE_CLOUD_PROJECT": "my-project",
                    "GOOGLE_CLOUD_LOCATION": "us-central1",
                },
                clear=True,
            ),
            patch("pi_ai.env_api_keys.Path") as mock_path,
        ):
            mock_path.return_value.exists.return_value = True
            mock_path.home.return_value.__truediv__ = lambda *a: mock_path.return_value
            # Reset cache for fresh test
            reset_vertex_adc_cache()
            assert get_env_api_key("google-vertex") == "<authenticated>"
        reset_vertex_adc_cache()

    def test_vertex_no_creds(self) -> None:
        reset_vertex_adc_cache()
        with patch.dict(os.environ, {}, clear=True), patch("pi_ai.env_api_keys.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            mock_path.home.return_value.__truediv__ = lambda *a: mock_path.return_value
            reset_vertex_adc_cache()
            assert get_env_api_key("google-vertex") is None
        reset_vertex_adc_cache()

    def test_unknown_provider(self) -> None:
        assert get_env_api_key("unknown-provider") is None

    def test_env_map_providers(self) -> None:
        providers_and_vars = [
            ("google", "GEMINI_API_KEY"),
            ("groq", "GROQ_API_KEY"),
            ("cerebras", "CEREBRAS_API_KEY"),
            ("xai", "XAI_API_KEY"),
            ("openrouter", "OPENROUTER_API_KEY"),
            ("mistral", "MISTRAL_API_KEY"),
            ("huggingface", "HF_TOKEN"),
        ]
        for provider, env_var in providers_and_vars:
            with patch.dict(os.environ, {env_var: "test-key"}, clear=True):
                assert get_env_api_key(provider) == "test-key", f"Failed for {provider}"
