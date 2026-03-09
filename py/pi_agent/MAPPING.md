# pi_agent Python Package Mapping

## TypeScript -> Python Module Mapping

| TypeScript file | Python file | Notes |
|----------------|-------------|-------|
| `packages/agent/src/types.ts` | `pi_agent/types.py` | Discriminated unions as dataclasses |
| `packages/agent/src/agent-loop.ts` | `pi_agent/agent_loop.py` | EventStream replaced with async generators |
| `packages/agent/src/agent.ts` | `pi_agent/agent.py` | Class with asyncio.Future for idle tracking |
| `packages/agent/src/proxy.ts` | `pi_agent/proxy.py` | httpx.AsyncClient replaces browser fetch |

## Key Design Decisions

### Async Generators instead of EventStream
The TypeScript codebase uses an `EventStream` class for streaming events. In Python, we use
native `AsyncIterator` via `async def` functions with `yield` statements. This is cleaner and
idiomatic Python.

### asyncio.Event replaces AbortSignal/AbortController
TypeScript uses `AbortSignal` and `AbortController` for cancellation. Python uses
`asyncio.Event` — when set, it signals abort. All async operations check `signal.is_set()`
after completion.

### asyncio.Future replaces Promise for wait_for_idle
TypeScript's `Agent.waitForIdle()` awaits a stored Promise. Python uses
`asyncio.Future[None]` created via `asyncio.get_running_loop().create_future()`.

### dataclass instead of interface/type
TypeScript interfaces and type aliases become Python `@dataclass` classes. Union types
(`AgentEvent`, `ProxyAssistantMessageEvent`) remain as Python union type aliases.

### ABC for AgentTool
TypeScript abstract classes become Python `ABC` with `@abstractmethod`. Concrete tools
subclass `AgentTool` and implement `execute()`.

### httpx instead of fetch
The proxy streaming uses `httpx.AsyncClient` with `client.stream()` for SSE streaming,
replacing the browser `fetch` API.

### inspect.isawaitable for dual sync/async callbacks
TypeScript callbacks can only be sync or async (explicit in type signature). Python
callbacks may return either; we use `inspect.isawaitable()` to handle both cases.

## Type Aliases

```python
AgentMessage = Message          # UserMessage | AssistantMessage | ToolResultMessage
AgentEvent = AgentStartEvent | AgentEndEvent | ...  # union of all event types
ProxyAssistantMessageEvent = ProxyStartEvent | ...  # union of all proxy event types
ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]
```

## Notable Changes from TypeScript

1. `agent_loop_continue` renamed from `agentLoopContinue` (snake_case)
2. `Agent.continue_()` renamed from `Agent.continue()` (Python keyword conflict)
3. `steering_mode`/`follow_up_mode` stored as `str` (no enum, matches TS string literal)
4. Tool validation uses `pi_ai.utils.validation.validate_tool_arguments` (same as TS AJV)
5. `_make_default_model()` has try/except fallback in case model isn't registered
