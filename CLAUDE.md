# Pi-Mono Python Rewrite Guide

## Project Structure

This is a TypeScript -> Python rewrite project. All Python code lives under the `py/` directory.

```
py/
├── pyproject.toml          # uv workspace root config
├── uv.lock
├── ruff.toml
├── mypy.ini
├── scripts/
│   ├── extract_public_api.py   # Parse TS exports, generate Python API checklist
│   └── check_parity.py         # Compare TS exports vs Python public API, report gaps
├── pi_types/               # Shared type definitions/protocols (implement first)
├── pi_ai/                  # AI/LLM abstraction layer (maps to packages/ai/)
├── pi_tui/                 # Terminal UI library (maps to packages/tui/)
├── pi_agent/               # Agent core (maps to packages/agent/)
├── pi_coding_agent/        # Coding agent (maps to packages/coding-agent/)
├── pi_web_ui/              # Web UI (maps to packages/web-ui/)
├── pi_mom/                 # Slack bot (maps to packages/mom/)
├── pi_pods/                # Pod management (maps to packages/pods/)
└── tests/
    ├── unit/               # Unit tests (subdirs per package)
    ├── integration/        # Cross-module integration tests
    ├── e2e/                # End-to-end tests
    └── comparison/         # TS vs Python behavior comparison tests
```

TS source code is in the `packages/` directory and serves as the rewrite reference. Always read the corresponding TS source files to understand interfaces and behavior before rewriting.

## Rewrite Principles

### API Parity
- Every public export from each TS package must have a corresponding Python implementation
- Function names: camelCase -> snake_case (e.g. `streamAnthropic` -> `stream_anthropic`)
- Class names: keep PascalCase
- File names: kebab-case.ts -> snake_case.py (e.g. `agent-loop.ts` -> `agent_loop.py`)
- TS `export function` -> module-level function, unified export via `__init__.py`
- Do not omit any public class, function, type, or constant

### Core Mapping Rules

| TS Pattern | Python Equivalent | Notes |
|------------|-------------------|-------|
| `interface` / `type` | `@dataclass` | Comes with `__init__`, `__eq__`, `__repr__` |
| Discriminated union `{ type: "foo" }` | `@dataclass` + `type: Literal["foo"]` | Use `isinstance()` instead of `event.type === ""` |
| `enum` | `StrEnum` or `Literal` union | Choose based on context |
| `namespace` | Python module | |
| `{ ...obj, field: val }` (spread) | `dataclasses.replace(obj, field=val)` | Maintains immutable updates |
| `Map<K, V>` | `dict[K, V]` | |
| TypeBox schema / `Type.Object({})` | Hand-written `dict` JSON Schema | Zero dependencies, don't introduce TypeBox equivalents |
| Generics `<TApi extends Api>` | Concretize directly | Python generics are impractical here, just remove them |
| Branded types (`string & {}`) | Plain `str` | Use comments to document semantics |
| Factory function `createXxxTool()` | Class inheritance `class XxxTool(AgentTool)` | Classes are more natural than factories in Python |

**Principle: Don't try to reproduce TS type gymnastics 1:1. `dataclass` + `Literal` + `isinstance` covers 90% of cases with cleaner code.**

### Async & Streaming

| TS Pattern | Python Equivalent |
|------------|-------------------|
| Custom `EventStream<T, R>` class | Native `AsyncIterator[T]` (async generator + `yield`) |
| `stream.push(event)` + `stream.end(result)` | `yield event` + `return` |
| `stream.result()` returning `Promise<R>` | Caller collects final value after iteration |
| IIFE `(async () => { ... })()` eager start | Lazy `async def gen(): yield ...` on-demand |
| `AbortController` / `AbortSignal` | `asyncio.Event` |
| `new Promise(resolve => ...)` manual resolve | `asyncio.Event().wait()` / `.set()` |
| `Promise.all([...])` | `asyncio.gather(...)` |

**Principle: Python's async generator is the natural replacement for EventStream. Don't port the EventStream class — just use `yield`. Use `asyncio.Event` as a unified replacement for AbortController.**

