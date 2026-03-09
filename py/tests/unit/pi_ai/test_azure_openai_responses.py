"""Tests for pi_ai.providers.azure_openai_responses — uses mocked openai SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_ai.providers.azure_openai_responses import (
    AzureOpenAIResponsesOptions,
    _build_default_base_url,
    _normalize_azure_base_url,
    _parse_deployment_name_map,
    _resolve_azure_config,
    _resolve_deployment_name,
    stream_azure_openai_responses,
    stream_simple_azure_openai_responses,
)
from pi_ai.types import (
    Context,
    ErrorEvent,
    Model,
    ModelCost,
    UserMessage,
)


def _make_model(model_id: str = "gpt-4o") -> Model:
    return Model(
        id=model_id,
        name=model_id,
        api="openai-responses",
        provider="azure-openai",
        base_url="https://myresource.openai.azure.com",
        max_tokens=4096,
        cost=ModelCost(input=5.0, output=15.0),
        input=["text"],
    )


def _make_context(text: str = "Hello") -> Context:
    return Context(messages=[UserMessage(content=text)])


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
        {
            "type": "response.output_item.added",
            "item": {"type": "message", "id": "msg1", "content": []},
        },
        {"type": "response.content_part.added", "part": {"type": "output_text", "text": ""}},
        {"type": "response.output_text.delta", "delta": text},
        {
            "type": "response.output_item.done",
            "item": {"type": "message", "id": "msg1", "content": [{"type": "output_text", "text": text}]},
        },
        {
            "type": "response.completed",
            "response": {
                "status": "completed",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "input_tokens_details": {"cached_tokens": 0},
                },
            },
        },
    ]


@pytest.mark.asyncio
async def test_stream_azure_basic() -> None:
    model = _make_model()
    context = _make_context("Hello")

    events = _build_text_events("Hi Azure!")

    mock_client = MagicMock()
    mock_client.responses.create = AsyncMock(return_value=_FakeStream(events))

    options = AzureOpenAIResponsesOptions(
        api_key="azure-key",
        azure_resource_name="myresource",
        azure_deployment_name="gpt-4o",
        azure_api_version="2025-01-01",
    )

    with patch("openai.AsyncAzureOpenAI", return_value=mock_client):
        collected = []
        async for event in stream_azure_openai_responses(model, context, options):
            collected.append(event)

    types = [e.type for e in collected]
    assert "start" in types
    assert "text_start" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_stream_azure_error() -> None:
    model = _make_model()
    context = _make_context()

    options = AzureOpenAIResponsesOptions(
        api_key="azure-key",
        azure_resource_name="myresource",
        azure_deployment_name="gpt-4o",
        azure_api_version="2025-01-01",
    )

    mock_client = MagicMock()
    mock_client.responses.create = AsyncMock(side_effect=RuntimeError("Azure error"))

    with patch("openai.AsyncAzureOpenAI", return_value=mock_client):
        collected = []
        async for event in stream_azure_openai_responses(model, context, options):
            collected.append(event)

    error_events = [e for e in collected if e.type == "error"]
    assert len(error_events) == 1
    assert isinstance(error_events[0], ErrorEvent)


@pytest.mark.asyncio
async def test_stream_simple_azure_missing_key_raises() -> None:
    model = _make_model()
    context = _make_context()

    with (
        patch("pi_ai.providers.azure_openai_responses.get_env_api_key", return_value=None),
        pytest.raises(ValueError, match="No API key"),
    ):
        async for _ in stream_simple_azure_openai_responses(model, context):
            pass


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


def test_parse_deployment_name_map_empty() -> None:
    assert _parse_deployment_name_map(None) == {}
    assert _parse_deployment_name_map("") == {}


def test_parse_deployment_name_map_valid() -> None:
    result = _parse_deployment_name_map("gpt-4o=my-gpt4o, gpt-4=my-gpt4")
    assert result == {"gpt-4o": "my-gpt4o", "gpt-4": "my-gpt4"}


def test_parse_deployment_name_map_invalid_entry() -> None:
    result = _parse_deployment_name_map("gpt-4o=my-gpt4o,invalid_entry")
    assert "gpt-4o" in result
    assert len(result) == 1


def test_resolve_deployment_name_from_options() -> None:
    model = _make_model()
    options = AzureOpenAIResponsesOptions(
        azure_deployment_name="custom-deployment",
        api_key="test-key",
    )
    assert _resolve_deployment_name(model, options) == "custom-deployment"


def test_resolve_deployment_name_fallback_to_model_id() -> None:
    model = _make_model()
    assert _resolve_deployment_name(model, None) == model.id


def test_normalize_azure_base_url() -> None:
    assert _normalize_azure_base_url("https://example.com/") == "https://example.com"
    assert _normalize_azure_base_url("https://example.com") == "https://example.com"


def test_build_default_base_url() -> None:
    url = _build_default_base_url("myresource")
    assert url == "https://myresource.openai.azure.com/openai/v1"


def test_resolve_azure_config_from_options() -> None:
    model = _make_model()
    options = AzureOpenAIResponsesOptions(
        api_key="key",
        azure_base_url="https://myresource.openai.azure.com",
        azure_api_version="2025-01-01",
    )
    base_url, resolved_api_version = _resolve_azure_config(model, options)
    assert base_url == "https://myresource.openai.azure.com"
    assert resolved_api_version == "2025-01-01"


def test_resolve_azure_config_from_resource_name() -> None:
    model = _make_model()
    options = AzureOpenAIResponsesOptions(
        api_key="key",
        azure_resource_name="myresource",
        azure_api_version="2025-01-01",
    )
    base_url, _ = _resolve_azure_config(model, options)
    assert "myresource" in base_url


def test_resolve_azure_config_from_model_base_url() -> None:
    model = _make_model()
    base_url, _ = _resolve_azure_config(model, None)
    assert "myresource" in base_url


def test_resolve_azure_config_no_url_raises() -> None:
    model = Model(
        id="gpt-4o",
        name="gpt-4o",
        api="openai-responses",
        provider="azure-openai",
        base_url="",
        input=["text"],
    )
    with pytest.raises(ValueError, match="Azure OpenAI base URL"):
        _resolve_azure_config(model, None)


@pytest.mark.asyncio
async def test_stream_simple_azure_basic() -> None:
    model = _make_model()
    context = _make_context("Hello")

    events = _build_text_events("Hi Azure!")

    mock_client = MagicMock()
    mock_client.responses.create = AsyncMock(return_value=_FakeStream(events))

    options = AzureOpenAIResponsesOptions(
        api_key="azure-key",
        azure_resource_name="myresource",
        azure_deployment_name="gpt-4o",
        azure_api_version="2025-01-01",
    )

    with patch("openai.AsyncAzureOpenAI", return_value=mock_client):
        collected = []
        async for event in stream_azure_openai_responses(model, context, options):
            collected.append(event)

    assert any(e.type == "done" for e in collected)
