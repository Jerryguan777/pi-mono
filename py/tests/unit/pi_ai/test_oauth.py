"""Tests for pi_ai.oauth — PKCE generation, registry, token refresh, and provider modules."""

from __future__ import annotations

import hashlib
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_ai.oauth import (
    get_oauth_api_key,
    get_oauth_provider,
    get_oauth_provider_info_list,
    get_oauth_providers,
    refresh_oauth_token,
    register_oauth_provider,
)
from pi_ai.oauth.pkce import _base64url_encode, generate_pkce
from pi_ai.oauth.types import (
    OAuthAuthInfo,
    OAuthCredentials,
    OAuthLoginCallbacks,
    OAuthPrompt,
    OAuthProviderInfo,
)

# ---------------------------------------------------------------------------
# PKCE
# ---------------------------------------------------------------------------


class TestPkce:
    async def test_generate_pkce_returns_pair(self) -> None:
        verifier, challenge = await generate_pkce()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 0
        assert len(challenge) > 0

    async def test_challenge_is_sha256_of_verifier(self) -> None:
        verifier, challenge = await generate_pkce()
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = _base64url_encode(digest)
        assert challenge == expected

    async def test_verifier_is_base64url(self) -> None:
        verifier, _ = await generate_pkce()
        # base64url characters only (no padding)
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert all(c in valid_chars for c in verifier)

    async def test_each_call_generates_different_values(self) -> None:
        v1, c1 = await generate_pkce()
        v2, c2 = await generate_pkce()
        assert v1 != v2
        assert c1 != c2

    def test_base64url_encode_no_padding(self) -> None:
        result = _base64url_encode(b"\x00\x01\x02")
        assert "=" not in result

    def test_base64url_encode_uses_url_safe_chars(self) -> None:
        # Bytes that would produce + and / in standard base64
        data = b"\xfb\xff\xfe"
        result = _base64url_encode(data)
        assert "+" not in result
        assert "/" not in result


# ---------------------------------------------------------------------------
# OAuthCredentials
# ---------------------------------------------------------------------------


class TestOAuthCredentials:
    def test_defaults(self) -> None:
        creds = OAuthCredentials()
        assert creds.refresh == ""
        assert creds.access == ""
        assert creds.expires == 0

    def test_getitem(self) -> None:
        creds = OAuthCredentials(refresh="r", access="a", expires=1000)
        assert creds["refresh"] == "r"
        assert creds["access"] == "a"
        assert creds["expires"] == 1000

    def test_getitem_extra(self) -> None:
        creds = OAuthCredentials(extra={"custom": "value"})
        assert creds["custom"] == "value"

    def test_setitem(self) -> None:
        creds = OAuthCredentials()
        creds["refresh"] = "new_refresh"
        assert creds.refresh == "new_refresh"
        creds["custom"] = "custom_val"
        assert creds.extra["custom"] == "custom_val"

    def test_get(self) -> None:
        creds = OAuthCredentials(refresh="r")
        assert creds.get("refresh") == "r"
        assert creds.get("missing", "default") == "default"


# ---------------------------------------------------------------------------
# OAuthProviderInfo / OAuthPrompt / OAuthAuthInfo / OAuthLoginCallbacks
# ---------------------------------------------------------------------------


class TestOAuthTypes:
    def test_provider_info(self) -> None:
        info = OAuthProviderInfo(id="test", name="Test Provider")
        assert info.id == "test"
        assert info.available is True

    def test_prompt(self) -> None:
        prompt = OAuthPrompt(message="Enter code:", placeholder="code", allow_empty=True)
        assert prompt.message == "Enter code:"
        assert prompt.allow_empty is True

    def test_auth_info(self) -> None:
        info = OAuthAuthInfo(url="https://example.com/auth", instructions="Go here")
        assert info.url == "https://example.com/auth"

    def test_login_callbacks(self) -> None:
        cb = OAuthLoginCallbacks()
        assert cb.on_auth is None
        assert cb.on_prompt is None


# ---------------------------------------------------------------------------
# Registry functions
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_get_known_providers(self) -> None:
        """All built-in providers should be registered."""
        provider = get_oauth_provider("anthropic")
        assert provider is not None
        assert provider.id == "anthropic"

        provider = get_oauth_provider("github-copilot")
        assert provider is not None

        provider = get_oauth_provider("google-gemini-cli")
        assert provider is not None

        provider = get_oauth_provider("google-antigravity")
        assert provider is not None

        provider = get_oauth_provider("openai-codex")
        assert provider is not None

    def test_get_unknown_provider(self) -> None:
        assert get_oauth_provider("nonexistent") is None

    def test_register_custom_provider(self) -> None:
        class CustomProvider:
            @property
            def id(self) -> str:
                return "custom-test"

            @property
            def name(self) -> str:
                return "Custom Test"

        custom = CustomProvider()
        register_oauth_provider(custom)
        assert get_oauth_provider("custom-test") is custom

    def test_get_all_providers(self) -> None:
        providers = get_oauth_providers()
        assert len(providers) >= 5  # At least the built-in ones
        ids = [p.id for p in providers]
        assert "anthropic" in ids
        assert "github-copilot" in ids

    def test_get_provider_info_list(self) -> None:
        info_list = get_oauth_provider_info_list()
        assert len(info_list) >= 5
        for info in info_list:
            assert isinstance(info, OAuthProviderInfo)
            assert info.available is True


# ---------------------------------------------------------------------------
# refresh_oauth_token
# ---------------------------------------------------------------------------


class TestRefreshOAuthToken:
    async def test_unknown_provider_raises(self) -> None:
        creds = OAuthCredentials(refresh="token")
        with pytest.raises(RuntimeError, match="Unknown OAuth provider"):
            await refresh_oauth_token("nonexistent", creds)

    async def test_delegates_to_provider(self) -> None:
        mock_provider = MagicMock()
        new_creds = OAuthCredentials(refresh="new", access="new_access", expires=9999)
        mock_provider.refresh_token = AsyncMock(return_value=new_creds)
        mock_provider.id = "test-refresh"

        register_oauth_provider(mock_provider)

        creds = OAuthCredentials(refresh="old")
        result = await refresh_oauth_token("test-refresh", creds)
        assert result.access == "new_access"
        mock_provider.refresh_token.assert_called_once_with(creds)


# ---------------------------------------------------------------------------
# get_oauth_api_key
# ---------------------------------------------------------------------------


