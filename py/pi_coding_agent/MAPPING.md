# TypeScript → Python Name Mapping

This file maps TypeScript names from `packages/coding-agent/src/core/` to their
Python equivalents in `pi_coding_agent/core/`. Use this as a reference when
porting additional code or when debugging cross-language issues.

## File Mapping

| TypeScript file | Python module |
|---|---|
| `event-bus.ts` | `event_bus.py` |
| `messages.ts` | `messages.py` |
| `exec.ts` | `exec.py` |
| `bash-executor.ts` | `bash_executor.py` |
| `system-prompt.ts` | `system_prompt.py` |
| `session-manager.ts` | `session_manager.py` |
| `package-manager.ts` | `package_manager.py` |
| `agent-session.ts` | `agent_session.py` |
| `config.ts` | `config.py` |
| `auth-storage.ts` | `auth_storage.py` |
| `settings-manager.ts` | `settings_manager.py` |
| `model-registry.ts` | `model_registry.py` |
| `model-resolver.ts` | `model_resolver.py` |
| `skills.ts` | `skills.py` |
| `prompt-templates.ts` | `prompt_templates.py` |
| `resource-loader.ts` | `resource_loader.py` |
| `compaction/utils.ts` | `compaction/utils.py` |
| `compaction/compaction.ts` | `compaction/compaction.py` |
| `compaction/branch-summarization.ts` | `compaction/branch_summarization.py` |
| `extensions/types.ts` | `extensions/types.py` |
| `extensions/loader.ts` | `extensions/loader.py` |
| `extensions/runner.ts` | `extensions/runner.py` |
| `extensions/wrapper.ts` | `extensions/wrapper.py` |
| `core/tools/truncate.ts` | `core/tools/truncate.py` |
| `core/tools/path-utils.ts` | `core/tools/path_utils.py` |
| `core/tools/edit-diff.ts` | `core/tools/edit_diff.py` |
| `core/tools/bash.ts` | `core/tools/bash.py` |
| `core/tools/read.ts` | `core/tools/read.py` |
| `core/tools/edit.ts` | `core/tools/edit.py` |
| `core/tools/write.ts` | `core/tools/write.py` |
| `core/tools/grep.ts` | `core/tools/grep.py` |
| `core/tools/find.ts` | `core/tools/find.py` |
| `core/tools/ls.ts` | `core/tools/ls.py` |

---

## event_bus.py

| TypeScript | Python | Notes |
|---|---|---|
| `EventBus` (interface) | `EventBus` (Protocol) | |
| `createEventBus()` | `create_event_bus()` | |
| `EventBusImpl` | `_EventBusImpl` | private |
| `bus.on(channel, handler)` | `bus.on(channel, handler)` | |
| `bus.emit(channel, data)` | `bus.emit(channel, data)` | |
| `bus.clear()` | `bus.clear()` | |

---

## messages.py

| TypeScript | Python | Notes |
|---|---|---|
| `BashExecutionMessage` | `BashExecutionMessage` | `output` → `stdout`; `stderr` added |
| `CustomMessage` | `CustomMessage` | |
| `BranchSummaryMessage` | `BranchSummaryMessage` | |
| `CompactionSummaryMessage` | `CompactionSummaryMessage` | |
| `AgentMessage` (widened) | `SessionMessage` | type alias including custom types |
| `bashExecutionToText()` | `bash_execution_to_text()` | |
| `convertToLlm()` | `convert_to_llm()` | |
| `createBranchSummaryMessage()` | `create_branch_summary_message()` | |
| `createCompactionSummaryMessage()` | `create_compaction_summary_message()` | |
| `createCustomMessage()` | `create_custom_message()` | |
| `COMPACTION_SUMMARY_PREFIX` | `COMPACTION_SUMMARY_PREFIX` | |
| `COMPACTION_SUMMARY_SUFFIX` | `COMPACTION_SUMMARY_SUFFIX` | |
| `BRANCH_SUMMARY_PREFIX` | `BRANCH_SUMMARY_PREFIX` | |
| `BRANCH_SUMMARY_SUFFIX` | `BRANCH_SUMMARY_SUFFIX` | |

---

## exec.py

| TypeScript | Python | Notes |
|---|---|---|
| `ExecOptions` | `ExecOptions` | `signal: AbortSignal` → `signal: asyncio.Event` |
| `ExecResult` | `ExecResult` | |
| `execCommand()` | `exec_command()` | |
| `AbortSignal` | `asyncio.Event` | |
| `AbortController` | `asyncio.Event` | |

