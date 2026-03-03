"""Agent loop — async generator that drives LLM → tool → loop cycles."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
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


async def _run_loop(
    context: AgentContext,
    config: AgentLoopConfig,
    messages: list[Message],
    new_messages: list[Message],
    first_turn: bool = True,
) -> AsyncIterator[AgentEvent]:
    """Main loop: stream LLM response, execute tools, repeat."""
    tools = context.tools or []

    while True:
        if not first_turn:
            yield TurnStartEvent()
        first_turn = False

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

        if not tool_calls:
            yield TurnEndEvent(message=assistant_msg, tool_results=[])
            yield AgentEndEvent(messages=new_messages)
            return

        # Execute tool calls
        tool_results: list[ToolResultMessage] = []
        async for event in _execute_tool_calls(tools, assistant_msg, tool_calls):
            yield event
            if isinstance(event, MessageEndEvent) and isinstance(event.message, ToolResultMessage):
                tool_results.append(event.message)
                messages.append(event.message)
                new_messages.append(event.message)

        yield TurnEndEvent(message=assistant_msg, tool_results=tool_results)


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

    partial_message: AssistantMessage | None = None
    added_partial = False

    async for event in stream_simple(config.model, llm_context, config.options):
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


async def _execute_tool_calls(
    tools: list[AgentTool],
    assistant_message: AssistantMessage,
    tool_calls: list[ToolCall],
) -> AsyncIterator[AgentEvent]:
    """Execute tool calls from an assistant message."""
    for tc in tool_calls:
        tool = next((t for t in tools if t.name == tc.name), None)

        yield ToolExecutionStartEvent(
            tool_call_id=tc.id,
            tool_name=tc.name,
            args=tc.arguments,
        )

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
                on_update=lambda partial: None,  # Simplified: no streaming updates in benchmark
            )
        except Exception as e:
            result = AgentToolResult(
                content=[TextContent(text=str(e))],
                details={},
            )
            is_error = True

        yield ToolExecutionEndEvent(
            tool_call_id=tc.id,
            tool_name=tc.name,
            result=result,
            is_error=is_error,
        )

        tool_result_msg = ToolResultMessage(
            tool_call_id=tc.id,
            tool_name=tc.name,
            content=result.content,
            details=result.details,
            is_error=is_error,
            timestamp=int(time.time() * 1000),
        )

        yield MessageStartEvent(message=tool_result_msg)
        yield MessageEndEvent(message=tool_result_msg)
