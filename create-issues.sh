#!/bin/bash
set -e
cd ~/pi-mono

# --- Phase 0: Task 0.1 ---
gh issue create \
  --title "[Python Rewrite] Project Scaffolding & Shared Types (Task 0.1)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Set up the Python monorepo workspace under `py/` and implement shared type definitions. This is the foundation all other tasks depend on.

## Scope

### 1. Create `py/` directory with uv workspace config

Create `py/pyproject.toml` as a uv workspace root:
```toml
[project]
name = "pi-mono"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["pi_types", "pi_ai", "pi_tui", "pi_agent", "pi_coding_agent", "pi_web_ui", "pi_mom", "pi_pods"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 2. Create `py/ruff.toml`
```toml
target-version = "py312"
line-length = 120

[lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]

[format]
quote-style = "double"
```

### 3. Create `py/mypy.ini`
```ini
[mypy]
python_version = 3.12
strict = True
warn_return_any = True
warn_unused_configs = True
```

### 4. Create `py/pi_types/` package

This package holds shared type definitions used across all other packages. Translate the following from TS:

**From `packages/ai/src/types.ts` — create `py/pi_types/ai_types.py`:**
- `KnownApi` — `Literal` union of: `"openai-completions"`, `"openai-responses"`, `"azure-openai-responses"`, `"openai-codex-responses"`, `"anthropic-messages"`, `"bedrock-converse-stream"`, `"google-generative-ai"`, `"google-gemini-cli"`, `"google-vertex"`
- `Api` — `str` (type alias)
- `KnownProvider` — `Literal` union of: `"amazon-bedrock"`, `"anthropic"`, `"google"`, `"google-gemini-cli"`, `"google-antigravity"`, `"google-vertex"`, `"openai"`, `"azure-openai-responses"`, `"openai-codex"`, `"github-copilot"`, `"xai"`, `"groq"`, `"cerebras"`, `"openrouter"`, `"vercel-ai-gateway"`, `"zai"`, `"mistral"`, `"minimax"`, `"minimax-cn"`, `"huggingface"`, `"opencode"`, `"kimi-coding"`
- `Provider` — `str` (type alias)
- `ThinkingLevel` — `Literal["minimal", "low", "medium", "high", "xhigh"]`
- `@dataclass ThinkingBudgets` — fields: `minimal: int | None`, `low: int | None`, `medium: int | None`, `high: int | None`
- `CacheRetention` — `Literal["none", "short", "long"]`
- `Transport` — `Literal["sse", "websocket", "auto"]`
- `@dataclass StreamOptions` — fields: `temperature: float | None`, `max_tokens: int | None`, `signal: asyncio.Event | None`, `api_key: str | None`, `transport: Transport | None`, `cache_retention: CacheRetention | None`, `session_id: str | None`, `on_payload: Callable[[Any], None] | None`, `headers: dict[str, str] | None`, `max_retry_delay_ms: int | None`, `metadata: dict[str, Any] | None`
- `@dataclass SimpleStreamOptions(StreamOptions)` — adds: `reasoning: ThinkingLevel | None`, `thinking_budgets: ThinkingBudgets | None`
- `@dataclass TextContent` — fields: `type: Literal["text"]`, `text: str`, `text_signature: str | None`
- `@dataclass ThinkingContent` — fields: `type: Literal["thinking"]`, `thinking: str`, `thinking_signature: str | None`
- `@dataclass ImageContent` — fields: `type: Literal["image"]`, `data: str`, `mime_type: str`
- `@dataclass ToolCall` — fields: `type: Literal["toolCall"]`, `id: str`, `name: str`, `arguments: dict[str, Any]`, `thought_signature: str | None`
- `@dataclass Usage` — fields: `input: int`, `output: int`, `cache_read: int`, `cache_write: int`, `total_tokens: int`, `cost: UsageCost`
- `@dataclass UsageCost` — fields: `input: float`, `output: float`, `cache_read: float`, `cache_write: float`, `total: float`
- `StopReason` — `Literal["stop", "length", "toolUse", "error", "aborted"]`
- `@dataclass UserMessage` — fields: `role: Literal["user"]`, `content: str | list[TextContent | ImageContent]`, `timestamp: int`
- `@dataclass AssistantMessage` — fields: `role: Literal["assistant"]`, `content: list[TextContent | ThinkingContent | ToolCall]`, `api: str`, `provider: str`, `model: str`, `usage: Usage`, `stop_reason: StopReason`, `error_message: str | None`, `timestamp: int`
- `@dataclass ToolResultMessage` — fields: `role: Literal["toolResult"]`, `tool_call_id: str`, `tool_name: str`, `content: list[TextContent | ImageContent]`, `details: Any`, `is_error: bool`, `timestamp: int`
- `Message` — type alias `UserMessage | AssistantMessage | ToolResultMessage`
- `@dataclass Tool` — fields: `name: str`, `description: str`, `parameters: dict[str, Any]` (JSON Schema dict, replaces TypeBox TSchema)
- `@dataclass Context` — fields: `system_prompt: str | None`, `messages: list[Message]`, `tools: list[Tool] | None`
- `@dataclass Model` — fields: `id: str`, `name: str`, `api: str`, `provider: str`, `base_url: str`, `reasoning: bool`, `input: list[str]`, `cost: ModelCost`, `context_window: int`, `max_tokens: int`, `headers: dict[str, str] | None`, `compat: dict[str, Any] | None`
- `@dataclass ModelCost` — fields: `input: float`, `output: float`, `cache_read: float`, `cache_write: float`
- `AssistantMessageEvent` — discriminated union (use `@dataclass` per variant with `type: Literal[...]`): `Start`, `TextStart`, `TextDelta`, `TextEnd`, `ThinkingStart`, `ThinkingDelta`, `ThinkingEnd`, `ToolcallStart`, `ToolcallDelta`, `ToolcallEnd`, `Done`, `Error`
- `@dataclass OpenAICompletionsCompat` — all optional bool/str fields matching TS interface
- `@dataclass OpenRouterRouting` — fields: `only: list[str] | None`, `order: list[str] | None`
- `@dataclass VercelGatewayRouting` — fields: `only: list[str] | None`, `order: list[str] | None`

Write `serialize()` and `deserialize()` functions for `Message`, `AssistantMessage`, `ToolResultMessage`, `Usage`.

**From `packages/agent/src/types.ts` — create `py/pi_types/agent_types.py`:**
- `AgentThinkingLevel` — `Literal["off", "minimal", "low", "medium", "high", "xhigh"]` (superset of AI ThinkingLevel)
- `AgentMessage` — type alias `Message | Any` (extensible via custom messages)
- `@dataclass AgentState` — fields: `system_prompt: str`, `model: Model`, `thinking_level: AgentThinkingLevel`, `tools: list[AgentTool]`, `messages: list[AgentMessage]`, `is_streaming: bool`, `stream_message: AgentMessage | None`, `pending_tool_calls: set[str]`, `error: str | None`
- `@dataclass AgentToolResult` — fields: `content: list[TextContent | ImageContent]`, `details: Any`
- `AgentToolUpdateCallback` — `Callable[[AgentToolResult], None]`
- `@dataclass AgentTool(Tool)` — adds: `label: str`, `execute: Callable` (async, signature: `(tool_call_id: str, params: dict, signal: asyncio.Event | None, on_update: AgentToolUpdateCallback | None) -> AgentToolResult`)
- `@dataclass AgentContext` — fields: `system_prompt: str`, `messages: list[AgentMessage]`, `tools: list[AgentTool] | None`
- `@dataclass AgentLoopConfig` — fields: `model: Model`, `convert_to_llm: Callable`, `transform_context: Callable | None`, `get_api_key: Callable | None`, `get_steering_messages: Callable | None`, `get_follow_up_messages: Callable | None`, plus all SimpleStreamOptions fields
- `AgentEvent` — discriminated union (`@dataclass` per variant): `AgentStart`, `AgentEnd`, `TurnStart`, `TurnEnd`, `MessageStart`, `MessageUpdate`, `MessageEnd`, `ToolExecutionStart`, `ToolExecutionUpdate`, `ToolExecutionEnd`

**Create `py/pi_types/__init__.py`:**
Export all public types from `ai_types` and `agent_types` via `__all__`.

**Create `py/pi_types/pyproject.toml`:**
```toml
[project]
name = "pi-types"
version = "0.1.0"
requires-python = ">=3.12"
```

### 5. Create `py/scripts/extract_public_api.py`

- Accept a TS file or directory path as CLI argument
- Parse each file for lines matching: `export (function|class|type|interface|const|enum) NAME`
- For each export, output a markdown checklist line:
  - `- [ ] type Name -> @dataclass Name`
  - `- [ ] function camelName() -> def snake_name()`
  - `- [ ] const NAME -> NAME`
  - `- [ ] enum Name -> class Name(StrEnum)`
  - `- [ ] class Name -> class Name`
- Convert function names from camelCase to snake_case in the output
- Handle `export { Name } from "./module"` re-exports
- Handle `export default` and `export *` (list as "re-export")

### 6. Create `py/scripts/check_parity.py` (skeleton)

- Accept two CLI arguments: TS source path and Python package name
- Use `extract_public_api.py` logic to get TS exports
- Scan Python package's `__all__` or public symbols (no underscore prefix)
- Convert TS names (camelCase) to Python names (snake_case) for comparison
- Output a report with sections: "Missing in Python", "Extra in Python", "Name mismatches"
- For now, implement the CLI structure and TS parsing; Python scanning can return a placeholder

### 7. Add `py/.github/workflows/python-ci.yml` (or update existing CI)

Create a GitHub Actions workflow at `.github/workflows/python-ci.yml`:
```yaml
name: Python CI
on:
  push:
    paths: ['py/**']
  pull_request:
    paths: ['py/**']
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: cd py && uv sync
      - run: cd py && ruff check .
      - run: cd py && ruff format --check .
      - run: cd py && mypy --strict .
      - run: cd py && pytest --cov --cov-fail-under=80
