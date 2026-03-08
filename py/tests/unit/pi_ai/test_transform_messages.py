"""Tests for pi_ai.providers.transform_messages — orphaned tool call flushing."""

from __future__ import annotations

from pi_ai.providers.transform_messages import transform_messages
from pi_ai.types import (
    AssistantMessage,
    Model,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


def _make_model(provider: str = "anthropic", api: str = "anthropic-messages", model_id: str = "claude") -> Model:
    return Model(id=model_id, provider=provider, api=api)


class TestOrphanedToolCallFlushing:
    def test_orphaned_tool_call_gets_synthetic_result(self) -> None:
        model = _make_model()
        tc = ToolCall(id="tc1", name="bash", arguments={"cmd": "ls"})
        assistant = AssistantMessage(
            content=[TextContent(text="Let me run that."), tc],
            provider="anthropic",
            api="anthropic-messages",
            model="claude",
        )
        # No tool result follows - user message comes next
        user = UserMessage(content=[TextContent(text="hello")])

        result = transform_messages([assistant, user], model)
        # Should have: assistant, synthetic tool result, user
        assert len(result) == 3
        assert result[0].role == "assistant"
        assert result[1].role == "toolResult"
        assert isinstance(result[1], ToolResultMessage)
        assert result[1].tool_call_id == "tc1"
        assert result[1].is_error is True
        assert result[2].role == "user"

    def test_matched_tool_call_no_synthetic(self) -> None:
        model = _make_model()
        tc = ToolCall(id="tc1", name="bash", arguments={})
        assistant = AssistantMessage(
            content=[tc],
            provider="anthropic",
            api="anthropic-messages",
            model="claude",
        )
        tool_result = ToolResultMessage(
            tool_call_id="tc1",
            tool_name="bash",
            content=[TextContent(text="output")],
        )
        user = UserMessage(content=[TextContent(text="ok")])

        result = transform_messages([assistant, tool_result, user], model)
        assert len(result) == 3
        # No synthetic result should be injected
        assert result[0].role == "assistant"
        assert result[1].role == "toolResult"
        assert isinstance(result[1], ToolResultMessage)
        assert result[1].tool_call_id == "tc1"
        assert result[2].role == "user"

    def test_partially_orphaned_tool_calls(self) -> None:
        model = _make_model()
        tc1 = ToolCall(id="tc1", name="bash", arguments={})
        tc2 = ToolCall(id="tc2", name="read", arguments={})
        assistant = AssistantMessage(
            content=[tc1, tc2],
            provider="anthropic",
            api="anthropic-messages",
            model="claude",
        )
        # Only tc1 has a result
        tool_result = ToolResultMessage(
            tool_call_id="tc1",
            tool_name="bash",
            content=[TextContent(text="output")],
        )
        user = UserMessage(content=[TextContent(text="next")])

        result = transform_messages([assistant, tool_result, user], model)
        # Should have: assistant, tool_result(tc1), synthetic_result(tc2), user
        assert len(result) == 4
        assert result[2].role == "toolResult"
        assert isinstance(result[2], ToolResultMessage)
        assert result[2].tool_call_id == "tc2"
        assert result[2].is_error is True

    def test_errored_assistant_message_skipped(self) -> None:
        model = _make_model()
        assistant = AssistantMessage(
            content=[TextContent(text="error")],
            provider="anthropic",
            api="anthropic-messages",
            model="claude",
            stop_reason="error",
        )
        user = UserMessage(content=[TextContent(text="retry")])

        result = transform_messages([assistant, user], model)
        # Error assistant should be filtered out
        assert len(result) == 1
        assert result[0].role == "user"

    def test_aborted_assistant_message_skipped(self) -> None:
        model = _make_model()
        assistant = AssistantMessage(
            content=[TextContent(text="aborted")],
            provider="anthropic",
            api="anthropic-messages",
            model="claude",
            stop_reason="aborted",
        )

        result = transform_messages([assistant], model)
        assert len(result) == 0

    def test_consecutive_assistants_flush_first(self) -> None:
        model = _make_model()
        tc1 = ToolCall(id="tc1", name="bash", arguments={})
        a1 = AssistantMessage(
            content=[tc1],
            provider="anthropic",
            api="anthropic-messages",
            model="claude",
        )
        tc2 = ToolCall(id="tc2", name="read", arguments={})
        a2 = AssistantMessage(
            content=[tc2],
            provider="anthropic",
            api="anthropic-messages",
            model="claude",
        )
        tool_result_2 = ToolResultMessage(
            tool_call_id="tc2",
            tool_name="read",
            content=[TextContent(text="content")],
        )

        result = transform_messages([a1, a2, tool_result_2], model)
        # a1's tool call is orphaned when a2 appears, so synthetic result injected
        # result: a1, synthetic(tc1), a2, tool_result_2
        assert len(result) == 4
        assert result[1].role == "toolResult"
        assert isinstance(result[1], ToolResultMessage)
        assert result[1].tool_call_id == "tc1"
        assert result[1].is_error is True
