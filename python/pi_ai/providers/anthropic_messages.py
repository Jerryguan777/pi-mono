"""Anthropic Messages API provider — async generator streaming."""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any

import anthropic

import re

from pi_ai.models import calculate_cost
from pi_ai.transform_messages import transform_messages
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    Cost,
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
)


def _parse_streaming_json(s: str) -> dict:
    """Best-effort parse of partial JSON."""
    if not s:
        return {}
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        for ch in ["}", "]"]:
            try:
                return json.loads(s + ch)
            except json.JSONDecodeError:
                pass
        return {}


def _normalize_tool_call_id(id_: str, model: Model, source: AssistantMessage) -> str:
    """Anthropic requires tool call IDs matching ^[a-zA-Z0-9_-]+$ (max 64 chars)."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", id_)[:64]


def _convert_messages(context: Context, model: Model) -> list[dict[str, Any]]:
    """Convert Context messages to Anthropic MessageParam format."""
    params: list[dict[str, Any]] = []

    transformed = transform_messages(context.messages, model, _normalize_tool_call_id)

    for i, msg in enumerate(transformed):
        if msg.role == "user":
            if isinstance(msg.content, str):
                if msg.content.strip():
                    params.append({"role": "user", "content": msg.content})
            else:
                blocks = []
                for item in msg.content:
                    if item.type == "text":
                        if item.text.strip():
                            blocks.append({"type": "text", "text": item.text})
                    elif item.type == "image":
                        blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": item.mime_type,
                                "data": item.data,
                            },
                        })
                if blocks:
                    params.append({"role": "user", "content": blocks})

        elif msg.role == "assistant":
            blocks = []
            for block in msg.content:
                if block.type == "text":
                    if block.text.strip():
                        blocks.append({"type": "text", "text": block.text})
                elif block.type == "thinking":
                    if block.thinking.strip():
                        if block.thinking_signature and block.thinking_signature.strip():
                            blocks.append({
                                "type": "thinking",
                                "thinking": block.thinking,
                                "signature": block.thinking_signature,
                            })
                        else:
                            blocks.append({"type": "text", "text": block.thinking})
                elif block.type == "toolCall":
                    blocks.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.arguments or {},
                    })
            if blocks:
                params.append({"role": "assistant", "content": blocks})

        elif msg.role == "toolResult":
            # Collect consecutive tool results into one user message
            tool_results = []
            text_parts = [c.text for c in msg.content if c.type == "text"]
            text_content = "\n".join(text_parts) if text_parts else ""
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": msg.tool_call_id,
                "content": text_content if text_content else "(no output)",
                "is_error": msg.is_error,
            })
            params.append({"role": "user", "content": tool_results})

    return params


def _convert_tools(tools: list) -> list[dict[str, Any]]:
    """Convert Tool objects to Anthropic tool format."""
    result = []
    for tool in tools:
        schema = tool.parameters
        result.append({
            "name": tool.name,
            "description": tool.description,
            "input_schema": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            },
        })
    return result


def _map_stop_reason(reason: str) -> str:
    """Map Anthropic stop reason to our StopReason."""
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "tool_use": "toolUse",
        "refusal": "error",
        "pause_turn": "stop",
        "stop_sequence": "stop",
    }
    return mapping.get(reason, "stop")


def _supports_adaptive_thinking(model_id: str) -> bool:
    """Check if model supports adaptive thinking (Opus 4.6+)."""
    return "opus-4-6" in model_id or "opus-4.6" in model_id


async def stream(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
) -> AsyncIterator[AssistantMessageEvent]:
    """Stream responses from Anthropic Messages API as an async generator."""
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
        api_key = options.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY or pass api_key.")

        beta_features = ["interleaved-thinking-2025-05-14"]
        client = anthropic.AsyncAnthropic(
            api_key=api_key,
            base_url=model.base_url if model.base_url else None,
            default_headers={
                "anthropic-beta": ",".join(beta_features),
            },
        )

        messages = _convert_messages(context, model)

        params: dict[str, Any] = {
            "model": model.id,
            "messages": messages,
            "max_tokens": options.max_tokens or (model.max_tokens // 3),
        }

        if context.system_prompt:
            params["system"] = [{"type": "text", "text": context.system_prompt}]

        if options.temperature is not None:
            params["temperature"] = options.temperature

        if context.tools:
            params["tools"] = _convert_tools(context.tools)

        # Thinking configuration
        if model.reasoning and options.reasoning:
            if _supports_adaptive_thinking(model.id):
                params["thinking"] = {"type": "adaptive"}
                effort_map = {"minimal": "low", "low": "low", "medium": "medium", "high": "high", "xhigh": "max"}
                effort = effort_map.get(options.reasoning, "high")
                params["output_config"] = {"effort": effort}
            else:
                budget_map = {"minimal": 1024, "low": 2048, "medium": 8192, "high": 32768, "xhigh": 32768}
                budget = budget_map.get(options.reasoning, 1024)
                params["thinking"] = {"type": "enabled", "budget_tokens": budget}

        anthropic_stream = client.messages.stream(**params)

        yield StartEvent(partial=output)

        # Track blocks by index
        blocks_by_index: dict[int, dict] = {}

        async with anthropic_stream as stream_ctx:
            async for event in stream_ctx:
                if options.abort_signal and options.abort_signal.is_set():
                    output.stop_reason = "aborted"
                    yield DoneEvent(reason="aborted", message=output)
                    return

                if event.type == "message_start":
                    msg = event.message
                    output.usage.input = msg.usage.input_tokens or 0
                    output.usage.output = msg.usage.output_tokens or 0
                    output.usage.cache_read = getattr(msg.usage, "cache_read_input_tokens", 0) or 0
                    output.usage.cache_write = getattr(msg.usage, "cache_creation_input_tokens", 0) or 0
                    output.usage.total_tokens = (
                        output.usage.input + output.usage.output
                        + output.usage.cache_read + output.usage.cache_write
                    )
                    calculate_cost(model, output.usage)

                elif event.type == "content_block_start":
                    cb = event.content_block
                    idx = event.index

                    if cb.type == "text":
                        block = TextContent(text="")
                        output.content.append(block)
                        blocks_by_index[idx] = {"type": "text", "content_idx": len(output.content) - 1}
                        yield TextStartEvent(content_index=len(output.content) - 1, partial=output)

                    elif cb.type == "thinking":
                        block = ThinkingContent(thinking="")
                        output.content.append(block)
                        blocks_by_index[idx] = {"type": "thinking", "content_idx": len(output.content) - 1}
                        yield ThinkingStartEvent(content_index=len(output.content) - 1, partial=output)

                    elif cb.type == "tool_use":
                        tc = ToolCall(
                            id=cb.id,
                            name=cb.name,
                            arguments=cb.input if isinstance(cb.input, dict) else {},
                        )
                        output.content.append(tc)
                        blocks_by_index[idx] = {
                            "type": "toolCall",
                            "content_idx": len(output.content) - 1,
                            "partial_json": "",
                        }
                        yield ToolCallStartEvent(content_index=len(output.content) - 1, partial=output)

                elif event.type == "content_block_delta":
                    idx = event.index
                    info = blocks_by_index.get(idx)
                    if not info:
                        continue

                    content_idx = info["content_idx"]

                    if event.delta.type == "text_delta":
                        block = output.content[content_idx]
                        if isinstance(block, TextContent):
                            block.text += event.delta.text
                            yield TextDeltaEvent(content_index=content_idx, delta=event.delta.text, partial=output)

                    elif event.delta.type == "thinking_delta":
                        block = output.content[content_idx]
                        if isinstance(block, ThinkingContent):
                            block.thinking += event.delta.thinking
                            yield ThinkingDeltaEvent(content_index=content_idx, delta=event.delta.thinking, partial=output)

                    elif event.delta.type == "input_json_delta":
                        block = output.content[content_idx]
                        if isinstance(block, ToolCall):
                            info["partial_json"] += event.delta.partial_json
                            block.arguments = _parse_streaming_json(info["partial_json"])
                            yield ToolCallDeltaEvent(
                                content_index=content_idx,
                                delta=event.delta.partial_json,
                                partial=output,
                            )

                    elif event.delta.type == "signature_delta":
                        block = output.content[content_idx]
                        if isinstance(block, ThinkingContent):
                            block.thinking_signature = (block.thinking_signature or "") + event.delta.signature

                elif event.type == "content_block_stop":
                    idx = event.index
                    info = blocks_by_index.get(idx)
                    if not info:
                        continue

                    content_idx = info["content_idx"]
                    block = output.content[content_idx]

                    if info["type"] == "text" and isinstance(block, TextContent):
                        yield TextEndEvent(content_index=content_idx, content=block.text, partial=output)
                    elif info["type"] == "thinking" and isinstance(block, ThinkingContent):
                        yield ThinkingEndEvent(content_index=content_idx, content=block.thinking, partial=output)
                    elif info["type"] == "toolCall" and isinstance(block, ToolCall):
                        block.arguments = _parse_streaming_json(info.get("partial_json", ""))
                        yield ToolCallEndEvent(content_index=content_idx, tool_call=block, partial=output)

                elif event.type == "message_delta":
                    delta = event.delta
                    if hasattr(delta, "stop_reason") and delta.stop_reason:
                        output.stop_reason = _map_stop_reason(delta.stop_reason)

                    usage = event.usage
                    if hasattr(usage, "input_tokens") and usage.input_tokens is not None:
                        output.usage.input = usage.input_tokens
                    if hasattr(usage, "output_tokens") and usage.output_tokens is not None:
                        output.usage.output = usage.output_tokens
                    if hasattr(usage, "cache_read_input_tokens") and getattr(usage, "cache_read_input_tokens", None) is not None:
                        output.usage.cache_read = usage.cache_read_input_tokens
                    if hasattr(usage, "cache_creation_input_tokens") and getattr(usage, "cache_creation_input_tokens", None) is not None:
                        output.usage.cache_write = usage.cache_creation_input_tokens

                    output.usage.total_tokens = (
                        output.usage.input + output.usage.output
                        + output.usage.cache_read + output.usage.cache_write
                    )
                    calculate_cost(model, output.usage)

        if options.abort_signal and options.abort_signal.is_set():
            output.stop_reason = "aborted"
            yield DoneEvent(reason="aborted", message=output)
            return

        yield DoneEvent(reason=output.stop_reason, message=output)

    except Exception as e:
        output.stop_reason = "aborted" if (options.abort_signal and options.abort_signal.is_set()) else "error"
        output.error_message = str(e)
        yield ErrorEvent(reason="error", error=output)