```

### 8. Create stub packages for all workspace members

Create minimal `pyproject.toml` + `__init__.py` for: `pi_ai`, `pi_tui`, `pi_agent`, `pi_coding_agent`, `pi_web_ui`, `pi_mom`, `pi_pods`. Each `pyproject.toml`:
```toml
[project]
name = "pi-<name>"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pi-types"]
```

### 9. Create test directory structure

```
py/tests/__init__.py
py/tests/unit/__init__.py
py/tests/unit/pi_types/__init__.py
py/tests/unit/pi_types/test_ai_types.py    # Test serialization/deserialization round-trip
py/tests/unit/pi_types/test_agent_types.py  # Test dataclass construction
```

Write tests for:
- Constructing each dataclass with valid data
- `serialize()` / `deserialize()` round-trip for Message types
- Type discrimination (isinstance checks on union types)
- Default values for optional fields

## Acceptance Criteria
- [ ] `cd py && uv sync` succeeds without errors
- [ ] `cd py && ruff check .` passes with zero violations
- [ ] `cd py && ruff format --check .` passes (already formatted)
- [ ] `cd py && mypy --strict .` passes with zero errors
- [ ] `cd py && pytest` passes — all tests in `tests/unit/pi_types/` green
- [ ] `from pi_types import Message, UserMessage, AssistantMessage, ToolResultMessage, Model, Tool, Context` works
- [ ] `from pi_types import AgentState, AgentTool, AgentToolResult, AgentEvent, AgentLoopConfig` works
- [ ] `python scripts/extract_public_api.py ../../packages/ai/src/types.ts` outputs a markdown checklist
- [ ] `python scripts/check_parity.py ../../packages/ai/src pi_ai` runs without crashing (output may show gaps)
- [ ] `.github/workflows/python-ci.yml` exists and is valid YAML
- [ ] All stub packages (`pi_ai`, `pi_tui`, etc.) are importable

## Metadata
- Phase: 0
- Package: pi_types (+ workspace scaffolding)
- TS reference files: `packages/ai/src/types.ts` (308 lines), `packages/agent/src/types.ts` (195 lines)
- Estimated Python lines: ~800
EOF
)"

# --- Phase 1: Task 1.1a - TUI Core ---
gh issue create \
  --title "[Python Rewrite] pi_tui: Terminal, Keys, Editor, TUI Framework (Task 1.1a)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the core TUI infrastructure from `packages/tui/src/`. This covers terminal abstraction, keyboard input handling, the editor component, and the main TUI framework. Total TS source: ~4,800 lines across 10 files.

## Scope

### Files to Rewrite

**`packages/tui/src/terminal.ts` -> `py/pi_tui/terminal.py`**
Exports to implement:
- `Terminal` — protocol/ABC defining terminal interface (write, read, resize, cursor operations)
- `ProcessTerminal` — concrete implementation using `sys.stdin`/`sys.stdout`

**`packages/tui/src/keys.ts` -> `py/pi_tui/keys.py`**
Exports to implement:
- `class Key` — represents a parsed keyboard input (key name, modifiers, raw bytes)
- `KeyId` — type alias for key identifiers (e.g., `"ctrl+c"`, `"enter"`, `"a"`)
- `KeyEventType` — `Literal["press", "repeat", "release"]`
- `parse_key(data: bytes) -> Key` — parse raw terminal input into Key objects
- `matches_key(key: Key, pattern: str) -> bool` — check if a key matches a pattern like `"ctrl+c"`
- `is_key_repeat(key: Key) -> bool`
- `is_key_release(key: Key) -> bool`
- `is_kitty_protocol_active() -> bool`
- `set_kitty_protocol_active(active: bool) -> None`

**`packages/tui/src/keybindings.ts` -> `py/pi_tui/keybindings.py`**
Exports to implement:
- `EditorAction` — `Literal` union of all editor actions (e.g., `"submit"`, `"newline"`, `"deleteBack"`, etc.)
- `@dataclass EditorKeybindingsConfig` — mapping of action -> key patterns
- `DEFAULT_EDITOR_KEYBINDINGS` — const with default keybinding configuration
- `class EditorKeybindingsManager` — manages keybinding lookup and customization
- `get_editor_keybindings() -> EditorKeybindingsConfig`
- `set_editor_keybindings(config: EditorKeybindingsConfig) -> None`

**`packages/tui/src/editor-component.ts` -> `py/pi_tui/editor_component.py`**
Exports to implement:
- `EditorComponent` — protocol/ABC for custom editor widgets (methods: `handle_key`, `render`, `get_cursor_position`)

**`packages/tui/src/kill-ring.ts` -> `py/pi_tui/kill_ring.py`**
Exports to implement:
- `class KillRing` — clipboard ring buffer for cut/copy/paste (methods: `kill`, `yank`, `yank_pop`, `current`)

**`packages/tui/src/undo-stack.ts` -> `py/pi_tui/undo_stack.py`**
Exports to implement:
- `class UndoStack` — undo/redo history (methods: `push`, `undo`, `redo`, `can_undo`, `can_redo`)

**`packages/tui/src/stdin-buffer.ts` -> `py/pi_tui/stdin_buffer.py`**
Exports to implement:
- `@dataclass StdinBufferOptions` — configuration (e.g., max buffer size)
- `StdinBufferEventMap` — type for event callbacks
- `class StdinBuffer` — buffers raw stdin and splits into individual key events, emits parsed Key objects

**`packages/tui/src/tui.ts` -> `py/pi_tui/tui.py`**
Exports to implement:
- `Component` — protocol/ABC: `render(width: int, height: int) -> list[str]`
- `Focusable` — protocol extending Component with `handle_key(key: Key) -> bool`
- `is_focusable(component: Component) -> bool` — isinstance check
- `SizeValue` — type for dimension values (int or `"auto"` or `"fill"`)
- `CURSOR_MARKER` — const string used to mark cursor position in rendered output
- `@dataclass OverlayOptions` — fields: `anchor: OverlayAnchor`, `margin: OverlayMargin`, `size: ...`
- `OverlayAnchor`, `OverlayMargin`, `OverlayHandle` — types for overlay positioning
- `class Container` — layout container for arranging components
- `class TUI` — main TUI application class (manages render loop, focus, overlays, terminal interaction)

**`packages/tui/src/utils.ts` -> `py/pi_tui/utils.py`**
Exports to implement:
- `visible_width(text: str) -> int` — calculate display width accounting for ANSI codes and wide chars
- `truncate_to_width(text: str, width: int) -> str` — truncate text to fit display width
- `wrap_text_with_ansi(text: str, width: int) -> list[str]` — word-wrap preserving ANSI codes

**`packages/tui/src/fuzzy.ts` -> `py/pi_tui/fuzzy.py`**
Exports to implement:
- `@dataclass FuzzyMatch` — fields: `item: T`, `score: int`, `positions: list[int]`
- `fuzzy_match(pattern: str, text: str) -> FuzzyMatch | None` — single item match
- `fuzzy_filter(pattern: str, items: list[T], key: Callable) -> list[FuzzyMatch]` — filter and sort by score

**`packages/tui/src/autocomplete.ts` -> `py/pi_tui/autocomplete.py`**
Exports to implement:
- `@dataclass AutocompleteItem` — fields: `label: str`, `value: str`, `description: str | None`
- `AutocompleteProvider` — protocol: `get_completions(text: str, cursor: int) -> list[AutocompleteItem]`
- `@dataclass SlashCommand` — fields: `name: str`, `description: str`
- `class CombinedAutocompleteProvider` — merges multiple providers

### Create `py/pi_tui/__init__.py`
Export all public symbols via `__all__`.

### Create `py/pi_tui/pyproject.toml`
```toml
[project]
name = "pi-tui"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pi-types"]
```

## Key Design Decisions
- Use `asyncio` for the TUI event loop, not threads
- Terminal I/O: use raw mode via `tty.setraw()` and `termios`
- ANSI escape parsing: implement directly, no external dependency
- Wide character width: use `unicodedata.east_asian_width()` or `wcwidth` package
- Kitty keyboard protocol: implement the subset needed for key repeat/release detection

## Tests — `py/tests/unit/pi_tui/`
- `test_keys.py`: Test `parse_key()` with various escape sequences (arrow keys, ctrl+c, unicode, function keys)
- `test_keybindings.py`: Test default keybindings, custom keybindings, key matching
- `test_kill_ring.py`: Test kill/yank/yank_pop cycle
- `test_undo_stack.py`: Test push/undo/redo boundaries
- `test_fuzzy.py`: Test fuzzy matching scoring and filtering
- `test_utils.py`: Test `visible_width`, `truncate_to_width`, `wrap_text_with_ansi` with ANSI codes and wide chars
- `test_autocomplete.py`: Test CombinedAutocompleteProvider merging

## Acceptance Criteria
- [ ] All exported symbols listed above exist in `py/pi_tui/`
- [ ] `MAPPING.md` created at `py/pi_tui/MAPPING.md`
- [ ] `cd py && mypy --strict pi_tui/` passes
- [ ] `cd py && ruff check pi_tui/` passes
- [ ] `cd py && pytest tests/unit/pi_tui/ --cov=pi_tui --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1 (project scaffolding)

## Metadata
- Phase: 1
- Package: tui
- TS reference: `packages/tui/src/` (terminal.ts, keys.ts, keybindings.ts, editor-component.ts, kill-ring.ts, undo-stack.ts, stdin-buffer.ts, tui.ts, utils.ts, fuzzy.ts, autocomplete.ts)
- TS lines: ~4,800
- Estimated Python lines: ~3,500
EOF
)"

# --- Phase 1: Task 1.1b - TUI Components ---
gh issue create \
  --title "[Python Rewrite] pi_tui: UI Components (Task 1.1b)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the TUI component library from `packages/tui/src/components/` and `terminal-image.ts`. These are reusable UI widgets built on the TUI framework from Task 1.1a.

## Scope

### Files to Rewrite

**`packages/tui/src/components/box.ts` -> `py/pi_tui/components/box.py`**
- `class Box(Component)` — bordered/padded container component

**`packages/tui/src/components/text.ts` -> `py/pi_tui/components/text.py`**
- `class Text(Component)` — styled text display

**`packages/tui/src/components/truncated-text.ts` -> `py/pi_tui/components/truncated_text.py`**
- `class TruncatedText(Component)` — text with ellipsis truncation

**`packages/tui/src/components/spacer.ts` -> `py/pi_tui/components/spacer.py`**
- `class Spacer(Component)` — empty space filler

**`packages/tui/src/components/input.ts` -> `py/pi_tui/components/input.py`**
- `class Input(Focusable)` — single-line text input with cursor

**`packages/tui/src/components/editor.ts` -> `py/pi_tui/components/editor.py`**
- `class Editor(Focusable)` — multi-line text editor with kill ring, undo, keybindings
- `@dataclass EditorOptions` — configuration (multiline, placeholder, etc.)
- `@dataclass EditorTheme` — styling configuration

**`packages/tui/src/components/loader.ts` -> `py/pi_tui/components/loader.py`**
- `class Loader(Component)` — animated loading spinner

**`packages/tui/src/components/cancellable-loader.ts` -> `py/pi_tui/components/cancellable_loader.py`**
- `class CancellableLoader(Focusable)` — loader with cancel key support

**`packages/tui/src/components/select-list.ts` -> `py/pi_tui/components/select_list.py`**
- `class SelectList(Focusable)` — navigable list with selection
- `@dataclass SelectItem` — fields: `label: str`, `value: T`, `description: str | None`
- `@dataclass SelectListTheme` — styling configuration

**`packages/tui/src/components/settings-list.ts` -> `py/pi_tui/components/settings_list.py`**
- `class SettingsList(Focusable)` — key-value settings editor
- `@dataclass SettingItem` — fields: `key: str`, `value: str`, `editable: bool`
- `@dataclass SettingsListTheme` — styling configuration

**`packages/tui/src/components/markdown.ts` -> `py/pi_tui/components/markdown.py`**
- `class Markdown(Component)` — renders markdown to terminal with syntax highlighting
- `@dataclass MarkdownTheme` — styling configuration
- `@dataclass DefaultTextStyle` — default text style settings

**`packages/tui/src/components/image.ts` -> `py/pi_tui/components/image.py`**
- `class Image(Component)` — displays images in terminal (via kitty/iterm2 protocol)
- `@dataclass ImageOptions` — configuration
- `@dataclass ImageTheme` — styling configuration

**`packages/tui/src/terminal-image.ts` -> `py/pi_tui/terminal_image.py`**
Exports to implement:
- `@dataclass ImageDimensions` — fields: `width: int`, `height: int`
- `@dataclass CellDimensions` — fields: `width: int`, `height: int` (terminal cell pixel size)
- `ImageProtocol` — `Literal["kitty", "iterm2", "sixel", "none"]`
- `@dataclass TerminalCapabilities` — fields: `image_protocol: ImageProtocol`, `...`
- `@dataclass ImageRenderOptions` — fields: `width: int | None`, `height: int | None`, `...`
- `detect_capabilities() -> TerminalCapabilities`
- `get_capabilities() -> TerminalCapabilities`
- `reset_capabilities_cache() -> None`
- `get_cell_dimensions() -> CellDimensions | None`
- `set_cell_dimensions(dims: CellDimensions) -> None`
- `allocate_image_id() -> int`
- `get_image_dimensions(data: bytes) -> ImageDimensions | None`
- `get_png_dimensions(data: bytes) -> ImageDimensions | None`
- `get_jpeg_dimensions(data: bytes) -> ImageDimensions | None`
- `get_gif_dimensions(data: bytes) -> ImageDimensions | None`
- `get_webp_dimensions(data: bytes) -> ImageDimensions | None`
- `calculate_image_rows(dims: ImageDimensions, width: int, cell: CellDimensions) -> int`
- `encode_kitty(data: bytes, image_id: int, ...) -> str` — kitty graphics protocol
- `encode_iterm2(data: bytes, ...) -> str` — iTerm2 inline image protocol
- `delete_kitty_image(image_id: int) -> str`
- `delete_all_kitty_images() -> str`
- `render_image(data: bytes, options: ImageRenderOptions) -> str`
- `image_fallback(alt_text: str) -> str`

### Create `py/pi_tui/components/__init__.py`
Export all component classes.

## Tests — `py/tests/unit/pi_tui/`
- `test_box.py`: Test Box rendering with borders, padding
- `test_editor.py`: Test Editor key handling, multiline editing, undo/redo integration
- `test_select_list.py`: Test navigation, selection, filtering
- `test_markdown.py`: Test markdown rendering to ANSI
- `test_terminal_image.py`: Test image dimension parsing (PNG/JPEG/GIF/WebP headers), kitty/iterm2 encoding

