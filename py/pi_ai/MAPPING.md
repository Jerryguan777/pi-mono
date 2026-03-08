# pi_ai Module Mapping (TS -> Python)

## types.ts -> types.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| type KnownApi | KnownApi (Literal) | Done | |
| type Api | Api (str alias) | Done | |
| type KnownProvider | KnownProvider (Literal) | Done | |
| type Provider | Provider (str alias) | Done | |
| type ThinkingLevel | ThinkingLevel (Literal) | Done | |
| interface ThinkingBudgets | @dataclass ThinkingBudgets | Done | |
| type CacheRetention | CacheRetention (Literal) | Done | |
| type Transport | Transport (Literal) | Done | |
| interface StreamOptions | @dataclass StreamOptions | Done | signal: AbortSignal -> asyncio.Event |
| interface SimpleStreamOptions | @dataclass SimpleStreamOptions | Done | Extends StreamOptions |
| type StreamFunction | (not ported) | Done | Not needed; Python uses plain functions |
| type ProviderStreamOptions | (not ported) | Done | Not needed in Python |
| interface TextContent | @dataclass TextContent | Done | Added text_signature field |
| interface ThinkingContent | @dataclass ThinkingContent | Done | |
| interface ImageContent | @dataclass ImageContent | Done | |
| interface ToolCall | @dataclass ToolCall | Done | |
| interface Usage | @dataclass Usage | Done | Includes nested UsageCost |
| type StopReason | StopReason (Literal) | Done | |
| interface UserMessage | @dataclass UserMessage | Done | |
| interface AssistantMessage | @dataclass AssistantMessage | Done | |
| interface ToolResultMessage | @dataclass ToolResultMessage | Done | |
| type Message | Message (Union type alias) | Done | |
| interface Tool | @dataclass Tool | Done | |
| interface Context | @dataclass Context | Done | |
| type AssistantMessageEvent | AssistantMessageEvent (Union) | Done | |
| interface Model | @dataclass Model | Done | Includes nested ModelCost |
| type (UsageCost inline) | @dataclass UsageCost | Done | Extracted to standalone dataclass |
| type (ModelCost inline) | @dataclass ModelCost | Done | Extracted to standalone dataclass |
| StartEvent (inline) | @dataclass StartEvent | Done | |
| TextStartEvent (inline) | @dataclass TextStartEvent | Done | |
| TextDeltaEvent (inline) | @dataclass TextDeltaEvent | Done | |
| TextEndEvent (inline) | @dataclass TextEndEvent | Done | |
| ThinkingStartEvent (inline) | @dataclass ThinkingStartEvent | Done | |
| ThinkingDeltaEvent (inline) | @dataclass ThinkingDeltaEvent | Done | |
| ThinkingEndEvent (inline) | @dataclass ThinkingEndEvent | Done | |
| ToolCallStartEvent (inline) | @dataclass ToolCallStartEvent | Done | |
| ToolCallDeltaEvent (inline) | @dataclass ToolCallDeltaEvent | Done | |
| ToolCallEndEvent (inline) | @dataclass ToolCallEndEvent | Done | |
| DoneEvent (inline) | @dataclass DoneEvent | Done | |
| ErrorEvent (inline) | @dataclass ErrorEvent | Done | |
| AssistantContentBlock (inline) | AssistantContentBlock (type alias) | Done | |

## models.ts -> models.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| calculateCost() | calculate_cost() | Done | Mutates usage.cost in place |

## utils/event-stream.ts -> event_stream.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| class EventStream<T, R> | class EventStream[T, R] | Done | Uses asyncio.Queue for push-based iteration |
| class AssistantMessageEventStream | class AssistantMessageEventStream | Done | Extends EventStream |
| createAssistantMessageEventStream() | (constructor) | Done | Just use AssistantMessageEventStream() |

## utils/sanitize-unicode.ts -> utils/sanitize_unicode.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| sanitizeSurrogates() | sanitize_surrogates() | Done | Uses encode/decode with surrogatepass |

## utils/json-parse.ts -> utils/json_parse.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| parseStreamingJson() | parse_streaming_json() | Done | Handles partial JSON from streaming tool calls |

## providers/simple-options.ts -> providers/simple_options.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| buildBaseOptions() | build_base_options() | Done | |
| clampReasoning() | clamp_reasoning() | Done | |
| adjustMaxTokensForThinking() | adjust_max_tokens_for_thinking() | Done | Returns (max_tokens, thinking_budget) tuple |

## providers/transform-messages.ts -> providers/transform_messages.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| transformMessages() | transform_messages() | Done | Handles thinking blocks, orphaned tool calls |

## providers/google-shared.ts -> providers/google_shared.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| isThinkingPart() | is_thinking_part() | Done | |
| retainThoughtSignature() | retain_thought_signature() | Done | |
| requiresToolCallId() | requires_tool_call_id() | Done | |
| convertMessages() | convert_messages() | Done | Converts to Gemini Content[] format |
| convertTools() | convert_tools() | Done | |
| mapToolChoice() | map_tool_choice() | Done | |
| mapStopReason() | map_stop_reason() | Done | |
| mapStopReasonString() | map_stop_reason_string() | Done | |

