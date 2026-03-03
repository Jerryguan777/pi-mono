"""Context compaction — token estimation, cut-point detection, summary generation."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

from pi_ai.types import (
    AssistantMessage,
    Message,
    Model,
    TextContent,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)


# --- Settings ---


@dataclass
class CompactionSettings:
    enabled: bool = True
    reserve_tokens: int = 16384
    keep_recent_tokens: int = 20000


# --- Token estimation ---


def estimate_tokens(message: Message) -> int:
    """Estimate token count for a message using chars/4 heuristic."""
    total = 0

    if isinstance(message, UserMessage):
        if isinstance(message.content, str):
            total += len(message.content) // 4
        elif isinstance(message.content, list):
            for block in message.content:
                if hasattr(block, "text"):
                    total += len(block.text) // 4
                elif hasattr(block, "data"):
                    # Image: rough estimate
                    total += 1000

    elif isinstance(message, AssistantMessage):
        for block in message.content:
            if hasattr(block, "text"):
                total += len(block.text) // 4
            elif hasattr(block, "thinking"):
                total += len(block.thinking) // 4
            elif isinstance(block, ToolCall):
                total += len(json.dumps(block.arguments)) // 4 + 20

    elif isinstance(message, ToolResultMessage):
        for block in message.content:
            if hasattr(block, "text"):
                total += len(block.text) // 4
            elif hasattr(block, "data"):
                total += 1000

    return max(total, 1)


def calculate_context_tokens(usage: Usage) -> int:
    """Calculate context tokens from Usage data."""
    return usage.input + usage.cache_read


# --- Threshold detection ---


def should_compact(
    context_tokens: int,
    context_window: int,
    settings: CompactionSettings,
) -> bool:
    """Check if compaction should be triggered based on threshold."""
    if not settings.enabled:
        return False
    # Compact when context reaches 80% of (window - reserve)
    threshold = (context_window - settings.reserve_tokens) * 0.8
    return context_tokens > threshold


# --- Cut-point detection ---


@dataclass
class CutPointResult:
    cut_index: int  # Index into entries list; entries before this are compacted
    kept_tokens: int  # Estimated tokens in kept portion
    compacted_tokens: int  # Estimated tokens in compacted portion
    compacted_messages: list[Message] = field(default_factory=list)
    kept_messages: list[Message] = field(default_factory=list)


def find_cut_point(
    messages: list[Message],
    keep_recent_tokens: int,
) -> CutPointResult | None:
    """Walk backwards from end, keeping ~keep_recent_tokens worth of messages.

    Returns None if there's nothing worth compacting (fewer than 4 messages).
    """
    if len(messages) < 4:
        return None

    # Calculate token counts per message
    tokens = [estimate_tokens(m) for m in messages]

    # Walk backwards, accumulating tokens
    kept_tokens = 0
    cut_index = len(messages)

    for i in range(len(messages) - 1, -1, -1):
        if kept_tokens + tokens[i] > keep_recent_tokens:
            cut_index = i + 1
            break
        kept_tokens += tokens[i]
    else:
        # All messages fit within keep_recent_tokens
        cut_index = 0

    # Ensure we compact at least something (at least 2 messages)
    if cut_index < 2:
        cut_index = 2

    # Don't cut in the middle of a tool call sequence (assistant with tool calls + tool results)
    # Advance cut_index past any orphaned tool results
    while cut_index < len(messages) and isinstance(messages[cut_index], ToolResultMessage):
        cut_index += 1

    if cut_index >= len(messages) - 1:
        return None

    compacted_messages = messages[:cut_index]
    kept_messages = messages[cut_index:]

    compacted_tokens = sum(tokens[:cut_index])
    kept_tokens = sum(tokens[cut_index:])

    return CutPointResult(
        cut_index=cut_index,
        kept_tokens=kept_tokens,
        compacted_tokens=compacted_tokens,
        compacted_messages=compacted_messages,
        kept_messages=kept_messages,
    )


# --- File operation tracking ---


def _extract_file_operations(messages: list[Message]) -> tuple[set[str], set[str]]:
    """Extract read and modified file paths from tool calls in messages."""
    read_files: set[str] = set()
    modified_files: set[str] = set()

    for msg in messages:
        if not isinstance(msg, AssistantMessage):
            continue
        for block in msg.content:
            if not isinstance(block, ToolCall):
                continue
            name = block.name
            args = block.arguments
            path = args.get("path", "")
            if not path:
                continue

            if name == "read":
                read_files.add(path)
            elif name in ("write", "edit"):
                modified_files.add(path)

    return read_files, modified_files


# --- Summary generation ---


SUMMARY_PROMPT = """Summarize the following conversation for context continuity. Use this exact format:

