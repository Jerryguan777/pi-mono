"""Tests for pi_ai.types — core type definitions and serialization."""

from __future__ import annotations

from pi_ai.types import (
    AssistantMessage,
    ImageContent,
    Model,
    ModelCost,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
    Usage,
    UsageCost,
    UserMessage,
    deserialize_content_block,
    deserialize_message,
    deserialize_model,
    deserialize_usage,
    serialize_content_block,
    serialize_message,
    serialize_model,
    serialize_usage,
)


class TestContentBlocks:
    def test_text_content_defaults(self) -> None:
        tc = TextContent()
        assert tc.type == "text"
        assert tc.text == ""
        assert tc.text_signature is None

    def test_thinking_content(self) -> None:
        tc = ThinkingContent(thinking="Let me think...")
        assert tc.type == "thinking"
        assert tc.thinking == "Let me think..."

    def test_image_content(self) -> None:
        ic = ImageContent(data="abc123", mime_type="image/png")
        assert ic.type == "image"
        assert ic.data == "abc123"
        assert ic.mime_type == "image/png"

    def test_tool_call(self) -> None:
        tc = ToolCall(id="tc_1", name="bash", arguments={"command": "ls"})
        assert tc.type == "toolCall"
        assert tc.name == "bash"
        assert tc.arguments == {"command": "ls"}
        assert tc.thought_signature is None


