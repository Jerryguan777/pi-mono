"""Tests for pi_ai.api_registry."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from pi_ai.api_registry import (
    ApiProvider,
    clear_api_providers,
    get_api_provider,
    get_api_providers,
    register_api_provider,
    unregister_api_providers,
)
from pi_ai.types import (
    AssistantMessageEvent,
    Context,
    DoneEvent,
    Model,
    SimpleStreamOptions,
    StreamOptions,
)


def _make_model(api: str = "test-api") -> Model:
    return Model(id="test-model", name="Test", api=api, provider="test-provider")


async def _dummy_stream(
    model: Model, context: Context, options: StreamOptions | None = None
) -> AsyncIterator[AssistantMessageEvent]:
    yield DoneEvent()


async def _dummy_stream_simple(
    model: Model, context: Context, options: SimpleStreamOptions | None = None
) -> AsyncIterator[AssistantMessageEvent]:
    yield DoneEvent()


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    clear_api_providers()


class TestApiRegistry:
    def test_register_and_get(self) -> None:
        provider = ApiProvider(api="test-api", stream=_dummy_stream, stream_simple=_dummy_stream_simple)
        register_api_provider(provider)
        result = get_api_provider("test-api")
        assert result is not None
        assert result.api == "test-api"

    def test_get_nonexistent(self) -> None:
        assert get_api_provider("nonexistent") is None

    def test_get_all_providers(self) -> None:
        p1 = ApiProvider(api="api-1", stream=_dummy_stream, stream_simple=_dummy_stream_simple)
        p2 = ApiProvider(api="api-2", stream=_dummy_stream, stream_simple=_dummy_stream_simple)
        register_api_provider(p1)
        register_api_provider(p2)
        all_providers = get_api_providers()
        assert len(all_providers) == 2

    def test_unregister_by_source_id(self) -> None:
        p1 = ApiProvider(api="api-1", stream=_dummy_stream, stream_simple=_dummy_stream_simple)
        p2 = ApiProvider(api="api-2", stream=_dummy_stream, stream_simple=_dummy_stream_simple)
        register_api_provider(p1, source_id="src1")
        register_api_provider(p2, source_id="src2")
        unregister_api_providers("src1")
        assert get_api_provider("api-1") is None
        assert get_api_provider("api-2") is not None

    def test_clear(self) -> None:
        p = ApiProvider(api="test", stream=_dummy_stream, stream_simple=_dummy_stream_simple)
        register_api_provider(p)
        clear_api_providers()
        assert get_api_providers() == []

    def test_api_mismatch_raises(self) -> None:
        provider = ApiProvider(api="test-api", stream=_dummy_stream, stream_simple=_dummy_stream_simple)
        register_api_provider(provider)
        registered = get_api_provider("test-api")
        assert registered is not None

        wrong_model = _make_model("wrong-api")
        with pytest.raises(ValueError, match="Mismatched api"):
            registered.stream(wrong_model, Context(), None)
