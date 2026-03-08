"""Message transformation for cross-provider compatibility.

Ported from packages/ai/src/providers/transform-messages.ts.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from pi_ai.types import (
    AssistantMessage,
    Message,
    Model,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
)


def transform_messages(
    messages: list[Message],
    model: Model,
    normalize_tool_call_id: Callable[[str], str] | None = None,
) -> list[Message]:
    """Transform messages for cross-provider compatibility.

    Handles thinking block conversion and tool call ID normalization.
    """
    tool_call_id_map: dict[str, str] = {}

    # First pass: transform messages
    transformed: list[Message] = []
    for msg in messages:
        if msg.role == "user":
            transformed.append(msg)
        elif msg.role == "toolResult":
            assert isinstance(msg, ToolResultMessage)
            normalized_id = tool_call_id_map.get(msg.tool_call_id)
            if normalized_id and normalized_id != msg.tool_call_id:
                transformed.append(
                    ToolResultMessage(
                        tool_call_id=normalized_id,
                        tool_name=msg.tool_name,
                        content=msg.content,
                        details=msg.details,
                        is_error=msg.is_error,
                        timestamp=msg.timestamp,
                    )
                )
            else:
                transformed.append(msg)
        elif msg.role == "assistant":
            assert isinstance(msg, AssistantMessage)
            is_same_model = msg.provider == model.provider and msg.api == model.api and msg.model == model.id

            new_content: list[TextContent | ThinkingContent | ToolCall] = []
            for block in msg.content:
                if isinstance(block, ThinkingContent):
                    # For same model: keep thinking blocks with signatures
                    if is_same_model and block.thinking_signature:
                        new_content.append(block)
                    elif not block.thinking or block.thinking.strip() == "":
                        continue  # Skip empty thinking blocks
                    elif is_same_model:
                        new_content.append(block)
                    else:
                        new_content.append(TextContent(text=block.thinking))
                elif isinstance(block, TextContent):
                    if is_same_model:
                        new_content.append(block)
                    else:
                        new_content.append(TextContent(text=block.text))
                elif isinstance(block, ToolCall):
                    normalized_tool_call = block

                    if not is_same_model and block.thought_signature:
                        normalized_tool_call = ToolCall(
                            id=block.id,
                            name=block.name,
                            arguments=block.arguments,
                        )

                    if not is_same_model and normalize_tool_call_id:
                        normalized_id = normalize_tool_call_id(block.id)
                        if normalized_id != block.id:
                            tool_call_id_map[block.id] = normalized_id
                            normalized_tool_call = ToolCall(
                                id=normalized_id,
                                name=normalized_tool_call.name,
                                arguments=normalized_tool_call.arguments,
                                thought_signature=normalized_tool_call.thought_signature,
                            )

                    new_content.append(normalized_tool_call)

            transformed.append(
                AssistantMessage(
                    content=new_content,
                    api=msg.api,
                    provider=msg.provider,
                    model=msg.model,
                    usage=msg.usage,
                    stop_reason=msg.stop_reason,
                    error_message=msg.error_message,
                    timestamp=msg.timestamp,
                )
            )
        else:
            transformed.append(msg)

    # Second pass: insert synthetic empty tool results for orphaned tool calls
    result: list[Message] = []
    pending_tool_calls: list[ToolCall] = []
    existing_tool_result_ids: set[str] = set()

    def _flush_orphaned_tool_calls() -> None:
        nonlocal pending_tool_calls, existing_tool_result_ids
        for tc in pending_tool_calls:
            if tc.id not in existing_tool_result_ids:
                result.append(
                    ToolResultMessage(
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        content=[TextContent(text="No result provided")],
                        is_error=True,
                        timestamp=int(time.time() * 1000),
                    )
                )
        pending_tool_calls = []
        existing_tool_result_ids = set()

    for tmsg in transformed:
        if tmsg.role == "assistant":
            assert isinstance(tmsg, AssistantMessage)
            if pending_tool_calls:
                _flush_orphaned_tool_calls()

            # Skip errored/aborted assistant messages
            if tmsg.stop_reason in ("error", "aborted"):
                continue

            tool_calls = [b for b in tmsg.content if isinstance(b, ToolCall)]
            if tool_calls:
                pending_tool_calls = tool_calls
                existing_tool_result_ids = set()

            result.append(tmsg)
        elif tmsg.role == "toolResult":
            assert isinstance(tmsg, ToolResultMessage)
            existing_tool_result_ids.add(tmsg.tool_call_id)
            result.append(tmsg)
        elif tmsg.role == "user":
            if pending_tool_calls:
                _flush_orphaned_tool_calls()
            result.append(tmsg)
        else:
            result.append(tmsg)

    return result
