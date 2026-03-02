"""Tests for LLM providers — requires API keys."""

import os
import pytest

from pi_ai.api_registry import register_default_providers, stream_simple
from pi_ai.models import get_model
from pi_ai.types import (
    Context,
    StreamOptions,
    TextContent,
    Tool,
    UserMessage,
)


@pytest.fixture(autouse=True)
def setup_providers():
    register_default_providers()


# --- OpenAI ---

@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
@pytest.mark.asyncio
async def test_openai_text_stream():
    model = get_model("openai", "gpt-4o-mini")
    context = Context(
        messages=[UserMessage(content="Say 'hello' and nothing else.")],
    )

    events = []
    async for event in stream_simple(model, context):
        events.append(event)

    types = [e.type for e in events]
    assert "start" in types
    assert "done" in types
    assert "text_delta" in types

    done = next(e for e in events if e.type == "done")
    assert "hello" in done.message.content[0].text.lower()


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
@pytest.mark.asyncio
async def test_openai_tool_call():
    model = get_model("openai", "gpt-4o-mini")
    context = Context(
        messages=[UserMessage(content="What's the weather in Tokyo?")],
        tools=[Tool(
            name="get_weather",
            description="Get weather for a city",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        )],
    )

    events = []
    async for event in stream_simple(model, context):
        events.append(event)

    types = [e.type for e in events]
    assert "toolcall_start" in types
    assert "toolcall_end" in types

    done = next(e for e in events if e.type == "done")
    tool_calls = [c for c in done.message.content if c.type == "toolCall"]
    assert len(tool_calls) >= 1
    assert tool_calls[0].name == "get_weather"
    assert "tokyo" in tool_calls[0].arguments.get("city", "").lower()


# --- Anthropic ---

@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
@pytest.mark.asyncio
async def test_anthropic_text_stream():
    model = get_model("anthropic", "claude-3-5-haiku-20241022")
    context = Context(
        messages=[UserMessage(content="Say 'hello' and nothing else.")],
    )

    events = []
    async for event in stream_simple(model, context):
        events.append(event)

    types = [e.type for e in events]
    assert "start" in types
    assert "done" in types

    done = next(e for e in events if e.type == "done")
    text_blocks = [c for c in done.message.content if c.type == "text"]
    assert any("hello" in b.text.lower() for b in text_blocks)


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
@pytest.mark.asyncio
async def test_anthropic_tool_call():
    model = get_model("anthropic", "claude-3-5-haiku-20241022")
    context = Context(
        messages=[UserMessage(content="What's the weather in Tokyo?")],
        tools=[Tool(
            name="get_weather",
            description="Get weather for a city",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        )],
    )

    events = []
    async for event in stream_simple(model, context):
        events.append(event)

    types = [e.type for e in events]
    assert "toolcall_end" in types

    done = next(e for e in events if e.type == "done")
    tool_calls = [c for c in done.message.content if c.type == "toolCall"]
    assert len(tool_calls) >= 1


# --- Google ---

@pytest.mark.skipif(
    not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")),
    reason="GOOGLE_API_KEY/GEMINI_API_KEY not set"
)
@pytest.mark.asyncio
async def test_google_text_stream():
    model = get_model("google", "gemini-2.0-flash")
    context = Context(
        messages=[UserMessage(content="Say 'hello' and nothing else.")],
    )

    events = []
    async for event in stream_simple(model, context):
        events.append(event)

    types = [e.type for e in events]
    assert "start" in types
    assert "done" in types

    done = next(e for e in events if e.type == "done")
    text_blocks = [c for c in done.message.content if c.type == "text"]
    assert any("hello" in b.text.lower() for b in text_blocks)