class TestGetOAuthApiKey:
    async def test_unknown_provider_raises(self) -> None:
        with pytest.raises(RuntimeError, match="Unknown OAuth provider"):
            await get_oauth_api_key("nonexistent", {})

    async def test_no_credentials_returns_none(self) -> None:
        result = await get_oauth_api_key("anthropic", {})
        assert result is None

    async def test_valid_non_expired_credentials(self) -> None:
        mock_provider = MagicMock()
        mock_provider.id = "test-apikey"
        mock_provider.get_api_key = MagicMock(return_value="the-api-key")
        mock_provider.refresh_token = AsyncMock()

        register_oauth_provider(mock_provider)

        future_ms = int(time.time() * 1000) + 3600_000  # 1 hour from now
        creds = OAuthCredentials(refresh="r", access="a", expires=future_ms)
        result = await get_oauth_api_key("test-apikey", {"test-apikey": creds})

        assert result is not None
        _returned_creds, api_key = result
        assert api_key == "the-api-key"
        mock_provider.refresh_token.assert_not_called()

    async def test_expired_credentials_triggers_refresh(self) -> None:
        mock_provider = MagicMock()
        mock_provider.id = "test-expired"
        new_creds = OAuthCredentials(
            refresh="new_r",
            access="new_a",
            expires=int(time.time() * 1000) + 3600_000,
        )
        mock_provider.refresh_token = AsyncMock(return_value=new_creds)
        mock_provider.get_api_key = MagicMock(return_value="refreshed-key")

        register_oauth_provider(mock_provider)

        old_creds = OAuthCredentials(refresh="old", access="old", expires=0)  # Already expired
        result = await get_oauth_api_key("test-expired", {"test-expired": old_creds})

        assert result is not None
        _, api_key = result
        assert api_key == "refreshed-key"
        mock_provider.refresh_token.assert_called_once()

    async def test_refresh_failure_raises(self) -> None:
        mock_provider = MagicMock()
        mock_provider.id = "test-fail"
        mock_provider.refresh_token = AsyncMock(side_effect=Exception("Network error"))

        register_oauth_provider(mock_provider)

        old_creds = OAuthCredentials(refresh="old", expires=0)
        with pytest.raises(RuntimeError, match="Failed to refresh"):
            await get_oauth_api_key("test-fail", {"test-fail": old_creds})


# ---------------------------------------------------------------------------
# Built-in provider properties
# ---------------------------------------------------------------------------


class TestBuiltInProviders:
    def test_anthropic_provider(self) -> None:
        from pi_ai.oauth.anthropic_oauth import anthropic_oauth_provider

        assert anthropic_oauth_provider.id == "anthropic"
        assert anthropic_oauth_provider.name == "Anthropic (Claude Pro/Max)"
        assert anthropic_oauth_provider.uses_callback_server is False
        creds = OAuthCredentials(access="test-key")
        assert anthropic_oauth_provider.get_api_key(creds) == "test-key"
        assert anthropic_oauth_provider.modify_models([], creds) == []

    def test_github_copilot_provider(self) -> None:
        from pi_ai.oauth.github_copilot import github_copilot_oauth_provider

        assert github_copilot_oauth_provider.id == "github-copilot"

    def test_gemini_cli_provider(self) -> None:
        from pi_ai.oauth.google_gemini_cli import gemini_cli_oauth_provider

        assert gemini_cli_oauth_provider.id == "google-gemini-cli"

    def test_antigravity_provider(self) -> None:
        from pi_ai.oauth.google_antigravity import antigravity_oauth_provider

        assert antigravity_oauth_provider.id == "google-antigravity"

    def test_openai_codex_provider(self) -> None:
        from pi_ai.oauth.openai_codex import openai_codex_oauth_provider

        assert openai_codex_oauth_provider.id == "openai-codex"


# ---------------------------------------------------------------------------
# GitHub Copilot helpers
# ---------------------------------------------------------------------------


class TestGitHubCopilotHelpers:
    def test_normalize_domain(self) -> None:
        from pi_ai.oauth.github_copilot import normalize_domain

        assert normalize_domain("https://github.com") == "github.com"
        assert normalize_domain("github.com") == "github.com"

    def test_normalize_domain_empty(self) -> None:
        from pi_ai.oauth.github_copilot import normalize_domain

        assert normalize_domain("") is None
        assert normalize_domain("   ") is None

    def test_normalize_domain_with_path(self) -> None:
        from pi_ai.oauth.github_copilot import normalize_domain

        assert normalize_domain("https://ghe.company.com/some/path") == "ghe.company.com"

    def test_normalize_domain_plain(self) -> None:
        from pi_ai.oauth.github_copilot import normalize_domain

        assert normalize_domain("ghe.company.com") == "ghe.company.com"

    def test_get_github_copilot_base_url(self) -> None:
        from pi_ai.oauth.github_copilot import get_github_copilot_base_url

        url = get_github_copilot_base_url()
        assert url == "https://api.individual.githubcopilot.com"

    def test_get_github_copilot_base_url_with_enterprise(self) -> None:
        from pi_ai.oauth.github_copilot import get_github_copilot_base_url

        url = get_github_copilot_base_url(enterprise_domain="ghe.company.com")
        assert url == "https://copilot-api.ghe.company.com"

    def test_get_github_copilot_base_url_from_token(self) -> None:
        from pi_ai.oauth.github_copilot import get_github_copilot_base_url

        token = "tid=abc;proxy-ep=proxy.example.com;exp=1234"
        url = get_github_copilot_base_url(token=token)
        assert url == "https://api.example.com"

    def test_get_github_copilot_base_url_token_no_proxy(self) -> None:
        from pi_ai.oauth.github_copilot import get_github_copilot_base_url

        token = "tid=abc;exp=1234"
        url = get_github_copilot_base_url(token=token)
        assert url == "https://api.individual.githubcopilot.com"


# ---------------------------------------------------------------------------
# GitHub Copilot OAuth flows (mocked)
# ---------------------------------------------------------------------------


