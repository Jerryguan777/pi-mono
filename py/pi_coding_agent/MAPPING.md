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
# pi_coding_agent TypeScript -> Python Mapping

| TS Function/Class/Type | Python Equivalent | Status | Notes |
|------------------------|-------------------|--------|-------|
| **config.ts** | **config.py** | | |
| `APP_NAME: string` | `APP_NAME: str` | Done | |
| `CONFIG_DIR_NAME: string` | `CONFIG_DIR_NAME: str` | Done | |
| `VERSION: string` | `VERSION: str` | Done | Hardcoded; TS reads package.json |
| `ENV_AGENT_DIR: string` | `ENV_AGENT_DIR: str` | Done | |
| `InstallMethod` type | `str` (type alias) | Done | Python always returns "pip" |
| `detectInstallMethod()` | `detect_install_method()` | Done | Always returns "pip" |
| `getUpdateInstruction()` | `get_update_instruction()` | Done | |
| `getPackageDir()` | `get_package_dir()` | Done | Returns Path(__file__).parent |
| `getThemesDir()` | `get_themes_dir()` | Done | Returns data/ dir inside package |
| `getExportTemplateDir()` | `get_export_template_dir()` | Done | |
| `getPackageJsonPath()` | N/A | Skipped | Not needed in Python |
| `getShareViewerUrl()` | `get_share_viewer_url()` | Done | |
| `getAgentDir()` | `get_agent_dir()` | Done | |
| `getCustomThemesDir()` | `get_custom_themes_dir()` | Done | |
| `getModelsPath()` | `get_models_path()` | Done | |
| `getAuthPath()` | `get_auth_path()` | Done | |
| `getSettingsPath()` | `get_settings_path()` | Done | |
| `getToolsDir()` | `get_tools_dir()` | Done | |
| `getBinDir()` | `get_bin_dir()` | Done | |
| `getPromptsDir()` | `get_prompts_dir()` | Done | |
| `getSessionsDir()` | `get_sessions_dir()` | Done | |
| `getDebugLogPath()` | `get_debug_log_path()` | Done | |
| **migrations.ts** | **migrations.py** | | |
| `migrateAuthToAuthJson()` | `migrate_auth_to_auth_json()` | Done | |
| `migrateSessionsFromAgentRoot()` | `migrate_sessions_from_agent_root()` | Done | |
| `showDeprecationWarnings()` | `show_deprecation_warnings()` | Done | Uses termios for raw mode |
| `runMigrations()` returns `{...}` | `run_migrations() -> MigrationResult` | Done | Uses dataclass instead of plain dict |
| **cli/args.ts** | **cli/args.py** | | |
| `Mode` type | `Mode` Literal | Done | |
| `ThinkingLevel` (re-exported) | `ThinkingLevel` Literal | Done | |
| `VALID_THINKING_LEVELS` | `VALID_THINKING_LEVELS` | Done | |
| `Args` interface | `Args` dataclass | Done | `continue` -> `continue_session`; `print` -> `print_mode` |
| `isValidThinkingLevel()` | `is_valid_thinking_level()` | Done | |
| `parseArgs()` | `parse_args()` | Done | `Map` -> `dict` for unknown_flags |
| `printHelp()` | `print_help()` | Done | |
| **cli/list-models.ts** | **cli/list_models.py** | | |
| `formatTokenCount()` (private) | `format_token_count()` | Done | Made public as per spec |
| `listModels()` | `list_models()` | Done | |
| **cli/file-processor.ts** | **cli/file_processor.py** | | |
| `ProcessedFiles` interface | `ProcessedFiles` dataclass | Done | |
| `ProcessFileOptions` interface | `ProcessFileOptions` dataclass | Done | |
| `processFileArguments()` | `process_file_arguments()` | Done | Image resize is no-op |
| **cli/config-selector.ts** | **cli/config_selector.py** | | |
| `ConfigSelectorOptions` interface | `ConfigSelectorOptions` dataclass | Done | |
| `selectConfig()` | `select_config()` | Done (stub) | Prints placeholder |
| **cli/session-picker.ts** | **cli/session_picker.py** | | |
| `selectSession()` | `select_session()` | Done (stub) | Uses input() instead of TUI |
| **modes/print-mode.ts** | **modes/print_mode.py** | | |
| `PrintModeOptions` interface | `PrintModeOptions` dataclass | Done | |
| `runPrintMode()` | `run_print_mode()` | Done | |
| **modes/interactive/theme/theme.ts** | **modes/interactive/theme.py** | | |
| `ColorMode` type | `ColorMode` Literal | Done | |
| `ThemeColor` type | `ThemeColor` Literal | Done | |
| `ThemeBg` type | `ThemeBg` Literal | Done | |
| `ThemeInfo` interface | `ThemeInfo` dataclass | Done | |
| `Theme` class | `Theme` class | Done | |
| `detectColorMode()` | `detect_color_mode()` | Done | |
| `hexToRgb()` | `hex_to_rgb()` | Done | Returns tuple instead of object |
| `rgbTo256()` | `rgb_to_256()` | Done | |
| `fgAnsi()` | `fg_ansi()` | Done | |
| `bgAnsi()` | `bg_ansi()` | Done | |
| `resolveVarRefs()` | `resolve_var_refs()` | Done | |
| `resolveThemeColors()` | `resolve_theme_colors()` | Done | |
| `getAvailableThemes()` | `get_available_themes()` | Done | |
| `getAvailableThemesWithPaths()` | `get_available_themes_with_paths()` | Done | |
| `loadThemeFromPath()` | `load_theme_from_path()` | Done | |
| `getThemeByName()` | `get_theme_by_name()` | Done | |
| `initTheme()` | `init_theme()` | Done | |
| `setTheme()` | `set_theme()` | Done | |
| `setThemeInstance()` | `set_theme_instance()` | Done | |
| `onThemeChange()` | `on_theme_change()` | Done | |
| `stopThemeWatcher()` | `stop_theme_watcher()` | Done | |
| `setRegisteredThemes()` | `set_registered_themes()` | Done | |
| `getResolvedThemeColors()` | `get_resolved_theme_colors()` | Done | |
| `isLightTheme()` | `is_light_theme()` | Done | |
| `getThemeExportColors()` | `get_theme_export_colors()` | Done | |
| `highlightCode()` | `highlight_code()` | Done | Uses Pygments if available |
| `getLanguageFromPath()` | `get_language_from_path()` | Done | |
| `getMarkdownTheme()` | `get_markdown_theme()` | Done | |
| `getSelectListTheme()` | `get_select_list_theme()` | Done | |
| `getEditorTheme()` | `get_editor_theme()` | Done | |
| `getSettingsListTheme()` | `get_settings_list_theme()` | Done | |
| `theme` (Proxy) | `theme` (_ThemeProxy) | Done | Module-level proxy singleton |
| **modes/interactive/interactive-mode.ts** | **modes/interactive/interactive_mode.py** | | |
| `InteractiveMode` class | `InteractiveMode` class | Done (stub) | Full TUI pending parallel tasks |
| **main.ts** | **main.py** | | |
| `main()` | `main()` | Done (stub) | Core session pending parallel tasks |
| **data files** | **data/** | | |
| `dark.json` | `data/dark.json` | Done | Copied from TS source |
| `light.json` | `data/light.json` | Done | Copied from TS source |
| `theme-schema.json` | `data/theme-schema.json` | Done | Copied from TS source |

---

# pi_coding_agent: TypeScript → Python Mapping

## Interactive Components (modes/interactive/components/)

| TS File | Python File | Status | Notes |
|---------|-------------|--------|-------|
| `src/modes/interactive/components/index.ts` | `modes/interactive/components/__init__.py` | Done | Re-exports all public symbols |
| `src/modes/interactive/components/armin.ts` | `modes/interactive/components/armin.py` | Done | Easter egg animated ASCII art component |
| `src/modes/interactive/components/assistant-message.ts` | `modes/interactive/components/assistant_message.py` | Done | Assistant chat message rendering |
| `src/modes/interactive/components/bash-execution.ts` | `modes/interactive/components/bash_execution.py` | Done | Streaming bash command output display |
| `src/modes/interactive/components/bordered-loader.ts` | `modes/interactive/components/bordered_loader.py` | Done | Loader with dynamic borders |
| `src/modes/interactive/components/branch-summary-message.ts` | `modes/interactive/components/branch_summary_message.py` | Done | Branch summary message rendering |
| `src/modes/interactive/components/compaction-summary-message.ts` | `modes/interactive/components/compaction_summary_message.py` | Done | Compaction summary message rendering |
| `src/modes/interactive/components/config-selector.ts` | `modes/interactive/components/config_selector.py` | Done | Extension/config resource selector |
| `src/modes/interactive/components/countdown-timer.ts` | `modes/interactive/components/countdown_timer.py` | Done | Countdown timer component |
| `src/modes/interactive/components/custom-editor.ts` | `modes/interactive/components/custom_editor.py` | Done | Editor subclass with app keybindings |
| `src/modes/interactive/components/custom-message.ts` | `modes/interactive/components/custom_message.py` | Done | Custom message rendering |
| `src/modes/interactive/components/daxnuts.ts` | `modes/interactive/components/daxnuts.py` | Done | Easter egg — Powered by Daxnuts animated pixel art |
| `src/modes/interactive/components/diff.ts` | `modes/interactive/components/diff.py` | Done | Word-level diff rendering with ANSI colors |
| `src/modes/interactive/components/dynamic-border.ts` | `modes/interactive/components/dynamic_border.py` | Done | Dynamic horizontal border component |
| `src/modes/interactive/components/extension-editor.ts` | `modes/interactive/components/extension_editor.py` | Done | Multi-line editor for extensions |
| `src/modes/interactive/components/extension-input.ts` | `modes/interactive/components/extension_input.py` | Done | Single-line input for extensions |
| `src/modes/interactive/components/extension-selector.ts` | `modes/interactive/components/extension_selector.py` | Done | Extension picker component |
| `src/modes/interactive/components/footer.ts` | `modes/interactive/components/footer.py` | Done | Two-line footer with tokens, context, extensions |
| `src/modes/interactive/components/keybinding-hints.ts` | `modes/interactive/components/keybinding_hints.py` | Done | Keybinding hint formatting utilities |
| `src/modes/interactive/components/login-dialog.ts` | `modes/interactive/components/login_dialog.py` | Done | OAuth login dialog component |
| `src/modes/interactive/components/model-selector.ts` | `modes/interactive/components/model_selector.py` | Done | Fuzzy model selector with scope toggle |
| `src/modes/interactive/components/oauth-selector.ts` | `modes/interactive/components/oauth_selector.py` | Done | OAuth provider selector |
| `src/modes/interactive/components/scoped-models-selector.ts` | `modes/interactive/components/scoped_models_selector.py` | Done | Scoped model toggle list |
| `src/modes/interactive/components/session-selector-search.ts` | `modes/interactive/components/session_selector_search.py` | Done | Session search query parsing |
| `src/modes/interactive/components/session-selector.ts` | `modes/interactive/components/session_selector.py` | Done | Session picker with search, sort, delete, rename |
| `src/modes/interactive/components/settings-selector.ts` | `modes/interactive/components/settings_selector.py` | Done | Settings panel using SettingsList |
| `src/modes/interactive/components/show-images-selector.ts` | `modes/interactive/components/show_images_selector.py` | Done | Show images toggle selector |
| `src/modes/interactive/components/skill-invocation-message.ts` | `modes/interactive/components/skill_invocation_message.py` | Done | Skill invocation message rendering |
| N/A (internal) | `modes/interactive/components/_theme.py` | Done | ANSI theme and syntax highlighting utilities |
| `src/modes/interactive/components/theme-selector.ts` | `modes/interactive/components/theme_selector.py` | Done | Color theme selector component |
| `src/modes/interactive/components/thinking-selector.ts` | `modes/interactive/components/thinking_selector.py` | Done | Thinking level selector component |
| `src/modes/interactive/components/tool-execution.ts` | `modes/interactive/components/tool_execution.py` | Done | Tool call/result rendering with expand/collapse |
| `src/modes/interactive/components/tree-selector.ts` | `modes/interactive/components/tree_selector.py` | Done | Session tree selector with filter modes, search, labels |
| `src/modes/interactive/components/user-message.ts` | `modes/interactive/components/user_message.py` | Done | User message rendering |
| `src/modes/interactive/components/user-message-selector.ts` | `modes/interactive/components/user_message_selector.py` | Done | User message picker component |
| `src/modes/interactive/components/visual-truncate.ts` | `modes/interactive/components/visual_truncate.py` | Done | Visual line truncation utility |

---

# pi_coding_agent — TypeScript → Python Mapping

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `RpcCommand` (union type) | `RpcCommand` (union of dataclasses) | Done | Individual dataclass per variant with `Literal` type field |
| `RpcPromptCommand` | `RpcPromptCommand` | Done | |
| `RpcSteerCommand` | `RpcSteerCommand` | Done | |
| `RpcFollowUpCommand` | `RpcFollowUpCommand` | Done | |
| `RpcAbortCommand` | `RpcAbortCommand` | Done | |
| `RpcNewSessionCommand` | `RpcNewSessionCommand` | Done | `parentSession` → `parent_session` |
| `RpcGetStateCommand` | `RpcGetStateCommand` | Done | |
| `RpcSetModelCommand` | `RpcSetModelCommand` | Done | `modelId` → `model_id` |
| `RpcCycleModelCommand` | `RpcCycleModelCommand` | Done | |
| `RpcGetAvailableModelsCommand` | `RpcGetAvailableModelsCommand` | Done | |
| `RpcSetThinkingLevelCommand` | `RpcSetThinkingLevelCommand` | Done | |
| `RpcCycleThinkingLevelCommand` | `RpcCycleThinkingLevelCommand` | Done | |
| `RpcSetSteeringModeCommand` | `RpcSetSteeringModeCommand` | Done | |
| `RpcSetFollowUpModeCommand` | `RpcSetFollowUpModeCommand` | Done | |
| `RpcCompactCommand` | `RpcCompactCommand` | Done | `customInstructions` → `custom_instructions` |
| `RpcSetAutoCompactionCommand` | `RpcSetAutoCompactionCommand` | Done | |
| `RpcSetAutoRetryCommand` | `RpcSetAutoRetryCommand` | Done | |
| `RpcAbortRetryCommand` | `RpcAbortRetryCommand` | Done | |
| `RpcBashCommand` | `RpcBashCommand` | Done | |
| `RpcAbortBashCommand` | `RpcAbortBashCommand` | Done | |
| `RpcGetSessionStatsCommand` | `RpcGetSessionStatsCommand` | Done | |
| `RpcExportHtmlCommand` | `RpcExportHtmlCommand` | Done | `outputPath` → `output_path` |
| `RpcSwitchSessionCommand` | `RpcSwitchSessionCommand` | Done | `sessionPath` → `session_path` |
| `RpcForkCommand` | `RpcForkCommand` | Done | `entryId` → `entry_id` |
| `RpcGetForkMessagesCommand` | `RpcGetForkMessagesCommand` | Done | |
| `RpcGetLastAssistantTextCommand` | `RpcGetLastAssistantTextCommand` | Done | |
| `RpcSetSessionNameCommand` | `RpcSetSessionNameCommand` | Done | |
| `RpcGetMessagesCommand` | `RpcGetMessagesCommand` | Done | |
| `RpcGetCommandsCommand` | `RpcGetCommandsCommand` | Done | |
| `RpcCommandType` | `RpcCommandType` | Done | `Literal` union string |
| `RpcSlashCommand` | `RpcSlashCommand` | Done | `@dataclass` |
| `RpcSessionState` | `RpcSessionState` | Done | `@dataclass`; camelCase → snake_case |
| `RpcResponse` | `RpcResponse` | Done | `@dataclass` |
| `RpcExtensionUIRequest` | `RpcExtensionUIRequest` | Done | `@dataclass` |
| `RpcExtensionUIResponse` | `RpcExtensionUIResponse` | Done | `@dataclass` |
| `deserialize_rpc_command()` | `deserialize_rpc_command()` | Done | |
| `serialize_rpc_session_state()` | `serialize_rpc_session_state()` | Done | |
| `deserialize_rpc_session_state()` | `deserialize_rpc_session_state()` | Done | |
| `serialize_rpc_response()` | `serialize_rpc_response()` | Done | |
| `deserialize_rpc_response()` | `deserialize_rpc_response()` | Done | |
| `serialize_rpc_extension_ui_request()` | `serialize_rpc_extension_ui_request()` | Done | |
| `deserialize_rpc_extension_ui_response()` | `deserialize_rpc_extension_ui_response()` | Done | |
| `RpcClient` class | `RpcClient` class | Done | Uses `asyncio.subprocess`; `asyncio.Future` for pending |
| `RpcClient.start()` | `RpcClient.start()` | Done | |
| `RpcClient.stop()` | `RpcClient.stop()` | Done | |
| `RpcClient.onEvent()` | `RpcClient.on_event()` | Done | Returns unsubscribe callable |
| `RpcClient.getStderr()` | `RpcClient.get_stderr()` | Done | |
| `RpcClient.prompt()` | `RpcClient.prompt()` | Done | |
| `RpcClient.steer()` | `RpcClient.steer()` | Done | |
| `RpcClient.followUp()` | `RpcClient.follow_up()` | Done | |
| `RpcClient.abort()` | `RpcClient.abort()` | Done | |
| `RpcClient.newSession()` | `RpcClient.new_session()` | Done | |
| `RpcClient.getState()` | `RpcClient.get_state()` | Done | |
| `RpcClient.setModel()` | `RpcClient.set_model()` | Done | |
| `RpcClient.cycleModel()` | `RpcClient.cycle_model()` | Done | |
| `RpcClient.getAvailableModels()` | `RpcClient.get_available_models()` | Done | |
| `RpcClient.setThinkingLevel()` | `RpcClient.set_thinking_level()` | Done | |
| `RpcClient.cycleThinkingLevel()` | `RpcClient.cycle_thinking_level()` | Done | |
| `RpcClient.setSteeringMode()` | `RpcClient.set_steering_mode()` | Done | |
| `RpcClient.setFollowUpMode()` | `RpcClient.set_follow_up_mode()` | Done | |
| `RpcClient.compact()` | `RpcClient.compact()` | Done | |
| `RpcClient.setAutoCompaction()` | `RpcClient.set_auto_compaction()` | Done | |
| `RpcClient.setAutoRetry()` | `RpcClient.set_auto_retry()` | Done | |
| `RpcClient.abortRetry()` | `RpcClient.abort_retry()` | Done | |
| `RpcClient.bash()` | `RpcClient.bash()` | Done | |
| `RpcClient.abortBash()` | `RpcClient.abort_bash()` | Done | |
| `RpcClient.getSessionStats()` | `RpcClient.get_session_stats()` | Done | |
| `RpcClient.exportHtml()` | `RpcClient.export_html()` | Done | |
| `RpcClient.switchSession()` | `RpcClient.switch_session()` | Done | |
| `RpcClient.fork()` | `RpcClient.fork()` | Done | |
| `RpcClient.getForkMessages()` | `RpcClient.get_fork_messages()` | Done | |
| `RpcClient.getLastAssistantText()` | `RpcClient.get_last_assistant_text()` | Done | |
| `RpcClient.setSessionName()` | `RpcClient.set_session_name()` | Done | |
| `RpcClient.getMessages()` | `RpcClient.get_messages()` | Done | |
| `RpcClient.getCommands()` | `RpcClient.get_commands()` | Done | |
| `RpcClient.waitForIdle()` | `RpcClient.wait_for_idle()` | Done | `timeout` in seconds (TS: ms) |
| `RpcClient.collectEvents()` | `RpcClient.collect_events()` | Done | |
| `RpcClient.promptAndWait()` | `RpcClient.prompt_and_wait()` | Done | |
| `runRpcMode()` | `run_rpc_mode()` | Done | Uses `AgentSessionProtocol` (stub Protocol) |
| `getShellConfig()` | `get_shell_config()` | Done | Returns `dict` with `shell` and `args` |
| `getShellEnv()` | `get_shell_env()` | Done | Prepends pi bin dir to PATH |
| `sanitizeBinaryOutput()` | `sanitize_binary_output()` | Done | Regex-based Unicode stripping |
| `killProcessTree()` | `kill_process_tree()` | Done | POSIX `killpg`; fallback to `ps` + recursive |
| `GitSource` interface | `GitSource` dataclass | Done | |
| `parseGitUrl()` | `parse_git_url()` | Done | Pure Python, no external deps |
| `copyToClipboard()` | `copy_to_clipboard()` | Done | OSC 52 + wl-copy / xclip / pbcopy |
| `ClipboardImage` interface | `ClipboardImage` dataclass | Done | |
| `isWaylandSession()` | `is_wayland_session()` | Done | |
| `extensionForImageMimeType()` | `extension_for_image_mime_type()` | Done | |
| `readClipboardImage()` | `read_clipboard_image()` | Done | Linux/macOS only |
| `convertToPng()` | `convert_to_png()` | Done | Uses Pillow |
| `ImageResizeOptions` interface | `ImageResizeOptions` dataclass | Done | |
| `ResizedImage` interface | `ResizedImage` dataclass | Done | |
| `resizeImage()` | `resize_image()` | Done | Uses Pillow |
| `formatDimensionNote()` | `format_dimension_note()` | Done | |
| `getToolPath()` | `get_tool_path()` | Done | |
| `ensureTool()` | `ensure_tool()` | Done | `async`; uses `httpx` |
| `ToolHtmlRenderer` interface | `ToolHtmlRenderer` Protocol | Done | `@runtime_checkable` |
| `ExportOptions` interface | `ExportOptions` dataclass | Done | |
| `exportSessionToHtml()` | `export_session_to_html()` | Done | Uses `SessionManagerProtocol` stub |
| `exportFromFile()` | `export_from_file()` | Done | |
