"""Tests for pi_ai.providers.transform_messages."""

from __future__ import annotations

from pi_ai.providers.transform_messages import transform_messages
from pi_ai.types import (
    AssistantMessage,
    Message,
    Model,
    ModelCost,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


def _make_model(model_id: str = "test-model", api: str = "test-api", provider: str = "test") -> Model:
    return Model(id=model_id, name="Test", api=api, provider=provider, cost=ModelCost())


def _make_assistant(
    content: list[TextContent | ThinkingContent | ToolCall] | None = None,
    model_id: str = "test-model",
    api: str = "test-api",
    provider: str = "test",
    stop_reason: str = "stop",
) -> AssistantMessage:
    return AssistantMessage(
        content=content or [TextContent(text="hello")],
        model=model_id,
        api=api,
        provider=provider,
        stop_reason=stop_reason,  # type: ignore[arg-type]
    )


class TestTransformMessages:
    def test_user_messages_pass_through(self) -> None:
        model = _make_model()
        msgs: list[Message] = [UserMessage(content="hi")]
        result = transform_messages(msgs, model)
        assert len(result) == 1
        assert result[0].role == "user"

    def test_same_model_keeps_thinking(self) -> None:
        model = _make_model()
        msgs: list[Message] = [_make_assistant(content=[ThinkingContent(thinking="hmm")])]
        result = transform_messages(msgs, model)
        assert len(result) == 1
        assert isinstance(result[0], AssistantMessage)
        assert isinstance(result[0].content[0], ThinkingContent)

    def test_different_model_converts_thinking_to_text(self) -> None:
        model = _make_model(model_id="other-model")
        msgs: list[Message] = [_make_assistant(content=[ThinkingContent(thinking="hmm")])]
        result = transform_messages(msgs, model)
        assert len(result) == 1
        assert isinstance(result[0], AssistantMessage)
        block = result[0].content[0]
        assert isinstance(block, TextContent)
        assert block.text == "hmm"

    def test_empty_thinking_removed_for_different_model(self) -> None:
        model = _make_model(model_id="other-model")
        msgs: list[Message] = [_make_assistant(content=[ThinkingContent(thinking="")])]
        result = transform_messages(msgs, model)
        assert isinstance(result[0], AssistantMessage)
        assert len(result[0].content) == 0

    def test_same_model_keeps_thinking_signature(self) -> None:
        model = _make_model()
        msgs: list[Message] = [_make_assistant(content=[ThinkingContent(thinking="", thinking_signature="sig123")])]
        result = transform_messages(msgs, model)
        assert isinstance(result[0], AssistantMessage)
        block = result[0].content[0]
        assert isinstance(block, ThinkingContent)
        assert block.thinking_signature == "sig123"

    def test_strips_text_signature_for_different_model(self) -> None:
        model = _make_model(model_id="other-model")
        msgs: list[Message] = [_make_assistant(content=[TextContent(text="hi", text_signature="sig")])]
        result = transform_messages(msgs, model)
        assert isinstance(result[0], AssistantMessage)
        block = result[0].content[0]
        assert isinstance(block, TextContent)
        assert block.text_signature is None

    def test_skips_errored_messages(self) -> None:
        model = _make_model()
        msgs: list[Message] = [
            _make_assistant(stop_reason="error"),
            _make_assistant(content=[TextContent(text="good")]),
        ]
        result = transform_messages(msgs, model)
        assert len(result) == 1
        assert isinstance(result[0], AssistantMessage)
        assert result[0].content[0].text == "good"  # type: ignore[union-attr]

    def test_skips_aborted_messages(self) -> None:
        model = _make_model()
        msgs: list[Message] = [_make_assistant(stop_reason="aborted")]
        result = transform_messages(msgs, model)
        assert len(result) == 0

    def test_inserts_synthetic_tool_results_for_orphaned_calls(self) -> None:
        model = _make_model()
        msgs: list[Message] = [
            _make_assistant(
                content=[ToolCall(id="tc_1", name="bash", arguments={"cmd": "ls"})],
                stop_reason="toolUse",
            ),
            UserMessage(content="interrupted"),
        ]
        result = transform_messages(msgs, model)
        # Should have: assistant, synthetic tool result, user
        assert len(result) == 3
        assert result[0].role == "assistant"
        assert result[1].role == "toolResult"
        assert isinstance(result[1], ToolResultMessage)
        assert result[1].is_error is True
        assert result[2].role == "user"

    def test_no_synthetic_for_existing_tool_results(self) -> None:
        model = _make_model()
        msgs: list[Message] = [
            _make_assistant(
                content=[ToolCall(id="tc_1", name="bash", arguments={})],
                stop_reason="toolUse",
            ),
            ToolResultMessage(tool_call_id="tc_1", tool_name="bash", content=[TextContent(text="ok")], is_error=False),
        ]
        result = transform_messages(msgs, model)
        # Should have: assistant, tool result (no synthetic)
        assert len(result) == 2

    def test_normalize_tool_call_id(self) -> None:
        model = _make_model(model_id="other-model")

        def normalizer(id: str, model: Model, source: AssistantMessage) -> str:
            return f"norm_{id}"

        msgs: list[Message] = [
            _make_assistant(
                content=[ToolCall(id="tc_1", name="bash", arguments={})],
                stop_reason="toolUse",
            ),
            ToolResultMessage(tool_call_id="tc_1", tool_name="bash", content=[], is_error=False),
        ]
        result = transform_messages(msgs, model, normalize_tool_call_id=normalizer)
        assert isinstance(result[0], AssistantMessage)
        tool_call = result[0].content[0]
        assert isinstance(tool_call, ToolCall)
        assert tool_call.id == "norm_tc_1"
        # Tool result should also be normalized
        assert isinstance(result[1], ToolResultMessage)
        assert result[1].tool_call_id == "norm_tc_1"

    def test_removes_thought_signature_for_different_model(self) -> None:
        model = _make_model(model_id="other-model")
        msgs: list[Message] = [
            _make_assistant(
                content=[ToolCall(id="tc_1", name="bash", arguments={}, thought_signature="sig")],
                stop_reason="toolUse",
            ),
            ToolResultMessage(tool_call_id="tc_1", tool_name="bash", content=[], is_error=False),
        ]
        result = transform_messages(msgs, model)
        assert isinstance(result[0], AssistantMessage)
        tc = result[0].content[0]
        assert isinstance(tc, ToolCall)
        assert tc.thought_signature is None
