"""OpenAI Responses API provider — async generator streaming."""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any

import openai

from pi_ai.models import calculate_cost
from pi_ai.transform_messages import transform_messages
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    DoneEvent,
    ErrorEvent,
    Model,
    StartEvent,
    StreamOptions,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ThinkingContent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    ToolCall,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    Usage,
    Cost,
)


def _parse_streaming_json(s: str) -> dict:
    """Best-effort parse of partial JSON."""
    if not s:
        return {}
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # Try closing braces
        attempt = s
        for ch in ["}", "]"]:
            try:
                return json.loads(attempt + ch)
            except json.JSONDecodeError:
                pass
        return {}


def _convert_messages(model: Model, context: Context) -> list[dict[str, Any]]:
    """Convert Context messages to OpenAI Responses API input format."""
    messages: list[dict[str, Any]] = []

    # System prompt
    if context.system_prompt:
        role = "developer" if model.reasoning else "system"
        messages.append({"role": role, "content": context.system_prompt})

    transformed = transform_messages(context.messages, model)

    for msg in transformed:
        if msg.role == "user":
            if isinstance(msg.content, str):
                messages.append({
                    "role": "user",
                    "content": [{"type": "input_text", "text": msg.content}],
                })
            else:
                content_parts = []
                for item in msg.content:
                    if item.type == "text":
                        content_parts.append({"type": "input_text", "text": item.text})
                    elif item.type == "image":
                        content_parts.append({
                            "type": "input_image",
                            "detail": "auto",
                            "image_url": f"data:{item.mime_type};base64,{item.data}",
                        })
                if content_parts:
                    messages.append({"role": "user", "content": content_parts})

        elif msg.role == "assistant":
            for block in msg.content:
                if block.type == "thinking":
                    if block.thinking_signature:
                        try:
                            reasoning_item = json.loads(block.thinking_signature)
                            # Only include fields the API accepts as input
                            allowed = {"id", "type", "encrypted_content", "summary"}
                            filtered = {
                                k: v for k, v in reasoning_item.items()
                                if k in allowed
                            }
                            messages.append(filtered)
                        except json.JSONDecodeError:
                            pass
                elif block.type == "text":
                    msg_id = block.text_signature or f"msg_{len(messages)}"
                    messages.append({
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": block.text, "annotations": []}],
                        "status": "completed",
                        "id": msg_id,
                    })
                elif block.type == "toolCall":
                    call_id, _, item_id = block.id.partition("|")
                    messages.append({
                        "type": "function_call",
                        "id": item_id or None,
                        "call_id": call_id,
                        "name": block.name,
                        "arguments": json.dumps(block.arguments),
                    })

        elif msg.role == "toolResult":
            text_parts = [c.text for c in msg.content if c.type == "text"]
            text_result = "\n".join(text_parts) if text_parts else "(no output)"
            call_id = msg.tool_call_id.split("|")[0]
            messages.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": text_result,
            })

    return messages


def _convert_tools(tools: list) -> list[dict[str, Any]]:
    """Convert Tool objects to OpenAI function tool format."""
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "strict": False,
        }
        for tool in tools
    ]


