"""Integration test: Agent loop x real tool execution.

Verifies the full chain: fake LLM returns tool calls -> real tools execute on disk
-> results flow back through the event stream with correct event ordering.
No tools are mocked. All file operations happen in a real temp directory.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator, Sequence
from pathlib import Path

import pytest

from pi_agent.agent_loop import agent_loop
from pi_agent.types import (
    AgentContext,
    AgentEndEvent,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentStartEvent,
    AgentTool,
    MessageEndEvent,
    MessageStartEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
)
from pi_ai.api_registry import clear_api_providers
from pi_ai.types import TextContent, ToolResultMessage, UserMessage
from pi_coding_agent.core.tools.edit import EditTool
from pi_coding_agent.core.tools.read import ReadTool
from pi_coding_agent.core.tools.write import WriteTool
from tests.helpers.fake_llm import (
    FakeLLM,
    make_fake_model,
    make_text_response,
    make_tool_call_response,
)


@pytest.fixture(autouse=True)
def _clean_registry() -> Generator[None, None, None]:
    clear_api_providers()
    yield
    clear_api_providers()


@pytest.fixture()
def work_dir() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as d:
        yield d


async def _collect_events(
    prompts: list[AgentMessage],
    fake: FakeLLM,
    tools: Sequence[AgentTool],
    system_prompt: str = "You are a helpful assistant.",
) -> list[AgentEvent]:
    model = make_fake_model()
    fake.register()

    context = AgentContext(
        system_prompt=system_prompt,
        messages=[],
        tools=list(tools),
    )
    config = AgentLoopConfig(model=model, max_turns=10)

    events: list[AgentEvent] = []
    async for event in agent_loop(prompts, context, config):
        events.append(event)
    return events


async def test_write_then_read(work_dir: str) -> None:
    """Fake LLM requests write -> then read -> results match."""
    file_path = os.path.join(work_dir, "hello.txt")
    file_content = "Hello, integration test!"

    fake = FakeLLM(
        [
            # Turn 1: write the file
            make_tool_call_response("write", {"path": file_path, "content": file_content}, "tc_write"),
            # Turn 2: read the file back
            make_tool_call_response("read", {"path": file_path}, "tc_read"),
            # Turn 3: final text response (no more tool calls -> loop ends)
            make_text_response("Done!"),
        ]
    )

    tools = [WriteTool(work_dir), ReadTool(work_dir)]
    events = await _collect_events(
        [UserMessage(content="Write and read a file")],
        fake,
        tools,
    )

    # File should actually exist on disk
    assert Path(file_path).exists()
    assert Path(file_path).read_text() == file_content

    # Check event types contain the expected tool execution events
    event_types = [type(e) for e in events]
    assert AgentStartEvent in event_types
    assert ToolExecutionStartEvent in event_types
    assert ToolExecutionEndEvent in event_types
    assert AgentEndEvent in event_types

    # Verify write tool execution
    write_starts = [e for e in events if isinstance(e, ToolExecutionStartEvent) and e.tool_name == "write"]
    write_ends = [e for e in events if isinstance(e, ToolExecutionEndEvent) and e.tool_name == "write"]
    assert len(write_starts) == 1
    assert len(write_ends) == 1
    assert not write_ends[0].is_error

    # Verify read tool execution returns the written content
    read_ends = [e for e in events if isinstance(e, ToolExecutionEndEvent) and e.tool_name == "read"]
    assert len(read_ends) == 1
    assert not read_ends[0].is_error
    read_text = read_ends[0].result.content[0]
    assert isinstance(read_text, TextContent)
    assert file_content in read_text.text


async def test_edit_modifies_file(work_dir: str) -> None:
    """Fake LLM requests write -> then edit -> file content is modified on disk."""
    file_path = os.path.join(work_dir, "code.py")
    original = "def greet():\n    return 'hello'\n"
    edited = "def greet():\n    return 'world'\n"

    fake = FakeLLM(
        [
            # Write file first
            make_tool_call_response("write", {"path": file_path, "content": original}, "tc_w"),
            # Edit the file
            make_tool_call_response(
                "edit",
                {"path": file_path, "old_text": "return 'hello'", "new_text": "return 'world'"},
                "tc_e",
            ),
            # Done
            make_text_response("File edited."),
        ]
    )

    tools = [WriteTool(work_dir), EditTool(work_dir)]
    events = await _collect_events(
        [UserMessage(content="Edit the file")],
        fake,
        tools,
    )

    # Verify disk state
    assert Path(file_path).read_text() == edited

    # Verify edit tool result is not an error
    edit_ends = [e for e in events if isinstance(e, ToolExecutionEndEvent) and e.tool_name == "edit"]
    assert len(edit_ends) == 1
    assert not edit_ends[0].is_error


async def test_event_ordering(work_dir: str) -> None:
    """Event stream follows correct ordering:
    AgentStart -> TurnStart -> MessageStart/End (user) ->
    MessageStart/End (assistant) -> ToolExecStart -> ToolExecEnd ->
    MessageStart/End (toolResult) -> TurnEnd -> ... -> AgentEnd
    """
    file_path = os.path.join(work_dir, "test.txt")

    fake = FakeLLM(
        [
            make_tool_call_response("write", {"path": file_path, "content": "data"}, "tc_1"),
            make_text_response("All done."),
        ]
    )

    tools = [WriteTool(work_dir)]
    events = await _collect_events(
        [UserMessage(content="Write a file")],
        fake,
        tools,
    )

    event_types = [type(e) for e in events]

    # Must start with AgentStart
    assert event_types[0] is AgentStartEvent

    # Must end with AgentEnd
    assert event_types[-1] is AgentEndEvent

    # ToolExecutionStart must come before ToolExecutionEnd
    tool_start_idx = event_types.index(ToolExecutionStartEvent)
    tool_end_idx = event_types.index(ToolExecutionEndEvent)
    assert tool_start_idx < tool_end_idx

    # After tool execution, a MessageStart/End for the tool result should appear
    post_tool_events = event_types[tool_end_idx + 1 :]
    assert MessageStartEvent in post_tool_events
    assert MessageEndEvent in post_tool_events

    # Verify tool result messages appear in the event stream
    tool_result_messages = [
        e for e in events if isinstance(e, MessageEndEvent) and isinstance(e.message, ToolResultMessage)
    ]
    assert len(tool_result_messages) >= 1


async def test_unknown_tool_returns_error(work_dir: str) -> None:
    """When the LLM calls a tool that does not exist, the event stream
    should include an error tool result rather than crashing."""
    fake = FakeLLM(
        [
            make_tool_call_response("nonexistent_tool", {"arg": "val"}, "tc_bad"),
            make_text_response("ok"),
        ]
    )

    tools = [WriteTool(work_dir)]
    events = await _collect_events(
        [UserMessage(content="Call bad tool")],
        fake,
        tools,
    )

    error_ends = [e for e in events if isinstance(e, ToolExecutionEndEvent) and e.is_error]
    assert len(error_ends) == 1
    assert "not found" in error_ends[0].result.content[0].text.lower()  # type: ignore[union-attr]


async def test_creates_subdirectories(work_dir: str) -> None:
    """WriteTool should create parent directories automatically."""
    nested_path = os.path.join(work_dir, "a", "b", "c", "deep.txt")

    fake = FakeLLM(
        [
            make_tool_call_response("write", {"path": nested_path, "content": "deep"}, "tc_deep"),
            make_text_response("Done"),
        ]
    )

    tools = [WriteTool(work_dir)]
    await _collect_events([UserMessage(content="Write deep")], fake, tools)

    assert Path(nested_path).exists()
    assert Path(nested_path).read_text() == "deep"
