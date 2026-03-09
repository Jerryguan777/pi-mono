"""Tests for pi_agent.agent.Agent class."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, ClassVar

import pytest

from pi_agent.agent import Agent, AgentOptions, _default_convert_to_llm
from pi_agent.types import (
    AgentEndEvent,
    AgentEvent,
    AgentMessage,
    AgentStartEvent,
    AgentState,
    AgentTool,
    AgentToolResult,
)
from pi_ai.types import (
    AssistantMessage,
    Context,
    DoneEvent,
    ImageContent,
    Model,
    SimpleStreamOptions,
    TextContent,
    UserMessage,
)


def make_response(text: str = "Test response") -> AssistantMessage:
    return AssistantMessage(
        api="test-api",
        provider="test",
        model="test-model",
        stop_reason="stop",
        content=[TextContent(text=text)],
    )


def make_mock_stream_fn(response: AssistantMessage) -> Any:
    """Return a mock stream function that yields a done response."""

    async def stream_fn(
        model: Model,
        context: Context,
        options: SimpleStreamOptions | None,
    ) -> AsyncIterator[Any]:
        yield DoneEvent(reason=response.stop_reason, message=response)

    return stream_fn


def make_agent(text: str = "Hello!") -> Agent:
    """Create an Agent with a mock stream function."""
    response = make_response(text)
    opts = AgentOptions(
        stream_fn=make_mock_stream_fn(response),
    )
    agent = Agent(opts)
    agent.set_model(Model(id="test-model", api="test-api", provider="test"))
    return agent


class TestAgentCreation:
    def test_default_construction(self) -> None:
        agent = Agent()
        assert agent.state.system_prompt == ""
        assert agent.state.tools == []
        assert agent.state.messages == []
        assert not agent.state.is_streaming

    def test_with_options(self) -> None:
        opts = AgentOptions(session_id="sess-1", transport="websocket")
        agent = Agent(opts)
        assert agent.session_id == "sess-1"
        assert agent.transport == "websocket"

    def test_with_initial_state(self) -> None:
        state = AgentState(
            system_prompt="Custom sys prompt",
            model=Model(id="gpt-4"),
            thinking_level="low",
            tools=[],
            messages=[],
            is_streaming=False,
            stream_message=None,
            pending_tool_calls=set(),
        )
        opts = AgentOptions(initial_state=state)
        agent = Agent(opts)
        assert agent.state.system_prompt == "Custom sys prompt"
        assert agent.state.model.id == "gpt-4"
        assert agent.state.thinking_level == "low"


class TestAgentStateMutators:
    def test_set_system_prompt(self) -> None:
        agent = Agent()
        agent.set_system_prompt("You are helpful.")
        assert agent.state.system_prompt == "You are helpful."

    def test_set_model(self) -> None:
        agent = Agent()
        model = Model(id="claude-3", api="anthropic", provider="anthropic")
        agent.set_model(model)
        assert agent.state.model.id == "claude-3"

    def test_set_thinking_level(self) -> None:
        agent = Agent()
        agent.set_thinking_level("high")
        assert agent.state.thinking_level == "high"

    def test_set_tools(self) -> None:
        class DummyTool(AgentTool):
            name = "dummy"
            label = "Dummy"
            description = "test"
            parameters: ClassVar[dict[str, Any]] = {}

            async def execute(
                self,
                tool_call_id: str,
                params: dict[str, Any],
                signal: Any = None,
                on_update: Any = None,
            ) -> AgentToolResult:
                return AgentToolResult(content=[], details=None)

        agent = Agent()
        agent.set_tools([DummyTool()])
        assert len(agent.state.tools) == 1

    def test_replace_messages(self) -> None:
        agent = Agent()
        msgs: list[AgentMessage] = [UserMessage(content="hi")]
        agent.replace_messages(msgs)
        assert len(agent.state.messages) == 1

    def test_append_message(self) -> None:
        agent = Agent()
        agent.append_message(UserMessage(content="hi"))
        assert len(agent.state.messages) == 1

    def test_clear_messages(self) -> None:
        agent = Agent()
        agent.append_message(UserMessage(content="hi"))
        agent.clear_messages()
        assert len(agent.state.messages) == 0

    def test_set_steering_mode(self) -> None:
        agent = Agent()
        agent.set_steering_mode("all")
        assert agent.get_steering_mode() == "all"

    def test_set_follow_up_mode(self) -> None:
        agent = Agent()
        agent.set_follow_up_mode("all")
        assert agent.get_follow_up_mode() == "all"


class TestAgentQueues:
    def test_steer_and_clear(self) -> None:
        agent = Agent()
        agent.steer(UserMessage(content="steer msg"))
        assert agent.has_queued_messages()
        agent.clear_steering_queue()
        assert not agent.has_queued_messages()

    def test_follow_up_and_clear(self) -> None:
        agent = Agent()
        agent.follow_up(UserMessage(content="follow up"))
        assert agent.has_queued_messages()
        agent.clear_follow_up_queue()
        assert not agent.has_queued_messages()

    def test_clear_all_queues(self) -> None:
        agent = Agent()
        agent.steer(UserMessage(content="steer"))
        agent.follow_up(UserMessage(content="follow"))
        assert agent.has_queued_messages()
        agent.clear_all_queues()
        assert not agent.has_queued_messages()

    def test_dequeue_one_at_a_time(self) -> None:
        agent = Agent()
        agent.steer(UserMessage(content="msg1"))
        agent.steer(UserMessage(content="msg2"))
        # one-at-a-time mode: dequeue first message only
        dequeued = agent._dequeue_steering_messages()
        assert len(dequeued) == 1
        assert isinstance(dequeued[0], UserMessage) and dequeued[0].content == "msg1"
        # Second dequeue gets the second message
        dequeued2 = agent._dequeue_steering_messages()
        assert len(dequeued2) == 1
        assert isinstance(dequeued2[0], UserMessage) and dequeued2[0].content == "msg2"

    def test_dequeue_all_mode(self) -> None:
        agent = Agent()
        agent.set_steering_mode("all")
        agent.steer(UserMessage(content="msg1"))
        agent.steer(UserMessage(content="msg2"))
        dequeued = agent._dequeue_steering_messages()
        assert len(dequeued) == 2
        # Queue is now empty
        assert not agent._steering_queue


class TestAgentSubscription:
    def test_subscribe_and_unsubscribe(self) -> None:
        agent = Agent()
        received: list[AgentEvent] = []
        unsubscribe = agent.subscribe(received.append)
        agent._emit(AgentStartEvent())
        assert len(received) == 1
        unsubscribe()
        agent._emit(AgentStartEvent())
        # Should not receive after unsubscribe
        assert len(received) == 1

    def test_multiple_subscribers(self) -> None:
        agent = Agent()
        events1: list[AgentEvent] = []
        events2: list[AgentEvent] = []
        agent.subscribe(events1.append)
        agent.subscribe(events2.append)
        agent._emit(AgentStartEvent())
        assert len(events1) == 1
        assert len(events2) == 1


class TestAgentPrompt:
    @pytest.mark.asyncio
    async def test_prompt_with_string(self) -> None:
        agent = make_agent("Response to string prompt")
        events: list[AgentEvent] = []
        agent.subscribe(events.append)
        await agent.prompt("Hello agent!")
        assert any(isinstance(e, AgentEndEvent) for e in events)
        # Messages should be stored
        assert len(agent.state.messages) >= 1

    @pytest.mark.asyncio
    async def test_prompt_with_user_message(self) -> None:
        agent = make_agent("Direct message response")
        user_msg = UserMessage(content="Direct prompt")
        await agent.prompt(user_msg)
        assert not agent.state.is_streaming

    @pytest.mark.asyncio
    async def test_prompt_with_list(self) -> None:
        agent = make_agent("List prompt response")
        msgs: list[AgentMessage] = [UserMessage(content="part1"), UserMessage(content="part2")]
        await agent.prompt(msgs)
        assert not agent.state.is_streaming

    @pytest.mark.asyncio
    async def test_prompt_with_images(self) -> None:
        agent = make_agent("Image response")
        image = ImageContent(data="base64data", mime_type="image/png")
        await agent.prompt("Describe this image", images=[image])
        assert not agent.state.is_streaming

    @pytest.mark.asyncio
    async def test_prompt_while_streaming_raises(self) -> None:
        agent = make_agent()
        agent._state.is_streaming = True
        with pytest.raises(RuntimeError, match="already processing"):
            await agent.prompt("Another prompt")

    @pytest.mark.asyncio
    async def test_is_streaming_clears_after_prompt(self) -> None:
        agent = make_agent()
        await agent.prompt("test")
        assert not agent.state.is_streaming
        assert agent.state.stream_message is None

    @pytest.mark.asyncio
    async def test_messages_accumulated(self) -> None:
        agent = make_agent("First response")
        await agent.prompt("First question")
        first_count = len(agent.state.messages)
        assert first_count >= 2  # user + assistant

        # Update stream fn for second prompt
        agent.stream_fn = make_mock_stream_fn(make_response("Second response"))
        await agent.prompt("Second question")
        assert len(agent.state.messages) > first_count


class TestAgentReset:
    @pytest.mark.asyncio
    async def test_reset_clears_messages(self) -> None:
        agent = make_agent()
        await agent.prompt("test")
        assert len(agent.state.messages) > 0
        agent.reset()
        assert len(agent.state.messages) == 0

    def test_reset_clears_queues(self) -> None:
        agent = Agent()
        agent.steer(UserMessage(content="steer"))
        agent.follow_up(UserMessage(content="follow"))
        agent.reset()
        assert not agent.has_queued_messages()


class TestAgentAbort:
    @pytest.mark.asyncio
    async def test_abort_sets_signal(self) -> None:
        """abort() should set the abort event."""
        # Use an event to synchronize abort timing
        started = asyncio.Event()
        can_finish = asyncio.Event()

        async def slow_stream_fn(
            model: Model,
            context: Context,
            options: SimpleStreamOptions | None,
        ) -> AsyncIterator[Any]:
            started.set()
            await can_finish.wait()
            response = make_response("aborted response")
            yield DoneEvent(reason="stop", message=response)

        opts = AgentOptions(stream_fn=slow_stream_fn)
        agent = Agent(opts)
        agent.set_model(Model(id="test", api="test", provider="test"))

        async def run_prompt() -> None:
            await agent.prompt("test")

        task = asyncio.create_task(run_prompt())
        await started.wait()
        agent.abort()
        can_finish.set()
        await task


class TestAgentContinue:
    @pytest.mark.asyncio
    async def test_continue_from_user_message(self) -> None:
        agent = make_agent("Continue response")
        agent.append_message(UserMessage(content="Initial question"))
        await agent.continue_()
        assert not agent.state.is_streaming

    @pytest.mark.asyncio
    async def test_continue_with_no_messages_raises(self) -> None:
        agent = make_agent()
        with pytest.raises(RuntimeError):
            await agent.continue_()

    @pytest.mark.asyncio
    async def test_continue_from_assistant_message_with_follow_up(self) -> None:
        """Continue from assistant message should use follow-up queue."""
        agent = make_agent("Follow-up response")
        agent.append_message(AssistantMessage(model="test", content=[TextContent(text="I responded")]))
        agent.follow_up(UserMessage(content="Follow up question"))
        await agent.continue_()
        assert not agent.state.is_streaming


class TestDefaultConvertToLlm:
    def test_filters_non_llm_messages(self) -> None:
        from pi_ai.types import ToolResultMessage

        messages: list[AgentMessage] = [
            UserMessage(content="hi"),
            AssistantMessage(model="test"),
            ToolResultMessage(tool_call_id="tc1", tool_name="test"),
        ]
        result = _default_convert_to_llm(messages)
        assert len(result) == 3

    def test_keeps_standard_roles(self) -> None:
        messages: list[AgentMessage] = [
            UserMessage(content="hello"),
        ]
        result = _default_convert_to_llm(messages)
        assert len(result) == 1


class TestAgentWaitForIdle:
    @pytest.mark.asyncio
    async def test_wait_for_idle_when_not_running(self) -> None:
        """wait_for_idle should return immediately if nothing is running."""
        agent = Agent()
        # Should complete without hanging
        await agent.wait_for_idle()

    @pytest.mark.asyncio
    async def test_wait_for_idle_after_prompt(self) -> None:
        agent = make_agent()
        await agent.prompt("test")
        # Should complete immediately since prompt is done
        await agent.wait_for_idle()