## Acceptance Criteria
- [ ] All component classes listed above exist
- [ ] `MAPPING.md` updated at `py/pi_tui/MAPPING.md`
- [ ] `cd py && mypy --strict pi_tui/` passes
- [ ] `cd py && ruff check pi_tui/` passes
- [ ] `cd py && pytest tests/unit/pi_tui/ --cov=pi_tui --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1, Task 1.1a (TUI core)

## Metadata
- Phase: 1
- Package: tui
- TS reference: `packages/tui/src/components/` (12 files), `packages/tui/src/terminal-image.ts`
- TS lines: ~5,000
- Estimated Python lines: ~3,500
EOF
)"

# --- Phase 1: Task 1.2a - AI Core ---
gh issue create \
  --title "[Python Rewrite] pi_ai: Core Types, Stream, Models, Registry (Task 1.2a)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the core AI abstraction layer from `packages/ai/src/`. This covers the streaming interface, model registry, API registry, and CLI entry point. Types are already in pi_types (Task 0.1).

## Scope

### Files to Rewrite

**`packages/ai/src/stream.ts` (60 lines) -> `py/pi_ai/stream.py`**
Exports to implement:
- `async def stream_simple(model: Model, context: Context, options: SimpleStreamOptions | None = None) -> AsyncIterator[AssistantMessageEvent]` — unified streaming function that delegates to the correct provider based on `model.api`
- This replaces the TS `streamSimple()` function. Use `async def` + `yield` (async generator pattern).

**`packages/ai/src/models.ts` (77 lines) -> `py/pi_ai/models.py`**
Exports to implement:
- `get_model(model_id: str) -> Model | None` — look up model by ID from the generated registry
- `get_models() -> list[Model]` — return all registered models
- `get_models_by_provider(provider: str) -> list[Model]` — filter by provider
- `get_models_by_api(api: str) -> list[Model]` — filter by API type

**`packages/ai/src/models.generated.ts` (12,786 lines) -> `py/pi_ai/models_generated.py`**
- This is a generated file containing all model definitions as a large list
- Convert to a Python module-level list of `Model` dataclass instances
- Preserve all model entries exactly (id, name, api, provider, baseUrl, reasoning, input, cost, contextWindow, maxTokens)
- Consider generating this file via a script that reads the TS source

**`packages/ai/src/api-registry.ts` (98 lines) -> `py/pi_ai/api_registry.py`**
Exports to implement:
- `StreamFunction` — type alias: `Callable[[Model, Context, StreamOptions | None], AsyncIterator[AssistantMessageEvent]]`
- `register_api(api: str, stream_fn: StreamFunction) -> None` — register a streaming function for an API type
- `get_api(api: str) -> StreamFunction | None` — retrieve registered streaming function
- `get_registered_apis() -> list[str]` — list all registered API identifiers
- Use a module-level `dict[str, StreamFunction]` as the registry

**`packages/ai/src/env-api-keys.ts` (115 lines) -> `py/pi_ai/env_api_keys.py`**
Exports to implement:
- `detect_api_keys() -> dict[str, str]` — scan environment variables for known API key patterns
- `get_api_key_for_provider(provider: str) -> str | None` — get API key for a specific provider
- Known env var mappings: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `AWS_ACCESS_KEY_ID`+`AWS_SECRET_ACCESS_KEY`, `AZURE_OPENAI_API_KEY`, `GROQ_API_KEY`, `XAI_API_KEY`, `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`, `MISTRAL_API_KEY`, `HUGGINGFACE_TOKEN`, etc.
- Use `os.environ` to read values

**`packages/ai/src/cli.ts` (133 lines) -> `py/pi_ai/cli.py`**
Exports to implement:
- CLI entry point using `typer` or `click`
- Commands: `list-models` (list all models, filterable by provider/api), `stream` (send a prompt and stream response)
- Register as console script in `pyproject.toml`

**`packages/ai/src/index.ts` -> `py/pi_ai/__init__.py`**
- Re-export all public symbols from submodules via `__all__`

### Create `py/pi_ai/pyproject.toml`
```toml
[project]
name = "pi-ai"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "pi-types",
  "httpx",
]

[project.optional-dependencies]
cli = ["typer"]

[project.scripts]
pi-ai = "pi_ai.cli:app"
```

## Key Design Decisions
- `stream_simple()` is an async generator that `yield`s `AssistantMessageEvent` — replaces TS EventStream
- The API registry maps API identifiers to async generator factory functions
- Models are plain `@dataclass` instances, not Pydantic (no validation needed for read-only data)
- `models_generated.py` can be very large; consider a lazy-loading pattern or just a module-level list

## Tests — `py/tests/unit/pi_ai/`
- `test_stream.py`: Test `stream_simple()` with a mock API registry entry; verify events are yielded in correct order
- `test_models.py`: Test `get_model()`, `get_models_by_provider()`, `get_models_by_api()` against generated data
- `test_api_registry.py`: Test `register_api()` / `get_api()` round-trip
- `test_env_api_keys.py`: Test `detect_api_keys()` with mocked environment variables
- `test_cli.py`: Test CLI commands using typer's testing utilities

## Acceptance Criteria
- [ ] `stream_simple()` async generator works with registered API providers
- [ ] Model registry contains all models from `models.generated.ts`
- [ ] `MAPPING.md` created at `py/pi_ai/MAPPING.md`
- [ ] `cd py && mypy --strict pi_ai/` passes
- [ ] `cd py && ruff check pi_ai/` passes
- [ ] `cd py && pytest tests/unit/pi_ai/ --cov=pi_ai --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1

## Metadata
- Phase: 1
- Package: ai
- TS reference: `packages/ai/src/` (stream.ts, models.ts, models.generated.ts, api-registry.ts, env-api-keys.ts, cli.ts, index.ts)
- TS lines: ~13,600 (12,786 is models.generated.ts)
- Estimated Python lines: ~13,500 (mostly generated models)
EOF
)"

# --- Phase 1: Task 1.2b - AI OpenAI Providers ---
gh issue create \
  --title "[Python Rewrite] pi_ai: OpenAI-Compatible Providers (Task 1.2b)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite all OpenAI-compatible provider implementations from `packages/ai/src/providers/`. These providers use the `openai` Python SDK. Total: ~2,973 lines across 9 files.

## Scope

### Files to Rewrite

**`packages/ai/src/providers/openai-responses.ts` (259 lines) -> `py/pi_ai/providers/openai_responses.py`**
Exports to implement:
- `async def stream_openai_responses(model: Model, context: Context, options: StreamOptions | None = None) -> AsyncIterator[AssistantMessageEvent]`
- Uses `openai.OpenAI` client with Responses API
- Must handle: text streaming, tool calls, thinking/reasoning, usage reporting

**`packages/ai/src/providers/openai-responses-shared.ts` (480 lines) -> `py/pi_ai/providers/openai_responses_shared.py`**
Exports to implement:
- Shared utilities for OpenAI Responses API providers
- Message conversion functions: convert `Message[]` to OpenAI responses format
- Tool definition conversion: convert `Tool` to OpenAI tool format
- Response event parsing: convert OpenAI streaming events to `AssistantMessageEvent`

**`packages/ai/src/providers/openai-completions.ts` (828 lines) -> `py/pi_ai/providers/openai_completions.py`**
Exports to implement:
- `async def stream_openai_completions(model: Model, context: Context, options: StreamOptions | None = None) -> AsyncIterator[AssistantMessageEvent]`
- Uses `openai.OpenAI` client with Chat Completions API
- Handle compat settings from `model.compat` (OpenAICompletionsCompat):
  - `supports_store`, `supports_developer_role`, `supports_reasoning_effort`
  - `supports_usage_in_streaming`, `max_tokens_field`, `requires_tool_result_name`
  - `requires_assistant_after_tool_result`, `requires_thinking_as_text`
  - `requires_mistral_tool_ids`, `thinking_format`, `supports_strict_mode`

**`packages/ai/src/providers/openai-codex-responses.ts` (863 lines) -> `py/pi_ai/providers/openai_codex_responses.py`**
Exports to implement:
- `async def stream_openai_codex_responses(model: Model, context: Context, options: StreamOptions | None = None) -> AsyncIterator[AssistantMessageEvent]`
- OpenAI Codex variant of the Responses API (different endpoint behavior)

**`packages/ai/src/providers/azure-openai-responses.ts` (256 lines) -> `py/pi_ai/providers/azure_openai_responses.py`**
Exports to implement:
- `async def stream_azure_openai_responses(model: Model, context: Context, options: StreamOptions | None = None) -> AsyncIterator[AssistantMessageEvent]`
- Uses `openai.AzureOpenAI` client
- Azure-specific auth (API key or Azure AD token)

**`packages/ai/src/providers/github-copilot-headers.ts` (37 lines) -> `py/pi_ai/providers/github_copilot_headers.py`**
Exports to implement:
- `get_copilot_headers() -> dict[str, str]` — return GitHub Copilot-specific HTTP headers
- Headers include: editor version, plugin version, machine ID

**`packages/ai/src/providers/transform-messages.ts` (167 lines) -> `py/pi_ai/providers/transform_messages.py`**
Exports to implement:
- `transform_messages_for_completions(messages: list[Message], compat: OpenAICompletionsCompat | None) -> list[dict]` — convert internal Message types to OpenAI chat completion format
- Handle: thinking-as-text conversion, Mistral tool ID normalization, assistant message insertion after tool results

**`packages/ai/src/providers/simple-options.ts` (46 lines) -> `py/pi_ai/providers/simple_options.py`**
Exports to implement:
- `resolve_simple_options(options: SimpleStreamOptions | None) -> StreamOptions` — extract provider-agnostic options, apply defaults

**`packages/ai/src/providers/register-builtins.ts` (73 lines) -> `py/pi_ai/providers/register_builtins.py`**
Exports to implement:
- `register_builtin_providers() -> None` — register all built-in provider stream functions with the API registry
- Must register: `openai-responses`, `openai-completions`, `openai-codex-responses`, `azure-openai-responses`, `anthropic-messages`, `bedrock-converse-stream`, `google-generative-ai`, `google-gemini-cli`, `google-vertex`

### Create `py/pi_ai/providers/__init__.py`
Export all provider stream functions.

## Key Design Decisions
- Use `openai` Python SDK (not raw HTTP) for all OpenAI-compatible providers
- Each provider is an async generator function, not a class
- Streaming: iterate `openai` SDK's async stream and `yield` converted `AssistantMessageEvent`s
- Abort signal: pass `asyncio.Event` — check `event.is_set()` between chunks to support cancellation
- Compat settings: read from `model.compat` dict, apply transformations before sending request

## Tests — `py/tests/unit/pi_ai/`
- `test_openai_responses.py`: Mock `openai.OpenAI` client, test streaming event conversion
- `test_openai_completions.py`: Mock client, test compat settings (each flag), message transformation
- `test_transform_messages.py`: Test message format conversion, thinking-as-text, Mistral IDs
- `test_register_builtins.py`: Verify all APIs are registered after calling `register_builtin_providers()`

## Acceptance Criteria
- [ ] All provider async generators yield correct `AssistantMessageEvent` sequences
- [ ] Compat settings from `model.compat` are respected
- [ ] `MAPPING.md` updated at `py/pi_ai/MAPPING.md`
- [ ] `cd py && mypy --strict pi_ai/` passes
- [ ] `cd py && ruff check pi_ai/` passes
- [ ] `cd py && pytest tests/unit/pi_ai/ --cov=pi_ai --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1, Task 1.2a (core types/registry)

## Metadata
- Phase: 1
- Package: ai
- TS reference: `packages/ai/src/providers/` (openai-*.ts, azure-*.ts, github-copilot-headers.ts, transform-messages.ts, simple-options.ts, register-builtins.ts)
- TS lines: ~2,973
- Estimated Python lines: ~2,200
EOF
)"

# --- Phase 1: Task 1.2c - AI Non-OpenAI Providers ---
gh issue create \
  --title "[Python Rewrite] pi_ai: Anthropic, Google, Bedrock Providers (Task 1.2c)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite non-OpenAI provider implementations. Each uses its native Python SDK. Total: ~3,773 lines across 5 files.

## Scope

### Files to Rewrite

**`packages/ai/src/providers/anthropic.ts` (851 lines) -> `py/pi_ai/providers/anthropic.py`**
Exports to implement:
- `async def stream_anthropic(model: Model, context: Context, options: StreamOptions | None = None) -> AsyncIterator[AssistantMessageEvent]`
- Uses `anthropic` Python SDK (`anthropic.Anthropic` client)
- Handle: text streaming, thinking blocks, tool use, cache control (`cache_retention` -> ephemeral cache breakpoints)
- Convert internal `Message` list to Anthropic format (system prompt separate, user/assistant alternation)
- Map `ThinkingLevel` to Anthropic's `thinking` parameter with budget tokens
- Parse streaming events: `message_start`, `content_block_start`, `content_block_delta`, `content_block_stop`, `message_delta`, `message_stop`
- Extract usage from `message_start.message.usage` and `message_delta.usage`

**`packages/ai/src/providers/google.ts` (452 lines) -> `py/pi_ai/providers/google.py`**
Exports to implement:
- `async def stream_google(model: Model, context: Context, options: StreamOptions | None = None) -> AsyncIterator[AssistantMessageEvent]`
- Uses `google-genai` Python SDK (`google.genai.Client`)
- Convert messages to Google format (Content with Parts)
- Handle: text, thinking, function calls, function responses
- Map thinking level to Google's `thinking_config`

**`packages/ai/src/providers/google-shared.ts` (317 lines) -> `py/pi_ai/providers/google_shared.py`**
Exports to implement:
- Shared conversion functions for Google providers:
  - `convert_messages_to_google(messages: list[Message]) -> list[dict]`
  - `convert_tools_to_google(tools: list[Tool]) -> list[dict]`
  - `parse_google_response(response) -> AssistantMessageEvent` generator

**`packages/ai/src/providers/google-vertex.ts` (482 lines) -> `py/pi_ai/providers/google_vertex.py`**
Exports to implement:
- `async def stream_google_vertex(model: Model, context: Context, options: StreamOptions | None = None) -> AsyncIterator[AssistantMessageEvent]`
- Uses `google-genai` SDK with Vertex AI configuration
- Requires `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` env vars

**`packages/ai/src/providers/google-gemini-cli.ts` (940 lines) -> `py/pi_ai/providers/google_gemini_cli.py`**
Exports to implement:
- `async def stream_google_gemini_cli(model: Model, context: Context, options: StreamOptions | None = None) -> AsyncIterator[AssistantMessageEvent]`
- Uses Google Gemini CLI OAuth flow for authentication
- Same streaming logic as `stream_google` but with different auth

**`packages/ai/src/providers/amazon-bedrock.ts` (731 lines) -> `py/pi_ai/providers/amazon_bedrock.py`**
Exports to implement:
- `async def stream_amazon_bedrock(model: Model, context: Context, options: StreamOptions | None = None) -> AsyncIterator[AssistantMessageEvent]`
- Uses `boto3` SDK with `bedrock-runtime` client
- API: `converse_stream()` — Bedrock's unified streaming API
- Convert messages to Bedrock format (similar to Anthropic but with Bedrock-specific wrapping)
- Handle: text, tool use, thinking (if supported by model)
- Auth: AWS credentials from environment or boto3 default chain

## Key Design Decisions
- Each provider is a standalone async generator function
- Use native Python SDKs: `anthropic`, `google-genai`, `boto3`
- All providers must yield the same `AssistantMessageEvent` sequence: `start` -> content events -> `done`/`error`
- Cost calculation: use `model.cost` rates × token counts from usage
- Error handling: catch SDK-specific exceptions, yield `AssistantMessageEvent` with `type="error"`

## Tests — `py/tests/unit/pi_ai/`
- `test_anthropic.py`: Mock `anthropic.Anthropic`, test streaming events, cache control, thinking levels
- `test_google.py`: Mock `google.genai.Client`, test message conversion, function call handling
- `test_google_vertex.py`: Test Vertex AI configuration
- `test_amazon_bedrock.py`: Mock `boto3` bedrock-runtime client, test `converse_stream` event parsing

## Acceptance Criteria
- [ ] All provider async generators yield correct `AssistantMessageEvent` sequences
- [ ] Each provider uses its native Python SDK (not raw HTTP)
- [ ] `MAPPING.md` updated at `py/pi_ai/MAPPING.md`
- [ ] `cd py && mypy --strict pi_ai/` passes
- [ ] `cd py && ruff check pi_ai/` passes
- [ ] `cd py && pytest tests/unit/pi_ai/ --cov=pi_ai --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1, Task 1.2a

