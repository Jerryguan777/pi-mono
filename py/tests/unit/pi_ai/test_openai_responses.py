"""Tests for pi_ai.providers.openai_responses — uses mocked openai SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_ai.providers.openai_responses import (
    OpenAIResponsesOptions,
    _apply_service_tier_pricing,
    _get_prompt_cache_retention,
    _get_service_tier_multiplier,
    _resolve_cache_retention,
    stream_openai_responses,
    stream_simple_openai_responses,
)
from pi_ai.types import (
    Context,
    UsageCost,
    ErrorEvent,
    Model,
    ModelCost,
    Tool,
    Usage,
    UserMessage,
)


def _make_model(model_id: str = "gpt-4o", reasoning: bool = False) -> Model:
    return Model(
        id=model_id,
        name=model_id,
        api="openai-responses",
        provider="openai",
        base_url="https://api.openai.com/v1",
        max_tokens=4096,
        reasoning=reasoning,
        cost=ModelCost(input=5.0, output=15.0),
        input=["text"],
    )


def _make_context(text: str = "Hello") -> Context:
    return Context(messages=[UserMessage(content=text)])


def _make_event(type_: str, **kwargs: Any) -> Any:
    obj: dict[str, Any] = {"type": type_}
    obj.update(kwargs)
    return obj


async def _fake_stream(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


class _FakeStream:
    def __init__(self, events: list[Any]) -> None:
        self._events = events

    def __aiter__(self) -> AsyncIterator[Any]:
        return _fake_stream(self._events)


def _build_text_events(text: str = "Hello!") -> list[Any]:
    return [
        _make_event(
            "response.output_item.added",
            item={"type": "message", "id": "msg1", "content": []},
        ),
        _make_event("response.content_part.added", part={"type": "output_text", "text": ""}),
        _make_event("response.output_text.delta", delta=text),
        _make_event(
            "response.output_item.done",
            item={"type": "message", "id": "msg1", "content": [{"type": "output_text", "text": text}]},
        ),
        _make_event(
            "response.completed",
            response={
                "status": "completed",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                    "input_tokens_details": {"cached_tokens": 0},
                },
                "service_tier": None,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_stream_responses_basic() -> None:
    model = _make_model()
    context = _make_context("Hello")

    events = _build_text_events("Hi there!")

    mock_client = MagicMock()
    mock_client.responses.create = AsyncMock(return_value=_FakeStream(events))

    with (
        patch("pi_ai.providers.openai_responses.get_env_api_key", return_value="sk-test"),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        collected = []
        async for event in stream_openai_responses(model, context):
            collected.append(event)

    types = [e.type for e in collected]
    assert "start" in types
    assert "text_start" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_stream_responses_error() -> None:
    model = _make_model()
    context = _make_context()

    mock_client = MagicMock()
    mock_client.responses.create = AsyncMock(side_effect=RuntimeError("API error"))

    with (
        patch("pi_ai.providers.openai_responses.get_env_api_key", return_value="sk-test"),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        collected = []
        async for event in stream_openai_responses(model, context):
            collected.append(event)

    error_events = [e for e in collected if e.type == "error"]
    assert len(error_events) == 1
    assert isinstance(error_events[0], ErrorEvent)


@pytest.mark.asyncio
async def test_stream_simple_responses_missing_key_raises() -> None:
    model = _make_model()
    context = _make_context()

    with (
        patch("pi_ai.providers.openai_responses.get_env_api_key", return_value=None),
        pytest.raises(ValueError, match="No API key"),
    ):
        async for _ in stream_simple_openai_responses(model, context):
            pass


@pytest.mark.asyncio
async def test_stream_responses_on_payload_called() -> None:
    model = _make_model()
    context = _make_context()

    payloads = []
    events = _build_text_events("hello")

    mock_client = MagicMock()
    mock_client.responses.create = AsyncMock(return_value=_FakeStream(events))

    options = OpenAIResponsesOptions(
        api_key="sk-test",
        on_payload=lambda p: payloads.append(p),
    )

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        async for _ in stream_openai_responses(model, context, options):
            pass

    assert len(payloads) == 1
    assert "model" in payloads[0]


def test_resolve_cache_retention_explicit() -> None:
    assert _resolve_cache_retention("long") == "long"
    assert _resolve_cache_retention("short") == "short"
    assert _resolve_cache_retention(None) == "short"


def test_resolve_cache_retention_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("PI_CACHE_RETENTION", "long")
    assert _resolve_cache_retention(None) == "long"


def test_get_prompt_cache_retention() -> None:
    assert _get_prompt_cache_retention("https://api.openai.com/v1", "long") == "24h"
    assert _get_prompt_cache_retention("https://other.api.com", "long") is None
    assert _get_prompt_cache_retention("https://api.openai.com/v1", "short") is None


def test_get_service_tier_multiplier() -> None:
    assert _get_service_tier_multiplier("flex") == 0.5
    assert _get_service_tier_multiplier("priority") == 2.0
    assert _get_service_tier_multiplier(None) == 1.0
    assert _get_service_tier_multiplier("standard") == 1.0


def test_apply_service_tier_pricing_no_change() -> None:
    usage = Usage(cost=UsageCost(input=1.0, output=2.0, total=3.0))
    _apply_service_tier_pricing(usage, None)
    assert usage.cost.input == 1.0
    assert usage.cost.output == 2.0


def test_apply_service_tier_pricing_flex() -> None:
    usage = Usage(cost=UsageCost(input=1.0, output=2.0, total=3.0))
    _apply_service_tier_pricing(usage, "flex")
    assert usage.cost.input == 0.5
    assert usage.cost.output == 1.0
    assert usage.cost.total == 1.5


def test_apply_service_tier_pricing_priority() -> None:
    usage = Usage(cost=UsageCost(input=1.0, output=2.0, total=3.0))
    _apply_service_tier_pricing(usage, "priority")
    assert usage.cost.input == 2.0
    assert usage.cost.output == 4.0


@pytest.mark.asyncio
async def test_stream_responses_with_tools() -> None:
    model = _make_model()
    context = _make_context("Hello")
    context.tools = [Tool(name="bash", description="Run bash", parameters={"type": "object"})]

    events = _build_text_events("Hi!")

    mock_client = MagicMock()
    mock_client.responses.create = AsyncMock(return_value=_FakeStream(events))

    with (
        patch("pi_ai.providers.openai_responses.get_env_api_key", return_value="sk-test"),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        collected = []
        async for event in stream_openai_responses(model, context):
            collected.append(event)

    assert any(e.type == "done" for e in collected)


@pytest.mark.asyncio
async def test_stream_responses_reasoning_model() -> None:
    model = _make_model(model_id="o3", reasoning=True)
    context = _make_context("Think hard")

    events = _build_text_events("Answer!")

    mock_client = MagicMock()
    mock_client.responses.create = AsyncMock(return_value=_FakeStream(events))

    options = OpenAIResponsesOptions(
        api_key="sk-test",
        reasoning_effort="high",
        reasoning_summary="auto",
    )

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        collected = []
        async for event in stream_openai_responses(model, context, options):
            collected.append(event)

    assert any(e.type == "done" for e in collected)
    call_kwargs = mock_client.responses.create.call_args[1]
    assert "reasoning" in call_kwargs


@pytest.mark.asyncio
async def test_stream_simple_responses_basic() -> None:
    model = _make_model()
    context = _make_context("Hello")

    events = _build_text_events("Hi!")

    mock_client = MagicMock()
    mock_client.responses.create = AsyncMock(return_value=_FakeStream(events))

    with (
        patch("pi_ai.providers.openai_responses.get_env_api_key", return_value="sk-test"),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        collected = []
        async for event in stream_simple_openai_responses(model, context):
            collected.append(event)

    assert any(e.type == "done" for e in collected)
