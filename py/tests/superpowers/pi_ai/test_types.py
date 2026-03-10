"""Tests for pi_ai.types — core dataclass models for the unified LLM API.

Ported from python-superpowers: tests behavioral contracts of the type system.
Unlike the original (Pydantic), the rewrite uses plain dataclasses, so
ValidationError tests are replaced with behavioural checks.
"""

import time

from pi_ai.types import (
    AssistantMessage,
    Context,
    ImageContent,
    Model,
    ModelCost,
    StreamOptions,
    TextContent,
    ThinkingContent,
    ThinkingLevel,
    Tool,
    ToolCall,
    ToolResultMessage,
    Usage,
    UsageCost,
    UserMessage,
    serialize_message,
    deserialize_message,
    serialize_content_block,
    deserialize_content_block,
)

# ── Content types ──────────────────────────────────────────────────────


class TestTextContent:
    def test_basic(self) -> None:
        t = TextContent(text="hello")
        assert t.type == "text"
        assert t.text == "hello"
        assert t.text_signature is None

    def test_with_signature(self) -> None:
        t = TextContent(text="hi", text_signature="sig123")
        assert t.text_signature == "sig123"

    def test_default_type(self) -> None:
        t = TextContent()
        assert t.type == "text"
        assert t.text == ""


class TestThinkingContent:
    def test_basic(self) -> None:
        t = ThinkingContent(thinking="let me think...")
        assert t.type == "thinking"
        assert t.thinking == "let me think..."
        assert t.thinking_signature is None

    def test_with_signature(self) -> None:
        t = ThinkingContent(thinking="hmm", thinking_signature="sig456")
        assert t.thinking_signature == "sig456"


class TestImageContent:
    def test_basic(self) -> None:
        img = ImageContent(data="base64data==", mime_type="image/png")
        assert img.type == "image"
        assert img.data == "base64data=="
        assert img.mime_type == "image/png"


class TestToolCall:
    def test_basic(self) -> None:
        tc = ToolCall(id="call_1", name="read_file", arguments={"path": "/tmp/x"})
        assert tc.type == "toolCall"
        assert tc.id == "call_1"
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "/tmp/x"}

    def test_empty_arguments(self) -> None:
        tc = ToolCall(id="call_2", name="ls", arguments={})
        assert tc.arguments == {}

    def test_default_arguments(self) -> None:
        tc = ToolCall(id="call_3", name="ls")
        assert tc.arguments == {}


# ── Supporting types ───────────────────────────────────────────────────


class TestUsageCost:
    def test_defaults(self) -> None:
        c = UsageCost()
        assert c.input == 0.0
        assert c.output == 0.0
        assert c.cache_read == 0.0
        assert c.cache_write == 0.0
        assert c.total == 0.0

    def test_custom_values(self) -> None:
        c = UsageCost(input=0.01, output=0.03, total=0.04)
        assert c.input == 0.01
        assert c.output == 0.03
        assert c.total == 0.04


class TestUsage:
    def test_defaults(self) -> None:
        u = Usage()
        assert u.input == 0
        assert u.output == 0
        assert u.cache_read == 0
        assert u.cache_write == 0
        assert u.total_tokens == 0
        assert u.cost == UsageCost()

    def test_custom(self) -> None:
        c = UsageCost(input=0.001, output=0.002, total=0.003)
        u = Usage(input=100, output=50, total_tokens=150, cost=c)
        assert u.input == 100
        assert u.output == 50
        assert u.total_tokens == 150
        assert u.cost.total == 0.003


class TestTool:
    def test_basic(self) -> None:
        t = Tool(
            name="read_file",
            description="Read a file",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        )
        assert t.name == "read_file"
        assert t.description == "Read a file"
        assert "properties" in t.parameters


class TestModelCost:
    def test_defaults(self) -> None:
        mc = ModelCost()
        assert mc.input == 0.0
        assert mc.output == 0.0
        assert mc.cache_read == 0.0
        assert mc.cache_write == 0.0


