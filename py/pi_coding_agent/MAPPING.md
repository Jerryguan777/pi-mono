# pi_coding_agent Python Port — TypeScript → Python Mapping

This document records the mapping from the original TypeScript source
(`packages/coding-agent/src/core/`) to the Python port
(`py/pi_coding_agent/core/`).

## File Mapping

| TypeScript source | Python module |
|---|---|
| `src/core/config.ts` | `core/config.py` |
| `src/core/compaction/utils.ts` | `core/compaction/utils.py` |
| `src/core/compaction/compaction.ts` | `core/compaction/compaction.py` |
| `src/core/compaction/branch-summarization.ts` | `core/compaction/branch_summarization.py` |
| `src/core/auth-storage.ts` | `core/auth_storage.py` |
| `src/core/settings-manager.ts` | `core/settings_manager.py` |
| `src/core/extensions/types.ts` | `core/extensions/types.py` |
| `src/core/extensions/loader.ts` | `core/extensions/loader.py` |
| `src/core/extensions/runner.ts` | `core/extensions/runner.py` |
| `src/core/extensions/wrapper.ts` | `core/extensions/wrapper.py` |
| `src/core/model-registry.ts` | `core/model_registry.py` |
| `src/core/model-resolver.ts` | `core/model_resolver.py` |
| `src/core/skills.ts` | `core/skills.py` |
| `src/core/prompt-templates.ts` | `core/prompt_templates.py` |
| `src/core/resource-loader.ts` | `core/resource_loader.py` |

## Naming Conventions

- TypeScript `camelCase` identifiers → Python `snake_case`
- TypeScript `PascalCase` class names are preserved
- TypeScript `interface Foo` → Python `@dataclass class Foo`
- TypeScript `type Foo = A | B` discriminated unions → Python `Literal["value"]` fields on dataclasses
- TypeScript `enum` → Python `StrEnum` or `Literal` type alias
- TypeScript `type Scope = "global" | "project"` → Python `SettingsScope = Literal["global", "project"]`

## Key Adaptation Decisions

### AbortController / AbortSignal → asyncio.Event
TypeScript uses `AbortController`/`AbortSignal` for cancellation. Python uses `asyncio.Event`.

### File locking (proper-lockfile) → threading.Lock
TypeScript uses `proper-lockfile` for cross-process file locking. Python uses `threading.Lock` (in-process only, sufficient for single-process agent).

### jiti (dynamic TS loading) → importlib.util
TypeScript loads extension plugins via `jiti`. Python loads `.py` extension files via `importlib.util.spec_from_file_location`.

### minimatch → fnmatch
TypeScript uses `minimatch` for glob pattern matching. Python uses the built-in `fnmatch` module.

### YAML frontmatter → PyYAML + fallback
TypeScript parses YAML frontmatter with a dedicated library. Python uses `PyYAML` (`yaml.safe_load`) with a basic key:value fallback parser.

### AJV/TypeBox schema validation → simplified runtime checks
TypeScript uses AJV + TypeBox for JSON schema validation of settings and model registry config. Python validates with simple `isinstance` checks and key presence tests.

### OAuth helpers → pi_ai
OAuth credential management delegates to `pi_ai` provider utilities.

### TUI types → Any
The TUI package (`pi-tui`) is not yet ported. All TUI-related types (`TUI`, `Component`, `EditorComponent`, etc.) are typed as `Any`.

### Session manager → not yet ported
The session manager is not yet ported. All session entry types are `dict[str, Any]` with duck-typed attribute access.

## Settings JSON Compatibility

Settings are persisted in JSON using camelCase keys (to remain compatible with the TypeScript `.pi/settings.json` format). The Python port maintains a bidirectional mapping dictionary (`_CAMEL_TO_SNAKE` / `_SNAKE_TO_CAMEL`) in `settings_manager.py`.

## Extension Factory Convention

TypeScript extensions export a default function via ES module default export. Python extensions must export a callable factory under one of these attribute names (checked in order):
1. `extension`
2. `register`
3. `factory`
4. `main`
5. Any non-underscore callable that is not a class

## Not Ported

The following TypeScript modules are intentionally excluded from this port (out of scope for Phase 2):

- `src/core/tools/` — agent tools (bash, read, write, edit, grep, find, ls, etc.)
- `src/core/system-prompt.ts` — system prompt assembly
- `src/core/session/` — session management
- `src/cli.ts` — CLI entry point
- `src/tui/` — TUI rendering
