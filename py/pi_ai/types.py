"""Core types for the pi_ai package — ported from packages/ai/src/types.ts."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Provider / API identifiers
# ---------------------------------------------------------------------------

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

# Open string union — any KnownApi or a custom string
Api = str

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

Provider = str

# ---------------------------------------------------------------------------
# Thinking levels / budgets
# ---------------------------------------------------------------------------

ThinkingLevel = Literal["minimal", "low", "medium", "high", "xhigh"]

StopReason = Literal["stop", "length", "toolUse", "error", "aborted"]

CacheRetention = Literal["none", "short", "long"]

Transport = Literal["sse", "websocket", "auto"]


@dataclass
class ThinkingBudgets:
    """Token budgets for each thinking level (token-based providers only)."""

    minimal: int | None = None
    low: int | None = None
    medium: int | None = None
    high: int | None = None


# ---------------------------------------------------------------------------
# Content blocks
# ---------------------------------------------------------------------------


@dataclass
class TextContent:
    type: Literal["text"] = "text"
    text: str = ""
    text_signature: str | None = None  # e.g. OpenAI responses message ID


@dataclass
class ThinkingContent:
    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    thinking_signature: str | None = None  # e.g. signature for replaying thought context


@dataclass
class ImageContent:
    type: Literal["image"] = "image"
    data: str = ""  # base64 encoded
    mime_type: str = ""  # e.g. "image/jpeg"


@dataclass
class ToolCall:
    type: Literal["toolCall"] = "toolCall"
    id: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    thought_signature: str | None = None  # Google-specific opaque signature


# ---------------------------------------------------------------------------
# Cost / usage
# ---------------------------------------------------------------------------


@dataclass
class CostBreakdown:
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
    cost: CostBreakdown = field(default_factory=CostBreakdown)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


@dataclass
class UserMessage:
    role: Literal["user"] = "user"
    content: str | list[TextContent | ImageContent] = ""
    timestamp: int = 0  # Unix ms


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
    timestamp: int = 0  # Unix ms


@dataclass
class ToolResultMessage:
    role: Literal["toolResult"] = "toolResult"
    tool_call_id: str = ""
    tool_name: str = ""
    content: list[TextContent | ImageContent] = field(default_factory=list)
    details: Any = None
    is_error: bool = False
    timestamp: int = 0  # Unix ms


Message = UserMessage | AssistantMessage | ToolResultMessage

# ---------------------------------------------------------------------------
# Tools / context
# ---------------------------------------------------------------------------


@dataclass
class Tool:
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)  # JSON Schema


@dataclass
class Context:
    messages: list[Message] = field(default_factory=list)
    system_prompt: str | None = None
    tools: list[Tool] | None = None


# ---------------------------------------------------------------------------
# Model cost / compat
# ---------------------------------------------------------------------------


@dataclass
class ModelCost:
    input: float = 0.0  # $/million tokens
    output: float = 0.0  # $/million tokens
    cache_read: float = 0.0
    cache_write: float = 0.0


@dataclass
class OpenAICompletionsCompat:
    """Compatibility settings for OpenAI-compatible completions APIs."""

    supports_store: bool | None = None
    supports_developer_role: bool | None = None
    supports_reasoning_effort: bool | None = None
    supports_usage_in_streaming: bool | None = None
    max_tokens_field: Literal["max_completion_tokens", "max_tokens"] | None = None
    requires_tool_result_name: bool | None = None
    requires_assistant_after_tool_result: bool | None = None
    requires_thinking_as_text: bool | None = None
    requires_mistral_tool_ids: bool | None = None
    thinking_format: Literal["openai", "zai", "qwen"] | None = None
    open_router_routing: OpenRouterRouting | None = None
    vercel_gateway_routing: VercelGatewayRouting | None = None
    supports_strict_mode: bool | None = None


@dataclass
class OpenAIResponsesCompat:
    """Compatibility settings for OpenAI Responses APIs (reserved for future use)."""

    pass


@dataclass
class OpenRouterRouting:
    """OpenRouter provider routing preferences."""

    only: list[str] | None = None
    order: list[str] | None = None


@dataclass
class VercelGatewayRouting:
    """Vercel AI Gateway routing preferences."""

    only: list[str] | None = None
    order: list[str] | None = None


@dataclass
class Model:
    """Unified model descriptor."""

    id: str = ""
    name: str = ""
    api: Api = ""
    provider: Provider = ""
    base_url: str = ""
    reasoning: bool = False
    input: list[Literal["text", "image"]] = field(default_factory=lambda: ["text"])
    cost: ModelCost = field(default_factory=ModelCost)
    context_window: int = 0
    max_tokens: int = 0
    headers: dict[str, str] | None = None
    compat: OpenAICompletionsCompat | OpenAIResponsesCompat | None = None


# ---------------------------------------------------------------------------
# Stream options
# ---------------------------------------------------------------------------


@dataclass
class StreamOptions:
    temperature: float | None = None
    max_tokens: int | None = None
    signal: Any | None = None  # asyncio.Event or similar abort signal
    api_key: str | None = None
    transport: Transport | None = None
    cache_retention: CacheRetention | None = None
    session_id: str | None = None
    on_payload: Callable[[Any], None] | None = None
    headers: dict[str, str] | None = None
    max_retry_delay_ms: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class SimpleStreamOptions(StreamOptions):
    reasoning: ThinkingLevel | None = None
    thinking_budgets: ThinkingBudgets | None = None


# ---------------------------------------------------------------------------
# Stream events
# ---------------------------------------------------------------------------


@dataclass
class StartEvent:
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["start"] = "start"


@dataclass
class TextStartEvent:
    content_index: int = 0
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["text_start"] = "text_start"


@dataclass
class TextDeltaEvent:
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["text_delta"] = "text_delta"


@dataclass
class TextEndEvent:
    content_index: int = 0
    content: str = ""
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["text_end"] = "text_end"


@dataclass
class ThinkingStartEvent:
    content_index: int = 0
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["thinking_start"] = "thinking_start"


@dataclass
class ThinkingDeltaEvent:
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["thinking_delta"] = "thinking_delta"


@dataclass
class ThinkingEndEvent:
    content_index: int = 0
    content: str = ""
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["thinking_end"] = "thinking_end"


@dataclass
class ToolcallStartEvent:
    content_index: int = 0
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["toolcall_start"] = "toolcall_start"


@dataclass
class ToolcallDeltaEvent:
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["toolcall_delta"] = "toolcall_delta"


@dataclass
class ToolcallEndEvent:
    content_index: int = 0
    tool_call: ToolCall = field(default_factory=ToolCall)
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["toolcall_end"] = "toolcall_end"


@dataclass
class DoneEvent:
    reason: Literal["stop", "length", "toolUse"] = "stop"
    message: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["done"] = "done"


@dataclass
class ErrorEvent:
    reason: Literal["aborted", "error"] = "error"
    error: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["error"] = "error"


AssistantMessageEvent = (
    StartEvent
    | TextStartEvent
    | TextDeltaEvent
    | TextEndEvent
    | ThinkingStartEvent
    | ThinkingDeltaEvent
    | ThinkingEndEvent
    | ToolcallStartEvent
    | ToolcallDeltaEvent
    | ToolcallEndEvent
    | DoneEvent
    | ErrorEvent
)

# Async generator type alias
AssistantMessageEventStream = AsyncGenerator[AssistantMessageEvent, None]

# Stream function callable type
StreamFunction = Callable[..., AssistantMessageEventStream]