class TestStreamOptions:
    def test_all_optional(self) -> None:
        so = StreamOptions()
        assert so.temperature is None
        assert so.max_tokens is None
        assert so.api_key is None
        assert so.transport is None
        assert so.cache_retention is None
        assert so.session_id is None
        assert so.headers is None
        assert so.max_retry_delay_ms is None
        assert so.metadata is None

    def test_with_values(self) -> None:
        so = StreamOptions(
            temperature=0.7,
            max_tokens=1024,
            api_key="sk-xxx",
            transport="sse",
            cache_retention="short",
            session_id="sess-1",
            headers={"X-Custom": "val"},
            max_retry_delay_ms=30000,
            metadata={"user_id": "u1"},
        )
        assert so.temperature == 0.7
        assert so.max_tokens == 1024
        assert so.transport == "sse"
        assert so.cache_retention == "short"
        assert so.headers == {"X-Custom": "val"}


# ── Messages ───────────────────────────────────────────────────────────


class TestUserMessage:
    def test_string_content(self) -> None:
        ts = time.time() * 1000
        m = UserMessage(content="Hello", timestamp=ts)
        assert m.role == "user"
        assert m.content == "Hello"
        assert m.timestamp == ts

    def test_list_content(self) -> None:
        m = UserMessage(
            content=[
                TextContent(text="describe this"),
                ImageContent(data="abc==", mime_type="image/jpeg"),
            ],
            timestamp=1000,
        )
        assert m.role == "user"
        assert len(m.content) == 2
        assert m.content[0].type == "text"
        assert m.content[1].type == "image"

    def test_default_role(self) -> None:
        m = UserMessage(content="hi")
        assert m.role == "user"


class TestAssistantMessage:
    def _make(self, **kwargs: object) -> AssistantMessage:
        defaults: dict = {
            "content": [TextContent(text="hi")],
            "api": "anthropic-messages",
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "usage": Usage(),
            "stop_reason": "stop",
            "timestamp": 1000.0,
        }
        defaults.update(kwargs)
        return AssistantMessage(**defaults)

    def test_basic(self) -> None:
        m = self._make()
        assert m.role == "assistant"
        assert m.api == "anthropic-messages"
        assert m.stop_reason == "stop"

    def test_mixed_content(self) -> None:
        m = self._make(
            content=[
                ThinkingContent(thinking="hmm"),
                TextContent(text="answer"),
                ToolCall(id="c1", name="bash", arguments={"cmd": "ls"}),
            ]
        )
        assert len(m.content) == 3
        assert m.content[0].type == "thinking"
        assert m.content[1].type == "text"
        assert m.content[2].type == "toolCall"

    def test_error_message(self) -> None:
        m = self._make(stop_reason="error", error_message="rate limited")
        assert m.error_message == "rate limited"
        assert m.stop_reason == "error"


class TestToolResultMessage:
    def test_basic(self) -> None:
        m = ToolResultMessage(
            tool_call_id="call_1",
            tool_name="read_file",
            content=[TextContent(text="file contents here")],
            is_error=False,
            timestamp=1000.0,
        )
        assert m.role == "toolResult"
        assert m.tool_call_id == "call_1"
        assert m.tool_name == "read_file"
        assert m.is_error is False

    def test_error_result(self) -> None:
        m = ToolResultMessage(
            tool_call_id="call_2",
            tool_name="bash",
            content=[TextContent(text="command failed")],
            is_error=True,
            timestamp=2000.0,
        )
        assert m.is_error is True

    def test_image_content(self) -> None:
        m = ToolResultMessage(
            tool_call_id="call_3",
            tool_name="screenshot",
            content=[ImageContent(data="img==", mime_type="image/png")],
            is_error=False,
            timestamp=3000.0,
        )
        assert m.content[0].type == "image"


# ── Context ────────────────────────────────────────────────────────────


