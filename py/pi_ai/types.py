"""Core types for the pi_ai package, ported from packages/ai/src/types.ts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Literal

# API identifiers
KnownApi = Literal[
    "openai-completions",
    "openai-responses",
    "azure-openai-responses",
    "openai-codex-responses",
    "anthropic-messages",
    "bedrock-converse-stream",
    "google-generative-ai",
    "google-gemini-cli",
    "google-vertex",
]

Api = str  # KnownApi | arbitrary string

KnownProvider = Literal[
    "amazon-bedrock",
    "anthropic",
    "google",
    "google-gemini-cli",
    "google-antigravity",
    "google-vertex",
    "openai",
    "azure-openai-responses",
    "openai-codex",
    "github-copilot",
    "xai",
    "groq",
    "cerebras",
    "openrouter",
    "vercel-ai-gateway",
    "zai",
    "mistral",
    "minimax",
    "minimax-cn",
    "huggingface",
    "opencode",
    "kimi-coding",
]

Provider = str  # KnownProvider | arbitrary string

ThinkingLevel = Literal["minimal", "low", "medium", "high", "xhigh"]

CacheRetention = Literal["none", "short", "long"]

Transport = Literal["sse", "websocket", "auto"]

StopReason = Literal["stop", "length", "toolUse", "error", "aborted"]


@dataclass
class ThinkingBudgets:
    minimal: int | None = None
    low: int | None = None
    medium: int | None = None
    high: int | None = None


@dataclass
class StreamOptions:
    temperature: float | None = None
    max_tokens: int | None = None
    signal: asyncio.Event | None = None
    api_key: str | None = None
    transport: Transport | None = None
    cache_retention: CacheRetention | None = None
    session_id: str | None = None
    on_payload: Any | None = None  # Callable[[Any], None] | None
    headers: dict[str, str] | None = None
    max_retry_delay_ms: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class SimpleStreamOptions(StreamOptions):
    reasoning: ThinkingLevel | None = None
    thinking_budgets: ThinkingBudgets | None = None


@dataclass
class TextContent:
    type: Literal["text"] = "text"
    text: str = ""
    text_signature: str | None = None


@dataclass
class ThinkingContent:
    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    thinking_signature: str | None = None


@dataclass
class ImageContent:
    type: Literal["image"] = "image"
    data: str = ""  # base64 encoded
    mime_type: str = ""


@dataclass
class ToolCall:
    type: Literal["toolCall"] = "toolCall"
    id: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    thought_signature: str | None = None


AssistantContentBlock = TextContent | ThinkingContent | ToolCall


@dataclass
class UsageCost:
    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0
    total: float = 0.0


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total_tokens: int = 0
    cost: UsageCost = field(default_factory=UsageCost)


@dataclass
class UserMessage:
    role: Literal["user"] = "user"
    content: str | list[TextContent | ImageContent] = ""
    timestamp: int = 0


@dataclass
class AssistantMessage:
    role: Literal["assistant"] = "assistant"
    content: list[TextContent | ThinkingContent | ToolCall] = field(default_factory=list)
    api: Api = ""
    provider: Provider = ""
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    stop_reason: StopReason = "stop"
    error_message: str | None = None
    timestamp: int = 0


@dataclass
class ToolResultMessage:
    role: Literal["toolResult"] = "toolResult"
    tool_call_id: str = ""
    tool_name: str = ""
    content: list[TextContent | ImageContent] = field(default_factory=list)
    details: Any = None
    is_error: bool = False
    timestamp: int = 0


Message = UserMessage | AssistantMessage | ToolResultMessage


@dataclass
class Tool:
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    system_prompt: str | None = None
    messages: list[Message] = field(default_factory=list)
    tools: list[Tool] | None = None


@dataclass
class ModelCost:
    input: float = 0.0  # $/million tokens
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0


@dataclass
class Model:
    id: str = ""
    name: str = ""
    api: Api = ""
    provider: Provider = ""
    base_url: str = ""
    reasoning: bool = False
    input: list[str] = field(default_factory=lambda: ["text"])
    cost: ModelCost = field(default_factory=ModelCost)
    context_window: int = 0
    max_tokens: int = 0
    headers: dict[str, str] | None = None


# --- Event types for streaming ---


@dataclass
class StartEvent:
    type: Literal["start"] = "start"
    partial: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class TextStartEvent:
    type: Literal["text_start"] = "text_start"
    content_index: int = 0
    partial: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class TextDeltaEvent:
    type: Literal["text_delta"] = "text_delta"
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class TextEndEvent:
    type: Literal["text_end"] = "text_end"
    content_index: int = 0
    content: str = ""
    partial: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class ThinkingStartEvent:
    type: Literal["thinking_start"] = "thinking_start"
    content_index: int = 0
    partial: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class ThinkingDeltaEvent:
    type: Literal["thinking_delta"] = "thinking_delta"
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class ThinkingEndEvent:
    type: Literal["thinking_end"] = "thinking_end"
    content_index: int = 0
    content: str = ""
    partial: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class ToolCallStartEvent:
    type: Literal["toolcall_start"] = "toolcall_start"
    content_index: int = 0
    partial: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class ToolCallDeltaEvent:
    type: Literal["toolcall_delta"] = "toolcall_delta"
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class ToolCallEndEvent:
    type: Literal["toolcall_end"] = "toolcall_end"
    content_index: int = 0
    tool_call: ToolCall = field(default_factory=ToolCall)
    partial: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class DoneEvent:
    type: Literal["done"] = "done"
    reason: StopReason = "stop"
    message: AssistantMessage = field(default_factory=AssistantMessage)


@dataclass
class ErrorEvent:
    type: Literal["error"] = "error"
    reason: StopReason = "error"
    error: AssistantMessage = field(default_factory=AssistantMessage)


AssistantMessageEvent = (
    StartEvent
    | TextStartEvent
    | TextDeltaEvent
    | TextEndEvent
    | ThinkingStartEvent
    | ThinkingDeltaEvent
    | ThinkingEndEvent
    | ToolCallStartEvent
    | ToolCallDeltaEvent
    | ToolCallEndEvent
    | DoneEvent
    | ErrorEvent
)