## Metadata
- Phase: 1
- Package: ai
- TS reference: `packages/ai/src/providers/` (anthropic.ts, google.ts, google-shared.ts, google-vertex.ts, google-gemini-cli.ts, amazon-bedrock.ts)
- TS lines: ~3,773
- Estimated Python lines: ~2,800
EOF
)"

# --- Phase 1: Task 1.2d - AI Utilities ---
gh issue create \
  --title "[Python Rewrite] pi_ai: Utilities (Event Stream, OAuth, JSON Parse, etc.) (Task 1.2d)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the AI utility modules from `packages/ai/src/utils/`. Total: ~2,641 lines across 14 files.

## Scope

### Files to Rewrite

**`packages/ai/src/utils/event-stream.ts` (87 lines) -> `py/pi_ai/utils/event_stream.py`**
Exports to implement:
- `AssistantMessageEventStream` — type alias for `AsyncIterator[AssistantMessageEvent]`
- `async def collect_stream(stream: AsyncIterator[AssistantMessageEvent]) -> AssistantMessage` — consume entire stream, return final AssistantMessage
- `async def map_stream(stream: AsyncIterator[AssistantMessageEvent], fn: Callable) -> AsyncIterator[AssistantMessageEvent]` — transform events

Note: Do NOT port the TS `EventStream` class. Use native Python async generators. The TS class has `push()`/`end()` methods that are replaced by `yield`/`return` in Python.

**`packages/ai/src/utils/json-parse.ts` (28 lines) -> `py/pi_ai/utils/json_parse.py`**
Exports to implement:
- `parse_partial_json(text: str) -> Any | None` — attempt to parse potentially incomplete JSON by adding closing brackets/braces
- Used for parsing streaming tool call arguments before the stream is complete

**`packages/ai/src/utils/overflow.ts` (121 lines) -> `py/pi_ai/utils/overflow.py`**
Exports to implement:
- `estimate_token_count(text: str) -> int` — rough token count estimation (chars/4 heuristic)
- `truncate_to_token_limit(messages: list[Message], limit: int) -> list[Message]` — truncate message list to fit context window
- `detect_overflow(messages: list[Message], context_window: int) -> bool` — check if messages exceed context

**`packages/ai/src/utils/sanitize-unicode.ts` (25 lines) -> `py/pi_ai/utils/sanitize_unicode.py`**
Exports to implement:
- `sanitize_unicode(text: str) -> str` — remove/replace problematic Unicode characters (zero-width chars, control chars, etc.)

**`packages/ai/src/utils/validation.ts` (84 lines) -> `py/pi_ai/utils/validation.py`**
Exports to implement:
- `validate_tool_arguments(tool: Tool, arguments: dict) -> list[str]` — validate tool call arguments against JSON Schema
- `validate_json_schema(schema: dict) -> bool` — check if a dict is a valid JSON Schema
- Use Python's `jsonschema` library or hand-written validation

**`packages/ai/src/utils/typebox-helpers.ts` (24 lines) -> `py/pi_ai/utils/schema_helpers.py`**
Exports to implement:
- `json_schema_from_dict(schema_dict: dict) -> dict` — normalize/clean JSON Schema dict
- `extract_properties(schema: dict) -> dict[str, dict]` — extract property definitions from JSON Schema
- This replaces TypeBox helpers — in Python we just use plain dicts for JSON Schema

**`packages/ai/src/utils/http-proxy.ts` (13 lines) -> `py/pi_ai/utils/http_proxy.py`**
Exports to implement:
- `get_proxy_url() -> str | None` — read proxy URL from `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` env vars
- `configure_proxy(client: httpx.AsyncClient) -> None` — apply proxy settings to httpx client

**`packages/ai/src/utils/oauth/` directory -> `py/pi_ai/utils/oauth/`**

**`packages/ai/src/utils/oauth/types.ts` (59 lines) -> `py/pi_ai/utils/oauth/types.py`**
- `@dataclass OAuthConfig` — fields: `client_id: str`, `auth_url: str`, `token_url: str`, `scopes: list[str]`, `redirect_port: int`
- `@dataclass OAuthToken` — fields: `access_token: str`, `refresh_token: str | None`, `expires_at: int | None`, `token_type: str`
- `@dataclass OAuthState` — fields: `code_verifier: str`, `state: str`, `redirect_uri: str`

**`packages/ai/src/utils/oauth/pkce.ts` (34 lines) -> `py/pi_ai/utils/oauth/pkce.py`**
- `generate_code_verifier() -> str` — random string for PKCE
- `generate_code_challenge(verifier: str) -> str` — SHA256 + base64url of verifier
- `generate_state() -> str` — random state parameter

**`packages/ai/src/utils/oauth/index.ts` (136 lines) -> `py/pi_ai/utils/oauth/__init__.py`**
- `async def start_oauth_flow(config: OAuthConfig) -> OAuthToken` — complete OAuth2 PKCE flow with local HTTP server
- `async def refresh_oauth_token(config: OAuthConfig, refresh_token: str) -> OAuthToken`
- Uses `http.server` or `aiohttp` for local callback server

**`packages/ai/src/utils/oauth/anthropic.ts` (138 lines) -> `py/pi_ai/utils/oauth/anthropic.py`**
- `ANTHROPIC_OAUTH_CONFIG` — const `OAuthConfig` for Anthropic
- `async def get_anthropic_oauth_token() -> OAuthToken`

**`packages/ai/src/utils/oauth/github-copilot.ts` (381 lines) -> `py/pi_ai/utils/oauth/github_copilot.py`**
- `async def get_copilot_token() -> str` — GitHub Copilot device flow authentication
- Device flow: POST to GitHub, poll for token, exchange for Copilot token

**`packages/ai/src/utils/oauth/google-antigravity.ts` (457 lines) -> `py/pi_ai/utils/oauth/google_antigravity.py`**
- `GOOGLE_ANTIGRAVITY_OAUTH_CONFIG` — const `OAuthConfig`
- `async def get_google_antigravity_token() -> OAuthToken`

**`packages/ai/src/utils/oauth/google-gemini-cli.ts` (599 lines) -> `py/pi_ai/utils/oauth/google_gemini_cli.py`**
- `GEMINI_CLI_OAUTH_CONFIG` — const `OAuthConfig`
- `async def get_gemini_cli_token() -> OAuthToken`

**`packages/ai/src/utils/oauth/openai-codex.ts` (455 lines) -> `py/pi_ai/utils/oauth/openai_codex.py`**
- `OPENAI_CODEX_OAUTH_CONFIG` — const `OAuthConfig`
- `async def get_openai_codex_token() -> OAuthToken`

### Create `py/pi_ai/utils/__init__.py`

## Tests — `py/tests/unit/pi_ai/`
- `test_event_stream.py`: Test `collect_stream()` with mock async generator
- `test_json_parse.py`: Test partial JSON parsing (incomplete objects, arrays, strings)
- `test_overflow.py`: Test token estimation, truncation, overflow detection
- `test_sanitize_unicode.py`: Test with various problematic Unicode inputs
- `test_validation.py`: Test tool argument validation against JSON schemas
- `test_oauth_pkce.py`: Test PKCE code verifier/challenge generation
- `test_http_proxy.py`: Test proxy URL detection from env vars

## Acceptance Criteria
- [ ] All utility functions listed above exist
- [ ] OAuth flows use `asyncio` (no blocking I/O)
- [ ] `MAPPING.md` updated at `py/pi_ai/MAPPING.md`
- [ ] `cd py && mypy --strict pi_ai/` passes
- [ ] `cd py && ruff check pi_ai/` passes
- [ ] `cd py && pytest tests/unit/pi_ai/ --cov=pi_ai --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1, Task 1.2a

## Metadata
- Phase: 1
- Package: ai
- TS reference: `packages/ai/src/utils/` (14 files)
- TS lines: ~2,641
- Estimated Python lines: ~2,000
EOF
)"

echo "Phase 0 and Phase 1 issues created successfully!"

# --- Phase 2: Task 2.1 - Agent Core ---
gh issue create \
  --title "[Python Rewrite] pi_agent: Agent Core Loop & Proxy (Task 2.1)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the agent core from `packages/agent/src/`. This is the async agent loop that orchestrates LLM calls and tool execution. Total: 1,518 lines across 4 files.

## Scope

### Files to Rewrite

**`packages/agent/src/agent.ts` -> `py/pi_agent/agent.py`**
Read the TS source to identify all exports. Key exports to implement:
- `class Agent` — main agent class managing the conversation loop
  - Constructor takes: `config: AgentLoopConfig`
  - Properties: `state: AgentState` (read-only), `messages: list[AgentMessage]`
  - Methods:
    - `async def run(initial_messages: list[AgentMessage]) -> AsyncIterator[AgentEvent]` — run the agent loop, yielding events
    - `def abort() -> None` — signal the agent to stop (sets `asyncio.Event`)
    - `subscribe(listener: Callable[[AgentEvent], None]) -> Callable[[], None]` — subscribe to events, returns unsubscribe function
  - State management: use instance attributes (`self.model`, `self.messages`, `self.is_streaming`, etc.) not a single state object
  - Keep the `subscribe()` + `_emit()` event notification pattern

**`packages/agent/src/agent-loop.ts` -> `py/pi_agent/agent_loop.py`**
Read the TS source to identify all exports. Key exports to implement:
- `async def run_agent_loop(config: AgentLoopConfig, messages: list[AgentMessage], signal: asyncio.Event | None = None) -> AsyncIterator[AgentEvent]`
- Loop logic:
  1. Emit `agent_start`
  2. Loop:
     a. Apply `transform_context` if provided
     b. Call `convert_to_llm` to get LLM-compatible messages
     c. Resolve API key via `get_api_key` if provided
     d. Call `stream_simple()` to get LLM response — yield `turn_start`, `message_start`, `message_update` events
     e. Collect tool calls from assistant response
     f. If no tool calls: check `get_steering_messages()` and `get_follow_up_messages()` — if none, break
     g. Execute tool calls in parallel (`asyncio.gather`), yielding `tool_execution_start/update/end` events
     h. Add tool results to messages
     i. Yield `turn_end`
     j. Check abort signal
  3. Emit `agent_end`

**`packages/agent/src/proxy.ts` -> `py/pi_agent/proxy.py`**
Read the TS source to identify all exports. Key exports to implement:
- Proxy utilities for agent communication (if any public exports exist)
- Read the file to determine exact exports

**`packages/agent/src/types.ts`**
- Already handled in Task 0.1 (pi_types/agent_types.py)
- Just re-export from pi_types in `py/pi_agent/__init__.py`

### Create `py/pi_agent/__init__.py`
```python
from pi_types.agent_types import *  # Re-export types
from .agent import Agent
from .agent_loop import run_agent_loop
# ... other public symbols
```

### Create `py/pi_agent/pyproject.toml`
```toml
[project]
name = "pi-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pi-types", "pi-ai"]
```

## Key Design Decisions
- `run_agent_loop` is an async generator that `yield`s `AgentEvent` — caller iterates to drive the loop
- Tool execution: use `asyncio.gather()` for parallel tool calls within a turn
- Abort: use `asyncio.Event` — check `event.is_set()` between LLM calls and tool executions
- The `Agent` class wraps `run_agent_loop` and adds state management + event subscriptions
- No threads — everything is `asyncio`

## Tests — `py/tests/unit/pi_agent/`
- `test_agent.py`: Test Agent class with mock tools and mock `stream_simple`
  - Test basic conversation: user message -> assistant response -> done
  - Test tool call loop: assistant calls tool -> tool result -> assistant responds
  - Test multi-turn with steering messages
  - Test abort signal stops the loop
- `test_agent_loop.py`: Test `run_agent_loop` directly
  - Test event sequence: agent_start -> turn_start -> message events -> turn_end -> agent_end
  - Test parallel tool execution
  - Test error handling (LLM error, tool error)

## Acceptance Criteria
- [ ] `Agent` class can run a complete conversation loop with mock tools
- [ ] Events are yielded in correct order
- [ ] Tool calls execute in parallel
- [ ] Abort signal stops the loop gracefully
- [ ] `MAPPING.md` created at `py/pi_agent/MAPPING.md`
- [ ] `cd py && mypy --strict pi_agent/` passes
- [ ] `cd py && ruff check pi_agent/` passes
- [ ] `cd py && pytest tests/unit/pi_agent/ --cov=pi_agent --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1, Task 1.2a (pi_ai core)