class TestMessages:
    def test_user_message_string_content(self) -> None:
        msg = UserMessage(content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp > 0

    def test_user_message_block_content(self) -> None:
        msg = UserMessage(content=[TextContent(text="hi"), ImageContent(data="x", mime_type="image/png")])
        assert isinstance(msg.content, list)
        assert len(msg.content) == 2

    def test_assistant_message(self) -> None:
        msg = AssistantMessage(
            content=[TextContent(text="Hello!")],
            api="anthropic-messages",
            provider="anthropic",
            model="claude-3",
            stop_reason="stop",
        )
        assert msg.role == "assistant"
        assert msg.stop_reason == "stop"
        assert msg.error_message is None

    def test_tool_result_message(self) -> None:
        msg = ToolResultMessage(
            tool_call_id="tc_1",
            tool_name="bash",
            content=[TextContent(text="output")],
            is_error=False,
        )
        assert msg.role == "toolResult"
        assert msg.tool_call_id == "tc_1"


class TestUsage:
    def test_usage_defaults(self) -> None:
        u = Usage()
        assert u.input == 0
        assert u.output == 0
        assert u.cost.total == 0.0

    def test_usage_cost(self) -> None:
        cost = UsageCost(input=0.01, output=0.02, total=0.03)
        assert cost.total == 0.03


class TestSerialization:
    def test_serialize_text_content(self) -> None:
        tc = TextContent(text="hello")
        data = serialize_content_block(tc)
        assert data == {"type": "text", "text": "hello"}

    def test_serialize_text_content_with_signature(self) -> None:
        tc = TextContent(text="hello", text_signature="sig123")
        data = serialize_content_block(tc)
        assert data["textSignature"] == "sig123"

    def test_serialize_thinking_content(self) -> None:
        tc = ThinkingContent(thinking="hmm", thinking_signature="sig")
        data = serialize_content_block(tc)
        assert data == {"type": "thinking", "thinking": "hmm", "thinkingSignature": "sig"}

    def test_serialize_image_content(self) -> None:
        ic = ImageContent(data="base64data", mime_type="image/jpeg")
        data = serialize_content_block(ic)
        assert data == {"type": "image", "data": "base64data", "mimeType": "image/jpeg"}

    def test_serialize_tool_call(self) -> None:
        tc = ToolCall(id="1", name="bash", arguments={"cmd": "ls"})
        data = serialize_content_block(tc)
        assert data["type"] == "toolCall"
        assert data["name"] == "bash"
        assert "thoughtSignature" not in data

    def test_serialize_tool_call_with_signature(self) -> None:
        tc = ToolCall(id="1", name="bash", arguments={}, thought_signature="sig")
        data = serialize_content_block(tc)
        assert data["thoughtSignature"] == "sig"

    def test_roundtrip_text_content(self) -> None:
        block = TextContent(text="hello")
        assert deserialize_content_block(serialize_content_block(block)) == block

    def test_roundtrip_thinking_content(self) -> None:
        block = ThinkingContent(thinking="hmm")
        assert deserialize_content_block(serialize_content_block(block)) == block

    def test_roundtrip_image_content(self) -> None:
        block = ImageContent(data="x", mime_type="image/png")
        assert deserialize_content_block(serialize_content_block(block)) == block

    def test_roundtrip_tool_call(self) -> None:
        block = ToolCall(id="1", name="bash", arguments={"cmd": "ls"})
        assert deserialize_content_block(serialize_content_block(block)) == block

    def test_deserialize_unknown_content_type_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="Unknown content block type"):
            deserialize_content_block({"type": "unknown"})

    def test_serialize_usage(self) -> None:
        usage = Usage(input=100, output=50, cache_read=10, cache_write=5, total_tokens=165)
        data = serialize_usage(usage)
        assert data["input"] == 100
        assert data["cacheRead"] == 10
        assert data["totalTokens"] == 165

    def test_roundtrip_usage(self) -> None:
        usage = Usage(input=100, output=50, cache_read=10, cache_write=5, total_tokens=165)
        data = serialize_usage(usage)
        restored = deserialize_usage(data)
        assert usage == restored

    def test_serialize_user_message_string(self) -> None:
        msg = UserMessage(content="hello", timestamp=1000.0)
        data = serialize_message(msg)
        assert data["role"] == "user"
        assert data["content"] == "hello"

    def test_serialize_user_message_blocks(self) -> None:
        msg = UserMessage(content=[TextContent(text="hi")], timestamp=1000.0)
        data = serialize_message(msg)
        assert isinstance(data["content"], list)
        assert data["content"][0]["text"] == "hi"

    def test_serialize_assistant_message(self) -> None:
        msg = AssistantMessage(
            content=[TextContent(text="hi")],
            api="openai-completions",
            provider="openai",
            model="gpt-4",
            stop_reason="stop",
            timestamp=1000.0,
        )
        data = serialize_message(msg)
        assert data["role"] == "assistant"
        assert data["stopReason"] == "stop"
        assert "errorMessage" not in data

    def test_serialize_assistant_message_with_error(self) -> None:
        msg = AssistantMessage(
            content=[],
            api="openai-completions",
            provider="openai",
            model="gpt-4",
            stop_reason="error",
            error_message="rate limited",
            timestamp=1000.0,
        )
        data = serialize_message(msg)
        assert data["errorMessage"] == "rate limited"

    def test_serialize_tool_result_message(self) -> None:
        msg = ToolResultMessage(
            tool_call_id="tc_1",
            tool_name="bash",
            content=[TextContent(text="output")],
            is_error=False,
            timestamp=1000.0,
        )
        data = serialize_message(msg)
        assert data["role"] == "toolResult"
        assert data["toolCallId"] == "tc_1"
        assert "details" not in data

    def test_roundtrip_user_message(self) -> None:
        msg = UserMessage(content="hello", timestamp=1000.0)
        assert deserialize_message(serialize_message(msg)) == msg

    def test_roundtrip_assistant_message(self) -> None:
        msg = AssistantMessage(
            content=[TextContent(text="hi")],
            api="openai-completions",
            provider="openai",
            model="gpt-4",
            stop_reason="stop",
            timestamp=2000.0,
        )
        assert deserialize_message(serialize_message(msg)) == msg

    def test_roundtrip_tool_result_message(self) -> None:
        msg = ToolResultMessage(
            tool_call_id="tc_1",
            tool_name="bash",
            content=[TextContent(text="ok")],
            is_error=False,
            timestamp=3000.0,
        )
        assert deserialize_message(serialize_message(msg)) == msg

    def test_deserialize_unknown_role_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="Unknown message role"):
            deserialize_message({"role": "unknown"})


class TestModel:
    def test_model_defaults(self) -> None:
        m = Model(id="gpt-4", name="GPT-4", api="openai-completions", provider="openai")
        assert m.reasoning is False
        assert m.input == ["text"]
        assert m.context_window == 0

    def test_serialize_model(self) -> None:
        m = Model(
            id="gpt-4",
            name="GPT-4",
            api="openai-completions",
            provider="openai",
            base_url="https://api.openai.com",
            cost=ModelCost(input=30.0, output=60.0),
            context_window=128000,
            max_tokens=4096,
        )
        data = serialize_model(m)
        assert data["id"] == "gpt-4"
        assert data["cost"]["input"] == 30.0
        assert data["contextWindow"] == 128000
        assert "headers" not in data

    def test_roundtrip_model(self) -> None:
        m = Model(
            id="gpt-4",
            name="GPT-4",
            api="openai-completions",
            provider="openai",
            base_url="https://api.openai.com",
            cost=ModelCost(input=30.0, output=60.0),
            context_window=128000,
            max_tokens=4096,
        )
        data = serialize_model(m)
        restored = deserialize_model(data)
        assert m == restored
