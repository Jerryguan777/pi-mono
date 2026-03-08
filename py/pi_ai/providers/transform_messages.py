"""Message transformation utilities — ported from packages/ai/src/providers/transform-messages.ts."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

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
    messages: Sequence[Message],
    model: Model,
    normalize_tool_call_id: Callable[[str, Model, AssistantMessage], str] | None = None,
) -> list[Message]:
    """Transform messages for cross-provider compatibility.

    Performs two passes:
    1. Normalize thinking blocks, tool call IDs, and content for target model.
    2. Insert synthetic empty tool results for orphaned tool calls.

    Args:
        messages: Original conversation messages.
        model: Target model to transform messages for.
        normalize_tool_call_id: Optional callable to normalize tool call IDs.

    Returns:
        Transformed message list safe to send to the target model.
    """
    # Build map from original tool call IDs to normalized IDs
    tool_call_id_map: dict[str, str] = {}

    # --- First pass: transform content blocks and tool call IDs ---
    transformed: list[Message] = []
    for msg in messages:
        if msg.role == "user":
            transformed.append(msg)
            continue

        if msg.role == "toolResult":
            tool_result = msg
            normalized_id = tool_call_id_map.get(tool_result.tool_call_id)
            if normalized_id and normalized_id != tool_result.tool_call_id:
                new_tr = ToolResultMessage(
                    role="toolResult",
                    tool_call_id=normalized_id,
                    tool_name=tool_result.tool_name,
                    content=tool_result.content,
                    details=tool_result.details,
                    is_error=tool_result.is_error,
                    timestamp=tool_result.timestamp,
                )
                transformed.append(new_tr)
            else:
                transformed.append(msg)
            continue

        if msg.role == "assistant":
            assistant_msg = msg
            is_same_model = (
                assistant_msg.provider == model.provider
                and assistant_msg.api == model.api
                and assistant_msg.model == model.id
            )

            new_content: list[TextContent | ThinkingContent | ToolCall] = []
            for block in assistant_msg.content:
                if isinstance(block, ThinkingContent):
                    # Same model with signature: keep for replay even if empty text
                    if is_same_model and block.thinking_signature:
                        new_content.append(block)
                    elif not block.thinking or not block.thinking.strip():
                        pass  # drop empty thinking block
                    elif is_same_model:
                        new_content.append(block)
                    else:
                        # Convert to text for cross-provider replay
                        new_content.append(TextContent(type="text", text=block.thinking))

                elif isinstance(block, TextContent):
                    if is_same_model:
                        new_content.append(block)
                    else:
                        new_content.append(TextContent(type="text", text=block.text))

                elif isinstance(block, ToolCall):
                    normalized_tool_call = ToolCall(
                        type="toolCall",
                        id=block.id,
                        name=block.name,
                        arguments=block.arguments,
                        thought_signature=block.thought_signature,
                    )

                    # Remove thought_signature for cross-provider replay
                    if not is_same_model and normalized_tool_call.thought_signature:
                        normalized_tool_call.thought_signature = None

                    if normalize_tool_call_id is not None:
                        normalized_id = normalize_tool_call_id(block.id, model, assistant_msg)
                        if normalized_id != block.id:
                            tool_call_id_map[block.id] = normalized_id
                            normalized_tool_call.id = normalized_id

                    new_content.append(normalized_tool_call)

                else:
                    new_content.append(block)

            # Skip assistant messages with no remaining content
            if not new_content:
                continue

            new_assistant = AssistantMessage(
                role="assistant",
                content=new_content,
                api=assistant_msg.api,
                provider=assistant_msg.provider,
                model=assistant_msg.model,
                usage=assistant_msg.usage,
                stop_reason=assistant_msg.stop_reason,
                error_message=assistant_msg.error_message,
                timestamp=assistant_msg.timestamp,
            )
            transformed.append(new_assistant)
            continue

        transformed.append(msg)

    # --- Second pass: insert synthetic tool results for orphaned tool calls ---
    result: list[Message] = []
    pending_tool_calls: list[ToolCall] = []
    existing_tool_result_ids: set[str] = set()

    for msg in transformed:
        if msg.role == "assistant":
            # Flush orphaned tool calls from previous assistant before this one
            if pending_tool_calls:
                for tc in pending_tool_calls:
                    if tc.id not in existing_tool_result_ids:
                        result.append(
                            ToolResultMessage(
                                role="toolResult",
                                tool_call_id=tc.id,
                                tool_name=tc.name,
                                content=[TextContent(type="text", text="No result provided")],
                                is_error=True,
                                timestamp=int(time.time() * 1000),
                            )
                        )
                pending_tool_calls = []
                existing_tool_result_ids = set()

            # Skip errored/aborted assistant messages
            if msg.stop_reason in ("error", "aborted"):
                continue

            # Track tool calls from this assistant
            tool_calls = [b for b in msg.content if isinstance(b, ToolCall)]
            if tool_calls:
                pending_tool_calls = tool_calls
                existing_tool_result_ids = set()

            result.append(msg)

        elif msg.role == "toolResult":
            existing_tool_result_ids.add(msg.tool_call_id)
            result.append(msg)

        elif msg.role == "user":
            # User message interrupts tool flow — flush orphans
            if pending_tool_calls:
                for tc in pending_tool_calls:
                    if tc.id not in existing_tool_result_ids:
                        result.append(
                            ToolResultMessage(
                                role="toolResult",
                                tool_call_id=tc.id,
                                tool_name=tc.name,
                                content=[TextContent(type="text", text="No result provided")],
                                is_error=True,
                                timestamp=int(time.time() * 1000),
                            )
                        )
                pending_tool_calls = []
                existing_tool_result_ids = set()
            result.append(msg)

        else:
            result.append(msg)

    return result
