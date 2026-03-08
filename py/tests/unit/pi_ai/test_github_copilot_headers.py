"""Tests for pi_ai.providers.github_copilot_headers."""

from __future__ import annotations

from pi_ai.providers.github_copilot_headers import (
    build_copilot_dynamic_headers,
    has_copilot_vision_input,
    infer_copilot_initiator,
)
from pi_ai.types import AssistantMessage, ImageContent, Message, TextContent, ToolResultMessage, UserMessage


def test_infer_initiator_empty() -> None:
    assert infer_copilot_initiator([]) == "user"


def test_infer_initiator_last_user() -> None:
    msgs = [UserMessage(content="hello")]
    assert infer_copilot_initiator(msgs) == "user"


def test_infer_initiator_last_assistant() -> None:
    msgs: list[Message] = [UserMessage(content="hi"), AssistantMessage()]
    assert infer_copilot_initiator(msgs) == "agent"


def test_infer_initiator_last_tool_result() -> None:
    msgs: list[Message] = [
        UserMessage(content="hi"),
        AssistantMessage(),
        ToolResultMessage(tool_call_id="c1", tool_name="bash", content=[]),
    ]
    assert infer_copilot_initiator(msgs) == "agent"


def test_has_vision_no_messages() -> None:
    assert not has_copilot_vision_input([])


def test_has_vision_text_only_user() -> None:
    msgs = [UserMessage(content=[TextContent(text="hello")])]
    assert not has_copilot_vision_input(msgs)


def test_has_vision_string_user() -> None:
    msgs = [UserMessage(content="hello")]
    assert not has_copilot_vision_input(msgs)


def test_has_vision_user_with_image() -> None:
    msgs = [UserMessage(content=[ImageContent(data="x", mime_type="image/png")])]
    assert has_copilot_vision_input(msgs)


def test_has_vision_tool_result_with_image() -> None:
    msgs: list[Message] = [
        UserMessage(content="hi"),
        ToolResultMessage(
            tool_call_id="c1",
            tool_name="read",
            content=[ImageContent(data="x", mime_type="image/jpeg")],
        ),
    ]
    assert has_copilot_vision_input(msgs)


def test_has_vision_tool_result_text_only() -> None:
    msgs = [
        ToolResultMessage(
            tool_call_id="c1",
            tool_name="read",
            content=[TextContent(text="result")],
        )
    ]
    assert not has_copilot_vision_input(msgs)


def test_build_headers_no_images() -> None:
    msgs = [UserMessage(content="hello")]
    headers = build_copilot_dynamic_headers(msgs, False)
    assert headers["X-Initiator"] == "user"
    assert headers["Openai-Intent"] == "conversation-edits"
    assert "Copilot-Vision-Request" not in headers


def test_build_headers_with_images() -> None:
    msgs = [AssistantMessage()]
    headers = build_copilot_dynamic_headers(msgs, True)
    assert headers["X-Initiator"] == "agent"
    assert headers["Copilot-Vision-Request"] == "true"


def test_build_headers_empty_messages() -> None:
    headers = build_copilot_dynamic_headers([], False)
    assert headers["X-Initiator"] == "user"