class TestGitHubCopilotExchangeDeviceCode:
    async def test_poll_for_github_access_token_success(self) -> None:
        from pi_ai.oauth.github_copilot import _poll_for_github_access_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "ghu_test123"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client):
            result = await _poll_for_github_access_token("github.com", "device123", 1, 30)
            assert result == "ghu_test123"

    async def test_refresh_github_copilot_token(self) -> None:
        from pi_ai.oauth.github_copilot import refresh_github_copilot_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "token": "copilot_token_abc",
            "expires_at": time.time() + 3600,
        }

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client):
            creds = await refresh_github_copilot_token("ghu_test123")
            assert creds.access == "copilot_token_abc"
            assert creds.refresh == "ghu_test123"

    async def test_refresh_github_copilot_token_enterprise(self) -> None:
        from pi_ai.oauth.github_copilot import refresh_github_copilot_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "token": "copilot_token_ent",
            "expires_at": time.time() + 3600,
        }

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client):
            creds = await refresh_github_copilot_token("ghu_test123", "ghe.company.com")
            assert creds.extra == {"enterprise_url": "ghe.company.com"}

    async def test_refresh_github_copilot_token_invalid_response(self) -> None:
        from pi_ai.oauth.github_copilot import refresh_github_copilot_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "data"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Invalid Copilot token response"),
        ):
            await refresh_github_copilot_token("ghu_test123")


# ---------------------------------------------------------------------------
# Anthropic OAuth flows (mocked)
# ---------------------------------------------------------------------------


class TestAnthropicOAuth:
    async def test_login_anthropic(self) -> None:
        from pi_ai.oauth.anthropic_oauth import login_anthropic

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "ant_access_123",
            "refresh_token": "ant_refresh_456",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        auth_urls: list[str] = []

        def on_auth_url(url: str) -> None:
            auth_urls.append(url)

        async def on_prompt_code() -> str:
            return "authcode123#stateXYZ"

        with patch("pi_ai.oauth.anthropic_oauth.httpx.AsyncClient", return_value=mock_client):
            creds = await login_anthropic(on_auth_url, on_prompt_code)
            assert creds.access == "ant_access_123"
            assert creds.refresh == "ant_refresh_456"
            assert len(auth_urls) == 1
            assert "oauth/authorize" in auth_urls[0]

    async def test_login_anthropic_failure(self) -> None:
        from pi_ai.oauth.anthropic_oauth import login_anthropic

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.anthropic_oauth.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Token exchange failed"),
        ):
            await login_anthropic(lambda url: None, AsyncMock(return_value="code#state"))

    async def test_refresh_anthropic_token(self) -> None:
        from pi_ai.oauth.anthropic_oauth import refresh_anthropic_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 7200,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.anthropic_oauth.httpx.AsyncClient", return_value=mock_client):
            creds = await refresh_anthropic_token("old_refresh")
            assert creds.access == "new_access"
            assert creds.refresh == "new_refresh"

    async def test_refresh_anthropic_token_failure(self) -> None:
        from pi_ai.oauth.anthropic_oauth import refresh_anthropic_token

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.anthropic_oauth.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Anthropic token refresh failed"),
        ):
            await refresh_anthropic_token("bad_refresh")


# ---------------------------------------------------------------------------
# OpenAI Codex helpers
# ---------------------------------------------------------------------------


class TestOpenAICodexHelpers:
    def test_parse_authorization_input_empty(self) -> None:
        from pi_ai.oauth.openai_codex import _parse_authorization_input

        assert _parse_authorization_input("") == {}
        assert _parse_authorization_input("   ") == {}

    def test_parse_authorization_input_url(self) -> None:
        from pi_ai.oauth.openai_codex import _parse_authorization_input

        result = _parse_authorization_input("http://localhost/callback?code=abc&state=xyz")
        assert result["code"] == "abc"
        assert result["state"] == "xyz"

    def test_parse_authorization_input_hash_format(self) -> None:
        from pi_ai.oauth.openai_codex import _parse_authorization_input

        result = _parse_authorization_input("mycode#mystate")
        assert result["code"] == "mycode"
        assert result["state"] == "mystate"

    def test_parse_authorization_input_code_equals(self) -> None:
        from pi_ai.oauth.openai_codex import _parse_authorization_input

        result = _parse_authorization_input("code=abc123&state=st456")
        assert result["code"] == "abc123"
        assert result["state"] == "st456"

    def test_parse_authorization_input_bare_code(self) -> None:
        from pi_ai.oauth.openai_codex import _parse_authorization_input

        result = _parse_authorization_input("simple_code")
        assert result["code"] == "simple_code"

    def test_decode_jwt_valid(self) -> None:
        import base64
        import json

        from pi_ai.oauth.openai_codex import _decode_jwt

        payload = {"sub": "user123", "exp": 9999999999}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"header.{encoded}.signature"
        result = _decode_jwt(token)
        assert result is not None
        assert result["sub"] == "user123"

    def test_decode_jwt_invalid(self) -> None:
        from pi_ai.oauth.openai_codex import _decode_jwt

        assert _decode_jwt("not.a.jwt.token") is None
        assert _decode_jwt("only_one_part") is None
        assert _decode_jwt("") is None

    def test_get_account_id_valid(self) -> None:
        import base64
        import json

        from pi_ai.oauth.openai_codex import _get_account_id

        payload = {"https://api.openai.com/auth": {"chatgpt_account_id": "acct_123"}}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"header.{encoded}.signature"
        result = _get_account_id(token)
        assert result == "acct_123"

    def test_get_account_id_missing(self) -> None:
        import base64
        import json

        from pi_ai.oauth.openai_codex import _get_account_id

        payload = {"sub": "user123"}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"header.{encoded}.signature"
        assert _get_account_id(token) is None

    def test_get_account_id_invalid_token(self) -> None:
        from pi_ai.oauth.openai_codex import _get_account_id

        assert _get_account_id("invalid") is None


# ---------------------------------------------------------------------------
# OpenAI Codex OAuth flows (mocked)
# ---------------------------------------------------------------------------