---

## bash_executor.py

| TypeScript | Python | Notes |
|---|---|---|
| `DEFAULT_MAX_BYTES` | `DEFAULT_MAX_BYTES` | 200 KB |
| `BashExecutorOptions` | `BashExecutorOptions` | `signal: AbortSignal` → `asyncio.Event` |
| `BashResult` | `BashResult` | |
| `executeBash()` | `execute_bash()` | |
| `executeBashWithOperations()` | `execute_bash_with_operations()` | |
| `sanitizeOutput()` | `_sanitize_output()` | private |
| `truncateTail()` | `_truncate_tail()` | private |

---

## system_prompt.py

| TypeScript | Python | Notes |
|---|---|---|
| `SystemPromptOptions` | `SystemPromptOptions` | |
| `SkillInfo` | `SkillInfo` | |
| `buildSystemPrompt()` | `build_system_prompt()` | |
| `formatSkillsForPrompt()` | `format_skills_for_prompt()` | |

---

## session_manager.py

| TypeScript | Python | Notes |
|---|---|---|
| `SessionHeader` | `SessionHeader` | |
| `SessionMessageEntry` | `SessionMessageEntry` | |
| `ThinkingLevelChangeEntry` | `ThinkingLevelChangeEntry` | |
| `ModelChangeEntry` | `ModelChangeEntry` | |
| `CompactionEntry` | `CompactionEntry` | |
| `BranchSummaryEntry` | `BranchSummaryEntry` | |
| `CustomEntry` | `CustomEntry` | |
| `CustomMessageEntry` | `CustomMessageEntry` | |
| `LabelEntry` | `LabelEntry` | |
| `SessionInfoEntry` | `SessionInfoEntry` | |
| `SessionEntry` | `SessionEntry` | type alias |
| `FileEntry` | `FileEntry` | type alias |
| `SessionContext` | `SessionContext` | |
| `SessionInfo` | `SessionInfo` | |
| `NewSessionOptions` | `NewSessionOptions` | |
| `SessionManager` | `SessionManager` | |
| `SessionManager.create()` | `SessionManager.create()` | classmethod |
| `SessionManager.open()` | `SessionManager.open()` | classmethod |
| `SessionManager.continueRecent()` | `SessionManager.continue_recent()` | classmethod |
| `SessionManager.inMemory()` | `SessionManager.in_memory()` | classmethod |
| `SessionManager.forkFrom()` | `SessionManager.fork_from()` | classmethod |
| `SessionManager.list()` | `SessionManager.list_sessions()` | renamed (Python `list` builtin conflict) |
| `SessionManager.listAll()` | `SessionManager.list_all()` | classmethod |
| `sm.appendMessage()` | `sm.append_message()` | |
| `sm.appendThinkingLevelChange()` | `sm.append_thinking_level_change()` | |
| `sm.appendModelChange()` | `sm.append_model_change()` | |
| `sm.appendCompaction()` | `sm.append_compaction()` | |
| `sm.appendSessionInfo()` | `sm.append_session_info()` | |
| `sm.appendCustomEntry()` | `sm.append_custom_entry()` | |
| `sm.appendCustomMessageEntry()` | `sm.append_custom_message_entry()` | |
| `sm.appendLabelChange()` | `sm.append_label_change()` | |
| `sm.getEntry()` | `sm.get_entry()` | |
| `sm.getEntries()` | `sm.get_entries()` | |
| `sm.getBranch()` | `sm.get_branch()` | |
| `sm.getChildren()` | `sm.get_children()` | |
| `sm.getTree()` | `sm.get_tree()` | |
| `sm.getLeafId()` | `sm.get_leaf_id()` | |
| `sm.getHeader()` | `sm.get_header()` | |
| `sm.getLabel()` | `sm.get_label()` | |
| `sm.getSessionId()` | `sm.get_session_id()` | |
| `sm.getSessionFile()` | `sm.get_session_file()` | |
| `sm.getSessionName()` | `sm.get_session_name()` | |
| `sm.branch()` | `sm.branch()` | |
| `sm.resetLeaf()` | `sm.reset_leaf()` | |
| `sm.branchWithSummary()` | `sm.branch_with_summary()` | |
| `sm.createBranchedSession()` | `sm.create_branched_session()` | |
| `sm.isPersisted()` | `sm.is_persisted()` | |
| `sm.newSession()` | `sm.new_session()` | |
| `sm.buildSessionContext()` | `sm.build_session_context()` | |
| `buildSessionContext()` | `build_session_context()` | standalone function |
| `getLatestCompactionEntry()` | `get_latest_compaction_entry()` | standalone function |
| `findMostRecentSession()` | `find_most_recent_session()` | standalone function |
| `loadEntriesFromFile()` | `load_entries_from_file()` | standalone function |
| `parseSessionEntries()` | `parse_session_entries()` | standalone function |
| `parentId` | `parent_id` | camelCase → snake_case in all entries |
| `thinkingLevel` | `thinking_level` | |
| `modelId` | `model_id` | |
| `firstKeptEntryId` | `first_kept_entry_id` | |
| `tokensBefore` | `tokens_before` | |
| `fromId` | `from_id` | |
| `fromHook` | `from_hook` | |
| `customType` | `custom_type` | |
| `targetId` | `target_id` | |
| `parentSession` | `parent_session` | |
| `excludeFromContext` | `exclude_from_context` | |
| `fullOutputPath` | `full_output_path` | |
| `exitCode` | `exit_code` | |

