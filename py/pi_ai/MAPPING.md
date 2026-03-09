# pi_ai — TS to Python Mapping

## types.ts → types.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `KnownApi` (type union) | `KnownApi` (StrEnum) | Done | |
| `Api` (type alias) | `Api = str` | Done | |
| `KnownProvider` (type union) | `KnownProvider` (StrEnum) | Done | |
| `Provider` (type alias) | `Provider = str` | Done | |
| `ThinkingLevel` (type) | `ThinkingLevel` (Literal) | Done | |
| `ThinkingBudgets` (interface) | `ThinkingBudgets` (dataclass) | Done | |
| `CacheRetention` (type) | `CacheRetention` (Literal) | Done | |
| `Transport` (type) | `Transport` (Literal) | Done | |
| `StreamOptions` (interface) | `StreamOptions` (dataclass) | Done | camelCase → snake_case fields |
| `SimpleStreamOptions` (interface) | `SimpleStreamOptions` (dataclass) | Done | Extends StreamOptions |
| `ProviderStreamOptions` (type) | N/A | Done | Not needed — Python uses StreamOptions directly |
| `StreamFunction` (type) | `StreamFunction` (Callable) | Done | In types.py |
| `TextContent` (interface) | `TextContent` (dataclass) | Done | |
| `ThinkingContent` (interface) | `ThinkingContent` (dataclass) | Done | |
| `ImageContent` (interface) | `ImageContent` (dataclass) | Done | |
| `ToolCall` (interface) | `ToolCall` (dataclass) | Done | |
| `Usage` (interface) | `Usage` (dataclass) | Done | Nested cost → UsageCost dataclass |
| `StopReason` (type) | `StopReason` (Literal) | Done | |
| `UserMessage` (interface) | `UserMessage` (dataclass) | Done | |
| `AssistantMessage` (interface) | `AssistantMessage` (dataclass) | Done | |
| `ToolResultMessage` (interface) | `ToolResultMessage` (dataclass) | Done | |
| `Message` (type union) | `Message` (Union type alias) | Done | |
| `Tool` (interface) | `Tool` (dataclass) | Done | parameters: JSON Schema dict |
| `Context` (interface) | `Context` (dataclass) | Done | |
| `AssistantMessageEvent` (union) | Event dataclasses + union alias | Done | Individual event dataclasses |
| `OpenAICompletionsCompat` | `OpenAICompletionsCompat` (dataclass) | Done | |
| `OpenAIResponsesCompat` | `OpenAIResponsesCompat` (dataclass) | Done | |
| `OpenRouterRouting` | `OpenRouterRouting` (dataclass) | Done | |
| `VercelGatewayRouting` | `VercelGatewayRouting` (dataclass) | Done | |
| `Model` (interface) | `Model` (dataclass) | Done | Generic `<TApi>` removed |
| `AssistantMessageEventStream` | `AssistantMessageEventStream` type alias | Done | AsyncGenerator |
| (serialization) | `serialize_*` / `deserialize_*` functions | Done | Explicit functions per CLAUDE.md |

## stream.ts → stream.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `stream()` | `stream()` | Done | Returns AsyncIterator |
| `complete()` | `complete()` | Done | Collects final message |
| `streamSimple()` | `stream_simple()` | Done | |
| `completeSimple()` | `complete_simple()` | Done | |

## api-registry.ts → api_registry.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `ApiProvider` (interface) | `ApiProvider` (dataclass) | Done | |
| `registerApiProvider()` | `register_api_provider()` | Done | |
| `getApiProvider()` | `get_api_provider()` | Done | |
| `getApiProviders()` | `get_api_providers()` | Done | |
| `unregisterApiProviders()` | `unregister_api_providers()` | Done | |
| `clearApiProviders()` | `clear_api_providers()` | Done | |

## models.ts → models.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `getModel()` | `get_model()` | Done | Returns Model or None |
| `getProviders()` | `get_providers()` | Done | |
| `getModels()` | `get_models()` | Done | |
| `calculateCost()` | `calculate_cost()` | Done | |
| `supportsXhigh()` | `supports_xhigh()` | Done | |
| `modelsAreEqual()` | `models_are_equal()` | Done | |
| `register_models()` | `register_models()` | Done | New — replaces auto-load from generated |
| `clear_model_registry()` | `clear_model_registry()` | Done | New — for testing |

## env-api-keys.ts → env_api_keys.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `getEnvApiKey()` | `get_env_api_key()` | Done | Uses os.environ instead of process.env |

## utils/event-stream.ts → (replaced by AsyncIterator)

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `EventStream` (class) | Native `AsyncIterator` | Done | Not ported — use async generators |
| `AssistantMessageEventStream` | `AsyncIterator[AssistantMessageEvent]` | Done | |
| `createAssistantMessageEventStream()` | N/A | Done | Not needed |