class TestOpenAICodexOAuthFlows:
    async def test_exchange_authorization_code_success(self) -> None:
        from pi_ai.oauth.openai_codex import _exchange_authorization_code

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "oai_access",
            "refresh_token": "oai_refresh",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client):
            result = await _exchange_authorization_code("code123", "verifier456")
            assert result is not None
            assert result["access"] == "oai_access"
            assert result["refresh"] == "oai_refresh"

    async def test_exchange_authorization_code_failure(self) -> None:
        from pi_ai.oauth.openai_codex import _exchange_authorization_code

        mock_response = MagicMock()
        mock_response.status_code = 400

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client):
            result = await _exchange_authorization_code("bad_code", "verifier")
            assert result is None

    async def test_exchange_authorization_code_missing_fields(self) -> None:
        from pi_ai.oauth.openai_codex import _exchange_authorization_code

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "token"}  # missing refresh_token

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client):
            result = await _exchange_authorization_code("code", "verifier")
            assert result is None

    async def test_refresh_access_token_success(self) -> None:
        from pi_ai.oauth.openai_codex import _refresh_access_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 7200,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client):
            result = await _refresh_access_token("old_refresh")
            assert result is not None
            assert result["access"] == "new_access"

    async def test_refresh_access_token_failure(self) -> None:
        from pi_ai.oauth.openai_codex import _refresh_access_token

        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client):
            result = await _refresh_access_token("bad_refresh")
            assert result is None

    async def test_refresh_access_token_exception(self) -> None:
        from pi_ai.oauth.openai_codex import _refresh_access_token

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client):
            result = await _refresh_access_token("refresh")
            assert result is None


# ---------------------------------------------------------------------------
# Google Antigravity helpers
# ---------------------------------------------------------------------------


class TestAntigravityHelpers:
    def test_parse_redirect_url(self) -> None:
        from pi_ai.oauth.google_antigravity import _parse_redirect_url

        result = _parse_redirect_url("http://localhost/callback?code=abc&state=xyz")
        assert result["code"] == "abc"
        assert result["state"] == "xyz"

    def test_parse_redirect_url_empty(self) -> None:
        from pi_ai.oauth.google_antigravity import _parse_redirect_url

        assert _parse_redirect_url("") == {}
        assert _parse_redirect_url("   ") == {}

    async def test_discover_project_success(self) -> None:
        from pi_ai.oauth.google_antigravity import _discover_project

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"cloudaicompanionProject": "my-project-123"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_antigravity.httpx.AsyncClient", return_value=mock_client):
            result = await _discover_project("test_token")
            assert result == "my-project-123"

    async def test_discover_project_dict_format(self) -> None:
        from pi_ai.oauth.google_antigravity import _discover_project

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"cloudaicompanionProject": {"id": "proj-dict"}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_antigravity.httpx.AsyncClient", return_value=mock_client):
            result = await _discover_project("test_token")
            assert result == "proj-dict"

    async def test_discover_project_fallback_to_default(self) -> None:
        from pi_ai.oauth.google_antigravity import _DEFAULT_PROJECT_ID, _discover_project

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_antigravity.httpx.AsyncClient", return_value=mock_client):
            result = await _discover_project("test_token")
            assert result == _DEFAULT_PROJECT_ID

    async def test_refresh_antigravity_token_success(self) -> None:
        from pi_ai.oauth.google_antigravity import refresh_antigravity_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_antigravity.httpx.AsyncClient", return_value=mock_client):
            creds = await refresh_antigravity_token("old_refresh", "proj-123")
            assert creds.access == "new_access"
            assert creds.refresh == "old_refresh"  # uses existing refresh token
            assert creds.extra["project_id"] == "proj-123"

    async def test_refresh_antigravity_token_failure(self) -> None:
        from pi_ai.oauth.google_antigravity import refresh_antigravity_token

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.google_antigravity.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Antigravity token refresh failed"),
        ):
            await refresh_antigravity_token("bad_refresh", "proj")

    async def test_get_user_email_success(self) -> None:
        from pi_ai.oauth.google_antigravity import _get_user_email

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"email": "user@example.com"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_antigravity.httpx.AsyncClient", return_value=mock_client):
            result = await _get_user_email("token")
            assert result == "user@example.com"

    async def test_get_user_email_failure(self) -> None:
        from pi_ai.oauth.google_antigravity import _get_user_email

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_antigravity.httpx.AsyncClient", return_value=mock_client):
            result = await _get_user_email("token")
            assert result is None

    def test_antigravity_provider_get_api_key(self) -> None:
        import json

        from pi_ai.oauth.google_antigravity import antigravity_oauth_provider

        creds = OAuthCredentials(access="tok", extra={"project_id": "proj"})
        api_key = antigravity_oauth_provider.get_api_key(creds)
        parsed = json.loads(api_key)
        assert parsed["token"] == "tok"
        assert parsed["projectId"] == "proj"

    async def test_antigravity_provider_refresh_missing_project(self) -> None:
        from pi_ai.oauth.google_antigravity import antigravity_oauth_provider

        creds = OAuthCredentials(refresh="r", access="a", extra={})
        with pytest.raises(RuntimeError, match="missing project_id"):
            await antigravity_oauth_provider.refresh_token(creds)


# ---------------------------------------------------------------------------
# Google Gemini CLI helpers
# ---------------------------------------------------------------------------