class TestContext:
    def test_minimal(self) -> None:
        ctx = Context(messages=[])
        assert ctx.system_prompt is None
        assert ctx.messages == []
        assert ctx.tools is None

    def test_full(self) -> None:
        ctx = Context(
            system_prompt="You are helpful.",
            messages=[UserMessage(content="hi", timestamp=1000)],
            tools=[Tool(name="bash", description="Run bash", parameters={"type": "object"})],
        )
        assert ctx.system_prompt == "You are helpful."
        assert len(ctx.messages) == 1
        assert len(ctx.tools) == 1


# ── Model ──────────────────────────────────────────────────────────────


class TestModel:
    def test_basic(self) -> None:
        m = Model(
            id="claude-sonnet-4-20250514",
            name="Claude Sonnet 4",
            api="anthropic-messages",
            provider="anthropic",
            base_url="https://api.anthropic.com",
            reasoning=True,
            input=["text", "image"],
            cost=ModelCost(input=3.0, output=15.0),
            context_window=200000,
            max_tokens=8192,
        )
        assert m.id == "claude-sonnet-4-20250514"
        assert m.reasoning is True
        assert m.input == ["text", "image"]
        assert m.cost.input == 3.0
        assert m.headers is None

    def test_with_headers(self) -> None:
        m = Model(
            id="test",
            name="Test",
            api="openai-completions",
            provider="openai",
            base_url="https://api.openai.com",
            reasoning=False,
            input=["text"],
            cost=ModelCost(),
            context_window=128000,
            max_tokens=4096,
            headers={"Authorization": "Bearer xxx"},
        )
        assert m.headers == {"Authorization": "Bearer xxx"}


# ── Literal/type alias checks ─────────────────────────────────────────


class TestLiterals:
    def test_stop_reason_values(self) -> None:
        """StopReason should accept valid values."""
        for reason in ("stop", "length", "toolUse", "error"):
            m = AssistantMessage(
                content=[],
                api="anthropic-messages",
                provider="anthropic",
                model="test",
                usage=Usage(),
                stop_reason=reason,
                timestamp=0,
            )
            assert m.stop_reason == reason

    def test_thinking_level_type(self) -> None:
        """ThinkingLevel should be a valid Literal type alias."""
        levels: list[ThinkingLevel] = ["minimal", "low", "medium", "high", "xhigh"]
        assert len(levels) == 5


# ── Serialization round-trip ───────────────────────────────────────────


class TestSerialization:
    def test_user_message_roundtrip(self) -> None:
        m = UserMessage(content="hello", timestamp=12345)
        data = serialize_message(m)
        m2 = deserialize_message(data)
        assert m2.content == "hello"
        assert m2.timestamp == 12345
        assert m2.role == "user"

    def test_assistant_message_roundtrip(self) -> None:
        m = AssistantMessage(
            content=[TextContent(text="hi"), ThinkingContent(thinking="hmm")],
            api="openai-responses",
            provider="openai",
            model="gpt-4o",
            usage=Usage(input=10, output=5, total_tokens=15),
            stop_reason="stop",
            timestamp=99999,
        )
        data = serialize_message(m)
        m2 = deserialize_message(data)
        assert len(m2.content) == 2
        assert m2.content[0].type == "text"
        assert m2.content[1].type == "thinking"
        assert m2.usage.input == 10

    def test_tool_result_roundtrip(self) -> None:
        m = ToolResultMessage(
            tool_call_id="c1",
            tool_name="bash",
            content=[TextContent(text="output")],
            is_error=False,
            timestamp=5000,
        )
        data = serialize_message(m)
        m2 = deserialize_message(data)
        assert m2.tool_call_id == "c1"
        assert m2.is_error is False

    def test_content_block_roundtrip(self) -> None:
        """Test content block serialization/deserialization."""
        blocks = [
            TextContent(text="hello"),
            ThinkingContent(thinking="hmm"),
            ImageContent(data="abc", mime_type="image/png"),
            ToolCall(id="c1", name="bash", arguments={"cmd": "ls"}),
        ]
        for block in blocks:
            data = serialize_content_block(block)
            restored = deserialize_content_block(data)
            assert restored.type == block.type