## Metadata
- Phase: 2
- Package: agent
- TS reference: `packages/agent/src/` (agent.ts, agent-loop.ts, proxy.ts, types.ts)
- TS lines: 1,518
- Estimated Python lines: ~1,100
EOF
)"

# --- Phase 2: Task 2.2a - Coding Agent Tools ---
gh issue create \
  --title "[Python Rewrite] pi_coding_agent: File Operation Tools (Task 2.2a)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the coding agent's file operation tools from `packages/coding-agent/src/core/tools/`. Each tool is a standalone module with consistent interfaces. Total: ~4,000 lines across 10 files.

## Scope

### Files to Rewrite

Read each TS source file to understand the exact interface. For each tool, implement:
1. A `@dataclass` for input parameters (replacing TypeBox schema)
2. A `@dataclass` for tool details (result metadata)
3. An operations protocol (for testability)
4. A factory function or the tool definition itself

**`packages/coding-agent/src/core/tools/bash.ts` -> `py/pi_coding_agent/tools/bash.py`**
- `@dataclass BashToolInput` — fields: `command: str`, `timeout: int | None`, `description: str | None`
- `@dataclass BashToolDetails` — fields: `command: str`, `output: str`, `exit_code: int`
- `@dataclass BashToolOptions` — fields: `cwd: str`, `timeout: int`, `max_output_bytes: int`
- `BashOperations` — protocol with `execute(command, timeout, cwd) -> BashResult`
- `bash_tool(options: BashToolOptions) -> AgentTool` — creates the bash tool
- `create_bash_tool(cwd: str) -> AgentTool` — convenience factory

**`packages/coding-agent/src/core/tools/read.ts` -> `py/pi_coding_agent/tools/read.py`**
- `@dataclass ReadToolInput` — fields: `file_path: str`, `offset: int | None`, `limit: int | None`
- `@dataclass ReadToolDetails` — fields: `file_path: str`, `content: str`, `line_count: int`
- `@dataclass ReadToolOptions` — fields: `cwd: str`, `max_lines: int`, `max_line_length: int`
- `ReadOperations` — protocol
- `read_tool(options: ReadToolOptions) -> AgentTool`
- `create_read_tool(cwd: str) -> AgentTool`

**`packages/coding-agent/src/core/tools/write.ts` -> `py/pi_coding_agent/tools/write.py`**
- `@dataclass WriteToolInput` — fields: `file_path: str`, `content: str`
- `WriteOperations` — protocol
- `write_tool(options: WriteToolOptions) -> AgentTool`
- `create_write_tool(cwd: str) -> AgentTool`

**`packages/coding-agent/src/core/tools/edit.ts` -> `py/pi_coding_agent/tools/edit.py`**
- `@dataclass EditToolInput` — fields: `file_path: str`, `old_string: str`, `new_string: str`, `replace_all: bool | None`
- `@dataclass EditToolDetails` — fields: `file_path: str`, `old_string: str`, `new_string: str`, `diff: str`
- `EditOperations` — protocol
- `edit_tool(options: EditToolOptions) -> AgentTool`
- `create_edit_tool(cwd: str) -> AgentTool`

**`packages/coding-agent/src/core/tools/edit-diff.ts` -> `py/pi_coding_agent/tools/edit_diff.py`**
- Diff generation utilities used by the edit tool

**`packages/coding-agent/src/core/tools/find.ts` -> `py/pi_coding_agent/tools/find.py`**
- `@dataclass FindToolInput` — fields: `pattern: str`, `path: str | None`
- `@dataclass FindToolDetails` — fields: `pattern: str`, `matches: list[str]`
- `FindOperations` — protocol
- `find_tool(options: FindToolOptions) -> AgentTool`
- `create_find_tool(cwd: str) -> AgentTool`

**`packages/coding-agent/src/core/tools/grep.ts` -> `py/pi_coding_agent/tools/grep.py`**
- `@dataclass GrepToolInput` — fields: `pattern: str`, `path: str | None`, `include: str | None`
- `@dataclass GrepToolDetails` — fields: `pattern: str`, `matches: list[dict]`
- `GrepOperations` — protocol
- `grep_tool(options: GrepToolOptions) -> AgentTool`
- `create_grep_tool(cwd: str) -> AgentTool`

**`packages/coding-agent/src/core/tools/ls.ts` -> `py/pi_coding_agent/tools/ls.py`**
- `@dataclass LsToolInput` — fields: `path: str | None`
- `@dataclass LsToolDetails` — fields: `path: str`, `entries: list[str]`
- `LsOperations` — protocol
- `ls_tool(options: LsToolOptions) -> AgentTool`
- `create_ls_tool(cwd: str) -> AgentTool`

**`packages/coding-agent/src/core/tools/truncate.ts` -> `py/pi_coding_agent/tools/truncate.py`**
- `@dataclass TruncationOptions` — fields: `max_lines: int`, `max_bytes: int`
- `@dataclass TruncationResult` — fields: `content: str`, `was_truncated: bool`, `original_lines: int`
- `truncate_head(text: str, options: TruncationOptions) -> TruncationResult`
- `truncate_tail(text: str, options: TruncationOptions) -> TruncationResult`
- `truncate_line(line: str, max_length: int) -> str`
- `DEFAULT_MAX_LINES: int` — const
- `DEFAULT_MAX_BYTES: int` — const
- `format_size(bytes: int) -> str`

**`packages/coding-agent/src/core/tools/path-utils.ts` -> `py/pi_coding_agent/tools/path_utils.py`**
- Path validation and resolution utilities
- `resolve_tool_path(path: str, cwd: str) -> Path` — resolve relative paths, validate within cwd
- `is_path_within(path: Path, root: Path) -> bool` — security check

**`packages/coding-agent/src/core/tools/index.ts` -> `py/pi_coding_agent/tools/__init__.py`**
- `@dataclass ToolsOptions` — fields: `cwd: str`
- `coding_tools(options: ToolsOptions) -> list[AgentTool]` — returns all coding tools
- `create_coding_tools(cwd: str) -> list[AgentTool]` — convenience factory
- `create_read_only_tools(cwd: str) -> list[AgentTool]` — read, find, grep, ls only
- `read_only_tools: list[AgentTool]` — pre-built read-only tools using `os.getcwd()`

## Key Design Decisions
- Each tool's `execute` method is `async` (even if sync internally) for consistency
- Use `pathlib.Path` for all file operations
- Use `subprocess` for bash execution (not `os.system`)
- Operations protocols allow dependency injection for testing (mock filesystem, mock subprocess)
- JSON Schema for tool parameters: hand-written dicts, not TypeBox

## Tests — `py/tests/unit/pi_coding_agent/`
- `test_bash_tool.py`: Test command execution, timeout, output truncation
- `test_read_tool.py`: Test file reading, offset/limit, line truncation, binary file detection
- `test_write_tool.py`: Test file creation, overwrite, directory creation
- `test_edit_tool.py`: Test string replacement, replace_all, non-unique match error, diff generation
- `test_find_tool.py`: Test glob pattern matching
- `test_grep_tool.py`: Test regex search, include filter
- `test_ls_tool.py`: Test directory listing
- `test_truncate.py`: Test head/tail truncation, line truncation, format_size
- `test_path_utils.py`: Test path resolution, security validation

## Acceptance Criteria
- [ ] All tool factories produce valid `AgentTool` instances
- [ ] `coding_tools()` returns bash, read, write, edit, find, grep, ls tools
- [ ] Each tool's execute method works with real filesystem (integration-style unit tests)
- [ ] Path security: tools reject paths outside cwd
- [ ] `MAPPING.md` created at `py/pi_coding_agent/MAPPING.md`
- [ ] `cd py && mypy --strict pi_coding_agent/` passes
- [ ] `cd py && ruff check pi_coding_agent/` passes
- [ ] `cd py && pytest tests/unit/pi_coding_agent/ --cov=pi_coding_agent --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1, Task 1.2a, Task 2.1

## Metadata
- Phase: 2
- Package: coding-agent
- TS reference: `packages/coding-agent/src/core/tools/` (10 files)
- TS lines: ~4,000
- Estimated Python lines: ~3,000
EOF
)"

# --- Phase 2: Task 2.2b - Coding Agent Session & Config ---
gh issue create \
  --title "[Python Rewrite] pi_coding_agent: Session Management & Config (Task 2.2b)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite session persistence, authentication storage, and configuration management from `packages/coding-agent/src/core/` and `packages/coding-agent/src/`. Total: ~5,000 lines.

## Scope

### Files to Rewrite

Read each TS source file for exact exports and logic.

**`packages/coding-agent/src/core/agent-session.ts` -> `py/pi_coding_agent/core/agent_session.py`**
Key exports:
- `@dataclass AgentSessionConfig` — session configuration
- `AgentSessionEvent` — type for session lifecycle events
- `AgentSessionEventListener` — callback type
- `@dataclass ModelCycleResult` — result of model cycling
- `@dataclass PromptOptions` — options for prompting
- `@dataclass SessionStats` — token usage, cost, turn count statistics
- `@dataclass ParsedSkillBlock` — parsed skill invocation from assistant message
- `parse_skill_block(text: str) -> ParsedSkillBlock | None`
- `class AgentSession` — main session class managing agent lifecycle
  - Wraps `Agent` with session persistence, model management, extension support
  - Methods: `prompt()`, `abort()`, `cycle_model()`, `get_stats()`, `subscribe()`

**`packages/coding-agent/src/core/session-manager.ts` -> `py/pi_coding_agent/core/session_manager.py`**
Key exports:
- `CURRENT_SESSION_VERSION: int` — const
- Session entry types (all `@dataclass`):
  - `SessionEntryBase`, `SessionMessageEntry`, `SessionInfoEntry`, `FileEntry`
  - `CompactionEntry`, `BranchSummaryEntry`, `ModelChangeEntry`, `ThinkingLevelChangeEntry`
  - `CustomEntry`, `CustomMessageEntry`
- `SessionEntry` — union type of all entry types
- `@dataclass SessionHeader` — fields: `version: int`, `created_at: int`, `session_id: str`
- `@dataclass SessionInfo` — fields: `id: str`, `name: str`, `created_at: int`, `updated_at: int`
- `@dataclass SessionContext` — fields: `messages: list[AgentMessage]`, `model: Model`, ...
- `@dataclass NewSessionOptions` — fields: `name: str | None`, `model: Model`, ...
- `class SessionManager` — manages session persistence to disk
  - Methods: `create_session()`, `load_session()`, `list_sessions()`, `delete_session()`, `save_entry()`, `build_context()`
  - Storage: JSON-lines files in `~/.pi/sessions/`
- `parse_session_entries(lines: list[str]) -> list[SessionEntry]`
- `migrate_session_entries(entries: list[SessionEntry]) -> list[SessionEntry]`
- `build_session_context(entries: list[SessionEntry]) -> SessionContext`
- `get_latest_compaction_entry(entries: list[SessionEntry]) -> CompactionEntry | None`

**`packages/coding-agent/src/core/settings-manager.ts` -> `py/pi_coding_agent/core/settings_manager.py`**
Key exports:
- `@dataclass CompactionSettings` — fields: `threshold: int`, `target: int`
- `@dataclass ImageSettings` — fields: `enabled: bool`, `max_size: int`
- `@dataclass RetrySettings` — fields: `max_retries: int`, `base_delay_ms: int`
- `PackageSource` — type for package source config
- `class SettingsManager` — reads/writes settings from `~/.pi/settings.json`
  - Methods: `get()`, `set()`, `get_all()`, `reset()`

**`packages/coding-agent/src/core/auth-storage.ts` -> `py/pi_coding_agent/core/auth_storage.py`**
Key exports:
- `@dataclass ApiKeyCredential` — fields: `type: Literal["api_key"]`, `api_key: str`
- `@dataclass OAuthCredential` — fields: `type: Literal["oauth"]`, `access_token: str`, `refresh_token: str | None`, `expires_at: int | None`
- `AuthCredential` — union type
- `AuthStorageBackend` — protocol: `load()`, `save()`, `delete()`
- `class FileAuthStorageBackend` — file-based storage in `~/.pi/auth/`
- `class InMemoryAuthStorageBackend` — in-memory storage for testing
- `class AuthStorage` — manages credentials per provider

**`packages/coding-agent/src/config.ts` -> `py/pi_coding_agent/config.py`**
Key exports:
- `VERSION: str` — package version
- `get_agent_dir() -> Path` — returns `~/.pi/` directory path (create if not exists)

**`packages/coding-agent/src/migrations.ts` -> `py/pi_coding_agent/migrations.py`**
Key exports:
- Session data migration functions for backward compatibility

## Tests — `py/tests/unit/pi_coding_agent/`
- `test_agent_session.py`: Test session lifecycle with mock Agent
- `test_session_manager.py`: Test create/load/list/delete sessions with temp directory
- `test_settings_manager.py`: Test get/set/reset with temp settings file
- `test_auth_storage.py`: Test file and in-memory backends

## Acceptance Criteria
- [ ] Sessions can be created, saved, loaded, and listed
- [ ] Settings persist to JSON file
- [ ] Auth credentials are stored and retrieved correctly
- [ ] `MAPPING.md` updated at `py/pi_coding_agent/MAPPING.md`
- [ ] `cd py && mypy --strict pi_coding_agent/` passes
- [ ] `cd py && ruff check pi_coding_agent/` passes
- [ ] `cd py && pytest tests/unit/pi_coding_agent/ --cov=pi_coding_agent --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1, Task 1.2a, Task 2.1

