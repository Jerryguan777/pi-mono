"""Provider registry and stream_simple() dispatch."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Callable, Coroutine

from pi_ai.types import AssistantMessageEvent, Context, Model, StreamOptions

# Type for a provider stream function: async generator yielding events
StreamFn = Callable[
    [Model, Context, StreamOptions | None],
    AsyncIterator[AssistantMessageEvent],
]

# Registry: api_name -> stream function
_registry: dict[str, StreamFn] = {}


def register_provider(api: str, stream_fn: StreamFn) -> None:
    """Register a provider's stream function."""
    _registry[api] = stream_fn


def get_provider(api: str) -> StreamFn | None:
    """Get a provider's stream function by API name."""
    return _registry.get(api)


async def stream_simple(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
) -> AsyncIterator[AssistantMessageEvent]:
    """Dispatch to the appropriate provider's stream function."""
    stream_fn = _registry.get(model.api)
    if not stream_fn:
        raise ValueError(f"No provider registered for API: {model.api}")
    async for event in stream_fn(model, context, options):
        yield event


def register_default_providers() -> None:
    """Register the 3 default providers."""
    from pi_ai.providers.openai_responses import stream as openai_stream
    from pi_ai.providers.anthropic_messages import stream as anthropic_stream
    from pi_ai.providers.google_genai import stream as google_stream

    register_provider("openai-responses", openai_stream)
    register_provider("anthropic-messages", anthropic_stream)
    register_provider("google-generative-ai", google_stream)
