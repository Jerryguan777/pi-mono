"""Tests for pi_coding_agent.core.messages."""

from __future__ import annotations

from pi_ai.types import AssistantMessage, UserMessage
from pi_coding_agent.core.messages import (
    BRANCH_SUMMARY_PREFIX,
    BRANCH_SUMMARY_SUFFIX,
    COMPACTION_SUMMARY_PREFIX,
    COMPACTION_SUMMARY_SUFFIX,
    BashExecutionMessage,
    BranchSummaryMessage,
    CompactionSummaryMessage,
    CustomMessage,
    bash_execution_to_text,
    convert_to_llm,
    create_branch_summary_message,
    create_compaction_summary_message,
    create_custom_message,
)


class TestBashExecutionMessage:
    def test_default_role(self) -> None:
        msg = BashExecutionMessage()
        assert msg.role == "bash_execution"

    def test_to_text_with_output(self) -> None:
        msg = BashExecutionMessage(command="ls", stdout="file.txt\n", exit_code=0)
        text = bash_execution_to_text(msg)
        assert "$ ls" in text
        assert "file.txt" in text
        assert "[exit 0]" in text

    def test_to_text_cancelled(self) -> None:
        msg = BashExecutionMessage(command="sleep 100", stdout="", cancelled=True)
        text = bash_execution_to_text(msg)
        assert "[cancelled]" in text

    def test_to_text_truncated(self) -> None:
        msg = BashExecutionMessage(command="cat big", stdout="lots of output", truncated=True)
        text = bash_execution_to_text(msg)
        assert "[output truncated]" in text


class TestCustomMessage:
    def test_default_role(self) -> None:
        msg = CustomMessage()
        assert msg.role == "custom"

    def test_create_custom_message(self) -> None:
        msg = create_custom_message("my-type", "hello", True, None, "2024-01-01T00:00:00Z")
        assert msg.custom_type == "my-type"
        assert msg.content == "hello"
        assert msg.display is True


class TestBranchSummaryMessage:
    def test_create_branch_summary(self) -> None:
        msg = create_branch_summary_message("summary text", "abc123", "2024-01-01T00:00:00Z")
        assert msg.role == "branch_summary"
        assert msg.summary == "summary text"
        assert msg.from_id == "abc123"

    def test_prefix_suffix_constants(self) -> None:
        assert BRANCH_SUMMARY_PREFIX.startswith("The following is a summary")
        assert BRANCH_SUMMARY_SUFFIX == "</summary>"


class TestCompactionSummaryMessage:
    def test_create_compaction_summary(self) -> None:
        msg = create_compaction_summary_message("compact", 5000, "2024-01-01T00:00:00Z")
        assert msg.role == "compaction_summary"
        assert msg.summary == "compact"
        assert msg.tokens_before == 5000

    def test_prefix_suffix_constants(self) -> None:
        assert "compacted" in COMPACTION_SUMMARY_PREFIX
        assert COMPACTION_SUMMARY_SUFFIX == "\n</summary>"


class TestConvertToLlm:
    def test_user_message_passes_through(self) -> None:
        msg = UserMessage(content="hello")
        result = convert_to_llm([msg])
        assert len(result) == 1
        assert result[0] is msg

    def test_assistant_message_passes_through(self) -> None:
        msg = AssistantMessage()
        result = convert_to_llm([msg])
        assert len(result) == 1

    def test_bash_message_becomes_user_message(self) -> None:
        bash = BashExecutionMessage(command="ls", stdout="ok")
        result = convert_to_llm([bash])
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)
        assert "ls" in str(result[0].content)

    def test_bash_message_excluded_from_context_is_filtered(self) -> None:
        bash = BashExecutionMessage(command="ls", stdout="ok", exclude_from_context=True)
        result = convert_to_llm([bash])
        assert result == []

    def test_compaction_summary_becomes_user_message(self) -> None:
        msg = CompactionSummaryMessage(summary="the summary", tokens_before=100)
        result = convert_to_llm([msg])
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)
        content = result[0].content
        assert isinstance(content, str)
        assert "the summary" in content

    def test_branch_summary_becomes_user_message(self) -> None:
        msg = BranchSummaryMessage(summary="branch text", from_id="id1")
        result = convert_to_llm([msg])
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)
        content = result[0].content
        assert isinstance(content, str)
        assert "branch text" in content

    def test_custom_message_becomes_user_message(self) -> None:
        msg = CustomMessage(custom_type="ext", content="extension data", display=True)
        result = convert_to_llm([msg])
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)

    def test_mixed_messages(self) -> None:
        from pi_coding_agent.core.messages import SessionMessage

        messages: list[SessionMessage] = [
            UserMessage(content="hi"),
            BashExecutionMessage(command="ls", stdout="ok"),
            AssistantMessage(),
        ]
        result = convert_to_llm(messages)
        # UserMessage + BashExecutionMessage (converted) + AssistantMessage = 3
        assert len(result) == 3
