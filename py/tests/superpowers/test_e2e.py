"""
E2E: Agent with coding tools reads a file using a mock stream function.

Ported from python-superpowers. The rewrite's Agent uses AgentOptions
and prompt() returns None (state is stored on agent.state.messages).
"""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import AsyncIterator

import pytest
from pi_agent.agent import Agent, AgentOptions
from pi_agent.types import (
    AgentContext,
    AgentEvent,
    AgentStartEvent,
    AgentState,
    MessageEndEvent,
)
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    DoneEvent,
    Model,
    SimpleStreamOptions,
    StartEvent,
    TextContent,
    TextDeltaEvent,
    ToolCall,
    ToolCallDeltaEvent,
    ToolCallStartEvent,
    UserMessage,
)
from pi_coding_agent.core.system_prompt import BuildSystemPromptOptions, build_system_prompt
from pi_coding_agent.core.tools import create_all_tools


def _make_e2e_stream_fn(file_path: str):
    """Create a stream function that simulates reading a file then responding."""
    call_count = 0

    async def stream_fn(
        model: Model, context: Context, options: SimpleStreamOptions | None = None
    ) -> AsyncIterator[AssistantMessageEvent]:
        nonlocal call_count
        call_count += 1

        partial = AssistantMessage(api="anthropic-messages", provider="test", model="test")

        yield StartEvent(partial=partial)
        if call_count == 1:
            # First call: tool_use to read the file
            tc = ToolCall(id="tc_1", name="read", arguments={"path": file_path})
            msg = AssistantMessage(
                api="anthropic-messages", provider="test", model="test",
                content=[tc], stop_reason="toolUse",
            )
            yield ToolCallStartEvent(partial=partial)
            yield ToolCallDeltaEvent(delta=f'{{"path": "{file_path}"}}', partial=partial)
            yield DoneEvent(reason="toolUse", message=msg)
        else:
            # Second call: text response
            msg = AssistantMessage(
                api="anthropic-messages", provider="test", model="test",
                content=[TextContent(text="The file has been read.")],
                stop_reason="stop",
            )
            yield TextDeltaEvent(delta="The file has been read.", partial=partial)
            yield DoneEvent(reason="stop", message=msg)

    return stream_fn


@pytest.mark.asyncio
async def test_e2e_agent_reads_file() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create test file
        test_file = os.path.join(tmp_dir, "hello.txt")
        with open(test_file, "w") as f:
            f.write("hello world\n")

        model = Model(id="test", name="test", api="anthropic-messages", provider="test")
        tools_dict = create_all_tools(tmp_dir)
        tools_list = list(tools_dict.values())

        system_prompt = build_system_prompt(BuildSystemPromptOptions(cwd=tmp_dir))

        initial_state = AgentState(
            system_prompt=system_prompt,
            model=model,
            thinking_level="off",
            tools=tools_list,
            messages=[],
            is_streaming=False,
            stream_message=None,
            pending_tool_calls=set(),
        )

        stream_fn = _make_e2e_stream_fn(test_file)

        agent = Agent(
            AgentOptions(
                initial_state=initial_state,
                stream_fn=stream_fn,
            )
        )

        # Collect events
        captured_events: list[AgentEvent] = []
        agent.subscribe(captured_events.append)

        await agent.prompt("Read hello.txt")

        messages = agent.state.messages

        # Should have at least: user + assistant(tool_call) + tool_result + assistant(text)
        assert len(messages) >= 4

        # First message should be user
        assert messages[0].role == "user"

        # Second should be assistant with tool call
        assert messages[1].role == "assistant"

        # Third should be tool result containing file content
        assert messages[2].role == "toolResult"
        tool_result_text = messages[2].content[0].text
        assert "hello world" in tool_result_text

        # Fourth should be final assistant response
        assert messages[3].role == "assistant"

        # Events should include lifecycle events
        event_types = [type(e).__name__ for e in captured_events]
        assert "AgentStartEvent" in event_types
        assert "AgentEndEvent" in event_types
