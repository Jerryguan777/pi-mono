"""Built-in provider registration — Python port of providers/register-builtins.ts.

In the Python port, actual provider implementations (anthropic, openai, etc.)
are not yet ported. This module provides the registration framework and
placeholder functions that will be replaced as providers are implemented.

Unlike the TS version, we do NOT auto-register on module import.
Call register_built_in_api_providers() explicitly when needed.
"""

from __future__ import annotations

from pi_ai.api_registry import clear_api_providers

# Built-in API names that will be registered when providers are implemented
BUILT_IN_APIS: list[str] = [
    "anthropic-messages",
    "openai-completions",
    "openai-responses",
    "azure-openai-responses",
    "openai-codex-responses",
    "google-generative-ai",
    "google-gemini-cli",
    "google-vertex",
    "bedrock-converse-stream",
]


def register_built_in_api_providers() -> None:
    """Register all built-in API providers.

    Note: Actual provider implementations are not yet ported.
    This function will be populated as providers are implemented in later phases.
    """
    # Provider implementations will be registered here as they are ported.
    # Example (when anthropic provider is ready):
    #   register_api_provider(ApiProvider(
    #       api="anthropic-messages",
    #       stream=stream_anthropic,
    #       stream_simple=stream_simple_anthropic,
    #   ))
    pass


def reset_api_providers() -> None:
    """Clear and re-register all built-in providers."""
    clear_api_providers()
    register_built_in_api_providers()
