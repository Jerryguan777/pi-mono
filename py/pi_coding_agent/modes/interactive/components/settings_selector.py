"""Settings selector component using SettingsList for keyboard-driven settings management."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pi_coding_agent.modes.interactive.components._theme import get_select_list_theme, get_settings_list_theme, theme
from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder
from pi_tui.components.select_list import SelectItem, SelectList
from pi_tui.components.settings_list import SettingItem, SettingsList, SettingsListOptions
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.tui import Container

_THINKING_DESCRIPTIONS: dict[str, str] = {
    "off": "No reasoning",
    "minimal": "Very brief reasoning (~1k tokens)",
    "low": "Light reasoning (~2k tokens)",
    "medium": "Moderate reasoning (~8k tokens)",
    "high": "Deep reasoning (~16k tokens)",
    "xhigh": "Maximum reasoning (~32k tokens)",
}


@dataclass
class SettingsConfig:
    auto_compact: bool = False
    show_images: bool = True
    auto_resize_images: bool = True
    block_images: bool = False
    enable_skill_commands: bool = True
    steering_mode: str = "one-at-a-time"
    follow_up_mode: str = "one-at-a-time"
    transport: str = "auto"
    thinking_level: str = "off"
    available_thinking_levels: list[str] = field(default_factory=lambda: ["off"])
    current_theme: str = "default"
    available_themes: list[str] = field(default_factory=lambda: ["default"])
    hide_thinking_block: bool = False
    collapse_changelog: bool = False
    double_escape_action: str = "none"
    show_hardware_cursor: bool = False
    editor_padding_x: int = 0
    autocomplete_max_visible: int = 10
    quiet_startup: bool = False
    clear_on_shrink: bool = False


@dataclass
class SettingsCallbacks:
    on_auto_compact_change: Callable[[bool], None] = field(default=lambda _: None)
    on_show_images_change: Callable[[bool], None] = field(default=lambda _: None)
    on_auto_resize_images_change: Callable[[bool], None] = field(default=lambda _: None)
    on_block_images_change: Callable[[bool], None] = field(default=lambda _: None)
    on_enable_skill_commands_change: Callable[[bool], None] = field(default=lambda _: None)
    on_steering_mode_change: Callable[[str], None] = field(default=lambda _: None)
    on_follow_up_mode_change: Callable[[str], None] = field(default=lambda _: None)
    on_transport_change: Callable[[str], None] = field(default=lambda _: None)
    on_thinking_level_change: Callable[[str], None] = field(default=lambda _: None)
    on_theme_change: Callable[[str], None] = field(default=lambda _: None)
    on_theme_preview: Callable[[str], None] | None = None
    on_hide_thinking_block_change: Callable[[bool], None] = field(default=lambda _: None)
    on_collapse_changelog_change: Callable[[bool], None] = field(default=lambda _: None)
    on_double_escape_action_change: Callable[[str], None] = field(default=lambda _: None)
    on_show_hardware_cursor_change: Callable[[bool], None] = field(default=lambda _: None)
    on_editor_padding_x_change: Callable[[int], None] = field(default=lambda _: None)
    on_autocomplete_max_visible_change: Callable[[int], None] = field(default=lambda _: None)
    on_quiet_startup_change: Callable[[bool], None] = field(default=lambda _: None)
    on_clear_on_shrink_change: Callable[[bool], None] = field(default=lambda _: None)
    on_cancel: Callable[[], None] = field(default=lambda: None)


class _SelectSubmenu(Container):
    def __init__(
        self,
        title: str,
        description: str,
        options: list[SelectItem],
        current_value: str,
        on_select: Callable[[str], None],
        on_cancel: Callable[[], None],
        on_selection_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self.add_child(Text(theme.bold(theme.fg("accent", title)), 0, 0))
        if description:
            self.add_child(Spacer(1))
            self.add_child(Text(theme.fg("muted", description), 0, 0))
        self.add_child(Spacer(1))

        self._select_list = SelectList(options, min(len(options), 10), get_select_list_theme())
        current_idx = next((i for i, o in enumerate(options) if o.value == current_value), -1)
        if current_idx >= 0:
            self._select_list.set_selected_index(current_idx)

        self._select_list.on_select = lambda item: on_select(item.value)
        self._select_list.on_cancel = on_cancel
        if on_selection_change:
            self._select_list.on_selection_change = lambda item: on_selection_change(item.value)

        self.add_child(self._select_list)
        self.add_child(Spacer(1))
        self.add_child(Text(theme.fg("dim", "  Enter to select \u00b7 Esc to go back"), 0, 0))

    def handle_input(self, data: str) -> None:
        self._select_list.handle_input(data)


def _make_thinking_submenu(
    cv: str, done: Callable[[str | None], None], config: SettingsConfig, callbacks: SettingsCallbacks
) -> _SelectSubmenu:
    def on_sel(v: str) -> None:
        callbacks.on_thinking_level_change(v)
        done(v)

    items = [
        SelectItem(value=lv, label=lv, description=_THINKING_DESCRIPTIONS.get(lv, ""))
        for lv in config.available_thinking_levels
    ]
    desc = "Select reasoning depth for thinking-capable models"
    return _SelectSubmenu("Thinking Level", desc, items, cv, on_sel, lambda: done(None))


def _make_theme_submenu(
    cv: str, done: Callable[[str | None], None], config: SettingsConfig, callbacks: SettingsCallbacks
) -> _SelectSubmenu:
    def on_sel(v: str) -> None:
        callbacks.on_theme_change(v)
        done(v)

    def on_cancel() -> None:
        if callbacks.on_theme_preview:
            callbacks.on_theme_preview(cv)
        done(None)

    def on_preview(v: str) -> None:
        if callbacks.on_theme_preview:
            callbacks.on_theme_preview(v)

    items = [SelectItem(value=t, label=t) for t in config.available_themes]
    return _SelectSubmenu("Theme", "Select color theme", items, cv, on_sel, on_cancel, on_preview)


class SettingsSelectorComponent(Container):
    """Main settings selector using SettingsList with keyboard navigation and submenus."""

    def __init__(self, config: SettingsConfig, callbacks: SettingsCallbacks) -> None:
        super().__init__()

        items: list[SettingItem] = [
            SettingItem(
                id="autocompact",
                label="Auto-compact",
                description="Automatically compact context when it gets too large",
                current_value="true" if config.auto_compact else "false",
                values=["true", "false"],
            ),
            SettingItem(
                id="steering-mode",
                label="Steering mode",
                description="Enter while streaming queues steering messages.",
                current_value=config.steering_mode,
                values=["one-at-a-time", "all"],
            ),
            SettingItem(
                id="follow-up-mode",
                label="Follow-up mode",
                description="Alt+Enter queues follow-up messages until agent stops.",
                current_value=config.follow_up_mode,
                values=["one-at-a-time", "all"],
            ),
            SettingItem(
                id="transport",
                label="Transport",
                description="Preferred transport for providers that support multiple transports",
                current_value=config.transport,
                values=["sse", "websocket", "auto"],
            ),
            SettingItem(
                id="hide-thinking",
                label="Hide thinking",
                description="Hide thinking blocks in assistant responses",
                current_value="true" if config.hide_thinking_block else "false",
                values=["true", "false"],
            ),
            SettingItem(
                id="collapse-changelog",
                label="Collapse changelog",
                description="Show condensed changelog after updates",
                current_value="true" if config.collapse_changelog else "false",
                values=["true", "false"],
            ),
            SettingItem(
                id="quiet-startup",
                label="Quiet startup",
                description="Disable verbose printing at startup",
                current_value="true" if config.quiet_startup else "false",
                values=["true", "false"],
            ),
            SettingItem(
                id="double-escape-action",
                label="Double-escape action",
                description="Action when pressing Escape twice with empty editor",
                current_value=config.double_escape_action,
                values=["tree", "fork", "none"],
            ),
            SettingItem(
                id="thinking",
                label="Thinking level",
                description="Reasoning depth for thinking-capable models",
                current_value=config.thinking_level,
                submenu=lambda cv, done: _make_thinking_submenu(cv, done, config, callbacks),
            ),
            SettingItem(
                id="theme",
                label="Theme",
                description="Color theme for the interface",
                current_value=config.current_theme,
                submenu=lambda cv, done: _make_theme_submenu(cv, done, config, callbacks),
            ),
        ]

        # Image-related items
        try:
            from pi_tui.capabilities import get_capabilities  # type: ignore[import-untyped]

            supports_images = get_capabilities().images
        except Exception:
            supports_images = False

        insert_idx = 1
        if supports_images:
            items.insert(
                insert_idx,
                SettingItem(
                    id="show-images",
                    label="Show images",
                    description="Render images inline in terminal",
                    current_value="true" if config.show_images else "false",
                    values=["true", "false"],
                ),
            )
            insert_idx += 1

        items.insert(
            insert_idx,
            SettingItem(
                id="auto-resize-images",
                label="Auto-resize images",
                description="Resize large images to 2000x2000 max for better model compatibility",
                current_value="true" if config.auto_resize_images else "false",
                values=["true", "false"],
            ),
        )
        insert_idx += 1

        items.insert(
            insert_idx,
            SettingItem(
                id="block-images",
                label="Block images",
                description="Prevent images from being sent to LLM providers",
                current_value="true" if config.block_images else "false",
                values=["true", "false"],
            ),
        )
        insert_idx += 1

        items.insert(
            insert_idx,
            SettingItem(
                id="skill-commands",
                label="Skill commands",
                description="Register skills as /skill:name commands",
                current_value="true" if config.enable_skill_commands else "false",
                values=["true", "false"],
            ),
        )
        insert_idx += 1

        items.insert(
            insert_idx,
            SettingItem(
                id="show-hardware-cursor",
                label="Show hardware cursor",
                description="Show the terminal cursor while still positioning it for IME support",
                current_value="true" if config.show_hardware_cursor else "false",
                values=["true", "false"],
            ),
        )
        insert_idx += 1

        items.insert(
            insert_idx,
            SettingItem(
                id="editor-padding",
                label="Editor padding",
                description="Horizontal padding for input editor (0-3)",
                current_value=str(config.editor_padding_x),
                values=["0", "1", "2", "3"],
            ),
        )
        insert_idx += 1

        items.insert(
            insert_idx,
            SettingItem(
                id="autocomplete-max-visible",
                label="Autocomplete max items",
                description="Max visible items in autocomplete dropdown (3-20)",
                current_value=str(config.autocomplete_max_visible),
                values=["3", "5", "7", "10", "15", "20"],
            ),
        )
        insert_idx += 1

        items.insert(
            insert_idx,
            SettingItem(
                id="clear-on-shrink",
                label="Clear on shrink",
                description="Clear empty rows when content shrinks (may cause flicker)",
                current_value="true" if config.clear_on_shrink else "false",
                values=["true", "false"],
            ),
        )

        def on_change(id_: str, new_value: str) -> None:
            switch: dict[str, Callable[[], None]] = {
                "autocompact": lambda: callbacks.on_auto_compact_change(new_value == "true"),
                "show-images": lambda: callbacks.on_show_images_change(new_value == "true"),
                "auto-resize-images": lambda: callbacks.on_auto_resize_images_change(new_value == "true"),
                "block-images": lambda: callbacks.on_block_images_change(new_value == "true"),
                "skill-commands": lambda: callbacks.on_enable_skill_commands_change(new_value == "true"),
                "steering-mode": lambda: callbacks.on_steering_mode_change(new_value),
                "follow-up-mode": lambda: callbacks.on_follow_up_mode_change(new_value),
                "transport": lambda: callbacks.on_transport_change(new_value),
                "hide-thinking": lambda: callbacks.on_hide_thinking_block_change(new_value == "true"),
                "collapse-changelog": lambda: callbacks.on_collapse_changelog_change(new_value == "true"),
                "quiet-startup": lambda: callbacks.on_quiet_startup_change(new_value == "true"),
                "double-escape-action": lambda: callbacks.on_double_escape_action_change(new_value),
                "show-hardware-cursor": lambda: callbacks.on_show_hardware_cursor_change(new_value == "true"),
                "editor-padding": lambda: callbacks.on_editor_padding_x_change(int(new_value)),
                "autocomplete-max-visible": lambda: callbacks.on_autocomplete_max_visible_change(int(new_value)),
                "clear-on-shrink": lambda: callbacks.on_clear_on_shrink_change(new_value == "true"),
            }
            fn = switch.get(id_)
            if fn:
                fn()

        self.add_child(DynamicBorder())
        self._settings_list = SettingsList(
            items,
            10,
            get_settings_list_theme(),
            on_change,
            callbacks.on_cancel,
            SettingsListOptions(enable_search=True),
        )
        self.add_child(self._settings_list)
        self.add_child(DynamicBorder())

    def get_settings_list(self) -> SettingsList:
        return self._settings_list