## Goal
[One sentence describing the user's original goal]

## Progress
### Done
- [Completed items as bullet points]

### In Progress
- [Current work items]

## Key Decisions
- [Important decisions made during the conversation]

## Next Steps
- [What should happen next]

{file_section}

Keep the summary concise but include all important context needed to continue the work."""


@dataclass
class CompactionPreparation:
    compacted_messages: list[Message]
    kept_messages: list[Message]
    cut_index: int
    compacted_tokens: int
    kept_tokens: int
    read_files: set[str]
    modified_files: set[str]


def prepare_compaction(
    messages: list[Message],
    settings: CompactionSettings,
) -> CompactionPreparation | None:
    """Prepare for compaction: find cut point, extract file ops."""
    result = find_cut_point(messages, settings.keep_recent_tokens)
    if result is None:
        return None

    read_files, modified_files = _extract_file_operations(result.compacted_messages)

    return CompactionPreparation(
        compacted_messages=result.compacted_messages,
        kept_messages=result.kept_messages,
        cut_index=result.cut_index,
        compacted_tokens=result.compacted_tokens,
        kept_tokens=result.kept_tokens,
        read_files=read_files,
        modified_files=modified_files,
    )


def _build_summary_prompt(messages: list[Message], prep: CompactionPreparation) -> str:
    """Build the prompt for LLM-based summary generation."""
    file_section = ""
    if prep.read_files or prep.modified_files:
        parts = []
        if prep.read_files:
            parts.append("## Files Read\n" + "\n".join(f"- {f}" for f in sorted(prep.read_files)))
        if prep.modified_files:
            parts.append("## Files Modified\n" + "\n".join(f"- {f}" for f in sorted(prep.modified_files)))
        file_section = "\n\n".join(parts)

    return SUMMARY_PROMPT.format(file_section=file_section)


async def generate_summary(
    messages: list[Message],
    prep: CompactionPreparation,
    model: Model,
    api_key: str | None = None,
    abort_signal: asyncio.Event | None = None,
    stream_fn: Any | None = None,
) -> str:
    """Generate a summary of compacted messages using the LLM.

    If no stream_fn is provided, falls back to pi_ai.api_registry.stream_simple.
    """
    from pi_ai.api_registry import stream_simple
    from pi_ai.types import Context, StreamOptions

    prompt_text = _build_summary_prompt(messages, prep)

    # Build a conversation with the compacted messages + summary request
    summary_messages: list[Message] = list(messages)
    summary_messages.append(UserMessage(content=prompt_text))

    ctx = Context(
        system_prompt="You are a helpful assistant that summarizes conversations.",
        messages=[UserMessage(content=prompt_text + "\n\nConversation to summarize:\n" + _format_messages_for_summary(messages))],
    )

    options = StreamOptions(api_key=api_key, abort_signal=abort_signal)

    stream = (stream_fn or stream_simple)(model, ctx, options)
    result_text = ""

    async for event in stream:
        if abort_signal and abort_signal.is_set():
            break
        if event.type == "done":
            for block in event.message.content:
                if hasattr(block, "text"):
                    result_text += block.text
            break

    return result_text or "Summary generation failed."


def _format_messages_for_summary(messages: list[Message]) -> str:
    """Format messages as readable text for summary generation."""
    parts: list[str] = []
    for msg in messages:
        if isinstance(msg, UserMessage):
            content = msg.content if isinstance(msg.content, str) else "[complex content]"
            parts.append(f"User: {content}")
        elif isinstance(msg, AssistantMessage):
            text_parts = [b.text for b in msg.content if hasattr(b, "text")]
            tool_parts = [f"[tool:{b.name}]" for b in msg.content if isinstance(b, ToolCall)]
            content = " ".join(text_parts + tool_parts)
            parts.append(f"Assistant: {content}")
        elif isinstance(msg, ToolResultMessage):
            text_parts = [b.text for b in msg.content if hasattr(b, "text")]
            content = " ".join(text_parts) if text_parts else "[result]"
            parts.append(f"Tool({msg.tool_name}): {content[:200]}")
    return "\n".join(parts)


# --- Compaction result ---


@dataclass
class CompactionResult:
    summary: str
    compacted_tokens: int
    kept_messages: list[Message]
    first_kept_entry_id: str | None = None


async def compact(
    preparation: CompactionPreparation,
    model: Model,
    api_key: str | None = None,
    abort_signal: asyncio.Event | None = None,
    stream_fn: Any | None = None,
) -> CompactionResult:
    """Run compaction: generate summary of compacted messages."""
    summary = await generate_summary(
        preparation.compacted_messages,
        preparation,
        model,
        api_key=api_key,
        abort_signal=abort_signal,
        stream_fn=stream_fn,
    )

    return CompactionResult(
        summary=summary,
        compacted_tokens=preparation.compacted_tokens,
        kept_messages=preparation.kept_messages,
    )
