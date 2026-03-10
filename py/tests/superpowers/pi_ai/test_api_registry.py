"""Tests for pi_ai.api_registry — provider registration and lookup.

Ported from python-superpowers. The rewrite uses ApiProvider dataclass
wrapping stream functions instead of a Protocol-based StreamProvider.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import pytest
from pi_ai.api_registry import (
    ApiProvider,
    clear_api_providers,
    get_api_provider,
    get_api_providers,
    register_api_provider,
    unregister_api_providers,
)

if TYPE_CHECKING:
    from pi_ai.types import AssistantMessageEvent, Context, Model, SimpleStreamOptions, StreamOptions


# ── Helpers ───────────────────────────────────────────────────────────


async def _fake_stream(
    model: Model, context: Context, options: StreamOptions | None = None
) -> AsyncIterator[AssistantMessageEvent]:
    yield  # type: ignore[misc]


async def _fake_stream_simple(
    model: Model, context: Context, options: SimpleStreamOptions | None = None
) -> AsyncIterator[AssistantMessageEvent]:
    yield  # type: ignore[misc]


def _make_provider(api: str) -> ApiProvider:
    return ApiProvider(api=api, stream=_fake_stream, stream_simple=_fake_stream_simple)


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    """Ensure every test starts with an empty registry."""
    clear_api_providers()


# ── Tests ─────────────────────────────────────────────────────────────


class TestRegisterAndRetrieve:
    def test_register_and_get(self) -> None:
        p = _make_provider("anthropic-messages")
        register_api_provider(p)
        result = get_api_provider("anthropic-messages")
        assert result is not None
        assert result.api == "anthropic-messages"

    def test_get_unknown_returns_none(self) -> None:
        assert get_api_provider("nonexistent") is None

    def test_overwrite_existing(self) -> None:
        p1 = _make_provider("api-x")
        p2 = _make_provider("api-x")
        register_api_provider(p1)
        register_api_provider(p2)
        result = get_api_provider("api-x")
        assert result is not None


class TestGetAllProviders:
    def test_empty(self) -> None:
        assert get_api_providers() == []

    def test_returns_all(self) -> None:
        register_api_provider(_make_provider("a"))
        register_api_provider(_make_provider("b"))
        all_providers = get_api_providers()
        assert len(all_providers) == 2


class TestClearProviders:
    def test_clear(self) -> None:
        register_api_provider(_make_provider("a"))
        register_api_provider(_make_provider("b"))
        clear_api_providers()
        assert get_api_providers() == []
        assert get_api_provider("a") is None


class TestUnregisterProviders:
    def test_unregister_by_source_id(self) -> None:
        register_api_provider(_make_provider("a"), source_id="plugin-1")
        register_api_provider(_make_provider("b"), source_id="plugin-1")
        register_api_provider(_make_provider("c"), source_id="plugin-2")

        unregister_api_providers("plugin-1")

        assert get_api_provider("a") is None
        assert get_api_provider("b") is None
        assert get_api_provider("c") is not None

    def test_unregister_nonexistent_source_is_noop(self) -> None:
        register_api_provider(_make_provider("a"), source_id="x")
        unregister_api_providers("nope")
        assert get_api_provider("a") is not None

    def test_providers_without_source_id_unaffected(self) -> None:
        register_api_provider(_make_provider("a"))  # no source_id
        unregister_api_providers("anything")
        assert get_api_provider("a") is not None
