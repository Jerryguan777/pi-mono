# pi_ai MAPPING — TS → Python

## providers/anthropic.ts → providers/anthropic.py

| TS Function/Class | Python Equivalent | Status | Notes |
|---|---|---|---|
| `type AnthropicEffort` | `AnthropicEffort = Literal[...]` | Done | Literal union |
| `interface AnthropicOptions` | `@dataclass AnthropicOptions` | Done | Extends StreamOptions |
| `streamAnthropic()` | `stream_anthropic()` | Done | AsyncGenerator |
| `streamSimpleAnthropic()` | `stream_simple_anthropic()` | Done | AsyncGenerator |

## providers/openai-completions.ts → providers/openai_completions.py

| TS Function/Class | Python Equivalent | Status | Notes |
|---|---|---|---|
| `interface OpenAICompletionsOptions` | `@dataclass OpenAICompletionsOptions` | Done | Extends StreamOptions |
| `streamOpenAICompletions()` | `stream_openai_completions()` | Done | AsyncGenerator |
| `streamSimpleOpenAICompletions()` | `stream_simple_openai_completions()` | Done | AsyncGenerator |
| `convertMessages()` | `convert_messages()` | Done | Public export |

## providers/openai-responses.ts → providers/openai_responses.py

| TS Function/Class | Python Equivalent | Status | Notes |
|---|---|---|---|
| `interface OpenAIResponsesOptions` | `@dataclass OpenAIResponsesOptions` | Done | Extends StreamOptions |
| `streamOpenAIResponses()` | `stream_openai_responses()` | Done | AsyncGenerator |
| `streamSimpleOpenAIResponses()` | `stream_simple_openai_responses()` | Done | AsyncGenerator |

## providers/openai-responses-shared.ts → providers/openai_responses_shared.py

| TS Function/Class | Python Equivalent | Status | Notes |
|---|---|---|---|
| `interface OpenAIResponsesStreamOptions` | `@dataclass OpenAIResponsesStreamOptions` | Done | |
| `interface ConvertResponsesMessagesOptions` | `@dataclass ConvertResponsesMessagesOptions` | Done | |
| `interface ConvertResponsesToolsOptions` | `@dataclass ConvertResponsesToolsOptions` | Done | |
| `convertResponsesMessages()` | `convert_responses_messages()` | Done | |
| `convertResponsesTools()` | `convert_responses_tools()` | Done | |
| `processResponsesStream()` | `process_responses_stream()` | Done | AsyncGenerator |

## providers/azure-openai-responses.ts → providers/azure_openai_responses.py

| TS Function/Class | Python Equivalent | Status | Notes |
|---|---|---|---|
| `interface AzureOpenAIResponsesOptions` | `@dataclass AzureOpenAIResponsesOptions` | Done | Extends StreamOptions |
| `streamAzureOpenAIResponses()` | `stream_azure_openai_responses()` | Done | AsyncGenerator |
| `streamSimpleAzureOpenAIResponses()` | `stream_simple_azure_openai_responses()` | Done | AsyncGenerator |

## providers/openai-codex-responses.ts → providers/openai_codex_responses.py

| TS Function/Class | Python Equivalent | Status | Notes |
|---|---|---|---|
| `interface OpenAICodexResponsesOptions` | `@dataclass OpenAICodexResponsesOptions` | Done | Extends StreamOptions |
| `streamOpenAICodexResponses()` | `stream_openai_codex_responses()` | Done | AsyncGenerator, uses httpx+websockets |
| `streamSimpleOpenAICodexResponses()` | `stream_simple_openai_codex_responses()` | Done | AsyncGenerator |

## providers/github-copilot-headers.ts → providers/github_copilot_headers.py

| TS Function/Class | Python Equivalent | Status | Notes |
|---|---|---|---|
| `inferCopilotInitiator()` | `infer_copilot_initiator()` | Done | |
| `hasCopilotVisionInput()` | `has_copilot_vision_input()` | Done | |
| `buildCopilotDynamicHeaders()` | `build_copilot_dynamic_headers()` | Done | |

## providers/simple-options.ts → providers/simple_options.py

| TS Function/Class | Python Equivalent | Status | Notes |
|---|---|---|---|
| `buildBaseOptions()` | `build_base_options()` | Done | |
| `clampReasoning()` | `clamp_reasoning()` | Done | |
| `adjustMaxTokensForThinking()` | `adjust_max_tokens_for_thinking()` | Done | Returns tuple |