### Serialization Notes

- `BashExecutionMessage.output` (TS) ↔ `BashExecutionMessage.stdout` (Python)
  - When serializing to JSONL: Python `stdout` → `output` key (TS compatibility)
  - When deserializing: `output` key → Python `stdout` field
- `hookMessage` role (v2) → `custom` role (v3): handled by migration
- `parentId: null` (JSON) ↔ `parent_id: None` (Python)

---

## package_manager.py

| TypeScript | Python | Notes |
|---|---|---|
| `PathMetadata` | `PathMetadata` | |
| `ResolvedResource` | `ResolvedResource` | |
| `ResolvedPaths` | `ResolvedPaths` | |
| `ProgressEvent` | `ProgressEvent` | |
| `ProgressCallback` | `ProgressCallback` | type alias |
| `MissingSourceAction` | `MissingSourceAction` | type alias |
| `PackageManager` (interface) | `PackageManager` (Protocol) | |
| `DefaultPackageManager` | `DefaultPackageManager` | |
| `createPackageManager()` | `create_package_manager()` | |
| `pm.resolve()` | `pm.resolve()` | async |
| `pm.install()` | `pm.install()` | async |
| `pm.remove()` | `pm.remove()` | async |
| `pm.update()` | `pm.update()` | async |
| `pm.resolveExtensionSources()` | `pm.resolve_extension_sources()` | async |
| `pm.addSourceToSettings()` | `pm.add_source_to_settings()` | |
| `pm.removeSourceFromSettings()` | `pm.remove_source_from_settings()` | |
| `pm.setProgressCallback()` | `pm.set_progress_callback()` | |
| `pm.getInstalledPath()` | `pm.get_installed_path()` | |

---

## agent_session.py

| TypeScript | Python | Notes |
|---|---|---|
| `AgentSessionConfig` | `AgentSessionConfig` | |
| `PromptOptions` | `PromptOptions` | |
| `SessionStats` | `SessionStats` | |
| `AutoCompactionStartEvent` | `AutoCompactionStartEvent` | |
| `AutoCompactionEndEvent` | `AutoCompactionEndEvent` | |
| `AutoRetryStartEvent` | `AutoRetryStartEvent` | |
| `AutoRetryEndEvent` | `AutoRetryEndEvent` | |
| `AgentSessionEvent` | `AgentSessionEvent` | type alias union |
| `AgentSessionEventListener` | `AgentSessionEventListener` | type alias |
| `AgentSession` | `AgentSession` | |
| `session.state` | `session.state` | property |
| `session.model` | `session.model` | property |
| `session.thinkingLevel` | `session.thinking_level` | property |
| `session.isStreaming` | `session.is_streaming` | property |
| `session.messages` | `session.messages` | property |
| `session.sessionId` | `session.session_id` | property |
| `session.sessionFile` | `session.session_file` | property |
| `session.sessionManager` | `session.session_manager` | property |
| `session.isCompacting` | `session.is_compacting` | property |
| `session.isBashRunning` | `session.is_bash_running` | property |
| `session.isRetrying` | `session.is_retrying` | property |
| `session.retryAttempt` | `session.retry_attempt` | property |
| `session.pendingMessageCount` | `session.pending_message_count` | property |
| `session.subscribe()` | `session.subscribe()` | |
| `session.prompt()` | `session.prompt()` | async |
| `session.abort()` | `session.abort()` | async |
| `session.abortBash()` | `session.abort_bash()` | |
| `session.abortCompaction()` | `session.abort_compaction()` | |
| `session.setModel()` | `session.set_model()` | async |
| `session.setThinkingLevel()` | `session.set_thinking_level()` | sync |
| `session.newSession()` | `session.new_session()` | async |
| `session.compact()` | `session.compact()` | async; raises NotImplementedError |
| `session.executeBash()` | `session.execute_bash()` | async |
| `session.getSessionStats()` | `session.get_session_stats()` | |
| `session.dispose()` | `session.dispose()` | |
| `AbortController` | `asyncio.Event` | |
| `AbortSignal` | `asyncio.Event` | |
| `THINKING_LEVELS` | `THINKING_LEVELS` | |
| `THINKING_LEVELS_WITH_XHIGH` | `THINKING_LEVELS_WITH_XHIGH` | |
| `DEFAULT_THINKING_LEVEL` | `DEFAULT_THINKING_LEVEL` | |

