"""Google Generative AI (Gemini) provider — async generator streaming."""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai.types import (
    Content,
    FunctionCallingConfig,
    FunctionDeclaration,
    GenerateContentConfig,
    Part,
    ThinkingConfig,
    Tool as GoogleTool,
    ToolConfig,
)

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
    ImageContent,
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

_tool_call_counter = 0


def _normalize_tool_call_id(id_: str, model: Model, source: AssistantMessage) -> str:
    """Google APIs require tool call IDs matching [a-zA-Z0-9_-] (max 64 chars)."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", id_)[:64]


def _convert_messages(model: Model, context: Context) -> list[Content]:
    """Convert Context messages to Google Generative AI Content format."""
    contents: list[Content] = []

    transformed = transform_messages(context.messages, model, _normalize_tool_call_id)

    for msg in transformed:
        if msg.role == "user":
            parts: list[Part] = []
            if isinstance(msg.content, str):
                parts.append(Part(text=msg.content))
            else:
                for item in msg.content:
                    if item.type == "text":
                        parts.append(Part(text=item.text))
                    elif item.type == "image":
                        parts.append(Part(
                            inline_data={"mime_type": item.mime_type, "data": item.data}
                        ))
            if parts:
                contents.append(Content(role="user", parts=parts))

        elif msg.role == "assistant":
            parts = []
            for block in msg.content:
                if block.type == "text":
                    parts.append(Part(text=block.text))
                elif block.type == "thinking":
                    parts.append(Part(text=block.thinking, thought=True))
                elif block.type == "toolCall":
                    parts.append(Part(
                        function_call={"name": block.name, "args": block.arguments}
                    ))
            if parts:
                contents.append(Content(role="model", parts=parts))

        elif msg.role == "toolResult":
            text_parts = [c.text for c in msg.content if c.type == "text"]
            result_text = "\n".join(text_parts) if text_parts else "(no output)"
            parts = [Part(
                function_response={"name": msg.tool_name, "response": {"result": result_text}}
            )]
            contents.append(Content(role="user", parts=parts))

    return contents


def _convert_tools(tools: list) -> list[GoogleTool]:
    """Convert Tool objects to Google tool format."""
    declarations = []
    for tool in tools:
        schema = tool.parameters
        declarations.append(FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters=schema,
        ))
    return [GoogleTool(function_declarations=declarations)]


def _map_stop_reason(reason: str | None) -> str:
    """Map Google finish reason to our StopReason."""
    if not reason:
        return "stop"
    mapping = {
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "error",
        "RECITATION": "error",
        "FINISH_REASON_UNSPECIFIED": "stop",
    }
    return mapping.get(reason, "stop")


def _is_thinking_part(part: Any) -> bool:
    """Check if a part is a thinking part."""
    return getattr(part, "thought", False) is True


async def stream(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
) -> AsyncIterator[AssistantMessageEvent]:
    """Stream responses from Google Generative AI as an async generator."""
    global _tool_call_counter
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
        api_key = options.api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("Google API key required. Set GOOGLE_API_KEY or GEMINI_API_KEY or pass api_key.")

        client = genai.Client(api_key=api_key)

        contents = _convert_messages(model, context)

        config = GenerateContentConfig()
        if options.temperature is not None:
            config.temperature = options.temperature
        if options.max_tokens is not None:
            config.max_output_tokens = options.max_tokens
        if context.system_prompt:
            config.system_instruction = context.system_prompt
        if context.tools:
            config.tools = _convert_tools(context.tools)

        # Thinking configuration
        if model.reasoning and options.reasoning:
            thinking_config = ThinkingConfig(include_thoughts=True)

            if "3-flash" in model.id or "3-pro" in model.id:
                level_map = {"minimal": "MINIMAL", "low": "LOW", "medium": "MEDIUM", "high": "HIGH"}
                if "3-pro" in model.id:
                    level_map = {"minimal": "LOW", "low": "LOW", "medium": "HIGH", "high": "HIGH"}
                # Clamp xhigh to high
                level = options.reasoning if options.reasoning != "xhigh" else "high"
                thinking_config.thinking_level = level_map.get(level, "MEDIUM")
            elif "2.5-pro" in model.id:
                budget_map = {"minimal": 128, "low": 2048, "medium": 8192, "high": 32768}
                level = options.reasoning if options.reasoning != "xhigh" else "high"
                thinking_config.thinking_budget = budget_map.get(level, 8192)
            elif "2.5-flash" in model.id:
                budget_map = {"minimal": 128, "low": 2048, "medium": 8192, "high": 24576}
                level = options.reasoning if options.reasoning != "xhigh" else "high"
                thinking_config.thinking_budget = budget_map.get(level, 8192)
            else:
                thinking_config.thinking_budget = -1  # dynamic

            config.thinking_config = thinking_config

        google_stream = client.models.generate_content_stream(
            model=model.id,
            contents=contents,
            config=config,
        )

        yield StartEvent(partial=output)

        current_block: TextContent | ThinkingContent | None = None

        for chunk in google_stream:
            candidate = chunk.candidates[0] if chunk.candidates else None
            if candidate and candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.text is not None:
                        is_thinking = _is_thinking_part(part)

                        # Check if we need to start a new block
                        if (
                            current_block is None
                            or (is_thinking and not isinstance(current_block, ThinkingContent))
                            or (not is_thinking and not isinstance(current_block, TextContent))
                        ):
                            # End current block
                            if current_block is not None:
                                idx = len(output.content) - 1
                                if isinstance(current_block, TextContent):
                                    yield TextEndEvent(content_index=idx, content=current_block.text, partial=output)
                                else:
                                    yield ThinkingEndEvent(content_index=idx, content=current_block.thinking, partial=output)

                            # Start new block
                            if is_thinking:
                                current_block = ThinkingContent(thinking="")
                                output.content.append(current_block)
                                yield ThinkingStartEvent(content_index=len(output.content) - 1, partial=output)
                            else:
                                current_block = TextContent(text="")
                                output.content.append(current_block)
                                yield TextStartEvent(content_index=len(output.content) - 1, partial=output)

                        # Append text
                        if isinstance(current_block, ThinkingContent):
                            current_block.thinking += part.text
                            sig = getattr(part, "thought_signature", None)
                            if sig:
                                current_block.thinking_signature = sig
                            yield ThinkingDeltaEvent(
                                content_index=len(output.content) - 1,
                                delta=part.text,
                                partial=output,
                            )
                        else:
                            current_block.text += part.text
                            yield TextDeltaEvent(
                                content_index=len(output.content) - 1,
                                delta=part.text,
                                partial=output,
                            )

                    if part.function_call:
                        # End current text/thinking block
                        if current_block is not None:
                            idx = len(output.content) - 1
                            if isinstance(current_block, TextContent):
                                yield TextEndEvent(content_index=idx, content=current_block.text, partial=output)
                            else:
                                yield ThinkingEndEvent(content_index=idx, content=current_block.thinking, partial=output)
                            current_block = None

                        # Generate unique ID
                        fc = part.function_call
                        provided_id = getattr(fc, "id", None)
                        _tool_call_counter += 1
                        tool_call_id = provided_id or f"{fc.name}_{int(time.time())}_{_tool_call_counter}"

                        # Check for duplicate IDs
                        existing_ids = {b.id for b in output.content if isinstance(b, ToolCall)}
                        if tool_call_id in existing_ids:
                            _tool_call_counter += 1
                            tool_call_id = f"{fc.name}_{int(time.time())}_{_tool_call_counter}"

                        args = dict(fc.args) if fc.args else {}
                        tc = ToolCall(
                            id=tool_call_id,
                            name=fc.name or "",
                            arguments=args,
                        )
                        output.content.append(tc)
                        idx = len(output.content) - 1
                        yield ToolCallStartEvent(content_index=idx, partial=output)
                        yield ToolCallDeltaEvent(content_index=idx, delta=json.dumps(args), partial=output)
                        yield ToolCallEndEvent(content_index=idx, tool_call=tc, partial=output)

            if candidate and candidate.finish_reason:
                output.stop_reason = _map_stop_reason(candidate.finish_reason)
                if any(isinstance(b, ToolCall) for b in output.content):
                    output.stop_reason = "toolUse"

            if chunk.usage_metadata:
                um = chunk.usage_metadata
                thoughts_tokens = getattr(um, "thoughts_token_count", 0) or 0
                output.usage = Usage(
                    input=um.prompt_token_count or 0,
                    output=(um.candidates_token_count or 0) + thoughts_tokens,
                    cache_read=getattr(um, "cached_content_token_count", 0) or 0,
                    cache_write=0,
                    total_tokens=um.total_token_count or 0,
                    cost=Cost(),
                )
                calculate_cost(model, output.usage)

        # End final block
        if current_block is not None:
            idx = len(output.content) - 1
            if isinstance(current_block, TextContent):
                yield TextEndEvent(content_index=idx, content=current_block.text, partial=output)
            else:
                yield ThinkingEndEvent(content_index=idx, content=current_block.thinking, partial=output)

        yield DoneEvent(reason=output.stop_reason, message=output)

    except Exception as e:
        output.stop_reason = "error"
        output.error_message = str(e)
        yield ErrorEvent(reason="error", error=output)