## Metadata
- Phase: 2
- Package: coding-agent
- TS reference: `packages/coding-agent/src/core/agent-session.ts`, `session-manager.ts`, `settings-manager.ts`, `auth-storage.ts`, `config.ts`, `migrations.ts`
- TS lines: ~5,000
- Estimated Python lines: ~3,800
EOF
)"

# --- Phase 2: Task 2.2c - Coding Agent Logic ---
gh issue create \
  --title "[Python Rewrite] pi_coding_agent: Model Resolution, Prompts, Compaction, Skills (Task 2.2c)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the agent's core logic modules: model selection, system prompts, context compaction, skills, and event bus. Total: ~6,000 lines.

## Scope

### Files to Rewrite

Read each TS source file for exact exports.

**`packages/coding-agent/src/core/model-resolver.ts` -> `py/pi_coding_agent/core/model_resolver.py`**
- Model resolution logic: given user preferences, environment, and available models, select the best model
- Handle model aliases, provider preferences, fallback chains

**`packages/coding-agent/src/core/model-registry.ts` -> `py/pi_coding_agent/core/model_registry.py`**
- `class ModelRegistry` — manages available models, custom model configurations
- Methods: `register()`, `get()`, `list()`, `get_default()`

**`packages/coding-agent/src/core/system-prompt.ts` -> `py/pi_coding_agent/core/system_prompt.py`**
- System prompt generation: assembles the system prompt from templates, context files, tool descriptions
- Read the TS file to understand all exported functions

**`packages/coding-agent/src/core/prompt-templates.ts` -> `py/pi_coding_agent/core/prompt_templates.py`**
- `@dataclass PromptTemplate` — fields: `name: str`, `system_prompt: str`, `tools: list[str] | None`
- Template loading and resolution

**`packages/coding-agent/src/core/messages.ts` -> `py/pi_coding_agent/core/messages.py`**
- `convert_to_llm(messages: list[AgentMessage]) -> list[Message]` — convert agent messages to LLM-compatible format
- Handle custom message types, filter non-LLM messages

**`packages/coding-agent/src/core/compaction/` directory -> `py/pi_coding_agent/core/compaction/`**

**`packages/coding-agent/src/core/compaction/compaction.ts` -> `py/pi_coding_agent/core/compaction/compaction.py`**
Key exports:
- `async def compact(messages: list[AgentMessage], model: Model, ...) -> CompactionResult`
- `@dataclass CompactionResult` — fields: `messages: list[AgentMessage]`, `summary: str`, `tokens_before: int`, `tokens_after: int`
- `should_compact(messages: list[AgentMessage], context_window: int, threshold: float) -> bool`
- `DEFAULT_COMPACTION_SETTINGS: CompactionSettings`

**`packages/coding-agent/src/core/compaction/branch-summarization.ts` -> `py/pi_coding_agent/core/compaction/branch_summarization.py`**
Key exports:
- `async def generate_branch_summary(options: GenerateBranchSummaryOptions) -> BranchSummaryResult`
- `@dataclass GenerateBranchSummaryOptions`
- `@dataclass BranchSummaryResult`
- `@dataclass BranchPreparation`
- Related helper functions for branch context management

**`packages/coding-agent/src/core/compaction/utils.ts` -> `py/pi_coding_agent/core/compaction/utils.py`**
Key exports:
- `estimate_tokens(text: str) -> int`
- `calculate_context_tokens(messages: list[Message]) -> int`
- `serialize_conversation(messages: list[Message]) -> str`
- `find_cut_point(messages: list[AgentMessage], target_tokens: int) -> CutPointResult`
- `find_turn_start_index(messages: list[AgentMessage], index: int) -> int`
- `get_last_assistant_usage(messages: list[AgentMessage]) -> Usage | None`
- Various helper types: `CutPointResult`, `CollectEntriesResult`, `FileOperations`

**`packages/coding-agent/src/core/skills.ts` -> `py/pi_coding_agent/core/skills.py`**
Key exports:
- `@dataclass Skill` — fields: `name: str`, `description: str`, `content: str`, `frontmatter: SkillFrontmatter`
- `@dataclass SkillFrontmatter` — fields: `name: str`, `description: str`, `...`
- `load_skills(dirs: list[Path]) -> LoadSkillsResult`
- `load_skills_from_dir(path: Path, options: LoadSkillsFromDirOptions) -> LoadSkillsResult`
- `format_skills_for_prompt(skills: list[Skill]) -> str`

**`packages/coding-agent/src/core/slash-commands.ts` -> `py/pi_coding_agent/core/slash_commands.py`**
- Slash command registration and execution

**`packages/coding-agent/src/core/event-bus.ts` -> `py/pi_coding_agent/core/event_bus.py`**
Key exports:
- `@dataclass EventBus` — typed event bus
- `@dataclass EventBusController` — controls event emission
- `create_event_bus() -> tuple[EventBus, EventBusController]`

**`packages/coding-agent/src/core/diagnostics.ts` -> `py/pi_coding_agent/core/diagnostics.py`**
- Diagnostic data collection for debugging

**`packages/coding-agent/src/core/timings.ts` -> `py/pi_coding_agent/core/timings.py`**
- Performance timing utilities

**`packages/coding-agent/src/core/defaults.ts` -> `py/pi_coding_agent/core/defaults.py`**
- Default configuration values

**`packages/coding-agent/src/core/keybindings.ts` -> `py/pi_coding_agent/core/keybindings.py`**
- Coding-agent specific keybinding configuration

**`packages/coding-agent/src/core/footer-data-provider.ts` -> `py/pi_coding_agent/core/footer_data_provider.py`**
- `ReadonlyFooterDataProvider` — protocol for providing footer data (git branch, extension status)

**`packages/coding-agent/src/core/resolve-config-value.ts` -> `py/pi_coding_agent/core/resolve_config_value.py`**
- Configuration value resolution with defaults and overrides

## Tests — `py/tests/unit/pi_coding_agent/`
- `test_compaction.py`: Test `should_compact`, `compact` with mock model
- `test_skills.py`: Test skill loading from directory, frontmatter parsing
- `test_event_bus.py`: Test event emission and subscription
- `test_messages.py`: Test `convert_to_llm` with various message types
- `test_model_registry.py`: Test model registration and lookup

