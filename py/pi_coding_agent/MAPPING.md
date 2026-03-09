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
