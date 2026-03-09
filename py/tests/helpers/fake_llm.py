"""Fake LLM provider for integration tests.

A deterministic LLM that returns a scripted sequence of AssistantMessage responses.
Implements the real ApiProvider interface so it can be registered in the API registry
and used by the agent loop without mocking.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

from pi_ai.api_registry import (
    ApiProvider,
    StreamFunction,
    StreamSimpleFunction,
    register_api_provider,
)
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    DoneEvent,
    Model,
    ModelCost,
    SimpleStreamOptions,
    StartEvent,
    StreamOptions,
    TextContent,
    ToolCall,
)

FAKE_API = "fake-llm"
FAKE_PROVIDER = "fake-provider"
FAKE_MODEL_ID = "fake-model"


def make_fake_model() -> Model:
    """Create a Model configured to use the fake LLM provider."""
    return Model(
        id=FAKE_MODEL_ID,
        name="Fake LLM",
        api=FAKE_API,
        provider=FAKE_PROVIDER,
        base_url="",
        cost=ModelCost(),
    )


class FakeLLM:
    """A scripted LLM that returns pre-configured responses in order.

    Each call to stream/stream_simple pops the next response from the queue.
    Raises RuntimeError if called with no responses remaining.
    """

    def __init__(self, responses: list[AssistantMessage]) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self._received_contexts: list[Context] = []

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def received_contexts(self) -> list[Context]:
        return self._received_contexts

    def _next_response(self, context: Context) -> AssistantMessage:
        self._received_contexts.append(context)
        self._call_count += 1
        if not self._responses:
            raise RuntimeError("FakeLLM has no more scripted responses")
        return self._responses.pop(0)

    async def _stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions | None = None,
    ) -> AsyncIterator[AssistantMessageEvent]:
        msg = self._next_response(context)
        yield StartEvent(partial=msg)
        yield DoneEvent(reason=msg.stop_reason, message=msg)

    async def _stream_simple(
        self,
        model: Model,
        context: Context,
        options: SimpleStreamOptions | None = None,
    ) -> AsyncIterator[AssistantMessageEvent]:
        msg = self._next_response(context)
        yield StartEvent(partial=msg)
        yield DoneEvent(reason=msg.stop_reason, message=msg)

    def as_provider(self) -> ApiProvider:
        """Return an ApiProvider that can be registered in the API registry."""
        return ApiProvider(
            api=FAKE_API,
            stream=cast(StreamFunction, self._stream),
            stream_simple=cast(StreamSimpleFunction, self._stream_simple),
        )

    def register(self) -> None:
        """Register this fake LLM as an API provider."""
        register_api_provider(self.as_provider())


def make_text_response(text: str) -> AssistantMessage:
    """Create an AssistantMessage with a single text content block."""
    return AssistantMessage(
        content=[TextContent(text=text)],
        api=FAKE_API,
        provider=FAKE_PROVIDER,
        model=FAKE_MODEL_ID,
        stop_reason="stop",
    )


def make_tool_call_response(
    tool_name: str,
    arguments: dict[str, Any],
    tool_call_id: str = "tc_001",
) -> AssistantMessage:
    """Create an AssistantMessage with a single tool call."""
    return AssistantMessage(
        content=[
            ToolCall(
                id=tool_call_id,
                name=tool_name,
                arguments=arguments,
            )
        ],
        api=FAKE_API,
        provider=FAKE_PROVIDER,
        model=FAKE_MODEL_ID,
        stop_reason="toolUse",
    )