## providers/google.ts -> providers/google.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| interface GoogleOptions | @dataclass GoogleOptions | Done | Extends StreamOptions |
| streamGoogle() | stream_google() | Done | Uses google-genai SDK |
| streamSimpleGoogle() | stream_simple_google() | Done | Handles reasoning level mapping |
| (GoogleThinkingConfig inline) | @dataclass GoogleThinkingConfig | Done | |

## providers/google-vertex.ts -> providers/google_vertex.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| interface GoogleVertexOptions | @dataclass GoogleVertexOptions | Done | Extends StreamOptions, adds project/location |
| streamGoogleVertex() | stream_google_vertex() | Done | Uses google-genai SDK with vertexai=True |
| streamSimpleGoogleVertex() | stream_simple_google_vertex() | Done | Handles reasoning level mapping |
| (GoogleVertexThinkingConfig inline) | @dataclass GoogleVertexThinkingConfig | Done | |

## providers/google-gemini-cli.ts -> providers/google_gemini_cli.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| type GoogleThinkingLevel | GoogleThinkingLevel (Literal) | Done | |
| interface GoogleGeminiCliOptions | @dataclass GoogleGeminiCliOptions | Done | Extends StreamOptions |
| extractRetryDelay() | extract_retry_delay() | Done | |
| buildRequest() | build_request() | Done | |
| streamGoogleGeminiCli() | stream_google_gemini_cli() | Done | Uses httpx for raw HTTP streaming |
| streamSimpleGoogleGeminiCli() | stream_simple_google_gemini_cli() | Done | Handles reasoning for Gemini CLI/Antigravity |

## providers/amazon-bedrock.ts -> providers/amazon_bedrock.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| interface BedrockOptions | @dataclass BedrockOptions | Done | Extends StreamOptions, adds region/profile |
| streamBedrock() | stream_bedrock() | Done | Uses boto3 bedrock-runtime converse_stream |
| streamSimpleBedrock() | stream_simple_bedrock() | Done | Handles Claude thinking configuration |

## utils/oauth/types.ts -> oauth/types.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| type OAuthCredentials | @dataclass OAuthCredentials | Done | Dict-like access via __getitem__/__setitem__ |
| type OAuthProviderId | OAuthProviderId (str alias) | Done | |
| type OAuthPrompt | @dataclass OAuthPrompt | Done | |
| type OAuthAuthInfo | @dataclass OAuthAuthInfo | Done | |
| interface OAuthLoginCallbacks | @dataclass OAuthLoginCallbacks | Done | |
| interface OAuthProviderInterface | class OAuthProviderInterface (Protocol) | Done | |
| interface OAuthProviderInfo | @dataclass OAuthProviderInfo | Done | |

## utils/oauth/pkce.ts -> oauth/pkce.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| generatePKCE() | generate_pkce() | Done | Returns (verifier, challenge) tuple |

## utils/oauth/index.ts -> oauth/__init__.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| getOAuthProvider() | get_oauth_provider() | Done | |
| registerOAuthProvider() | register_oauth_provider() | Done | |
| getOAuthProviders() | get_oauth_providers() | Done | |
| getOAuthProviderInfoList() | get_oauth_provider_info_list() | Done | Deprecated |
| refreshOAuthToken() | refresh_oauth_token() | Done | Deprecated |
| getOAuthApiKey() | get_oauth_api_key() | Done | Auto-refreshes expired tokens |
| (re-exports) | __all__ list | Done | All sub-module exports gathered |

## utils/oauth/anthropic.ts -> oauth/anthropic_oauth.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| loginAnthropic() | login_anthropic() | Done | Manual code paste flow |
| refreshAnthropicToken() | refresh_anthropic_token() | Done | |
| anthropicOAuthProvider | anthropic_oauth_provider | Done | AnthropicOAuthProvider class instance |

## utils/oauth/github-copilot.ts -> oauth/github_copilot.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| normalizeDomain() | normalize_domain() | Done | |
| getGitHubCopilotBaseUrl() | get_github_copilot_base_url() | Done | |
| refreshGitHubCopilotToken() | refresh_github_copilot_token() | Done | |
| loginGitHubCopilot() | login_github_copilot() | Done | Device code flow |
| githubCopilotOAuthProvider | github_copilot_oauth_provider | Done | GitHubCopilotOAuthProvider class instance |

## utils/oauth/google-gemini-cli.ts -> oauth/google_gemini_cli.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| refreshGoogleCloudToken() | refresh_google_cloud_token() | Done | |
| loginGeminiCli() | login_gemini_cli() | Done | Local callback server + PKCE |
| geminiCliOAuthProvider | gemini_cli_oauth_provider | Done | GeminiCliOAuthProvider class instance |

## utils/oauth/google-antigravity.ts -> oauth/google_antigravity.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| refreshAntigravityToken() | refresh_antigravity_token() | Done | |
| loginAntigravity() | login_antigravity() | Done | Local callback server + PKCE |
| antigravityOAuthProvider | antigravity_oauth_provider | Done | AntigravityOAuthProvider class instance |

## utils/oauth/openai-codex.ts -> oauth/openai_codex.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| loginOpenAICodex() | login_openai_codex() | Done | Local callback server + PKCE |
| refreshOpenAICodexToken() | refresh_openai_codex_token() | Done | |
| openaiCodexOAuthProvider | openai_codex_oauth_provider | Done | OpenAICodexOAuthProvider class instance |