async def stream(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
) -> AsyncIterator[AssistantMessageEvent]:
    """Stream responses from OpenAI Responses API as an async generator."""
    options = options or StreamOptions()

    output = AssistantMessage(
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        stop_reason="stop",
        timestamp=int(time.time() * 1000),
    )

    try:
        api_key = options.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY or pass api_key.")

        client = openai.AsyncOpenAI(api_key=api_key, base_url=model.base_url or None)

        input_messages = _convert_messages(model, context)

        params: dict[str, Any] = {
            "model": model.id,
            "input": input_messages,
            "stream": True,
            "store": False,
        }

        if options.max_tokens:
            params["max_output_tokens"] = options.max_tokens

        if options.temperature is not None:
            params["temperature"] = options.temperature

        if context.tools:
            params["tools"] = _convert_tools(context.tools)

        # Reasoning configuration
        if model.reasoning and options.reasoning:
            effort_map = {"minimal": "low", "low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh"}
            effort = effort_map.get(options.reasoning, "medium")
            # Clamp xhigh for models that don't support it
            if effort == "xhigh" and not (model.id.startswith("gpt-5.2") or model.id.startswith("gpt-5.3")):
                effort = "high"
            params["reasoning"] = {"effort": effort, "summary": "auto"}
            params["include"] = ["reasoning.encrypted_content"]

        openai_stream = await client.responses.create(**params)

        yield StartEvent(partial=output)

        # Track current item/block for streaming
        current_block: TextContent | ThinkingContent | dict | None = None

        async for event in openai_stream:
            if options.abort_signal and options.abort_signal.is_set():
                output.stop_reason = "aborted"
                yield DoneEvent(reason="aborted", message=output)
                return

            if event.type == "response.output_item.added":
                item = event.item
                if item.type == "reasoning":
                    current_block = ThinkingContent(thinking="")
                    output.content.append(current_block)
                    yield ThinkingStartEvent(content_index=len(output.content) - 1, partial=output)
                elif item.type == "message":
                    current_block = TextContent(text="")
                    output.content.append(current_block)
                    yield TextStartEvent(content_index=len(output.content) - 1, partial=output)
                elif item.type == "function_call":
                    tc = ToolCall(
                        id=f"{item.call_id}|{item.id}",
                        name=item.name,
                        arguments={},
                    )
                    current_block = {"tool_call": tc, "partial_json": item.arguments or ""}
                    output.content.append(tc)
                    yield ToolCallStartEvent(content_index=len(output.content) - 1, partial=output)

            elif event.type == "response.reasoning_summary_text.delta":
                if current_block and isinstance(current_block, ThinkingContent):
                    current_block.thinking += event.delta
                    yield ThinkingDeltaEvent(
                        content_index=len(output.content) - 1,
                        delta=event.delta,
                        partial=output,
                    )

            elif event.type == "response.output_text.delta":
                if current_block and isinstance(current_block, TextContent):
                    current_block.text += event.delta
                    yield TextDeltaEvent(
                        content_index=len(output.content) - 1,
                        delta=event.delta,
                        partial=output,
                    )

            elif event.type == "response.function_call_arguments.delta":
                if current_block and isinstance(current_block, dict):
                    current_block["partial_json"] += event.delta
                    current_block["tool_call"].arguments = _parse_streaming_json(current_block["partial_json"])
                    yield ToolCallDeltaEvent(
                        content_index=len(output.content) - 1,
                        delta=event.delta,
                        partial=output,
                    )

            elif event.type == "response.output_item.done":
                item = event.item
                idx = len(output.content) - 1

                if item.type == "reasoning" and isinstance(current_block, ThinkingContent):
                    summary_parts = getattr(item, "summary", None) or []
                    current_block.thinking = "\n\n".join(
                        getattr(s, "text", "") for s in summary_parts
                    ) if summary_parts else current_block.thinking
                    current_block.thinking_signature = json.dumps(item.model_dump()) if hasattr(item, "model_dump") else None
                    yield ThinkingEndEvent(content_index=idx, content=current_block.thinking, partial=output)
                    current_block = None

                elif item.type == "message" and isinstance(current_block, TextContent):
                    parts = getattr(item, "content", []) or []
                    current_block.text = "".join(
                        getattr(c, "text", "") if getattr(c, "type", "") == "output_text" else getattr(c, "refusal", "")
                        for c in parts
                    )
                    current_block.text_signature = getattr(item, "id", None)
                    yield TextEndEvent(content_index=idx, content=current_block.text, partial=output)
                    current_block = None

                elif item.type == "function_call":
                    if isinstance(current_block, dict):
                        tc = current_block["tool_call"]
                        tc.arguments = _parse_streaming_json(
                            current_block["partial_json"] or getattr(item, "arguments", "{}") or "{}"
                        )
                        yield ToolCallEndEvent(content_index=idx, tool_call=tc, partial=output)
                        current_block = None

            elif event.type == "response.completed":
                response = event.response
                if response and response.usage:
                    cached = 0
                    if hasattr(response.usage, "input_tokens_details") and response.usage.input_tokens_details:
                        cached = getattr(response.usage.input_tokens_details, "cached_tokens", 0) or 0
                    output.usage = Usage(
                        input=(response.usage.input_tokens or 0) - cached,
                        output=response.usage.output_tokens or 0,
                        cache_read=cached,
                        cache_write=0,
                        total_tokens=response.usage.total_tokens or 0,
                        cost=Cost(),
                    )
                    calculate_cost(model, output.usage)

                # Map status
                status = getattr(response, "status", "completed") if response else "completed"
                status_map = {"completed": "stop", "incomplete": "length", "failed": "error", "cancelled": "error"}
                output.stop_reason = status_map.get(status, "stop")

                if any(b.type == "toolCall" for b in output.content) and output.stop_reason == "stop":
                    output.stop_reason = "toolUse"

            elif event.type == "error":
                raise RuntimeError(f"Error {getattr(event, 'code', '?')}: {getattr(event, 'message', 'Unknown')}")

        if options.abort_signal and options.abort_signal.is_set():
            output.stop_reason = "aborted"
            yield DoneEvent(reason="aborted", message=output)
            return

        yield DoneEvent(reason=output.stop_reason, message=output)

    except Exception as e:
        output.stop_reason = "aborted" if (options.abort_signal and options.abort_signal.is_set()) else "error"
        output.error_message = str(e)
        yield ErrorEvent(reason="error", error=output)