class TestGeminiCliHelpers:
    def test_parse_redirect_url(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _parse_redirect_url

        result = _parse_redirect_url("http://localhost/cb?code=abc&state=xyz")
        assert result["code"] == "abc"
        assert result["state"] == "xyz"

    def test_parse_redirect_url_empty(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _parse_redirect_url

        assert _parse_redirect_url("") == {}

    def test_get_default_tier_none(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _get_default_tier

        result = _get_default_tier(None)
        assert result["id"] == "legacy-tier"

    def test_get_default_tier_empty(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _get_default_tier

        result = _get_default_tier([])
        assert result["id"] == "legacy-tier"

    def test_get_default_tier_with_default(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _get_default_tier

        tiers: list[dict[str, Any]] = [{"id": "free-tier", "isDefault": True}, {"id": "standard-tier"}]
        result = _get_default_tier(tiers)
        assert result["id"] == "free-tier"

    def test_get_default_tier_no_default(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _get_default_tier

        tiers = [{"id": "free-tier"}, {"id": "standard-tier"}]
        result = _get_default_tier(tiers)
        assert result["id"] == "legacy-tier"

    def test_is_vpc_sc_affected_user_true(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _is_vpc_sc_affected_user

        payload = {"error": {"details": [{"reason": "SECURITY_POLICY_VIOLATED"}]}}
        assert _is_vpc_sc_affected_user(payload) is True

    def test_is_vpc_sc_affected_user_false(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _is_vpc_sc_affected_user

        assert _is_vpc_sc_affected_user(None) is False
        assert _is_vpc_sc_affected_user({}) is False
        assert _is_vpc_sc_affected_user({"error": "string"}) is False
        assert _is_vpc_sc_affected_user({"error": {"details": "not a list"}}) is False

    async def test_refresh_google_cloud_token_success(self) -> None:
        from pi_ai.oauth.google_gemini_cli import refresh_google_cloud_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client):
            creds = await refresh_google_cloud_token("old_refresh", "proj-abc")
            assert creds.access == "new_access"
            assert creds.extra["project_id"] == "proj-abc"

    async def test_refresh_google_cloud_token_failure(self) -> None:
        from pi_ai.oauth.google_gemini_cli import refresh_google_cloud_token

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Google Cloud token refresh failed"),
        ):
            await refresh_google_cloud_token("bad", "proj")

    async def test_get_user_email_success(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _get_user_email

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"email": "user@gmail.com"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client):
            result = await _get_user_email("token")
            assert result == "user@gmail.com"

    async def test_get_user_email_failure(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _get_user_email

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client):
            result = await _get_user_email("token")
            assert result is None

    def test_gemini_cli_provider_get_api_key(self) -> None:
        import json

        from pi_ai.oauth.google_gemini_cli import gemini_cli_oauth_provider

        creds = OAuthCredentials(access="tok", extra={"project_id": "proj"})
        api_key = gemini_cli_oauth_provider.get_api_key(creds)
        parsed = json.loads(api_key)
        assert parsed["token"] == "tok"
        assert parsed["projectId"] == "proj"

    async def test_gemini_cli_provider_refresh_missing_project(self) -> None:
        from pi_ai.oauth.google_gemini_cli import gemini_cli_oauth_provider

        creds = OAuthCredentials(refresh="r", access="a", extra={})
        with pytest.raises(RuntimeError, match="missing project_id"):
            await gemini_cli_oauth_provider.refresh_token(creds)

    def test_gemini_cli_provider_properties(self) -> None:
        from pi_ai.oauth.google_gemini_cli import gemini_cli_oauth_provider

        assert gemini_cli_oauth_provider.uses_callback_server is True
        assert gemini_cli_oauth_provider.name == "Google Cloud Code Assist (Gemini CLI)"

    def test_openai_codex_provider_properties(self) -> None:
        from pi_ai.oauth.openai_codex import openai_codex_oauth_provider

        assert openai_codex_oauth_provider.uses_callback_server is True
        assert openai_codex_oauth_provider.name == "ChatGPT Plus/Pro (Codex Subscription)"
        creds = OAuthCredentials(access="tok")
        assert openai_codex_oauth_provider.get_api_key(creds) == "tok"
        assert openai_codex_oauth_provider.modify_models([], creds) == []


# ---------------------------------------------------------------------------
# Gemini CLI _discover_project (mocked)
# ---------------------------------------------------------------------------


class TestGeminiCliDiscoverProject:
    async def test_discover_project_existing_tier_with_project(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _discover_project

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "currentTier": {"id": "standard-tier"},
            "cloudaicompanionProject": "existing-project",
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client):
            result = await _discover_project("token")
            assert result == "existing-project"

    async def test_discover_project_existing_tier_env_fallback(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _discover_project

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"currentTier": {"id": "standard-tier"}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            patch(
                "pi_ai.oauth.google_gemini_cli.os.environ.get",
                side_effect=lambda k: "env-proj" if k == "GOOGLE_CLOUD_PROJECT" else None,
            ),
        ):
            result = await _discover_project("token")
            assert result == "env-proj"

    async def test_discover_project_existing_tier_no_project_raises(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _discover_project

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"currentTier": {"id": "standard-tier"}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            patch("pi_ai.oauth.google_gemini_cli.os.environ.get", return_value=None),
            pytest.raises(RuntimeError, match="requires setting GOOGLE_CLOUD_PROJECT"),
        ):
            await _discover_project("token")

    async def test_discover_project_onboard_success(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _discover_project

        load_response = MagicMock()
        load_response.status_code = 200
        load_response.json.return_value = {
            "allowedTiers": [{"id": "free-tier", "isDefault": True}],
        }

        onboard_response = MagicMock()
        onboard_response.status_code = 200
        onboard_response.json.return_value = {
            "done": True,
            "response": {"cloudaicompanionProject": {"id": "provisioned-proj"}},
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[load_response, onboard_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            patch("pi_ai.oauth.google_gemini_cli.os.environ.get", return_value=None),
        ):
            result = await _discover_project("token")
            assert result == "provisioned-proj"

    async def test_discover_project_onboard_failure(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _discover_project

        load_response = MagicMock()
        load_response.status_code = 200
        load_response.json.return_value = {
            "allowedTiers": [{"id": "free-tier", "isDefault": True}],
        }

        onboard_response = MagicMock()
        onboard_response.status_code = 500
        onboard_response.reason_phrase = "Internal Server Error"
        onboard_response.text = "error"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[load_response, onboard_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            patch("pi_ai.oauth.google_gemini_cli.os.environ.get", return_value=None),
            pytest.raises(RuntimeError, match="onboardUser failed"),
        ):
            await _discover_project("token")

    async def test_discover_project_load_error_not_vpc(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _discover_project

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.reason_phrase = "Forbidden"
        mock_response.text = "Not allowed"
        mock_response.json.return_value = {"error": {"message": "denied"}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            patch("pi_ai.oauth.google_gemini_cli.os.environ.get", return_value=None),
            pytest.raises(RuntimeError, match="loadCodeAssist failed"),
        ):
            await _discover_project("token")

    async def test_discover_project_vpc_sc_user(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _discover_project

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "error": {"details": [{"reason": "SECURITY_POLICY_VIOLATED"}]},
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            patch(
                "pi_ai.oauth.google_gemini_cli.os.environ.get",
                side_effect=lambda k: "vpc-proj" if k == "GOOGLE_CLOUD_PROJECT" else None,
            ),
        ):
            result = await _discover_project("token")
            assert result == "vpc-proj"

    async def test_discover_project_non_free_tier_no_env_raises(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _discover_project

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "allowedTiers": [{"id": "standard-tier", "isDefault": True}],
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            patch("pi_ai.oauth.google_gemini_cli.os.environ.get", return_value=None),
            pytest.raises(RuntimeError, match="requires setting GOOGLE_CLOUD_PROJECT"),
        ):
            await _discover_project("token")


# ---------------------------------------------------------------------------
# Gemini CLI _poll_operation (mocked)
# ---------------------------------------------------------------------------


class TestGeminiCliPollOperation:
    async def test_poll_operation_done_immediately(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _poll_operation

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"done": True, "response": {"id": "proj"}}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client):
            result = await _poll_operation("ops/123", {"Authorization": "Bearer tok"})
            assert result["done"] is True

    async def test_poll_operation_error(self) -> None:
        from pi_ai.oauth.google_gemini_cli import _poll_operation

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.reason_phrase = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Failed to poll operation"),
        ):
            await _poll_operation("ops/123", {})


# ---------------------------------------------------------------------------
# GitHub Copilot _start_device_flow, modify_models
# ---------------------------------------------------------------------------


class TestGitHubCopilotAdvanced:
    async def test_start_device_flow(self) -> None:
        from pi_ai.oauth.github_copilot import _start_device_flow

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "device_code": "dc123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://github.com/login/device",
            "interval": 5,
            "expires_in": 900,
        }

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client):
            data = await _start_device_flow("github.com")
            assert data["device_code"] == "dc123"
            assert data["user_code"] == "ABCD-1234"

    async def test_start_device_flow_missing_field(self) -> None:
        from pi_ai.oauth.github_copilot import _start_device_flow

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"device_code": "dc"}  # missing fields

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Invalid device code response"),
        ):
            await _start_device_flow("github.com")

    async def test_start_device_flow_not_dict(self) -> None:
        from pi_ai.oauth.github_copilot import _start_device_flow

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = "not a dict"

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Invalid device code response"),
        ):
            await _start_device_flow("github.com")

    def test_modify_models_with_copilot_models(self) -> None:
        from pi_ai.oauth.github_copilot import github_copilot_oauth_provider
        from pi_ai.types import Model

        creds = OAuthCredentials(access="tid=abc;exp=1234", extra={})
        models = [
            Model(id="gpt-4", provider="github-copilot", base_url="old"),
            Model(id="other", provider="openai", base_url="keep"),
        ]
        result = github_copilot_oauth_provider.modify_models(models, creds)
        assert result[0].base_url != "old"
        assert result[1].base_url == "keep"

    async def test_fetch_json_error(self) -> None:
        from pi_ai.oauth.github_copilot import _fetch_json

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        mock_response.text = "not found"

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="404"),
        ):
            await _fetch_json("https://example.com", method="GET")

    async def test_poll_device_code_error(self) -> None:
        from pi_ai.oauth.github_copilot import _poll_for_github_access_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "access_denied"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Device flow failed"),
        ):
            await _poll_for_github_access_token("github.com", "dc", 1, 30)

    async def test_poll_device_code_cancelled(self) -> None:
        import asyncio

        from pi_ai.oauth.github_copilot import _poll_for_github_access_token

        signal = asyncio.Event()
        signal.set()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "authorization_pending"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Login cancelled"),
        ):
            await _poll_for_github_access_token("github.com", "dc", 1, 30, signal)


