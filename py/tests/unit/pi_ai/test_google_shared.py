"""Tests for pi_ai.providers.google_shared — shared Google provider utilities."""

from __future__ import annotations

from typing import Any

from pi_ai.providers.google_shared import (
    convert_messages,
    convert_tools,
    is_thinking_part,
    map_stop_reason,
    map_stop_reason_string,
    map_tool_choice,
    requires_tool_call_id,
    retain_thought_signature,
)
from pi_ai.types import (
    AssistantMessage,
    Context,
    ImageContent,
    Message,
    Model,
    TextContent,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)

# ---------------------------------------------------------------------------
# is_thinking_part
# ---------------------------------------------------------------------------


class TestIsThinkingPart:
    def test_thought_true(self) -> None:
        assert is_thinking_part({"thought": True, "text": "hmm"}) is True

    def test_thought_false(self) -> None:
        assert is_thinking_part({"thought": False, "text": "hi"}) is False

    def test_no_thought_key(self) -> None:
        assert is_thinking_part({"text": "hi"}) is False

    def test_thought_none(self) -> None:
        assert is_thinking_part({"thought": None}) is False


# ---------------------------------------------------------------------------
# retain_thought_signature
# ---------------------------------------------------------------------------


class TestRetainThoughtSignature:
    def test_incoming_non_empty_replaces(self) -> None:
        assert retain_thought_signature("old_sig", "new_sig") == "new_sig"

    def test_incoming_empty_keeps_existing(self) -> None:
        assert retain_thought_signature("existing", "") == "existing"

    def test_incoming_none_keeps_existing(self) -> None:
        assert retain_thought_signature("existing", None) == "existing"

    def test_both_none(self) -> None:
        assert retain_thought_signature(None, None) is None

    def test_existing_none_incoming_non_empty(self) -> None:
        assert retain_thought_signature(None, "new") == "new"


# ---------------------------------------------------------------------------
# requires_tool_call_id
# ---------------------------------------------------------------------------


class TestRequiresToolCallId:
    def test_claude_model(self) -> None:
        assert requires_tool_call_id("claude-3.5-sonnet") is True

    def test_gpt_oss_model(self) -> None:
        assert requires_tool_call_id("gpt-oss-4o") is True

    def test_gemini_model(self) -> None:
        assert requires_tool_call_id("gemini-2.0-flash") is False

    def test_empty_string(self) -> None:
        assert requires_tool_call_id("") is False


# ---------------------------------------------------------------------------
# map_tool_choice
# ---------------------------------------------------------------------------


class TestMapToolChoice:
    def test_auto(self) -> None:
        assert map_tool_choice("auto") == "AUTO"

    def test_none(self) -> None:
        assert map_tool_choice("none") == "NONE"

    def test_any(self) -> None:
        assert map_tool_choice("any") == "ANY"

    def test_unknown_defaults_to_auto(self) -> None:
        assert map_tool_choice("something_else") == "AUTO"


# ---------------------------------------------------------------------------
# map_stop_reason / map_stop_reason_string
# ---------------------------------------------------------------------------


class TestMapStopReason:
    def test_stop(self) -> None:
        assert map_stop_reason("STOP") == "stop"

    def test_max_tokens(self) -> None:
        assert map_stop_reason("MAX_TOKENS") == "length"

    def test_unknown(self) -> None:
        assert map_stop_reason("SAFETY") == "error"

    def test_string_variant(self) -> None:
        assert map_stop_reason_string("STOP") == "stop"
        assert map_stop_reason_string("MAX_TOKENS") == "length"
        assert map_stop_reason_string("OTHER") == "error"


# ---------------------------------------------------------------------------
# convert_tools
# ---------------------------------------------------------------------------


