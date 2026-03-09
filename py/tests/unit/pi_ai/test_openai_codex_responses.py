"""Tests for pi_ai.providers.openai_codex_responses — uses mocked httpx."""

from __future__ import annotations

# A valid minimal JWT with {"https://api.openai.com/auth": {"chatgpt_account_id": "acc123"}}
import base64
import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_ai.providers.openai_codex_responses import (
    OpenAICodexResponsesOptions,
    _clamp_reasoning_effort,
    _extract_account_id,
    _is_retryable_error,
    _resolve_codex_url,
    stream_openai_codex_responses,
    stream_simple_openai_codex_responses,
)
from pi_ai.types import (
    Context,
    ErrorEvent,
    Model,
    ModelCost,
    UserMessage,
)

_FAKE_PAYLOAD = {"https://api.openai.com/auth": {"chatgpt_account_id": "acc123"}}
_ENCODED = base64.urlsafe_b64encode(json.dumps(_FAKE_PAYLOAD).encode()).decode().rstrip("=")
_FAKE_JWT = f"header.{_ENCODED}.sig"


def _make_model(model_id: str = "gpt-5.1") -> Model:
    return Model(
        id=model_id,
        name=model_id,
        api="openai-codex-responses",
        provider="openai-codex",
        base_url="https://chatgpt.com/backend-api",
        max_tokens=32000,
        cost=ModelCost(),
        input=["text"],
    )


def _make_context(text: str = "Hello") -> Context:
    return Context(messages=[UserMessage(content=text)])


def test_is_retryable_error() -> None:
    assert _is_retryable_error(429, "") is True
    assert _is_retryable_error(500, "") is True
    assert _is_retryable_error(503, "") is True
    assert _is_retryable_error(200, "") is False
    assert _is_retryable_error(400, "rate limit exceeded") is True
    assert _is_retryable_error(400, "normal error") is False


def test_resolve_codex_url() -> None:
    assert _resolve_codex_url(None) == "https://chatgpt.com/backend-api/codex/responses"
    assert _resolve_codex_url("https://chatgpt.com/backend-api") == "https://chatgpt.com/backend-api/codex/responses"
    assert (
        _resolve_codex_url("https://chatgpt.com/backend-api/codex") == "https://chatgpt.com/backend-api/codex/responses"
    )
    assert (
        _resolve_codex_url("https://chatgpt.com/backend-api/codex/responses")
        == "https://chatgpt.com/backend-api/codex/responses"
    )


def test_extract_account_id() -> None:
    account_id = _extract_account_id(_FAKE_JWT)
    assert account_id == "acc123"


def test_extract_account_id_invalid() -> None:
    with pytest.raises(ValueError):
        _extract_account_id("not.a.jwt")


def test_clamp_reasoning_effort_gpt51() -> None:
    assert _clamp_reasoning_effort("gpt-5.1", "xhigh") == "high"
    assert _clamp_reasoning_effort("gpt-5.1", "high") == "high"
    assert _clamp_reasoning_effort("gpt-5.1", "medium") == "medium"


def test_clamp_reasoning_effort_codex_mini() -> None:
    assert _clamp_reasoning_effort("gpt-5.1-codex-mini", "xhigh") == "high"
    assert _clamp_reasoning_effort("gpt-5.1-codex-mini", "medium") == "medium"
    assert _clamp_reasoning_effort("gpt-5.1-codex-mini", "low") == "medium"


def test_clamp_reasoning_effort_gpt52() -> None:
    assert _clamp_reasoning_effort("gpt-5.2", "minimal") == "low"
    assert _clamp_reasoning_effort("gpt-5.2", "low") == "low"


def test_clamp_reasoning_effort_default() -> None:
    assert _clamp_reasoning_effort("gpt-4o", "high") == "high"


@pytest.mark.asyncio
async def test_stream_codex_missing_api_key() -> None:
    model = _make_model()
    context = _make_context()
    collected = []
    async for event in stream_openai_codex_responses(model, context):
        collected.append(event)
    error_events = [e for e in collected if e.type == "error"]
    assert len(error_events) == 1
    assert isinstance(error_events[0], ErrorEvent)


@pytest.mark.asyncio
async def test_stream_codex_basic_text() -> None:
    """Test the codex stream with mocked HTTP response."""
    model = _make_model()
    context = _make_context("Hello")

    sse_events = [
        json.dumps({"type": "response.output_item.added", "item": {"type": "message", "id": "msg1", "content": []}}),
        json.dumps({"type": "response.content_part.added", "part": {"type": "output_text", "text": ""}}),
        json.dumps({"type": "response.output_text.delta", "delta": "Hello!"}),
        json.dumps(
            {
                "type": "response.output_item.done",
                "item": {"type": "message", "id": "msg1", "content": [{"type": "output_text", "text": "Hello!"}]},
            }
        ),
        json.dumps(
            {
                "type": "response.completed",
                "response": {
                    "status": "completed",
                    "usage": {"input_tokens": 5, "output_tokens": 2, "input_tokens_details": {}},
                },
            }
        ),
        "[DONE]",
    ]

    sse_text = "\n".join(f"data: {e}" for e in sse_events) + "\n\n"

    async def _fake_aiter_text() -> AsyncIterator[str]:
        yield sse_text

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_text = _fake_aiter_text
    mock_response.aread = AsyncMock(return_value=b"")

    mock_response_cm = MagicMock()
    mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response_cm.__aexit__ = AsyncMock(return_value=None)

    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=MagicMock(stream=MagicMock(return_value=mock_response_cm)))
    mock_client_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client_cm):
        options = OpenAICodexResponsesOptions(api_key=_FAKE_JWT)
        collected = []
        async for event in stream_openai_codex_responses(model, context, options):
            collected.append(event)

    types = [e.type for e in collected]
    assert "start" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_stream_simple_codex_missing_key_raises() -> None:
    model = _make_model()
    context = _make_context()

    with (
        patch("pi_ai.providers.openai_codex_responses.get_env_api_key", return_value=None),
        pytest.raises(ValueError, match="No API key"),
    ):
        async for _ in stream_simple_openai_codex_responses(model, context):
            pass