# ---------------------------------------------------------------------------
# OpenAI Codex refresh_openai_codex_token (mocked)
# ---------------------------------------------------------------------------


class TestOpenAICodexRefreshToken:
    async def test_refresh_openai_codex_token_success(self) -> None:
        import base64
        import json

        from pi_ai.oauth.openai_codex import refresh_openai_codex_token

        # Build a valid JWT with account_id
        payload = {"https://api.openai.com/auth": {"chatgpt_account_id": "acct_test"}}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        fake_jwt = f"header.{encoded}.signature"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": fake_jwt,
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client):
            creds = await refresh_openai_codex_token("old_refresh")
            assert creds.access == fake_jwt
            assert creds.refresh == "new_refresh"
            assert creds.extra["account_id"] == "acct_test"

    async def test_refresh_openai_codex_token_failure(self) -> None:
        from pi_ai.oauth.openai_codex import refresh_openai_codex_token

        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Failed to refresh"),
        ):
            await refresh_openai_codex_token("bad")

    async def test_refresh_openai_codex_token_no_account_id(self) -> None:
        import base64
        import json

        from pi_ai.oauth.openai_codex import refresh_openai_codex_token

        payload = {"sub": "user"}  # no account_id
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        fake_jwt = f"header.{encoded}.signature"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": fake_jwt,
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="Failed to extract accountId"),
        ):
            await refresh_openai_codex_token("refresh")


# ---------------------------------------------------------------------------
# Antigravity login flow (mocked)
# ---------------------------------------------------------------------------


