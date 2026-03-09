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