class TestConvertTools:
    def test_empty_tools_returns_none(self) -> None:
        assert convert_tools([]) is None

    def test_single_tool_default_schema_key(self) -> None:
        tools = [Tool(name="bash", description="Run command", parameters={"type": "object"})]
        result = convert_tools(tools)
        assert result is not None
        assert len(result) == 1
        decls = result[0]["functionDeclarations"]
        assert len(decls) == 1
        assert decls[0]["name"] == "bash"
        assert "parametersJsonSchema" in decls[0]
        assert "parameters" not in decls[0]

    def test_use_parameters_flag(self) -> None:
        tools = [Tool(name="bash", description="Run command", parameters={"type": "object"})]
        result = convert_tools(tools, use_parameters=True)
        assert result is not None
        decls = result[0]["functionDeclarations"]
        assert "parameters" in decls[0]
        assert "parametersJsonSchema" not in decls[0]

    def test_multiple_tools(self) -> None:
        tools = [
            Tool(name="bash", description="Run bash", parameters={}),
            Tool(name="read", description="Read file", parameters={}),
        ]
        result = convert_tools(tools)
        assert result is not None
        decls = result[0]["functionDeclarations"]
        assert len(decls) == 2


# ---------------------------------------------------------------------------
# convert_messages
# ---------------------------------------------------------------------------


