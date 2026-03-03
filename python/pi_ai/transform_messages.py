"""Cross-provider message normalization.

Transforms a conversation history so it can be replayed on a (potentially different)
model.  Three concerns are handled:

1. **Thinking blocks** — same model keeps signatures for replay; cross-model converts
   non-empty thinking to plain text, drops empty thinking.
2. **Tool call IDs** — optionally normalized via a caller-supplied function (e.g.
   OpenAI 450-char IDs → Anthropic max-64-char IDs).  Corresponding ToolResultMessage
   IDs are rewritten to match.
3. **Orphaned tool calls** — if an assistant message contains tool calls but no matching
   tool results appear before the next assistant/user message, synthetic error results
   are inserted so the provider API stays happy.
4. **Error/aborted messages** — assistant messages with stop_reason "error" or "aborted"
   are dropped entirely to avoid replaying partial/broken turns.
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Callable

from pi_ai.types import (
    AssistantMessage,
    ContentBlock,
    Message,
    Model,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
)

NormalizeToolCallId = Callable[[str, Model, AssistantMessage], str]


def transform_messages(
    messages: list[Message],
    model: Model,
    normalize_tool_call_id: NormalizeToolCallId | None = None,
) -> list[Message]:
    """Normalize *messages* for replay on *model*.

    Returns a new list — the originals are not mutated.
    """
    tool_call_id_map: dict[str, str] = {}

    # --- First pass: content-level transforms ---
    transformed: list[Message] = []
    for msg in messages:
        if msg.role == "user":
            transformed.append(msg)
            continue

        if msg.role == "toolResult":
            normalized_id = tool_call_id_map.get(msg.tool_call_id)
            if normalized_id and normalized_id != msg.tool_call_id:
                transformed.append(replace(msg, tool_call_id=normalized_id))
            else:
                transformed.append(msg)
            continue

        if msg.role == "assistant":
            assert isinstance(msg, AssistantMessage)
            is_same_model = (
                msg.provider == model.provider
                and msg.api == model.api
                and msg.model == model.id
            )

            new_content: list[ContentBlock] = []
            for block in msg.content:
                if isinstance(block, ThinkingContent):
                    # Same model + has signature → keep (needed for replay,
                    # even when thinking text is empty like OpenAI encrypted reasoning)
                    if is_same_model and block.thinking_signature:
                        new_content.append(block)
                    # Empty thinking → drop
                    elif not block.thinking or block.thinking.strip() == "":
                        pass
                    # Same model without signature → keep as-is
                    elif is_same_model:
                        new_content.append(block)
                    # Cross-model → convert to plain text
                    else:
                        new_content.append(TextContent(text=block.thinking))

                elif isinstance(block, TextContent):
                    if is_same_model:
                        new_content.append(block)
                    else:
                        # Strip signature when crossing models
                        new_content.append(TextContent(text=block.text))

                elif isinstance(block, ToolCall):
                    tc = block
                    # Strip thought_signature for cross-model
                    if not is_same_model and tc.thought_signature:
                        tc = replace(tc, thought_signature=None)
                    # Normalize tool call ID for cross-model
                    if not is_same_model and normalize_tool_call_id:
                        new_id = normalize_tool_call_id(tc.id, model, msg)
                        if new_id != tc.id:
                            tool_call_id_map[block.id] = new_id
                            tc = replace(tc, id=new_id)
                    new_content.append(tc)

                else:
                    new_content.append(block)

            transformed.append(replace(msg, content=new_content))
            continue

        # Unknown role — pass through
        transformed.append(msg)

    # --- Second pass: orphan handling + error/aborted filtering ---
    result: list[Message] = []
    pending_tool_calls: list[ToolCall] = []
    existing_result_ids: set[str] = set()

    for msg in transformed:
        if msg.role == "assistant":
            assert isinstance(msg, AssistantMessage)

            # Flush orphaned tool calls from a *previous* assistant turn
            _flush_orphans(result, pending_tool_calls, existing_result_ids)
            pending_tool_calls = []
            existing_result_ids = set()

            # Drop error/aborted messages — incomplete turns shouldn't be replayed
            if msg.stop_reason in ("error", "aborted"):
                continue

            # Track tool calls for orphan detection
            pending_tool_calls = [
                b for b in msg.content if isinstance(b, ToolCall)
            ]

            result.append(msg)

        elif msg.role == "toolResult":
            assert isinstance(msg, ToolResultMessage)
            existing_result_ids.add(msg.tool_call_id)
            result.append(msg)

        elif msg.role == "user":
            # User message interrupts tool flow — flush orphans first
            _flush_orphans(result, pending_tool_calls, existing_result_ids)
            pending_tool_calls = []
            existing_result_ids = set()
            result.append(msg)

        else:
            result.append(msg)

    return result


def _flush_orphans(
    result: list[Message],
    pending_tool_calls: list[ToolCall],
    existing_result_ids: set[str],
) -> None:
    """Insert synthetic error tool results for tool calls that have no matching result."""
    for tc in pending_tool_calls:
        if tc.id not in existing_result_ids:
            result.append(
                ToolResultMessage(
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    content=[TextContent(text="No result provided")],
                    is_error=True,
                    timestamp=int(time.time() * 1000),
                )
            )