### Python Best Practices
- Async code uses `asyncio` + `async`/`await`, no threads
- Streaming uses `async generator` (`async def stream() -> AsyncIterator[...]`)
- Error handling uses exceptions, not error codes
- Type annotations use Python 3.12+ syntax (`list[str]` not `List[str]`, `X | None` not `Optional[X]`)
- File paths use `pathlib.Path`
- Logging uses the `logging` module
- Configuration uses `pydantic-settings` or environment variables
- Strings use f-strings
- State management: use instance attributes directly (`self.model`, `self.messages`, etc.) instead of a single state object pattern; but keep the `subscribe()` + `_emit()` event notification pattern
- Serialization: `dataclass` is not JSON-native — write explicit `serialize` / `deserialize` functions, which are lighter and more controllable than pydantic's `.model_dump()`. Keep serialization functions in the same module as type definitions

### Don'ts
- Don't translate TS code line-by-line — write Pythonic implementations
- Don't keep TS-style callback/Promise chains — use async/await
- Don't use bare dicts where structured data should be a class
- Don't carry TS null/undefined dual-value logic into Python (Python only has None)
- Don't add features that don't exist in the TS source
- Don't omit public APIs that exist in the TS source
- Don't prematurely abstract the I/O layer (e.g. Operations interface) — operate on files directly in the initial port, add abstraction later if remote execution is needed
- Don't introduce heavyweight type validation libraries to replace TypeBox — hand-written dict JSON Schema is sufficient

## Required Deliverables Per Module

1. **Implementation code** — with full type annotations, placed in `py/<package_name>/`
2. **MAPPING.md** — placed in `py/<package_name>/MAPPING.md`, format:
   ```markdown
   | TS Function/Class | Python Equivalent | Status | Notes |
   |-------------------|-------------------|--------|-------|
   | streamAnthropic() | stream_anthropic() | Done | Uses anthropic SDK |
   ```
3. **Unit tests** — placed in `py/tests/unit/<package_name>/`, coverage >= 80%
4. **Pass mypy --strict** (run in `py/` directory)
5. **Pass ruff check && ruff format** (run in `py/` directory)

## Quality Tools (all run from the `py/` directory)

```bash
cd py/
uv sync                         # Install dependencies
ruff check .                    # Lint
ruff format .                   # Format
mypy --strict .                 # Type check
pytest --cov --cov-fail-under=80  # Tests + coverage
python scripts/check_parity.py  # TS vs Python API parity check
```

## Tech Stack

| Purpose | Python Library |
|---------|---------------|
| Package management | uv workspace |
| Type checking | mypy (strict) |
| Lint + formatting | ruff |
| Testing | pytest + pytest-asyncio (auto mode) + pytest-cov |
| Data models | dataclass (lightweight) / pydantic (when validation is needed) |
| CLI | typer or click |
| HTTP client | httpx |
| OpenAI | openai |
| Anthropic | anthropic |
| Google AI | google-genai |
| AWS Bedrock | boto3 |
| Slack | slack-bolt |
| SSH | asyncssh or paramiko |
| Terminal UI | textual or prompt-toolkit |
| Git | gitpython or subprocess |
| Mocking | unittest.mock.AsyncMock (replaces vitest's vi.fn()) |

## Scripts

### extract_public_api.py
- **Input**: TS source file or directory path
- **Behavior**: Parses all `export`ed functions, classes, types, interfaces, and consts
- **Output**: Markdown checklist with each export's name, kind, and signature
- **Usage**: `python scripts/extract_public_api.py ../../packages/ai/src/types.ts`
- **Example output**:
  ```
  - [ ] type Message -> class/TypedDict
  - [ ] function createStream() -> async def create_stream()
  - [ ] const DEFAULT_MODEL -> DEFAULT_MODEL
  ```

### check_parity.py
- **Input**: TS package path + corresponding Python package path
- **Behavior**: Compares TS export list vs Python `__all__` / public API
- **Output**: Reports missing, extra, and name-mismatched items
- **Usage**: `python scripts/check_parity.py ../../packages/ai/src pi_ai`

## Workflow

1. Read the task scope and acceptance criteria from the GitHub Issue
2. Read the corresponding TS source files to understand interfaces and behavior
3. Run `python scripts/extract_public_api.py` to generate the API checklist
4. Define Python interfaces (Protocol / ABC) first, then implement
5. Write tests immediately after implementing each function/class
6. Fill in MAPPING.md
7. Run all quality checks (ruff, mypy, pytest)
8. Commit and push to the current branch