## utils/overflow.ts → utils/overflow.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `OVERFLOW_PATTERNS` | `OVERFLOW_PATTERNS` | Done | Compiled re.Pattern list |
| `isContextOverflow()` | `is_context_overflow()` | Done | |
| `getOverflowPatterns()` | `get_overflow_patterns()` | Done | |

## utils/validation.ts → utils/validation.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `validateToolCall()` | `validate_tool_call()` | Done | Uses jsonschema instead of AJV |
| `validateToolArguments()` | `validate_tool_arguments()` | Done | |

## utils/sanitize-unicode.ts → utils/sanitize_unicode.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `sanitizeSurrogates()` | `sanitize_surrogates()` | Done | |

## utils/json-parse.ts → utils/json_parse.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `parseStreamingJson()` | `parse_streaming_json()` | Done | Uses partial-json-parser library |

## utils/http-proxy.ts → utils/http_proxy.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| (proxy setup) | No-op module | Done | httpx reads proxy env vars natively |

## providers/register-builtins.ts → providers/register_builtins.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `registerBuiltInApiProviders()` | `register_built_in_api_providers()` | Done | Placeholder — providers not yet ported |
| `resetApiProviders()` | `reset_api_providers()` | Done | |
| `BUILT_IN_APIS` | `BUILT_IN_APIS` | Done | New — list of API names for reference |

## providers/simple-options.ts → providers/simple_options.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `buildBaseOptions()` | `build_base_options()` | Done | |
| `clampReasoning()` | `clamp_reasoning()` | Done | |
| `adjustMaxTokensForThinking()` | `adjust_max_tokens_for_thinking()` | Done | Returns tuple instead of object |

## providers/transform-messages.ts → providers/transform_messages.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `transformMessages()` | `transform_messages()` | Done | |

## providers/anthropic.ts → providers/anthropic.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `type AnthropicEffort` | `AnthropicEffort = Literal[...]` | Done | Literal union |
| `interface AnthropicOptions` | `@dataclass AnthropicOptions` | Done | Extends StreamOptions |
| `streamAnthropic()` | `stream_anthropic()` | Done | AsyncGenerator |
| `streamSimpleAnthropic()` | `stream_simple_anthropic()` | Done | AsyncGenerator |

## providers/openai-completions.ts → providers/openai_completions.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `interface OpenAICompletionsOptions` | `@dataclass OpenAICompletionsOptions` | Done | Extends StreamOptions |
| `streamOpenAICompletions()` | `stream_openai_completions()` | Done | AsyncGenerator |
| `streamSimpleOpenAICompletions()` | `stream_simple_openai_completions()` | Done | AsyncGenerator |
| `convertMessages()` | `convert_messages()` | Done | Public export |

## providers/openai-responses.ts → providers/openai_responses.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `interface OpenAIResponsesOptions` | `@dataclass OpenAIResponsesOptions` | Done | Extends StreamOptions |
| `streamOpenAIResponses()` | `stream_openai_responses()` | Done | AsyncGenerator |
| `streamSimpleOpenAIResponses()` | `stream_simple_openai_responses()` | Done | AsyncGenerator |

## providers/openai-responses-shared.ts → providers/openai_responses_shared.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `interface OpenAIResponsesStreamOptions` | `@dataclass OpenAIResponsesStreamOptions` | Done | |
| `interface ConvertResponsesMessagesOptions` | `@dataclass ConvertResponsesMessagesOptions` | Done | |
| `interface ConvertResponsesToolsOptions` | `@dataclass ConvertResponsesToolsOptions` | Done | |
| `convertResponsesMessages()` | `convert_responses_messages()` | Done | |
| `convertResponsesTools()` | `convert_responses_tools()` | Done | |
| `processResponsesStream()` | `process_responses_stream()` | Done | AsyncGenerator |

## providers/azure-openai-responses.ts → providers/azure_openai_responses.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `interface AzureOpenAIResponsesOptions` | `@dataclass AzureOpenAIResponsesOptions` | Done | Extends StreamOptions |
| `streamAzureOpenAIResponses()` | `stream_azure_openai_responses()` | Done | AsyncGenerator |
| `streamSimpleAzureOpenAIResponses()` | `stream_simple_azure_openai_responses()` | Done | AsyncGenerator |

## providers/openai-codex-responses.ts → providers/openai_codex_responses.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `interface OpenAICodexResponsesOptions` | `@dataclass OpenAICodexResponsesOptions` | Done | Extends StreamOptions |
| `streamOpenAICodexResponses()` | `stream_openai_codex_responses()` | Done | AsyncGenerator, uses httpx+websockets |
| `streamSimpleOpenAICodexResponses()` | `stream_simple_openai_codex_responses()` | Done | AsyncGenerator |

## providers/github-copilot-headers.ts → providers/github_copilot_headers.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `inferCopilotInitiator()` | `infer_copilot_initiator()` | Done | |
| `hasCopilotVisionInput()` | `has_copilot_vision_input()` | Done | |
| `buildCopilotDynamicHeaders()` | `build_copilot_dynamic_headers()` | Done | |