class TestAntigravityLoginFlow:
    async def test_login_antigravity_success(self) -> None:
        import asyncio

        from pi_ai.oauth.google_antigravity import login_antigravity

        # Mock token exchange response
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": "ag_access",
            "refresh_token": "ag_refresh",
            "expires_in": 3600,
        }

        # Mock user info response
        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {"email": "user@test.com"}

        # Mock discover project response
        discover_response = MagicMock()
        discover_response.status_code = 200
        discover_response.json.return_value = {"cloudaicompanionProject": "proj-x"}

        mock_client = AsyncMock()
        # post is called for: token exchange, then discover project
        mock_client.post = AsyncMock(side_effect=[token_response, discover_response])
        mock_client.get = AsyncMock(return_value=userinfo_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        auth_infos: list[object] = []

        def on_auth(info: object) -> None:
            auth_infos.append(info)

        # Mock server to return code+state immediately
        async def mock_start_callback_server() -> tuple[MagicMock, asyncio.Future[dict[str, str] | None]]:
            loop = asyncio.get_event_loop()
            future: asyncio.Future[dict[str, str] | None] = loop.create_future()
            server_mock = MagicMock()
            server_mock.close = MagicMock()
            server_mock.wait_closed = AsyncMock()
            return server_mock, future

        with (
            patch("pi_ai.oauth.google_antigravity.httpx.AsyncClient", return_value=mock_client),
            patch("pi_ai.oauth.google_antigravity._start_callback_server", mock_start_callback_server),
            patch("pi_ai.oauth.google_antigravity.generate_pkce", AsyncMock(return_value=("verifier", "challenge"))),
        ):
            # We need to provide on_manual_code_input that returns a URL with code+state
            async def manual_input() -> str:
                return "http://localhost/callback?code=authcode&state=verifier"

            creds = await login_antigravity(on_auth, on_manual_code_input=manual_input)
            assert creds.access == "ag_access"
            assert creds.refresh == "ag_refresh"
            assert creds.extra["project_id"] == "proj-x"
            assert creds.extra["email"] == "user@test.com"
            assert len(auth_infos) == 1

    async def test_login_antigravity_no_code(self) -> None:
        import asyncio

        from pi_ai.oauth.google_antigravity import login_antigravity

        async def mock_start_callback_server() -> tuple[MagicMock, asyncio.Future[dict[str, str] | None]]:
            loop = asyncio.get_event_loop()
            future: asyncio.Future[dict[str, str] | None] = loop.create_future()
            future.set_result(None)
            server_mock = MagicMock()
            server_mock.close = MagicMock()
            server_mock.wait_closed = AsyncMock()
            return server_mock, future

        with (
            patch("pi_ai.oauth.google_antigravity._start_callback_server", mock_start_callback_server),
            patch("pi_ai.oauth.google_antigravity.generate_pkce", AsyncMock(return_value=("verifier", "challenge"))),
            pytest.raises(RuntimeError, match="No authorization code received"),
        ):
            await login_antigravity(lambda info: None)

    async def test_login_antigravity_state_mismatch(self) -> None:
        import asyncio

        from pi_ai.oauth.google_antigravity import login_antigravity

        async def mock_start_callback_server() -> tuple[MagicMock, asyncio.Future[dict[str, str] | None]]:
            loop = asyncio.get_event_loop()
            future: asyncio.Future[dict[str, str] | None] = loop.create_future()
            future.set_result({"code": "authcode", "state": "wrong_state"})
            server_mock = MagicMock()
            server_mock.close = MagicMock()
            server_mock.wait_closed = AsyncMock()
            return server_mock, future

        with (
            patch("pi_ai.oauth.google_antigravity._start_callback_server", mock_start_callback_server),
            patch("pi_ai.oauth.google_antigravity.generate_pkce", AsyncMock(return_value=("verifier", "challenge"))),
            pytest.raises(RuntimeError, match="state mismatch"),
        ):
            await login_antigravity(lambda info: None)

    async def test_login_antigravity_token_exchange_fails(self) -> None:
        import asyncio

        from pi_ai.oauth.google_antigravity import login_antigravity

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def mock_start_callback_server() -> tuple[MagicMock, asyncio.Future[dict[str, str] | None]]:
            loop = asyncio.get_event_loop()
            future: asyncio.Future[dict[str, str] | None] = loop.create_future()
            future.set_result({"code": "authcode", "state": "verifier"})
            server_mock = MagicMock()
            server_mock.close = MagicMock()
            server_mock.wait_closed = AsyncMock()
            return server_mock, future

        with (
            patch("pi_ai.oauth.google_antigravity.httpx.AsyncClient", return_value=mock_client),
            patch("pi_ai.oauth.google_antigravity._start_callback_server", mock_start_callback_server),
            patch("pi_ai.oauth.google_antigravity.generate_pkce", AsyncMock(return_value=("verifier", "challenge"))),
            pytest.raises(RuntimeError, match="Token exchange failed"),
        ):
            await login_antigravity(lambda info: None)

    async def test_login_antigravity_no_refresh_token(self) -> None:
        import asyncio

        from pi_ai.oauth.google_antigravity import login_antigravity

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "ag_access",
            "expires_in": 3600,
        }  # no refresh_token

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def mock_start_callback_server() -> tuple[MagicMock, asyncio.Future[dict[str, str] | None]]:
            loop = asyncio.get_event_loop()
            future: asyncio.Future[dict[str, str] | None] = loop.create_future()
            future.set_result({"code": "authcode", "state": "verifier"})
            server_mock = MagicMock()
            server_mock.close = MagicMock()
            server_mock.wait_closed = AsyncMock()
            return server_mock, future

        with (
            patch("pi_ai.oauth.google_antigravity.httpx.AsyncClient", return_value=mock_client),
            patch("pi_ai.oauth.google_antigravity._start_callback_server", mock_start_callback_server),
            patch("pi_ai.oauth.google_antigravity.generate_pkce", AsyncMock(return_value=("verifier", "challenge"))),
            pytest.raises(RuntimeError, match="No refresh token"),
        ):
            await login_antigravity(lambda info: None)


# ---------------------------------------------------------------------------
# Gemini CLI login flow (mocked)
# ---------------------------------------------------------------------------


class TestGeminiCliLoginFlow:
    async def test_login_gemini_cli_success(self) -> None:
        import asyncio

        from pi_ai.oauth.google_gemini_cli import login_gemini_cli

        # Mock token exchange response
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": "gc_access",
            "refresh_token": "gc_refresh",
            "expires_in": 3600,
        }

        # Mock user info response
        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {"email": "user@gmail.com"}

        # Mock discover project response
        discover_response = MagicMock()
        discover_response.status_code = 200
        discover_response.json.return_value = {
            "currentTier": {"id": "free-tier"},
            "cloudaicompanionProject": "gc-proj",
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[token_response, discover_response])
        mock_client.get = AsyncMock(return_value=userinfo_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        auth_infos: list[object] = []

        def on_auth(info: object) -> None:
            auth_infos.append(info)

        async def mock_start_callback_server() -> tuple[MagicMock, asyncio.Future[dict[str, str] | None]]:
            loop = asyncio.get_event_loop()
            future: asyncio.Future[dict[str, str] | None] = loop.create_future()
            server_mock = MagicMock()
            server_mock.close = MagicMock()
            server_mock.wait_closed = AsyncMock()
            return server_mock, future

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            patch("pi_ai.oauth.google_gemini_cli._start_callback_server", mock_start_callback_server),
            patch("pi_ai.oauth.google_gemini_cli.generate_pkce", AsyncMock(return_value=("verifier", "challenge"))),
        ):

            async def manual_input() -> str:
                return "http://localhost/callback?code=authcode&state=verifier"

            creds = await login_gemini_cli(on_auth, on_manual_code_input=manual_input)
            assert creds.access == "gc_access"
            assert creds.refresh == "gc_refresh"
            assert creds.extra["project_id"] == "gc-proj"
            assert len(auth_infos) == 1

    async def test_login_gemini_cli_no_code(self) -> None:
        import asyncio

        from pi_ai.oauth.google_gemini_cli import login_gemini_cli

        async def mock_start_callback_server() -> tuple[MagicMock, asyncio.Future[dict[str, str] | None]]:
            loop = asyncio.get_event_loop()
            future: asyncio.Future[dict[str, str] | None] = loop.create_future()
            future.set_result(None)
            server_mock = MagicMock()
            server_mock.close = MagicMock()
            server_mock.wait_closed = AsyncMock()
            return server_mock, future

        with (
            patch("pi_ai.oauth.google_gemini_cli._start_callback_server", mock_start_callback_server),
            patch("pi_ai.oauth.google_gemini_cli.generate_pkce", AsyncMock(return_value=("verifier", "challenge"))),
            pytest.raises(RuntimeError, match="No authorization code received"),
        ):
            await login_gemini_cli(lambda info: None)

    async def test_login_gemini_cli_state_mismatch(self) -> None:
        import asyncio

        from pi_ai.oauth.google_gemini_cli import login_gemini_cli

        async def mock_start_callback_server() -> tuple[MagicMock, asyncio.Future[dict[str, str] | None]]:
            loop = asyncio.get_event_loop()
            future: asyncio.Future[dict[str, str] | None] = loop.create_future()
            future.set_result({"code": "authcode", "state": "wrong"})
            server_mock = MagicMock()
            server_mock.close = MagicMock()
            server_mock.wait_closed = AsyncMock()
            return server_mock, future

        with (
            patch("pi_ai.oauth.google_gemini_cli._start_callback_server", mock_start_callback_server),
            patch("pi_ai.oauth.google_gemini_cli.generate_pkce", AsyncMock(return_value=("verifier", "challenge"))),
            pytest.raises(RuntimeError, match="state mismatch"),
        ):
            await login_gemini_cli(lambda info: None)

    async def test_login_gemini_cli_token_exchange_fails(self) -> None:
        import asyncio

        from pi_ai.oauth.google_gemini_cli import login_gemini_cli

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def mock_start_callback_server() -> tuple[MagicMock, asyncio.Future[dict[str, str] | None]]:
            loop = asyncio.get_event_loop()
            future: asyncio.Future[dict[str, str] | None] = loop.create_future()
            future.set_result({"code": "authcode", "state": "verifier"})
            server_mock = MagicMock()
            server_mock.close = MagicMock()
            server_mock.wait_closed = AsyncMock()
            return server_mock, future

        with (
            patch("pi_ai.oauth.google_gemini_cli.httpx.AsyncClient", return_value=mock_client),
            patch("pi_ai.oauth.google_gemini_cli._start_callback_server", mock_start_callback_server),
            patch("pi_ai.oauth.google_gemini_cli.generate_pkce", AsyncMock(return_value=("verifier", "challenge"))),
            pytest.raises(RuntimeError, match="Token exchange failed"),
        ):
            await login_gemini_cli(lambda info: None)


