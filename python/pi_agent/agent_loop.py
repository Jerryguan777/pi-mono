"""Agent loop — async generator that drives LLM → tool → loop cycles."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from pi_ai.api_registry import stream_simple
from pi_ai.types import (
    AssistantMessage,
    Context,
    Message,
    Model,
    StreamOptions,
    TextContent,
    ToolCall,
    ToolResultMessage,
)
from pi_ai.validation import validate_tool_arguments

from pi_agent.types import (
    AgentContext,
    AgentEndEvent,
    AgentEvent,
    AgentLoopConfig,
    AgentStartEvent,
    AgentTool,
    AgentToolResult,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)


@dataclass
class _ToolExecutionResult:
    """Result of executing a batch of tool calls, including any steering interruption."""
    tool_results: list[ToolResultMessage] = field(default_factory=list)
    steering_messages: list[Message] | None = None
    events: list[AgentEvent] = field(default_factory=list)


async def agent_loop(
    prompts: list[Message],
    context: AgentContext,
    config: AgentLoopConfig,
) -> AsyncIterator[AgentEvent]:
    """Start an agent loop with prompt messages.

    Yields AgentEvents as the agent processes the conversation.
    The agent loops: LLM call → tool execution → repeat until no more tool calls.
    """
    new_messages: list[Message] = list(prompts)
    current_messages = list(context.messages) + list(prompts)

    yield AgentStartEvent()
    yield TurnStartEvent()

    for prompt in prompts:
        yield MessageStartEvent(message=prompt)
        yield MessageEndEvent(message=prompt)

    async for event in _run_loop(
        context=context,
        config=config,
        messages=current_messages,
        new_messages=new_messages,
        first_turn=True,
    ):
        yield event


async def agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
) -> AsyncIterator[AgentEvent]:
    """Continue an agent loop from the current context without adding new prompts.

    Used for retries or resuming — context must already contain messages and
    the last message must not be an assistant message.
    """
    if not context.messages:
        raise ValueError("agent_loop_continue requires non-empty context.messages")

    last = context.messages[-1]
    if isinstance(last, AssistantMessage):
        raise ValueError(
            "agent_loop_continue: last message must not be assistant "
            "(the LLM provider would reject it)"
        )

    current_messages = list(context.messages)
    new_messages: list[Message] = []

    yield AgentStartEvent()
    yield TurnStartEvent()

    async for event in _run_loop(
        context=context,
        config=config,
        messages=current_messages,
        new_messages=new_messages,
        first_turn=True,
    ):
        yield event


async def _run_loop(
    context: AgentContext,
    config: AgentLoopConfig,
    messages: list[Message],
    new_messages: list[Message],
    first_turn: bool = True,
) -> AsyncIterator[AgentEvent]:
    """Double-loop: outer handles follow-up, inner handles steering + tool calls."""
    tools = context.tools or []

    # Outer loop — follow-up messages
    while True:
        has_tool_calls = True
        pending_messages: list[Message] = []

        # Poll for initial steering messages (user may have typed while waiting)
        if config.get_steering_messages:
            pending_messages = await config.get_steering_messages()

        # Inner loop — streaming + tool execution
        while has_tool_calls or pending_messages:
            if config.abort_signal and config.abort_signal.is_set():
                yield AgentEndEvent(messages=new_messages)
                return

            if not first_turn:
                yield TurnStartEvent()
            first_turn = False

            # Inject pending messages (steering) before the LLM call
            if pending_messages:
                for msg in pending_messages:
                    messages.append(msg)
                    new_messages.append(msg)
                    yield MessageStartEvent(message=msg)
                    yield MessageEndEvent(message=msg)
                pending_messages = []

            # Stream assistant response
            assistant_msg: AssistantMessage | None = None
            async for event in _stream_assistant_response(context, config, messages):
                yield event
                if isinstance(event, MessageEndEvent) and isinstance(event.message, AssistantMessage):
                    assistant_msg = event.message

            if assistant_msg is None:
                yield AgentEndEvent(messages=new_messages)
                return

            new_messages.append(assistant_msg)

            if assistant_msg.stop_reason in ("error", "aborted"):
                yield TurnEndEvent(message=assistant_msg, tool_results=[])
                yield AgentEndEvent(messages=new_messages)
                return

            # Check for tool calls
            tool_calls = [c for c in assistant_msg.content if isinstance(c, ToolCall)]
            has_tool_calls = bool(tool_calls)

            if not tool_calls:
                yield TurnEndEvent(message=assistant_msg, tool_results=[])
                # Poll steering after turn with no tool calls
                if config.get_steering_messages:
                    pending_messages = await config.get_steering_messages()
                continue

            # Execute tool calls (may be interrupted by steering)
            exec_result = await _execute_tool_calls(tools, assistant_msg, tool_calls, config)

            # Yield all collected events
            for ev in exec_result.events:
                yield ev

            # Apply tool results to message lists
            for tr in exec_result.tool_results:
                messages.append(tr)
                new_messages.append(tr)

            yield TurnEndEvent(message=assistant_msg, tool_results=exec_result.tool_results)

            # If steering interrupted tool execution, use those messages
            if exec_result.steering_messages:
                pending_messages = exec_result.steering_messages
                has_tool_calls = True  # force inner loop to continue
            elif config.get_steering_messages:
                # Poll steering after tool turn
                pending_messages = await config.get_steering_messages()

        # Inner loop exited — check for follow-up messages
        if config.get_follow_up_messages:
            follow_up = await config.get_follow_up_messages()
            if follow_up:
                # Inject follow-up and loop back
                for msg in follow_up:
                    messages.append(msg)
                    new_messages.append(msg)
                # Reset first_turn so next iteration emits TurnStartEvent
                first_turn = False
                # Emit follow-up message events at the start of the next turn
                # by setting them as pending in the next outer iteration
                # Actually, we need to emit them — let the outer loop re-enter
                # with pending messages already in the list but events not yet emitted.
                # Simpler: yield the message events here, then continue.
                yield TurnStartEvent()
                for msg in follow_up:
                    yield MessageStartEvent(message=msg)
                    yield MessageEndEvent(message=msg)
                # The inner loop will pick up from here; set first_turn so inner
                # doesn't emit another TurnStartEvent on the first iteration.
                first_turn = True
                continue
            # No follow-up — we're done
            break
        else:
            break

    yield AgentEndEvent(messages=new_messages)


async def _stream_assistant_response(
    context: AgentContext,
    config: AgentLoopConfig,
    messages: list[Message],
) -> AsyncIterator[AgentEvent]:
    """Stream an assistant response from the LLM."""
    from pi_ai.types import Tool as AiTool

    tools = context.tools or []

    # Convert AgentTools to AI Tools for context
    ai_tools = [
        AiTool(name=t.name, description=t.description, parameters=t.parameters)
        for t in tools
    ] if tools else None

    # Apply transform_context hook (if provided)
    ctx_messages = messages
    if config.transform_context:
        ctx_messages = await config.transform_context(list(messages))

    # Apply convert_to_llm hook (always)
    llm_messages = config.convert_to_llm(ctx_messages)

    llm_context = Context(
        system_prompt=context.system_prompt,
        messages=llm_messages,
        tools=ai_tools,
    )

    stream_options = config.options or StreamOptions()
    if config.abort_signal:
        stream_options = StreamOptions(
            temperature=stream_options.temperature,
            max_tokens=stream_options.max_tokens,
            api_key=stream_options.api_key,
            reasoning=stream_options.reasoning,
            abort_signal=config.abort_signal,
        )

    partial_message: AssistantMessage | None = None
    added_partial = False

    stream_function = config.stream_fn or stream_simple
    async for event in stream_function(config.model, llm_context, stream_options):
        if config.abort_signal and config.abort_signal.is_set():
            break

        if event.type == "start":
            partial_message = event.partial
            messages.append(partial_message)
            added_partial = True
            yield MessageStartEvent(message=partial_message)

        elif event.type in (
            "text_start", "text_delta", "text_end",
            "thinking_start", "thinking_delta", "thinking_end",
            "toolcall_start", "toolcall_delta", "toolcall_end",
        ):
            if partial_message:
                partial_message = event.partial
                messages[-1] = partial_message
                yield MessageUpdateEvent(message=partial_message, assistant_message_event=event)

        elif event.type in ("done", "error"):
            final_message = event.message if event.type == "done" else event.error
            if added_partial:
                messages[-1] = final_message
            else:
                messages.append(final_message)
            if not added_partial:
                yield MessageStartEvent(message=final_message)
            yield MessageEndEvent(message=final_message)
            return

    # Fallback if stream ends without done/error
    if partial_message:
        yield MessageEndEvent(message=partial_message)


def _skip_tool_call(tc: ToolCall) -> tuple[list[AgentEvent], ToolResultMessage]:
    """Generate synthetic result + events for a skipped tool call."""
    result = AgentToolResult(
        content=[TextContent(text="Skipped due to queued user message.")],
        details={},
    )

    events: list[AgentEvent] = [
        ToolExecutionStartEvent(
            tool_call_id=tc.id,
            tool_name=tc.name,
            args=tc.arguments,
        ),
        ToolExecutionEndEvent(
            tool_call_id=tc.id,
            tool_name=tc.name,
            result=result,
            is_error=True,
        ),
    ]

    tool_result_msg = ToolResultMessage(
        tool_call_id=tc.id,
        tool_name=tc.name,
        content=result.content,
        details=result.details,
        is_error=True,
        timestamp=int(time.time() * 1000),
    )

    events.append(MessageStartEvent(message=tool_result_msg))
    events.append(MessageEndEvent(message=tool_result_msg))

    return events, tool_result_msg


async def _execute_tool_calls(
    tools: list[AgentTool],
    assistant_message: AssistantMessage,
    tool_calls: list[ToolCall],
    config: AgentLoopConfig,
) -> _ToolExecutionResult:
    """Execute tool calls, checking for steering interruption between each."""
    exec_result = _ToolExecutionResult()

    for i, tc in enumerate(tool_calls):
        # Abort check before each tool
        if config.abort_signal and config.abort_signal.is_set():
            for remaining_tc in tool_calls[i:]:
                skip_events, skip_msg = _skip_tool_call(remaining_tc)
                exec_result.events.extend(skip_events)
                exec_result.tool_results.append(skip_msg)
            break

        tool = next((t for t in tools if t.name == tc.name), None)

        exec_result.events.append(ToolExecutionStartEvent(
            tool_call_id=tc.id,
            tool_name=tc.name,
            args=tc.arguments,
        ))

        result: AgentToolResult
        is_error = False

        try:
            if not tool:
                raise ValueError(f"Tool {tc.name} not found")

            # Validate arguments
            from pi_ai.types import Tool as AiTool
            ai_tool = AiTool(name=tool.name, description=tool.description, parameters=tool.parameters)
            validated_args = validate_tool_arguments(ai_tool, tc)

            result = await tool.execute(
                tc.id,
                validated_args,
                on_update=lambda partial: None,
                abort_signal=config.abort_signal,
            )
        except Exception as e:
            result = AgentToolResult(
                content=[TextContent(text=str(e))],
                details={},
            )
            is_error = True

        exec_result.events.append(ToolExecutionEndEvent(
            tool_call_id=tc.id,
            tool_name=tc.name,
            result=result,
            is_error=is_error,
        ))

        tool_result_msg = ToolResultMessage(
            tool_call_id=tc.id,
            tool_name=tc.name,
            content=result.content,
            details=result.details,
            is_error=is_error,
            timestamp=int(time.time() * 1000),
        )

        exec_result.events.append(MessageStartEvent(message=tool_result_msg))
        exec_result.events.append(MessageEndEvent(message=tool_result_msg))
        exec_result.tool_results.append(tool_result_msg)

        # Check steering after each tool (except the last)
        if config.get_steering_messages and i < len(tool_calls) - 1:
            steering = await config.get_steering_messages()
            if steering:
                # Skip remaining tool calls
                for remaining_tc in tool_calls[i + 1:]:
                    skip_events, skip_msg = _skip_tool_call(remaining_tc)
                    exec_result.events.extend(skip_events)
                    exec_result.tool_results.append(skip_msg)
                exec_result.steering_messages = steering
                break

    return exec_result
