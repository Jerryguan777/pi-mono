"""Tests for pi_ai.providers.register_builtins."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from pi_ai.api_registry import clear_api_providers, get_api_provider, get_api_providers
from pi_ai.providers.register_builtins import (
    BUILT_IN_APIS,
    register_built_in_api_providers,
    reset_api_providers,
)


@pytest.fixture(autouse=True)
def clean_registry() -> Generator[None, None, None]:
    """Isolate each test: clear providers before and after."""
    clear_api_providers()
    yield
    clear_api_providers()


class TestBuiltInApisList:
    def test_length(self) -> None:
        assert len(BUILT_IN_APIS) == 9

    def test_contains_all_expected_apis(self) -> None:
        expected = {
            "anthropic-messages",
            "openai-completions",
            "openai-responses",
            "azure-openai-responses",
            "openai-codex-responses",
            "google-generative-ai",
            "google-gemini-cli",
            "google-vertex",
            "bedrock-converse-stream",
        }
        assert set(BUILT_IN_APIS) == expected


class TestRegisterBuiltInApiProviders:
    def test_registers_all_nine_providers(self) -> None:
        register_built_in_api_providers()
        providers = get_api_providers()
        assert len(providers) == 9

    def test_registered_apis_match_built_in_list(self) -> None:
        register_built_in_api_providers()
        registered_apis = {p.api for p in get_api_providers()}
        assert registered_apis == set(BUILT_IN_APIS)

    def test_each_provider_has_stream_and_stream_simple(self) -> None:
        register_built_in_api_providers()
        for api in BUILT_IN_APIS:
            provider = get_api_provider(api)
            assert provider is not None, f"Provider not registered: {api}"
            assert callable(provider.stream), f"stream not callable for {api}"
            assert callable(provider.stream_simple), f"stream_simple not callable for {api}"

    def test_idempotent_double_call(self) -> None:
        """Calling register twice should not duplicate providers."""
        register_built_in_api_providers()
        register_built_in_api_providers()
        assert len(get_api_providers()) == 9


class TestResetApiProviders:
    def test_reset_re_registers_all_providers(self) -> None:
        reset_api_providers()
        assert len(get_api_providers()) == 9

    def test_reset_clears_then_re_registers(self) -> None:
        """reset should overwrite any previously registered providers."""
        from collections.abc import AsyncGenerator
        from typing import cast

        from pi_ai.api_registry import ApiProvider, StreamFunction, register_api_provider
        from pi_ai.types import AssistantMessageEvent, Context, Model, StreamOptions

        async def _stub(
            model: Model, context: Context, options: StreamOptions | None = None
        ) -> AsyncGenerator[AssistantMessageEvent, None]:
            return
            yield  # make it a generator

        # Register a custom provider that would be overwritten by reset
        register_api_provider(
            ApiProvider(
                api="custom-api",
                stream=cast(StreamFunction, _stub),
                stream_simple=cast(StreamFunction, _stub),
            )
        )
        assert get_api_provider("custom-api") is not None

        reset_api_providers()

        # custom-api should be gone, only built-ins remain
        assert get_api_provider("custom-api") is None
        assert len(get_api_providers()) == 9