class TestConvertMessages:
    def _model(self, **kwargs: Any) -> Model:
        defaults: dict[str, Any] = dict(
            id="gemini-2.0-flash",
            provider="google",
            api="google-generative-ai",
            input=["text"],
        )
        defaults.update(kwargs)
        return Model(**defaults)

    def test_user_message_string(self) -> None:
        model = self._model()
        ctx = Context(messages=[UserMessage(content="hello")])
        result = convert_messages(model, ctx)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["parts"][0]["text"] == "hello"

    def test_user_message_with_text_content(self) -> None:
        model = self._model()
        ctx = Context(messages=[UserMessage(content=[TextContent(text="hi")])])
        result = convert_messages(model, ctx)
        assert len(result) == 1
        assert result[0]["parts"][0]["text"] == "hi"

    def test_user_message_image_filtered_when_not_supported(self) -> None:
        model = self._model(input=["text"])
        ctx = Context(
            messages=[
                UserMessage(
                    content=[
                        TextContent(text="look"),
                        ImageContent(data="base64", mime_type="image/png"),
                    ]
                )
            ]
        )
        result = convert_messages(model, ctx)
        # Image should be filtered out since model doesn't support image input
        assert len(result) == 1
        parts = result[0]["parts"]
        assert len(parts) == 1
        assert "text" in parts[0]

    def test_user_message_image_included_when_supported(self) -> None:
        model = self._model(input=["text", "image"])
        ctx = Context(
            messages=[
                UserMessage(
                    content=[
                        TextContent(text="look"),
                        ImageContent(data="base64", mime_type="image/png"),
                    ]
                )
            ]
        )
        result = convert_messages(model, ctx)
        parts = result[0]["parts"]
        assert len(parts) == 2
        assert "inlineData" in parts[1]

    def test_assistant_message_text(self) -> None:
        model = self._model()
        msg = AssistantMessage(
            content=[TextContent(text="response")],
            provider="google",
            model="gemini-2.0-flash",
        )
        ctx = Context(messages=[UserMessage(content="hi"), msg])
        result = convert_messages(model, ctx)
        assert len(result) == 2
        assert result[1]["role"] == "model"
        assert result[1]["parts"][0]["text"] == "response"

    def test_assistant_message_empty_text_skipped(self) -> None:
        model = self._model()
        msg = AssistantMessage(
            content=[TextContent(text="   ")],
            provider="google",
            model="gemini-2.0-flash",
        )
        ctx = Context(messages=[UserMessage(content="hi"), msg])
        result = convert_messages(model, ctx)
        # Empty text blocks are skipped, and empty assistant parts_list -> skipped
        assert len(result) == 1

    def test_assistant_message_thinking_same_provider(self) -> None:
        model = self._model()
        msg = AssistantMessage(
            content=[ThinkingContent(thinking="deep thought", thinking_signature="AAAA")],
            api="google-generative-ai",
            provider="google",
            model="gemini-2.0-flash",
        )
        ctx = Context(messages=[UserMessage(content="hi"), msg])
        result = convert_messages(model, ctx)
        assert len(result) == 2
        part = result[1]["parts"][0]
        assert part.get("thought") is True
        assert part["text"] == "deep thought"

    def test_assistant_message_thinking_different_provider(self) -> None:
        model = self._model()
        msg = AssistantMessage(
            content=[ThinkingContent(thinking="deep thought")],
            provider="anthropic",
            model="claude-3.5",
        )
        ctx = Context(messages=[UserMessage(content="hi"), msg])
        result = convert_messages(model, ctx)
        assert len(result) == 2
        part = result[1]["parts"][0]
        # Should be converted to plain text, not a thinking part
        assert "thought" not in part
        assert part["text"] == "deep thought"

    def test_assistant_message_tool_call(self) -> None:
        model = self._model()
        msg = AssistantMessage(
            content=[ToolCall(id="tc_1", name="bash", arguments={"cmd": "ls"})],
            provider="google",
            model="gemini-2.0-flash",
        )
        ctx = Context(messages=[UserMessage(content="hi"), msg])
        result = convert_messages(model, ctx)
        assert len(result) == 2
        part = result[1]["parts"][0]
        assert "functionCall" in part
        assert part["functionCall"]["name"] == "bash"

    def test_assistant_tool_call_includes_id_for_claude(self) -> None:
        model = self._model(id="claude-3.5-sonnet")
        msg = AssistantMessage(
            content=[ToolCall(id="tc_1", name="bash", arguments={})],
            provider="google",
            model="claude-3.5-sonnet",
        )
        ctx = Context(messages=[UserMessage(content="hi"), msg])
        result = convert_messages(model, ctx)
        fc = result[1]["parts"][0]["functionCall"]
        assert "id" in fc

    def test_tool_result_message(self) -> None:
        model = self._model()
        msgs: list[Message] = [
            UserMessage(content="hi"),
            AssistantMessage(
                content=[ToolCall(id="tc_1", name="bash", arguments={"cmd": "ls"})],
                provider="google",
                model="gemini-2.0-flash",
            ),
            ToolResultMessage(
                tool_call_id="tc_1",
                tool_name="bash",
                content=[TextContent(text="file.txt")],
            ),
        ]
        ctx = Context(messages=msgs)
        result = convert_messages(model, ctx)
        # User message, model message, and tool result (as user message)
        assert len(result) == 3
        tool_part = result[2]["parts"][0]
        assert "functionResponse" in tool_part
        assert tool_part["functionResponse"]["name"] == "bash"
        assert tool_part["functionResponse"]["response"]["output"] == "file.txt"

    def test_tool_result_error(self) -> None:
        model = self._model()
        msgs: list[Message] = [
            UserMessage(content="hi"),
            AssistantMessage(
                content=[ToolCall(id="tc_1", name="bash", arguments={})],
                provider="google",
                model="gemini-2.0-flash",
            ),
            ToolResultMessage(
                tool_call_id="tc_1",
                tool_name="bash",
                content=[TextContent(text="command not found")],
                is_error=True,
            ),
        ]
        ctx = Context(messages=msgs)
        result = convert_messages(model, ctx)
        fr = result[2]["parts"][0]["functionResponse"]
        assert "error" in fr["response"]
        assert fr["response"]["error"] == "command not found"

    def test_consecutive_tool_results_merged(self) -> None:
        model = self._model()
        msgs: list[Message] = [
            UserMessage(content="hi"),
            AssistantMessage(
                content=[
                    ToolCall(id="tc_1", name="bash", arguments={}),
                    ToolCall(id="tc_2", name="read", arguments={}),
                ],
                provider="google",
                model="gemini-2.0-flash",
            ),
            ToolResultMessage(tool_call_id="tc_1", tool_name="bash", content=[TextContent(text="out1")]),
            ToolResultMessage(tool_call_id="tc_2", tool_name="read", content=[TextContent(text="out2")]),
        ]
        ctx = Context(messages=msgs)
        result = convert_messages(model, ctx)
        # User, model, then both tool results should be merged into one user turn
        assert len(result) == 3
        assert len(result[2]["parts"]) == 2

    def test_gemini_3_tool_call_without_signature_becomes_text(self) -> None:
        """Gemini 3 models: tool calls without thought_signature become text context."""
        model = self._model(id="gemini-3-flash")
        msg = AssistantMessage(
            content=[ToolCall(id="tc_1", name="bash", arguments={"cmd": "ls"})],
            provider="other",
            model="other-model",
        )
        ctx = Context(messages=[UserMessage(content="hi"), msg])
        result = convert_messages(model, ctx)
        # The tool call should be rendered as text for gemini-3 models
        part = result[1]["parts"][0]
        assert "text" in part
        assert "Historical context" in part["text"]