# ---------------------------------------------------------------------------
# OpenAI Codex login flow (mocked)
# ---------------------------------------------------------------------------


class TestOpenAICodexLoginFlow:
    async def test_login_openai_codex_manual_code(self) -> None:
        import base64
        import json

        from pi_ai.oauth.openai_codex import login_openai_codex

        # Build a valid JWT with account_id
        payload = {"https://api.openai.com/auth": {"chatgpt_account_id": "acct_abc"}}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        fake_jwt = f"header.{encoded}.signature"

        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": fake_jwt,
            "refresh_token": "oai_refresh",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=token_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        auth_infos: list[object] = []

        with (
            patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client),
            patch(
                "pi_ai.oauth.openai_codex._start_local_oauth_server",
                AsyncMock(return_value=(None, AsyncMock())),
            ),
            patch(
                "pi_ai.oauth.openai_codex.generate_pkce",
                AsyncMock(return_value=("verifier", "challenge")),
            ),
        ):
            creds = await login_openai_codex(
                on_auth=lambda info: auth_infos.append(info),
                on_prompt=AsyncMock(return_value="authcode123"),
            )
            assert creds.access == fake_jwt
            assert creds.refresh == "oai_refresh"
            assert creds.extra["account_id"] == "acct_abc"

    async def test_login_openai_codex_no_code(self) -> None:
        from pi_ai.oauth.openai_codex import login_openai_codex

        with (
            patch(
                "pi_ai.oauth.openai_codex._start_local_oauth_server",
                AsyncMock(return_value=(None, AsyncMock())),
            ),
            patch(
                "pi_ai.oauth.openai_codex.generate_pkce",
                AsyncMock(return_value=("verifier", "challenge")),
            ),
            pytest.raises(RuntimeError, match="Missing authorization code"),
        ):
            await login_openai_codex(
                on_auth=lambda info: None,
                on_prompt=AsyncMock(return_value=""),
            )

    async def test_login_openai_codex_token_exchange_fails(self) -> None:
        from pi_ai.oauth.openai_codex import login_openai_codex

        mock_response = MagicMock()
        mock_response.status_code = 400

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("pi_ai.oauth.openai_codex.httpx.AsyncClient", return_value=mock_client),
            patch(
                "pi_ai.oauth.openai_codex._start_local_oauth_server",
                AsyncMock(return_value=(None, AsyncMock())),
            ),
            patch(
                "pi_ai.oauth.openai_codex.generate_pkce",
                AsyncMock(return_value=("verifier", "challenge")),
            ),
            pytest.raises(RuntimeError, match="Token exchange failed"),
        ):
            await login_openai_codex(
                on_auth=lambda info: None,
                on_prompt=AsyncMock(return_value="somecode"),
            )


# ---------------------------------------------------------------------------
# GitHub Copilot login flow (mocked)
# ---------------------------------------------------------------------------


class TestGitHubCopilotLoginFlow:
    async def test_login_github_copilot_success(self) -> None:
        import time as time_mod

        from pi_ai.oauth.github_copilot import login_github_copilot

        # Mock device flow
        device_data = {
            "device_code": "dc123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://github.com/login/device",
            "interval": 1,
            "expires_in": 900,
        }

        # device flow response
        device_response = MagicMock()
        device_response.status_code = 200
        device_response.json.return_value = device_data

        # poll returns access token
        poll_response = MagicMock()
        poll_response.status_code = 200
        poll_response.json.return_value = {"access_token": "ghu_abc123"}

        # copilot token refresh
        copilot_response = MagicMock()
        copilot_response.status_code = 200
        copilot_response.json.return_value = {
            "token": "copilot_token",
            "expires_at": time_mod.time() + 3600,
        }

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[device_response, poll_response, copilot_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        auth_calls: list[tuple[str, str | None]] = []

        with patch("pi_ai.oauth.github_copilot.httpx.AsyncClient", return_value=mock_client):
            creds = await login_github_copilot(
                on_auth=lambda url, instructions=None: auth_calls.append((url, instructions)),
                on_prompt=AsyncMock(return_value=""),  # empty = github.com
            )
            assert creds.access == "copilot_token"
            assert len(auth_calls) == 1
