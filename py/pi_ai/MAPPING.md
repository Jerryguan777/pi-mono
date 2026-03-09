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

## models.generated.ts -> models_generated.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `MODELS` (const) | `MODELS` (dict) | Done | Generated from TS source |
| (auto-load) | `load_models()` | Done | Called on import to populate model registry |

## providers/register-builtins.ts → providers/register_builtins.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `registerBuiltInApiProviders()` | `register_built_in_api_providers()` | Done | All 9 providers registered |
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

## providers/google-shared.ts → providers/google_shared.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `isThinkingPart()` | `is_thinking_part()` | Done | |
| `retainThoughtSignature()` | `retain_thought_signature()` | Done | |
| `requiresToolCallId()` | `requires_tool_call_id()` | Done | |
| `convertMessages()` | `convert_messages()` | Done | Converts to Gemini Content[] format |
| `convertTools()` | `convert_tools()` | Done | |
| `mapToolChoice()` | `map_tool_choice()` | Done | |
| `mapStopReason()` | `map_stop_reason()` | Done | |
| `mapStopReasonString()` | `map_stop_reason_string()` | Done | |

## providers/google.ts → providers/google.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `interface GoogleOptions` | `@dataclass GoogleOptions` | Done | Extends StreamOptions |
| `streamGoogle()` | `stream_google()` | Done | Uses google-genai SDK |
| `streamSimpleGoogle()` | `stream_simple_google()` | Done | |

## providers/google-vertex.ts → providers/google_vertex.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `interface GoogleVertexOptions` | `@dataclass GoogleVertexOptions` | Done | Extends StreamOptions, adds project/location |
| `streamGoogleVertex()` | `stream_google_vertex()` | Done | Uses google-genai SDK with vertexai=True |
| `streamSimpleGoogleVertex()` | `stream_simple_google_vertex()` | Done | |

## providers/google-gemini-cli.ts → providers/google_gemini_cli.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `type GoogleThinkingLevel` | `GoogleThinkingLevel` (Literal) | Done | |
| `interface GoogleGeminiCliOptions` | `@dataclass GoogleGeminiCliOptions` | Done | Extends StreamOptions |
| `extractRetryDelay()` | `extract_retry_delay()` | Done | |
| `buildRequest()` | `build_request()` | Done | |
| `streamGoogleGeminiCli()` | `stream_google_gemini_cli()` | Done | Uses httpx for raw HTTP streaming |
| `streamSimpleGoogleGeminiCli()` | `stream_simple_google_gemini_cli()` | Done | |

## providers/amazon-bedrock.ts → providers/amazon_bedrock.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `interface BedrockOptions` | `@dataclass BedrockOptions` | Done | Extends StreamOptions, adds region/profile |
| `streamBedrock()` | `stream_bedrock()` | Done | Uses boto3 bedrock-runtime converse_stream |
| `streamSimpleBedrock()` | `stream_simple_bedrock()` | Done | |

## utils/oauth/types.ts → oauth/types.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `type OAuthCredentials` | `@dataclass OAuthCredentials` | Done | |
| `type OAuthProviderId` | `OAuthProviderId` (str alias) | Done | |
| `type OAuthPrompt` | `@dataclass OAuthPrompt` | Done | |
| `type OAuthAuthInfo` | `@dataclass OAuthAuthInfo` | Done | |
| `interface OAuthLoginCallbacks` | `@dataclass OAuthLoginCallbacks` | Done | |
| `interface OAuthProviderInterface` | `class OAuthProviderInterface` (Protocol) | Done | |
| `interface OAuthProviderInfo` | `@dataclass OAuthProviderInfo` | Done | |

## utils/oauth/pkce.ts → oauth/pkce.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `generatePKCE()` | `generate_pkce()` | Done | Returns (verifier, challenge) tuple |

## utils/oauth/index.ts → oauth/__init__.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `getOAuthProvider()` | `get_oauth_provider()` | Done | |
| `registerOAuthProvider()` | `register_oauth_provider()` | Done | |
| `getOAuthProviders()` | `get_oauth_providers()` | Done | |
| `getOAuthProviderInfoList()` | `get_oauth_provider_info_list()` | Done | Deprecated |
| `refreshOAuthToken()` | `refresh_oauth_token()` | Done | Deprecated |
| `getOAuthApiKey()` | `get_oauth_api_key()` | Done | Auto-refreshes expired tokens |

## utils/oauth/anthropic.ts → oauth/anthropic_oauth.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `loginAnthropic()` | `login_anthropic()` | Done | |
| `refreshAnthropicToken()` | `refresh_anthropic_token()` | Done | |
| `anthropicOAuthProvider` | `anthropic_oauth_provider` | Done | |

## utils/oauth/github-copilot.ts → oauth/github_copilot.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `normalizeDomain()` | `normalize_domain()` | Done | |
| `getGitHubCopilotBaseUrl()` | `get_github_copilot_base_url()` | Done | |
| `refreshGitHubCopilotToken()` | `refresh_github_copilot_token()` | Done | |
| `loginGitHubCopilot()` | `login_github_copilot()` | Done | Device code flow |
| `githubCopilotOAuthProvider` | `github_copilot_oauth_provider` | Done | |

## utils/oauth/google-gemini-cli.ts → oauth/google_gemini_cli.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `refreshGoogleCloudToken()` | `refresh_google_cloud_token()` | Done | |
| `loginGeminiCli()` | `login_gemini_cli()` | Done | Local callback server + PKCE |
| `geminiCliOAuthProvider` | `gemini_cli_oauth_provider` | Done | |

## utils/oauth/google-antigravity.ts → oauth/google_antigravity.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `refreshAntigravityToken()` | `refresh_antigravity_token()` | Done | |
| `loginAntigravity()` | `login_antigravity()` | Done | Local callback server + PKCE |
| `antigravityOAuthProvider` | `antigravity_oauth_provider` | Done | |

## utils/oauth/openai-codex.ts → oauth/openai_codex.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `loginOpenAICodex()` | `login_openai_codex()` | Done | Local callback server + PKCE |
| `refreshOpenAICodexToken()` | `refresh_openai_codex_token()` | Done | |
| `openaiCodexOAuthProvider` | `openai_codex_oauth_provider` | Done | |
