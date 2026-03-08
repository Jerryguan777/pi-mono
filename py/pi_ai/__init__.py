"""Unified multi-provider LLM API — Python port of @mariozechner/pi-ai."""

from __future__ import annotations

# Environment API keys
from pi_ai.env_api_keys import get_env_api_key

# Model utilities
from pi_ai.models import calculate_cost, models_are_equal, supports_xhigh

# Providers
from pi_ai.providers.anthropic import (
    AnthropicEffort,
    AnthropicOptions,
    stream_anthropic,
    stream_simple_anthropic,
)
from pi_ai.providers.azure_openai_responses import (
    AzureOpenAIResponsesOptions,
    stream_azure_openai_responses,
    stream_simple_azure_openai_responses,
)
from pi_ai.providers.github_copilot_headers import (
    build_copilot_dynamic_headers,
    has_copilot_vision_input,
    infer_copilot_initiator,
)
from pi_ai.providers.openai_codex_responses import (
    OpenAICodexResponsesOptions,
    stream_openai_codex_responses,
    stream_simple_openai_codex_responses,
)
from pi_ai.providers.openai_completions import (
    OpenAICompletionsOptions,
    convert_messages,
    stream_openai_completions,
    stream_simple_openai_completions,
)
from pi_ai.providers.openai_responses import (
    OpenAIResponsesOptions,
    stream_openai_responses,
    stream_simple_openai_responses,
)
from pi_ai.providers.openai_responses_shared import (
    ConvertResponsesMessagesOptions,
    ConvertResponsesToolsOptions,
    OpenAIResponsesStreamOptions,
    convert_responses_messages,
    convert_responses_tools,
    process_responses_stream,
)
from pi_ai.providers.simple_options import (
    adjust_max_tokens_for_thinking,
    build_base_options,
    clamp_reasoning,
)
from pi_ai.providers.transform_messages import transform_messages

# Core types
from pi_ai.types import (
    Api,
    AssistantMessage,
    AssistantMessageEvent,
    AssistantMessageEventStream,
    CacheRetention,
    Context,
    CostBreakdown,
    DoneEvent,
    ErrorEvent,
    ImageContent,
    KnownApi,
    KnownProvider,
    Message,
    Model,
    ModelCost,
    OpenAICompletionsCompat,
    OpenAIResponsesCompat,
    OpenRouterRouting,
    Provider,
    SimpleStreamOptions,
    StartEvent,
    StopReason,
    StreamFunction,
    StreamOptions,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ThinkingBudgets,
    ThinkingContent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingLevel,
    ThinkingStartEvent,
    Tool,
    ToolCall,
    ToolcallDeltaEvent,
    ToolcallEndEvent,
    ToolcallStartEvent,
    ToolResultMessage,
    Transport,
    Usage,
    UserMessage,
    VercelGatewayRouting,
)

# Utils
from pi_ai.utils.json_parse import parse_streaming_json
from pi_ai.utils.sanitize_unicode import sanitize_surrogates

__all__ = [
    "AnthropicEffort",
    "AnthropicOptions",
    "Api",
    "AssistantMessage",
    "AssistantMessageEvent",
    "AssistantMessageEventStream",
    "AzureOpenAIResponsesOptions",
    "CacheRetention",
    "Context",
    "ConvertResponsesMessagesOptions",
    "ConvertResponsesToolsOptions",
    "CostBreakdown",
    "DoneEvent",
    "ErrorEvent",
    "ImageContent",
    "KnownApi",
    "KnownProvider",
    "Message",
    "Model",
    "ModelCost",
    "OpenAICodexResponsesOptions",
    "OpenAICompletionsCompat",
    "OpenAICompletionsOptions",
    "OpenAIResponsesCompat",
    "OpenAIResponsesOptions",
    "OpenAIResponsesStreamOptions",
    "OpenRouterRouting",
    "Provider",
    "SimpleStreamOptions",
    "StartEvent",
    "StopReason",
    "StreamFunction",
    "StreamOptions",
    "TextContent",
    "TextDeltaEvent",
    "TextEndEvent",
    "TextStartEvent",
    "ThinkingBudgets",
    "ThinkingContent",
    "ThinkingDeltaEvent",
    "ThinkingEndEvent",
    "ThinkingLevel",
    "ThinkingStartEvent",
    "Tool",
    "ToolCall",
    "ToolResultMessage",
    "ToolcallDeltaEvent",
    "ToolcallEndEvent",
    "ToolcallStartEvent",
    "Transport",
    "Usage",
    "UserMessage",
    "VercelGatewayRouting",
    "adjust_max_tokens_for_thinking",
    "build_base_options",
    "build_copilot_dynamic_headers",
    "calculate_cost",
    "clamp_reasoning",
    "convert_messages",
    "convert_responses_messages",
    "convert_responses_tools",
    "get_env_api_key",
    "has_copilot_vision_input",
    "infer_copilot_initiator",
    "models_are_equal",
    "parse_streaming_json",
    "process_responses_stream",
    "sanitize_surrogates",
    "stream_anthropic",
    "stream_azure_openai_responses",
    "stream_openai_codex_responses",
    "stream_openai_completions",
    "stream_openai_responses",
    "stream_simple_anthropic",
    "stream_simple_azure_openai_responses",
    "stream_simple_openai_codex_responses",
    "stream_simple_openai_completions",
    "stream_simple_openai_responses",
    "supports_xhigh",
    "transform_messages",
]