## Acceptance Criteria
- [ ] Context compaction works correctly with mock LLM
- [ ] Skills load from directory and format for prompt
- [ ] Event bus emits and receives typed events
- [ ] `MAPPING.md` updated at `py/pi_coding_agent/MAPPING.md`
- [ ] `cd py && mypy --strict pi_coding_agent/` passes
- [ ] `cd py && pytest tests/unit/pi_coding_agent/ --cov=pi_coding_agent --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1, Task 1.2a, Task 2.1

## Metadata
- Phase: 2
- Package: coding-agent
- TS lines: ~6,000
- Estimated Python lines: ~4,500
EOF
)"

# --- Phase 2: Task 2.2d - Coding Agent Extensions & SDK ---
gh issue create \
  --title "[Python Rewrite] pi_coding_agent: Extensions System & SDK (Task 2.2d)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the extension system and SDK interface from `packages/coding-agent/src/core/extensions/` and `packages/coding-agent/src/core/sdk.ts`. Total: ~3,000 lines.

## Scope

### Files to Rewrite

**`packages/coding-agent/src/core/extensions/types.ts` -> `py/pi_coding_agent/core/extensions/types.py`**
All extension-related types (read the TS file for full list). Key types:
- `Extension` — protocol defining extension interface
- `ExtensionFactory` — callable that creates an Extension
- `ExtensionContext`, `ExtensionActions`, `ExtensionAPI`
- `ExtensionEvent` — union of all extension events
- `ExtensionUIContext`, `ExtensionUIDialogOptions`, `ExtensionWidgetOptions`
- `ExtensionFlag`, `ExtensionShortcut`, `ExtensionHandler`
- `ToolDefinition`, `RegisteredTool`, `RegisteredCommand`
- `ToolCallEvent` variants: `BashToolCallEvent`, `EditToolCallEvent`, `ReadToolCallEvent`, `WriteToolCallEvent`, `FindToolCallEvent`, `GrepToolCallEvent`, `LsToolCallEvent`, `CustomToolCallEvent`
- `ToolResultEvent`, `InputEvent`, `InputEventResult`
- Session events: `SessionStartEvent`, `SessionShutdownEvent`, `SessionCompactEvent`, `SessionForkEvent`, `SessionSwitchEvent`, `SessionTreeEvent`, plus `Before*` variants
- Agent events: `AgentStartEvent`, `AgentEndEvent`, `BeforeAgentStartEvent`
- `TurnStartEvent`, `TurnEndEvent`, `ContextEvent`, `ContextUsage`
- `MessageRenderer`, `MessageRenderOptions`
- `SlashCommandInfo`, `SlashCommandLocation`, `SlashCommandSource`
- `WidgetPlacement`, `ProviderConfig`, `ProviderModelConfig`
- `CompactOptions`, `ExecOptions`, `ExecResult`
- `AppAction`, `KeybindingsManager`, `TerminalInputHandler`

**`packages/coding-agent/src/core/extensions/loader.ts` -> `py/pi_coding_agent/core/extensions/loader.py`**
- `discover_and_load_extensions(paths: list[Path]) -> LoadExtensionsResult`
- Extension discovery: scan directories for extension files
- Extension loading: import Python modules dynamically

**`packages/coding-agent/src/core/extensions/runner.ts` -> `py/pi_coding_agent/core/extensions/runner.py`**
- `class ExtensionRunner` — manages extension lifecycle
  - Methods: `start()`, `stop()`, `emit_event()`, `get_tools()`, `get_commands()`
- `create_extension_runtime(extension: Extension, context: ExtensionContext) -> ExtensionRuntime`

**`packages/coding-agent/src/core/extensions/wrapper.ts` -> `py/pi_coding_agent/core/extensions/wrapper.py`**
- `wrap_tools_with_extensions(tools: list[AgentTool], runner: ExtensionRunner) -> list[AgentTool]`
- `wrap_tool_with_extensions(tool: AgentTool, runner: ExtensionRunner) -> AgentTool`
- `wrap_registered_tool(tool: RegisteredTool) -> AgentTool`
- `wrap_registered_tools(tools: list[RegisteredTool]) -> list[AgentTool]`
- Tool call event type guards: `is_bash_tool_result()`, `is_edit_tool_result()`, etc.

**`packages/coding-agent/src/core/sdk.ts` -> `py/pi_coding_agent/core/sdk.py`**
Key exports:
- `@dataclass CreateAgentSessionOptions` — all options for creating a session programmatically
- `@dataclass CreateAgentSessionResult` — session + cleanup function
- `async def create_agent_session(options: CreateAgentSessionOptions) -> CreateAgentSessionResult`
- `@dataclass PromptTemplate` — template for prompt customization
- Tool factory functions (re-exports): `create_coding_tools()`, `create_bash_tool()`, `create_edit_tool()`, etc.
- `read_only_tools` — pre-built read-only tools list

**`packages/coding-agent/src/core/exec.ts` -> `py/pi_coding_agent/core/exec.py`**
- Command execution utilities

**`packages/coding-agent/src/core/bash-executor.ts` -> `py/pi_coding_agent/core/bash_executor.py`**
- `@dataclass BashExecutorOptions` — configuration for bash execution
- `@dataclass BashResult` — fields: `stdout: str`, `stderr: str`, `exit_code: int`
- `async def execute_bash(command: str, options: BashExecutorOptions) -> BashResult`
- `async def execute_bash_with_operations(command: str, operations: BashOperations) -> BashResult`

**`packages/coding-agent/src/core/resource-loader.ts` -> `py/pi_coding_agent/core/resource_loader.py`**
- `ResourceLoader` — protocol for loading context resources (CLAUDE.md files, etc.)
- `class DefaultResourceLoader` — default implementation scanning filesystem
- `@dataclass ResourceDiagnostic`, `@dataclass ResourceCollision`
- `@dataclass ResolvedResource`

**`packages/coding-agent/src/core/package-manager.ts` -> `py/pi_coding_agent/core/package_manager.py`**
- `PackageManager` — protocol for managing extension packages
- `class DefaultPackageManager` — default implementation
- `@dataclass PathMetadata`, `@dataclass ResolvedPaths`
- `ProgressCallback`, `ProgressEvent` types

## Tests — `py/tests/unit/pi_coding_agent/`
- `test_extensions_loader.py`: Test extension discovery and loading from temp directory
- `test_extensions_runner.py`: Test ExtensionRunner lifecycle events
- `test_extensions_wrapper.py`: Test tool wrapping with extension hooks
- `test_sdk.py`: Test `create_agent_session` with mock dependencies
- `test_bash_executor.py`: Test bash execution with timeout, output capture

## Acceptance Criteria
- [ ] Extensions can be discovered, loaded, and executed
- [ ] Tool wrapping intercepts tool calls and results
- [ ] SDK `create_agent_session` produces a working session
- [ ] `MAPPING.md` updated
- [ ] mypy, ruff, pytest all pass

## Dependencies
- Blocked by: Task 0.1, Task 1.2a, Task 2.1

## Metadata
- Phase: 2
- Package: coding-agent
- TS lines: ~3,000
- Estimated Python lines: ~2,200
EOF
)"

# --- Phase 2: Task 2.2e - Coding Agent CLI ---
gh issue create \
  --title "[Python Rewrite] pi_coding_agent: CLI & Utility Functions (Task 2.2e)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the CLI entry point and utility functions from `packages/coding-agent/src/cli/`, `packages/coding-agent/src/cli.ts`, `packages/coding-agent/src/main.ts`, and `packages/coding-agent/src/utils/`. Total: ~4,000 lines.

## Scope

### Files to Rewrite

**`packages/coding-agent/src/main.ts` -> `py/pi_coding_agent/main.py`**
- `async def main() -> None` — application entry point
- Parse CLI args, initialize session, start selected mode

**`packages/coding-agent/src/cli.ts` -> `py/pi_coding_agent/cli.py`**
- CLI setup using `typer` or `click`
- Register as console script `pi-agent` in pyproject.toml

**`packages/coding-agent/src/cli/args.ts` -> `py/pi_coding_agent/cli/args.py`**
- CLI argument definitions and parsing

**`packages/coding-agent/src/cli/config-selector.ts` -> `py/pi_coding_agent/cli/config_selector.py`**
- Interactive configuration selection

**`packages/coding-agent/src/cli/file-processor.ts` -> `py/pi_coding_agent/cli/file_processor.py`**
- Process input files (stdin, file arguments)

**`packages/coding-agent/src/cli/list-models.ts` -> `py/pi_coding_agent/cli/list_models.py`**
- `list-models` command implementation

**`packages/coding-agent/src/cli/session-picker.ts` -> `py/pi_coding_agent/cli/session_picker.py`**
- Interactive session selection UI

**`packages/coding-agent/src/utils/git.ts` -> `py/pi_coding_agent/utils/git.py`**
- Git operations: branch detection, status, diff (use `subprocess` to call git)

**`packages/coding-agent/src/utils/clipboard.ts` -> `py/pi_coding_agent/utils/clipboard.py`**
- `copy_to_clipboard(text: str) -> bool` — copy text to system clipboard

**`packages/coding-agent/src/utils/clipboard-image.ts` -> `py/pi_coding_agent/utils/clipboard_image.py`**
- Image clipboard support

**`packages/coding-agent/src/utils/clipboard-native.ts` -> `py/pi_coding_agent/utils/clipboard_native.py`**
- Native clipboard bindings

**`packages/coding-agent/src/utils/image-convert.ts` -> `py/pi_coding_agent/utils/image_convert.py`**
- Image format conversion

**`packages/coding-agent/src/utils/image-resize.ts` -> `py/pi_coding_agent/utils/image_resize.py`**
- Image resizing

**`packages/coding-agent/src/utils/mime.ts` -> `py/pi_coding_agent/utils/mime.py`**
- MIME type detection

**`packages/coding-agent/src/utils/shell.ts` -> `py/pi_coding_agent/utils/shell.py`**
- `get_shell_config() -> dict` — detect user's shell and config

**`packages/coding-agent/src/utils/frontmatter.ts` -> `py/pi_coding_agent/utils/frontmatter.py`**
- `parse_frontmatter(text: str) -> tuple[dict, str]` — parse YAML frontmatter
- `strip_frontmatter(text: str) -> str`

**`packages/coding-agent/src/utils/sleep.ts` -> `py/pi_coding_agent/utils/sleep.py`**
- `async def sleep(ms: int) -> None` — async sleep (just wraps asyncio.sleep)

**`packages/coding-agent/src/utils/tools-manager.ts` -> `py/pi_coding_agent/utils/tools_manager.py`**
- Tool registration and management utilities

**`packages/coding-agent/src/utils/changelog.ts` -> `py/pi_coding_agent/utils/changelog.py`**
- Changelog display

**`packages/coding-agent/src/utils/photon.ts` -> `py/pi_coding_agent/utils/photon.py`**
- Image processing utilities

## Tests — `py/tests/unit/pi_coding_agent/`
- `test_cli.py`: Test CLI commands using typer test client
- `test_git.py`: Test git operations with temp repo
- `test_frontmatter.py`: Test frontmatter parsing
- `test_shell.py`: Test shell detection

## Acceptance Criteria
- [ ] `pi-agent --help` displays usage information
- [ ] `pi-agent list-models` lists available models
- [ ] Git utilities work with real git repos
- [ ] `MAPPING.md` updated
- [ ] mypy, ruff, pytest all pass

## Dependencies
- Blocked by: Task 2.2a, 2.2b, 2.2c, 2.2d

## Metadata
- Phase: 2
- Package: coding-agent
- TS lines: ~4,000
- Estimated Python lines: ~3,000
EOF
)"

# --- Phase 2: Task 2.2f - Coding Agent Modes ---
gh issue create \
  --title "[Python Rewrite] pi_coding_agent: Interactive, RPC & Print Modes (Task 2.2f)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the run modes from `packages/coding-agent/src/modes/`. These are the different ways the coding agent can be used: interactive TUI, RPC server, and simple print mode. Total: ~6,000 lines.

## Scope

### Files to Rewrite

**Interactive Mode — `packages/coding-agent/src/modes/interactive/`**

**`interactive-mode.ts` -> `py/pi_coding_agent/modes/interactive/interactive_mode.py`**
- `class InteractiveMode` — main TUI-based interactive mode
- `@dataclass InteractiveModeOptions` — configuration
- Manages: TUI layout, user input, message display, tool execution visualization
- Uses pi_tui components for rendering

**`theme/theme.ts` -> `py/pi_coding_agent/modes/interactive/theme.py`**
- `class Theme` — color and styling configuration
- `@dataclass ThemeColor` — individual color definition
- `init_theme() -> Theme`
- `get_markdown_theme() -> MarkdownTheme`
- `get_select_list_theme() -> SelectListTheme`
- `get_settings_list_theme() -> SettingsListTheme`
- `get_language_from_path(path: str) -> str` — detect language for syntax highlighting
- `highlight_code(code: str, language: str) -> str` — syntax highlight code

**`components/` directory -> `py/pi_coding_agent/modes/interactive/components/`**
~35 component files. Key components to implement:
- `AssistantMessageComponent` — renders assistant messages with streaming
- `UserMessageComponent` — renders user messages
- `BashExecutionComponent` — renders bash tool execution with output
- `ToolExecutionComponent` — renders generic tool execution
- `FooterComponent` — status bar with model, tokens, cost
- `DiffComponent` — renders file diffs
- `ModelSelectorComponent` — model selection dialog
- `SessionSelectorComponent` — session picker
- `SettingsSelectorComponent` — settings editor
- `LoginDialogComponent` — auth/login flow
- `ExtensionSelectorComponent` — extension management
- (Read TS source for full list — each file is a TUI component)

**RPC Mode — `packages/coding-agent/src/modes/rpc/`**

**`rpc-mode.ts` -> `py/pi_coding_agent/modes/rpc/rpc_mode.py`**
- `async def run_rpc_mode(options) -> None` — start RPC server
- JSON-RPC over stdin/stdout

**`rpc-client.ts` -> `py/pi_coding_agent/modes/rpc/rpc_client.py`**
- RPC client for connecting to the RPC server

**`rpc-types.ts` -> `py/pi_coding_agent/modes/rpc/rpc_types.py`**
- RPC message types and protocol definitions

**Print Mode — `packages/coding-agent/src/modes/print-mode.ts`**
- `@dataclass PrintModeOptions` — configuration
- `async def run_print_mode(options: PrintModeOptions) -> None` — non-interactive mode, prints output to stdout

**HTML Export — `packages/coding-agent/src/core/export-html/`**

**`index.ts` -> `py/pi_coding_agent/core/export_html/__init__.py`**
- HTML export of conversation transcripts

**`ansi-to-html.ts` -> `py/pi_coding_agent/core/export_html/ansi_to_html.py`**
- Convert ANSI escape sequences to HTML spans

**`tool-renderer.ts` -> `py/pi_coding_agent/core/export_html/tool_renderer.py`**
- Render tool calls/results as HTML

**`packages/coding-agent/src/modes/index.ts` -> `py/pi_coding_agent/modes/__init__.py`**
- Re-export: `InteractiveMode`, `run_print_mode`, `run_rpc_mode`

## Tests — `py/tests/unit/pi_coding_agent/`
- `test_print_mode.py`: Test print mode with mock session, verify stdout output
- `test_rpc_types.py`: Test RPC message serialization
- `test_ansi_to_html.py`: Test ANSI-to-HTML conversion
- `test_theme.py`: Test theme initialization, language detection

## Acceptance Criteria
- [ ] Interactive mode can start and render basic UI (with mock terminal)
- [ ] Print mode produces correct output to stdout
- [ ] RPC mode accepts JSON-RPC requests over stdin
- [ ] `MAPPING.md` updated
- [ ] mypy, ruff, pytest all pass

## Dependencies
- Blocked by: Task 1.1a (TUI core), Task 1.1b (TUI components), Task 2.2a-d

## Metadata
- Phase: 2
- Package: coding-agent
- TS lines: ~6,000
- Estimated Python lines: ~4,500
EOF
)"

echo "Phase 2 issues created successfully!"

# --- Phase 3: Task 3.1a - Web UI Backend ---
gh issue create \
  --title "[Python Rewrite] pi_web_ui: Web UI Backend (Task 3.1a)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the Web UI backend from `packages/web-ui/src/`. The TS web-ui is a Lit-based frontend library. The Python rewrite provides a FastAPI backend that the frontend communicates with. Total TS source: ~14,539 lines.

Note: The frontend remains as TypeScript/Lit web components. This task creates the Python backend API that the frontend calls.

## Scope

### Backend API (new) — `py/pi_web_ui/`

**`py/pi_web_ui/app.py`** — FastAPI application
- REST API endpoints matching the TS frontend's expected API:
  - `POST /api/sessions` — create session
  - `GET /api/sessions` — list sessions
  - `GET /api/sessions/{id}` — get session
  - `DELETE /api/sessions/{id}` — delete session
  - `POST /api/sessions/{id}/prompt` — send prompt (SSE streaming response)
  - `POST /api/sessions/{id}/abort` — abort current generation
  - `GET /api/models` — list available models
  - `POST /api/settings` — update settings
  - `GET /api/settings` — get settings

**`py/pi_web_ui/storage/` directory** — Storage layer
Rewrite storage types and backends:

From `packages/web-ui/src/storage/types.ts` -> `py/pi_web_ui/storage/types.py`:
- `@dataclass SessionData` — session data
- `@dataclass SessionMetadata` — session metadata
- `StorageBackend` — protocol for storage backends
- `StorageTransaction` — protocol for transactions
- `@dataclass StoreConfig`, `@dataclass IndexConfig`

From `packages/web-ui/src/storage/store.ts` -> `py/pi_web_ui/storage/store.py`:
- `class Store` — generic key-value store

From `packages/web-ui/src/storage/app-storage.ts` -> `py/pi_web_ui/storage/app_storage.py`:
- `class AppStorage` — application-level storage facade
- `get_app_storage() -> AppStorage`
- `set_app_storage(storage: AppStorage) -> None`

From `packages/web-ui/src/storage/stores/` -> `py/pi_web_ui/storage/stores/`:
- `class SessionsStore` — session CRUD
- `class SettingsStore` — settings persistence
- `class ProviderKeysStore` — API key storage
- `class CustomProvidersStore` — custom provider configs

Storage backend: use SQLite (via `aiosqlite`) instead of IndexedDB.

**`py/pi_web_ui/tools/` directory** — Server-side tools
From `packages/web-ui/src/tools/`:
- `extract_document_tool` — document extraction tool
- `javascript_repl_tool` — JS REPL tool (adapt to Python REPL)
- Tool renderer registry

**`py/pi_web_ui/utils/` directory** — Utility functions
From `packages/web-ui/src/utils/`:
- `format_cost()`, `format_token_count()`, `format_usage()`, `format_model_cost()`
- `get_auth_token()`, `clear_auth_token()`
- Proxy utilities

### Create `py/pi_web_ui/pyproject.toml`
```toml
[project]
name = "pi-web-ui"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "pi-types",
  "pi-ai",
  "pi-agent",
  "pi-coding-agent",
  "fastapi",
  "uvicorn",
  "aiosqlite",
]
```

## Tests — `py/tests/unit/pi_web_ui/`
- `test_app.py`: Test FastAPI endpoints using `httpx.AsyncClient`
- `test_storage.py`: Test SQLite storage backend
- `test_sessions_store.py`: Test session CRUD operations
- `test_format.py`: Test cost/token formatting

## Acceptance Criteria
- [ ] `uvicorn pi_web_ui.app:app` starts the server
- [ ] All API endpoints return correct responses
- [ ] Session creation, listing, deletion work
- [ ] Streaming prompt responses work via SSE
- [ ] `MAPPING.md` created at `py/pi_web_ui/MAPPING.md`
- [ ] mypy, ruff, pytest all pass

## Dependencies
- Blocked by: Task 1.2a (pi_ai), Task 2.1 (pi_agent)

## Metadata
- Phase: 3
- Package: web-ui
- TS reference: `packages/web-ui/src/` (storage, tools, utils — backend-relevant portions)
- Estimated Python lines: ~3,000
EOF
)"

# --- Phase 3: Task 3.1b - Web UI Frontend Adaptation ---
gh issue create \
  --title "[Python Rewrite] pi_web_ui: Frontend Adaptation (Task 3.1b)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Adapt the existing TypeScript/Lit frontend to communicate with the new Python FastAPI backend instead of the Node.js backend. The frontend code stays as TypeScript — this task only modifies the API communication layer.

## Scope

### Modifications (NOT full rewrites)

**Update API client in frontend:**
- Modify API base URL configuration to point to Python backend
- Ensure request/response formats match FastAPI endpoints from Task 3.1a
- Update SSE streaming client to match Python SSE format

**Verify compatibility:**
- All chat functionality works end-to-end
- Session management (create, list, switch, delete)
- Model selection
- Settings persistence
- Streaming responses display correctly

### No Python code in this task
This task modifies the existing TS frontend to work with the Python backend. No new Python code is written.

## Acceptance Criteria
- [ ] Frontend connects to Python backend successfully
- [ ] Chat messages send and receive correctly
- [ ] Streaming responses render in real-time
- [ ] Session management works end-to-end
- [ ] Model switching works

## Dependencies
- Blocked by: Task 3.1a (Python backend)

## Metadata
- Phase: 3
- Package: web-ui (frontend)
- Estimated changes: ~200 lines of TS modifications
EOF
)"

# --- Phase 3: Task 3.2 - Mom (Slack Bot) ---
gh issue create \
  --title "[Python Rewrite] pi_mom: Slack Bot (Task 3.2)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the Slack bot from `packages/mom/src/`. Uses `slack-bolt` Python SDK. Total TS source: 4,120 lines across 12 files.

## Scope

### Files to Rewrite

**`packages/mom/src/agent.ts` -> `py/pi_mom/agent.py`**
- Agent logic for the Slack bot
- Wraps pi_agent with Slack-specific behavior
- Handles message threading, channel context

**`packages/mom/src/slack.ts` -> `py/pi_mom/slack.py`**
- `slack-bolt` app setup and event handlers
- Events: `message`, `app_mention`, `reaction_added`
- Slash commands registration
- Message formatting (Slack mrkdwn)

**`packages/mom/src/sandbox.ts` -> `py/pi_mom/sandbox.py`**
- Sandbox environment for code execution
- Isolated execution context for bot-triggered actions

**`packages/mom/src/store.ts` -> `py/pi_mom/store.py`**
- Conversation state persistence
- Thread-to-session mapping

**`packages/mom/src/context.ts` -> `py/pi_mom/context.py`**
- Context management for Slack conversations

**`packages/mom/src/events.ts` -> `py/pi_mom/events.py`**
- Event types for the Slack bot

**`packages/mom/src/download.ts` -> `py/pi_mom/download.py`**
- File download utilities for Slack attachments

**`packages/mom/src/log.ts` -> `py/pi_mom/log.py`**
- Logging configuration (use Python `logging` module)

**`packages/mom/src/main.ts` -> `py/pi_mom/main.py`**
- Entry point: initialize Slack app, start bolt server

**`packages/mom/src/tools/` directory -> `py/pi_mom/tools/`**

**`tools/index.ts` -> `py/pi_mom/tools/__init__.py`**
- Tool registration for the Slack bot agent

**`tools/bash.ts` -> `py/pi_mom/tools/bash.py`**
- Bash tool adapted for Slack (sandboxed execution)

**`tools/read.ts` -> `py/pi_mom/tools/read.py`**
- File read tool for Slack bot

**`tools/write.ts` -> `py/pi_mom/tools/write.py`**
- File write tool for Slack bot

**`tools/edit.ts` -> `py/pi_mom/tools/edit.py`**
- File edit tool for Slack bot

**`tools/attach.ts` -> `py/pi_mom/tools/attach.py`**
- Slack file attachment tool

**`tools/truncate.ts` -> `py/pi_mom/tools/truncate.py`**
- Output truncation for Slack message limits

### Create `py/pi_mom/pyproject.toml`
```toml
[project]
name = "pi-mom"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "pi-types",
  "pi-ai",
  "pi-agent",
  "slack-bolt",
]

