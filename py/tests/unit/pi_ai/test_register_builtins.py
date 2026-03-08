"""Tests for pi_ai.providers.register_builtins."""

from __future__ import annotations

from pi_ai.providers.register_builtins import (
    BUILT_IN_APIS,
    register_built_in_api_providers,
    reset_api_providers,
)


class TestRegisterBuiltins:
    def test_built_in_apis_list(self) -> None:
        assert len(BUILT_IN_APIS) == 9
        assert "anthropic-messages" in BUILT_IN_APIS
        assert "openai-completions" in BUILT_IN_APIS
        assert "bedrock-converse-stream" in BUILT_IN_APIS

    def test_register_does_not_raise(self) -> None:
        register_built_in_api_providers()

    def test_reset_does_not_raise(self) -> None:
        reset_api_providers()