### Unimplemented Stubs

The following require parallel task 3-3 (compaction module):

- `session.compact()` → raises `NotImplementedError`
- `session._check_compaction()` → no-op stub

---

## Tools

| TypeScript | Python | Notes |
|---|---|---|
| `packages/coding-agent/src/core/tools/truncate.ts` | `core/tools/truncate.py` | |
| `packages/coding-agent/src/core/tools/path-utils.ts` | `core/tools/path_utils.py` | |
| `packages/coding-agent/src/core/tools/edit-diff.ts` | `core/tools/edit_diff.py` | |
| `packages/coding-agent/src/core/tools/bash.ts` | `core/tools/bash.py` | |
| `packages/coding-agent/src/core/tools/read.ts` | `core/tools/read.py` | |
| `packages/coding-agent/src/core/tools/edit.ts` | `core/tools/edit.py` | |
| `packages/coding-agent/src/core/tools/write.ts` | `core/tools/write.py` | |
| `packages/coding-agent/src/core/tools/grep.ts` | `core/tools/grep.py` | |
| `packages/coding-agent/src/core/tools/find.ts` | `core/tools/find.py` | |
| `packages/coding-agent/src/core/tools/ls.ts` | `core/tools/ls.py` | |

### Key Differences

- TypeScript uses TypeBox JSON Schema; Python uses plain `dict[str, Any]` for JSON Schema.
- TypeScript uses `AbortSignal`; Python uses `asyncio.Event`.
- TypeScript uses `execa` for subprocess; Python uses `asyncio.create_subprocess_shell`.
- TypeScript uses `ripgrep` binary via `execa`; Python uses `subprocess.run` with fallback to `re`.
- TypeScript uses `fd` binary for find; Python uses `subprocess.run` with fallback to `glob.glob`.
- Image resizing (TypeScript uses `sharp`) is not implemented; images are returned as raw base64.
- TypeScript `stream.Readable` I/O; Python uses `asyncio.StreamReader`.

---

## General Conventions

| TypeScript pattern | Python equivalent |
|---|---|
| `camelCase` names | `snake_case` names |
| `interface Foo { ... }` | `@dataclass class Foo` |
| `type Foo = A \| B` | `Foo = A \| B` (type alias) |
| `enum Foo` | `Literal["a", "b"]` or `StrEnum` |
| `AbortController` / `AbortSignal` | `asyncio.Event` |
| `Promise<T>` | `Coroutine[..., T]` (async def) |
| `readonly` fields | regular fields (enforced by convention) |
| `undefined` | `None` |
| `Record<string, T>` | `dict[str, T]` |
| `Array<T>` | `list[T]` |
| `export function foo()` | `def foo()` (module-level) |
| `export class Foo` | `class Foo` |
| `private _foo` | `self._foo` (by convention) |
| JSONL `parentId` (camelCase) | `parent_id` in Python, serialized as `parentId` |

---

## Key Adaptation Decisions (Extensions/Settings/Compaction)

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

## Settings JSON Compatibility

Settings are persisted in JSON using camelCase keys (to remain compatible with the TypeScript `.pi/settings.json` format). The Python port maintains a bidirectional mapping dictionary (`_CAMEL_TO_SNAKE` / `_SNAKE_TO_CAMEL`) in `settings_manager.py`.

## Extension Factory Convention

TypeScript extensions export a default function via ES module default export. Python extensions must export a callable factory under one of these attribute names (checked in order):
1. `extension`
2. `register`
3. `factory`
4. `main`
5. Any non-underscore callable that is not a class