[project.scripts]
pi-mom = "pi_mom.main:main"
```

## Key Design Decisions
- Use `slack-bolt` for Python (replaces `@slack/bolt` for Node)
- Async mode: use `slack-bolt`'s async handlers (`AsyncApp`)
- Message storage: use SQLite or file-based JSON (not in-memory)
- Tool execution: reuse pi_coding_agent tools where possible, adapt for sandbox

## Tests — `py/tests/unit/pi_mom/`
- `test_agent.py`: Test agent logic with mock Slack client
- `test_slack.py`: Test event handlers with `slack-bolt` test utilities
- `test_store.py`: Test conversation persistence
- `test_tools.py`: Test each tool with mock filesystem

## Acceptance Criteria
- [ ] Slack bot starts and connects (with valid SLACK_BOT_TOKEN)
- [ ] Responds to mentions and direct messages
- [ ] Tool execution works in sandbox
- [ ] `MAPPING.md` created at `py/pi_mom/MAPPING.md`
- [ ] `cd py && mypy --strict pi_mom/` passes
- [ ] `cd py && ruff check pi_mom/` passes
- [ ] `cd py && pytest tests/unit/pi_mom/ --cov=pi_mom --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 2.1, Task 2.2a (tools)

## Metadata
- Phase: 3
- Package: mom
- TS reference: `packages/mom/src/` (12 files)
- TS lines: 4,120
- Estimated Python lines: ~3,000
EOF
)"

# --- Phase 3: Task 3.3 - Pods ---
gh issue create \
  --title "[Python Rewrite] pi_pods: Pod Management CLI (Task 3.3)" \
  --label "python-rewrite" \
  --body "$(cat <<'EOF'
## Overview
Rewrite the pod management CLI from `packages/pods/src/`. Total TS source: 1,773 lines across 7 files.

## Scope

### Files to Rewrite

**`packages/pods/src/types.ts` -> `py/pi_pods/types.py`**
- Read the TS file for all exported types
- Convert interfaces/types to `@dataclass`

**`packages/pods/src/config.ts` -> `py/pi_pods/config.py`**
- Pod configuration management
- Read/write pod configs from file

**`packages/pods/src/model-configs.ts` -> `py/pi_pods/model_configs.py`**
- Model configuration definitions for pods

**`packages/pods/src/ssh.ts` -> `py/pi_pods/ssh.py`**
- SSH connection management using `asyncssh` or `paramiko`
- `async def connect_ssh(host: str, user: str, key_path: Path) -> SSHConnection`
- `async def execute_remote(conn: SSHConnection, command: str) -> str`
- Port forwarding setup

**`packages/pods/src/commands/pods.ts` -> `py/pi_pods/commands/pods.py`**
- CLI commands for pod lifecycle:
  - `create` — create a new pod
  - `list` — list all pods
  - `start` — start a pod
  - `stop` — stop a pod
  - `delete` — delete a pod
  - `ssh` — SSH into a pod
  - `status` — show pod status

**`packages/pods/src/commands/models.ts` -> `py/pi_pods/commands/models.py`**
- CLI commands for model management on pods

**`packages/pods/src/commands/prompt.ts` -> `py/pi_pods/commands/prompt.py`**
- CLI commands for prompting models on pods

**`packages/pods/src/cli.ts` -> `py/pi_pods/cli.py`**
- CLI entry point using `typer` or `click`
- Register commands from `commands/` module

**`packages/pods/src/index.ts` -> `py/pi_pods/__init__.py`**
- Re-export public API

### Create `py/pi_pods/pyproject.toml`
```toml
[project]
name = "pi-pods"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "pi-types",
  "pi-ai",
  "pi-agent",
  "asyncssh",
  "typer",
]

[project.scripts]
pi-pods = "pi_pods.cli:app"
```

## Key Design Decisions
- Use `asyncssh` for async SSH (preferred over paramiko for async compatibility)
- Use `typer` for CLI (consistent with other packages)
- Pod configs stored in `~/.pi/pods/` as JSON files

## Tests — `py/tests/unit/pi_pods/`
- `test_config.py`: Test config read/write with temp files
- `test_model_configs.py`: Test model configuration
- `test_ssh.py`: Test SSH connection setup (mock asyncssh)
- `test_cli.py`: Test CLI commands using typer test client

## Acceptance Criteria
- [ ] `pi-pods --help` shows available commands
- [ ] Pod lifecycle commands work (with mock SSH)
- [ ] SSH connection management works
- [ ] `MAPPING.md` created at `py/pi_pods/MAPPING.md`
- [ ] `cd py && mypy --strict pi_pods/` passes
- [ ] `cd py && ruff check pi_pods/` passes
- [ ] `cd py && pytest tests/unit/pi_pods/ --cov=pi_pods --cov-fail-under=80` passes

## Dependencies
- Blocked by: Task 0.1, Task 2.1

## Metadata
- Phase: 3
- Package: pods
- TS reference: `packages/pods/src/` (7 files)
- TS lines: 1,773
- Estimated Python lines: ~1,300
EOF
)"

echo ""
echo "=== All issues created successfully! ==="
echo "Phase 0: 1 issue (Task 0.1)"
echo "Phase 1: 4 issues (Task 1.1a, 1.1b, 1.2a, 1.2b, 1.2c, 1.2d)"
echo "Phase 2: 6 issues (Task 2.1, 2.2a, 2.2b, 2.2c, 2.2d, 2.2e, 2.2f)"
echo "Phase 3: 4 issues (Task 3.1a, 3.1b, 3.2, 3.3)"
echo "Total: 15 issues"
