"""Interactive mode UI components for pi_coding_agent."""

from __future__ import annotations

from pi_coding_agent.modes.interactive.components._theme import (
    Theme,
    get_available_themes,
    get_editor_theme,
    get_language_from_path,
    get_markdown_theme,
    get_select_list_theme,
    get_settings_list_theme,
    highlight_code,
    theme,
)
from pi_coding_agent.modes.interactive.components.armin import ArminComponent
from pi_coding_agent.modes.interactive.components.assistant_message import AssistantMessageComponent
from pi_coding_agent.modes.interactive.components.bash_execution import BashExecutionComponent
from pi_coding_agent.modes.interactive.components.bordered_loader import BorderedLoader
from pi_coding_agent.modes.interactive.components.branch_summary_message import BranchSummaryMessageComponent
from pi_coding_agent.modes.interactive.components.compaction_summary_message import CompactionSummaryMessageComponent
from pi_coding_agent.modes.interactive.components.config_selector import (
    ConfigSelectorComponent,
    PathMetadata,
    ResolvedPaths,
    ResolvedResource,
    ResourceGroup,
    ResourceItem,
    ResourceSubgroup,
    build_groups,
)
from pi_coding_agent.modes.interactive.components.countdown_timer import CountdownTimer
from pi_coding_agent.modes.interactive.components.custom_editor import CustomEditor
from pi_coding_agent.modes.interactive.components.custom_message import CustomMessageComponent
from pi_coding_agent.modes.interactive.components.daxnuts import DaxnutsComponent
from pi_coding_agent.modes.interactive.components.diff import render_diff
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_coding_agent.modes.interactive.components.extension_editor import ExtensionEditorComponent
from pi_coding_agent.modes.interactive.components.extension_input import ExtensionInputComponent
from pi_coding_agent.modes.interactive.components.extension_selector import ExtensionSelectorComponent
from pi_coding_agent.modes.interactive.components.footer import FooterComponent
from pi_coding_agent.modes.interactive.components.keybinding_hints import (
    app_key,
    app_key_hint,
    editor_key,
    key_hint,
    raw_key_hint,
)
from pi_coding_agent.modes.interactive.components.login_dialog import LoginDialogComponent
from pi_coding_agent.modes.interactive.components.model_selector import ModelSelectorComponent
from pi_coding_agent.modes.interactive.components.oauth_selector import OAuthSelectorComponent
from pi_coding_agent.modes.interactive.components.scoped_models_selector import (
    ModelsCallbacks,
    ModelsConfig,
    ScopedModelsSelectorComponent,
)
from pi_coding_agent.modes.interactive.components.session_selector import SessionSelectorComponent
from pi_coding_agent.modes.interactive.components.session_selector_search import (
    MatchResult,
    NameFilter,
    ParsedSearchQuery,
    SortMode,
    filter_and_sort_sessions,
    has_session_name,
    match_session,
    parse_search_query,
)
from pi_coding_agent.modes.interactive.components.settings_selector import (
    SettingsCallbacks,
    SettingsConfig,
    SettingsSelectorComponent,
)
from pi_coding_agent.modes.interactive.components.show_images_selector import ShowImagesSelectorComponent
from pi_coding_agent.modes.interactive.components.skill_invocation_message import SkillInvocationMessageComponent
from pi_coding_agent.modes.interactive.components.theme_selector import ThemeSelectorComponent
from pi_coding_agent.modes.interactive.components.thinking_selector import ThinkingSelectorComponent
from pi_coding_agent.modes.interactive.components.tool_execution import ToolExecutionComponent
from pi_coding_agent.modes.interactive.components.tree_selector import TreeSelectorComponent
from pi_coding_agent.modes.interactive.components.user_message import UserMessageComponent
from pi_coding_agent.modes.interactive.components.user_message_selector import (
    UserMessageItem,
    UserMessageSelectorComponent,
)
from pi_coding_agent.modes.interactive.components.visual_truncate import (
    VisualTruncateResult,
    truncate_to_visual_lines,
)

__all__ = [
    "ArminComponent",
    "AssistantMessageComponent",
    "BashExecutionComponent",
    "BorderedLoader",
    "BranchSummaryMessageComponent",
    "CompactionSummaryMessageComponent",
    "ConfigSelectorComponent",
    "CountdownTimer",
    "CustomEditor",
    "CustomMessageComponent",
    "DaxnutsComponent",
    "DynamicBorder",
    "ExtensionEditorComponent",
    "ExtensionInputComponent",
    "ExtensionSelectorComponent",
    "FooterComponent",
    "LoginDialogComponent",
    "MatchResult",
    "ModelSelectorComponent",
    "ModelsCallbacks",
    "ModelsConfig",
    "NameFilter",
    "OAuthSelectorComponent",
    "ParsedSearchQuery",
    "PathMetadata",
    "ResolvedPaths",
    "ResolvedResource",
    "ResourceGroup",
    "ResourceItem",
    "ResourceSubgroup",
    "ScopedModelsSelectorComponent",
    "SessionSelectorComponent",
    "SettingsCallbacks",
    "SettingsConfig",
    "SettingsSelectorComponent",
    "ShowImagesSelectorComponent",
    "SkillInvocationMessageComponent",
    "SortMode",
    "Theme",
    "ThemeSelectorComponent",
    "ThinkingSelectorComponent",
    "ToolExecutionComponent",
    "TreeSelectorComponent",
    "UserMessageComponent",
    "UserMessageItem",
    "UserMessageSelectorComponent",
    "VisualTruncateResult",
    "app_key",
    "app_key_hint",
    "build_groups",
    "editor_key",
    "filter_and_sort_sessions",
    "get_available_themes",
    "get_editor_theme",
    "get_language_from_path",
    "get_markdown_theme",
    "get_select_list_theme",
    "get_settings_list_theme",
    "has_session_name",
    "highlight_code",
    "key_hint",
    "match_session",
    "parse_search_query",
    "raw_key_hint",
    "render_diff",
    "theme",
    "truncate_to_visual_lines",
]
