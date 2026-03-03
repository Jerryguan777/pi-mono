"""Session entry types for JSONL persistence."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Union

from pi_ai.types import (
    AssistantMessage,
    Cost,
    ImageContent,
    Message,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)


def _gen_id() -> str:
    """Generate an 8-char hex ID."""
    return uuid.uuid4().hex[:8]


def _timestamp() -> str:
    """ISO-8601 UTC timestamp."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# --- Session header ---


@dataclass
class SessionHeader:
    type: Literal["session"] = "session"
    version: int = 3
    id: str = ""
    timestamp: str = ""
    cwd: str = ""
    parent_session: str | None = None


# --- Entry base ---


@dataclass
class SessionEntryBase:
    type: str = ""
    id: str = ""
    parent_id: str | None = None
    timestamp: str = ""


# --- Concrete entry types ---


@dataclass
class SessionMessageEntry(SessionEntryBase):
    type: Literal["message"] = "message"
    message: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompactionEntry(SessionEntryBase):
    type: Literal["compaction"] = "compaction"
    summary: str = ""
    first_kept_entry_id: str = ""
    tokens_before: int = 0
    details: dict[str, Any] | None = None


@dataclass
class ModelChangeEntry(SessionEntryBase):
    type: Literal["model_change"] = "model_change"
    provider: str = ""
    model_id: str = ""


@dataclass
class ThinkingLevelChangeEntry(SessionEntryBase):
    type: Literal["thinking_level_change"] = "thinking_level_change"
    thinking_level: str = ""


@dataclass
class BranchSummaryEntry(SessionEntryBase):
    type: Literal["branch_summary"] = "branch_summary"
    from_id: str = ""
    summary: str = ""
    details: dict[str, Any] | None = None


SessionEntry = Union[
    SessionMessageEntry,
    CompactionEntry,
    ModelChangeEntry,
    ThinkingLevelChangeEntry,
    BranchSummaryEntry,
]


# --- Session context (reconstructed for LLM) ---


@dataclass
class SessionContext:
    messages: list[Message] = field(default_factory=list)
    summary: str | None = None
    compaction_entry_id: str | None = None


# --- Session tree node (for UI display) ---


@dataclass
class SessionTreeNode:
    entry: SessionEntry
    children: list[SessionTreeNode] = field(default_factory=list)


# --- Message serialization ---


def serialize_message(msg: Message) -> dict[str, Any]:
    """Convert a Message to a JSON-serializable dict."""
    d = asdict(msg)
    # Ensure role is present
    d["role"] = msg.role
    return d


def _deserialize_content_block(d: dict[str, Any]) -> TextContent | ThinkingContent | ToolCall | ImageContent:
    """Deserialize a content block dict back to typed dataclass."""
    t = d.get("type", "")
    if t == "text":
        return TextContent(
            text=d.get("text", ""),
            text_signature=d.get("text_signature"),
        )
    if t == "thinking":
        return ThinkingContent(
            thinking=d.get("thinking", ""),
            thinking_signature=d.get("thinking_signature"),
        )
    if t == "toolCall":
        return ToolCall(
            id=d.get("id", ""),
            name=d.get("name", ""),
            arguments=d.get("arguments", {}),
            thought_signature=d.get("thought_signature"),
        )
    if t == "image":
        return ImageContent(
            data=d.get("data", ""),
            mime_type=d.get("mime_type", ""),
        )
    # Fallback to TextContent
    return TextContent(text=str(d))


def deserialize_message(d: dict[str, Any]) -> Message:
    """Convert a dict back to a Message."""
    role = d.get("role", "")

    if role == "user":
        content = d.get("content", "")
        if isinstance(content, list):
            content = [_deserialize_content_block(c) for c in content]
        return UserMessage(
            content=content,
            timestamp=d.get("timestamp", 0),
        )

    if role == "assistant":
        raw_content = d.get("content", [])
        content_blocks = [_deserialize_content_block(c) for c in raw_content]
        usage_d = d.get("usage", {})
        cost_d = usage_d.get("cost", {})
        return AssistantMessage(
            content=content_blocks,
            api=d.get("api", ""),
            provider=d.get("provider", ""),
            model=d.get("model", ""),
            usage=Usage(
                input=usage_d.get("input", 0),
                output=usage_d.get("output", 0),
                cache_read=usage_d.get("cache_read", 0),
                cache_write=usage_d.get("cache_write", 0),
                total_tokens=usage_d.get("total_tokens", 0),
                cost=Cost(
                    input=cost_d.get("input", 0.0),
                    output=cost_d.get("output", 0.0),
                    cache_read=cost_d.get("cache_read", 0.0),
                    cache_write=cost_d.get("cache_write", 0.0),
                    total=cost_d.get("total", 0.0),
                ),
            ),
            stop_reason=d.get("stop_reason", "stop"),
            error_message=d.get("error_message"),
            timestamp=d.get("timestamp", 0),
        )

    if role == "toolResult":
        raw_content = d.get("content", [])
        content_blocks = [_deserialize_content_block(c) for c in raw_content]
        return ToolResultMessage(
            tool_call_id=d.get("tool_call_id", ""),
            tool_name=d.get("tool_name", ""),
            content=content_blocks,
            details=d.get("details"),
            is_error=d.get("is_error", False),
            timestamp=d.get("timestamp", 0),
        )

    raise ValueError(f"Unknown message role: {role}")


# --- Entry serialization ---


def serialize_entry(entry: SessionEntry | SessionHeader) -> dict[str, Any]:
    """Serialize a session entry to a JSON-serializable dict."""
    return asdict(entry)


def deserialize_entry(d: dict[str, Any]) -> SessionEntry | SessionHeader:
    """Deserialize a dict back to a session entry."""
    t = d.get("type", "")

    if t == "session":
        return SessionHeader(
            version=d.get("version", 3),
            id=d.get("id", ""),
            timestamp=d.get("timestamp", ""),
            cwd=d.get("cwd", ""),
            parent_session=d.get("parent_session"),
        )

    if t == "message":
        return SessionMessageEntry(
            id=d.get("id", ""),
            parent_id=d.get("parent_id"),
            timestamp=d.get("timestamp", ""),
            message=d.get("message", {}),
        )

    if t == "compaction":
        return CompactionEntry(
            id=d.get("id", ""),
            parent_id=d.get("parent_id"),
            timestamp=d.get("timestamp", ""),
            summary=d.get("summary", ""),
            first_kept_entry_id=d.get("first_kept_entry_id", ""),
            tokens_before=d.get("tokens_before", 0),
            details=d.get("details"),
        )

    if t == "model_change":
        return ModelChangeEntry(
            id=d.get("id", ""),
            parent_id=d.get("parent_id"),
            timestamp=d.get("timestamp", ""),
            provider=d.get("provider", ""),
            model_id=d.get("model_id", ""),
        )

    if t == "thinking_level_change":
        return ThinkingLevelChangeEntry(
            id=d.get("id", ""),
            parent_id=d.get("parent_id"),
            timestamp=d.get("timestamp", ""),
            thinking_level=d.get("thinking_level", ""),
        )

    if t == "branch_summary":
        return BranchSummaryEntry(
            id=d.get("id", ""),
            parent_id=d.get("parent_id"),
            timestamp=d.get("timestamp", ""),
            from_id=d.get("from_id", ""),
            summary=d.get("summary", ""),
            details=d.get("details"),
        )

    raise ValueError(f"Unknown entry type: {t}")