## providers/transform-messages.ts → providers/transform_messages.py

| TS Function/Class | Python Equivalent | Status | Notes |
|---|---|---|---|
| `transformMessages()` | `transform_messages()` | Done | |

## types.ts → types.py

| TS Type | Python Equivalent | Status | Notes |
|---|---|---|---|
| `type KnownApi` | `KnownApi = Literal[...]` | Done | |
| `type Api` | `Api = str` | Done | Plain str |
| `type KnownProvider` | `KnownProvider = Literal[...]` | Done | |
| `type Provider` | `Provider = str` | Done | Plain str |
| `type ThinkingLevel` | `ThinkingLevel = Literal[...]` | Done | |
| `interface ThinkingBudgets` | `@dataclass ThinkingBudgets` | Done | |
| `type CacheRetention` | `CacheRetention = Literal[...]` | Done | |
| `type Transport` | `Transport = Literal[...]` | Done | |
| `interface StreamOptions` | `@dataclass StreamOptions` | Done | |
| `interface SimpleStreamOptions` | `@dataclass SimpleStreamOptions` | Done | |
| `type StreamFunction<...>` | `StreamFunction` type alias | Done | |
| `interface TextContent` | `@dataclass TextContent` | Done | |
| `interface ThinkingContent` | `@dataclass ThinkingContent` | Done | |
| `interface ImageContent` | `@dataclass ImageContent` | Done | |
| `interface ToolCall` | `@dataclass ToolCall` | Done | |
| `interface Usage` | `@dataclass Usage` | Done | |
| `type StopReason` | `StopReason = Literal[...]` | Done | |
| `interface UserMessage` | `@dataclass UserMessage` | Done | |
| `interface AssistantMessage` | `@dataclass AssistantMessage` | Done | |
| `interface ToolResultMessage` | `@dataclass ToolResultMessage` | Done | |
| `type Message` | `Message = UserMessage \| ...` | Done | |
| `interface Tool` | `@dataclass Tool` | Done | `parameters: dict[str,Any]` |
| `interface Context` | `@dataclass Context` | Done | |
| `type AssistantMessageEvent` | `AssistantMessageEvent` union | Done | Dataclass variants |
| `interface OpenAICompletionsCompat` | `@dataclass OpenAICompletionsCompat` | Done | |
| `interface OpenAIResponsesCompat` | `@dataclass OpenAIResponsesCompat` | Done | |
| `interface OpenRouterRouting` | `@dataclass OpenRouterRouting` | Done | |
| `interface VercelGatewayRouting` | `@dataclass VercelGatewayRouting` | Done | |
| `interface Model<TApi>` | `@dataclass Model` | Done | TApi generic removed |
| `class AssistantMessageEventStream` | `AssistantMessageEventStream` type alias | Done | AsyncGenerator |

## env-api-keys.ts → env_api_keys.py

| TS Function | Python Equivalent | Status | Notes |
|---|---|---|---|
| `getEnvApiKey()` | `get_env_api_key()` | Done | |

## models.ts → models.py (partial — no catalog)

| TS Function | Python Equivalent | Status | Notes |
|---|---|---|---|
| `calculateCost()` | `calculate_cost()` | Done | |
| `supportsXhigh()` | `supports_xhigh()` | Done | |
| `modelsAreEqual()` | `models_are_equal()` | Done | |

## utils/json-parse.ts → utils/json_parse.py

| TS Function | Python Equivalent | Status | Notes |
|---|---|---|---|
| `parseStreamingJson()` | `parse_streaming_json()` | Done | Simple repair heuristic |

## utils/sanitize-unicode.ts → utils/sanitize_unicode.py

| TS Function | Python Equivalent | Status | Notes |
|---|---|---|---|
| `sanitizeSurrogates()` | `sanitize_surrogates()` | Done | |

## utils/event-stream.ts → utils/event_stream.py

| TS Class | Python Equivalent | Status | Notes |
|---|---|---|---|
| `class EventStream<T, R>` | `AsyncGenerator` (not ported) | Done | Per CLAUDE.md guidance |
| `class AssistantMessageEventStream` | `AssistantMessageEventStream` type alias | Done | |
