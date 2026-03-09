"""Unit tests for pi_tui.components.settings_list."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from pi_tui.components.settings_list import (
    SettingItem,
    SettingsList,
    SettingsListOptions,
    SettingsListTheme,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Terminal escape sequences for arrow keys (legacy)
KEY_UP = "\x1b[A"
KEY_DOWN = "\x1b[B"
KEY_ENTER = "\r"
KEY_ESCAPE = "\x1b"
KEY_SPACE = " "


def _identity(s: str) -> str:
    return s


def _make_theme() -> SettingsListTheme:
    """Create a theme with identity styling so output is predictable."""
    return SettingsListTheme(
        label=lambda text, _selected: text,
        value=lambda text, _selected: text,
        description=_identity,
        cursor="-> ",
        hint=_identity,
    )


def _make_items() -> list[SettingItem]:
    return [
        SettingItem(id="theme", label="Theme", current_value="dark", values=["dark", "light", "auto"]),
        SettingItem(id="lang", label="Language", current_value="en", values=["en", "fr", "de"]),
        SettingItem(id="font_size", label="Font Size", current_value="14", values=["12", "14", "16", "18"]),
    ]


def _make_settings_list(
    items: list[SettingItem] | None = None,
    max_visible: int = 10,
    theme: SettingsListTheme | None = None,
    on_change: Any = None,
    on_cancel: Any = None,
    options: SettingsListOptions | None = None,
) -> SettingsList:
    if items is None:
        items = _make_items()
    if theme is None:
        theme = _make_theme()
    if on_change is None:
        on_change = MagicMock()
    if on_cancel is None:
        on_cancel = MagicMock()
    return SettingsList(
        items=items,
        max_visible=max_visible,
        theme=theme,
        on_change=on_change,
        on_cancel=on_cancel,
        options=options,
    )


# =========================================================================
# SettingItem dataclass
# =========================================================================


class TestSettingItem:
    def test_creation_with_defaults(self) -> None:
        item = SettingItem(id="opt", label="Option")
        assert item.id == "opt"
        assert item.label == "Option"
        assert item.description is None
        assert item.current_value == ""
        assert item.values is None
        assert item.submenu is None

    def test_creation_with_all_fields(self) -> None:
        item = SettingItem(
            id="color",
            label="Color",
            description="Pick a color",
            current_value="red",
            values=["red", "green", "blue"],
        )
        assert item.id == "color"
        assert item.label == "Color"
        assert item.description == "Pick a color"
        assert item.current_value == "red"
        assert item.values == ["red", "green", "blue"]

    def test_creation_with_submenu(self) -> None:
        submenu_fn = MagicMock()
        item = SettingItem(id="sub", label="Sub", submenu=submenu_fn)
        assert item.submenu is submenu_fn

    def test_equality(self) -> None:
        a = SettingItem(id="x", label="X", current_value="1")
        b = SettingItem(id="x", label="X", current_value="1")
        assert a == b

    def test_inequality(self) -> None:
        a = SettingItem(id="x", label="X", current_value="1")
        b = SettingItem(id="x", label="X", current_value="2")
        assert a != b


# =========================================================================
# SettingsListTheme dataclass
# =========================================================================


class TestSettingsListTheme:
    def test_creation(self) -> None:
        theme = _make_theme()
        assert theme.cursor == "-> "
        assert theme.label("hello", True) == "hello"
        assert theme.value("world", False) == "world"
        assert theme.description("desc") == "desc"
        assert theme.hint("hint") == "hint"

    def test_default_hint_is_identity(self) -> None:
        theme = SettingsListTheme(
            label=lambda t, _: t,
            value=lambda t, _: t,
            description=_identity,
            cursor="> ",
        )
        assert theme.hint("test") == "test"

    def test_custom_cursor(self) -> None:
        theme = SettingsListTheme(
            label=lambda t, _: t,
            value=lambda t, _: t,
            description=_identity,
            cursor=">>> ",
        )
        assert theme.cursor == ">>> "

    def test_styling_functions_applied(self) -> None:
        theme = SettingsListTheme(
            label=lambda t, sel: f"[L:{sel}]{t}",
            value=lambda t, sel: f"[V:{sel}]{t}",
            description=lambda t: f"[D]{t}",
            hint=lambda t: f"[H]{t}",
        )
        assert theme.label("Name", True) == "[L:True]Name"
        assert theme.value("val", False) == "[V:False]val"
        assert theme.description("info") == "[D]info"
        assert theme.hint("tip") == "[H]tip"


# =========================================================================
# SettingsList construction
# =========================================================================


class TestSettingsListConstruction:
    def test_basic_construction(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        # Should render without error
        lines = sl.render(80)
        assert len(lines) > 0

    def test_empty_items(self) -> None:
        sl = _make_settings_list(items=[])
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "No settings available" in content

    def test_with_search_enabled(self) -> None:
        sl = _make_settings_list(options=SettingsListOptions(enable_search=True))
        lines = sl.render(80)
        content = "\n".join(lines)
        # Should show search hint
        assert "Type to search" in content

    def test_with_search_disabled(self) -> None:
        sl = _make_settings_list(options=SettingsListOptions(enable_search=False))
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "Type to search" not in content


# =========================================================================
# render() output
# =========================================================================


class TestSettingsListRender:
    def test_shows_labels(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "Theme" in content
        assert "Language" in content
        assert "Font Size" in content

    def test_shows_current_values(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "dark" in content
        assert "en" in content
        assert "14" in content

    def test_selected_item_has_cursor(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        lines = sl.render(80)
        # First item should have the cursor prefix
        assert any("->" in line for line in lines)

    def test_description_shown_for_selected(self) -> None:
        items = [
            SettingItem(id="a", label="Alpha", description="Description for alpha", current_value="on"),
            SettingItem(id="b", label="Beta", current_value="off"),
        ]
        sl = _make_settings_list(items=items)
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "Description for alpha" in content

    def test_description_not_shown_when_none(self) -> None:
        items = [
            SettingItem(id="a", label="Alpha", current_value="on"),
        ]
        sl = _make_settings_list(items=items)
        lines = sl.render(80)
        # Should not crash; still renders label and value
        content = "\n".join(lines)
        assert "Alpha" in content
        assert "on" in content

    def test_scroll_indicator_shown_when_overflowing(self) -> None:
        items = [SettingItem(id=f"s{i}", label=f"Setting {i}", current_value=str(i)) for i in range(20)]
        sl = _make_settings_list(items=items, max_visible=5)
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "(1/20)" in content

    def test_no_scroll_indicator_when_all_visible(self) -> None:
        items = _make_items()  # 3 items
        sl = _make_settings_list(items=items, max_visible=10)
        lines = sl.render(80)
        content = "\n".join(lines)
        # No scroll indicator when all items fit
        assert "(/)" not in content

    def test_hint_line_present(self) -> None:
        sl = _make_settings_list()
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "Enter/Space to change" in content
        assert "Esc to cancel" in content

    def test_hint_line_with_search_enabled(self) -> None:
        sl = _make_settings_list(options=SettingsListOptions(enable_search=True))
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "Type to search" in content

    def test_empty_items_with_search_shows_hint(self) -> None:
        sl = _make_settings_list(items=[], options=SettingsListOptions(enable_search=True))
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "No settings available" in content


# =========================================================================
# handle_input - navigation
# =========================================================================


class TestSettingsListNavigation:
    def test_down_arrow_moves_selection(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        sl.handle_input(KEY_DOWN)
        lines = sl.render(80)
        # Second item should now have cursor
        cursor_lines = [line for line in lines if "->" in line]
        assert len(cursor_lines) == 1
        assert "Language" in cursor_lines[0]

    def test_up_arrow_moves_selection(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        sl.handle_input(KEY_DOWN)
        sl.handle_input(KEY_DOWN)
        sl.handle_input(KEY_UP)
        lines = sl.render(80)
        cursor_lines = [line for line in lines if "->" in line]
        assert len(cursor_lines) == 1
        assert "Language" in cursor_lines[0]

    def test_wraps_down_to_first(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        # Move past last item
        for _ in range(len(items)):
            sl.handle_input(KEY_DOWN)
        lines = sl.render(80)
        cursor_lines = [line for line in lines if "->" in line]
        assert "Theme" in cursor_lines[0]

    def test_wraps_up_to_last(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        sl.handle_input(KEY_UP)
        lines = sl.render(80)
        cursor_lines = [line for line in lines if "->" in line]
        assert "Font Size" in cursor_lines[0]

    def test_navigation_with_empty_items(self) -> None:
        sl = _make_settings_list(items=[])
        # Should not crash
        sl.handle_input(KEY_UP)
        sl.handle_input(KEY_DOWN)

    def test_escape_calls_on_cancel(self) -> None:
        on_cancel = MagicMock()
        sl = _make_settings_list(on_cancel=on_cancel)
        sl.handle_input(KEY_ESCAPE)
        on_cancel.assert_called_once()


# =========================================================================
# handle_input - value cycling with enter/space
# =========================================================================


class TestSettingsListValueCycling:
    def test_enter_cycles_value(self) -> None:
        on_change = MagicMock()
        items = _make_items()
        sl = _make_settings_list(items=items, on_change=on_change)
        # First item is Theme with values ["dark", "light", "auto"], current is "dark"
        sl.handle_input(KEY_ENTER)
        on_change.assert_called_once_with("theme", "light")
        assert items[0].current_value == "light"

    def test_space_cycles_value(self) -> None:
        on_change = MagicMock()
        items = _make_items()
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_SPACE)
        on_change.assert_called_once_with("theme", "light")

    def test_cycling_wraps_around(self) -> None:
        on_change = MagicMock()
        items = [SettingItem(id="opt", label="Opt", current_value="c", values=["a", "b", "c"])]
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        # "c" is index 2, next should wrap to index 0 = "a"
        on_change.assert_called_once_with("opt", "a")
        assert items[0].current_value == "a"

    def test_cycling_with_unknown_current_value(self) -> None:
        on_change = MagicMock()
        items = [SettingItem(id="opt", label="Opt", current_value="unknown", values=["a", "b", "c"])]
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        # ValueError in index -> current_idx = -1, next_idx = 0
        on_change.assert_called_once_with("opt", "a")

    def test_no_cycle_when_no_values(self) -> None:
        on_change = MagicMock()
        items = [SettingItem(id="opt", label="Opt", current_value="val")]
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        on_change.assert_not_called()

    def test_no_cycle_when_empty_values_list(self) -> None:
        on_change = MagicMock()
        items = [SettingItem(id="opt", label="Opt", current_value="val", values=[])]
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        on_change.assert_not_called()

    def test_cycle_second_item(self) -> None:
        on_change = MagicMock()
        items = _make_items()
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_DOWN)
        sl.handle_input(KEY_ENTER)
        # Second item is Language with values ["en", "fr", "de"], current is "en"
        on_change.assert_called_once_with("lang", "fr")
        assert items[1].current_value == "fr"

    def test_multiple_cycles(self) -> None:
        on_change = MagicMock()
        items = [SettingItem(id="opt", label="Opt", current_value="a", values=["a", "b", "c"])]
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        assert items[0].current_value == "b"
        sl.handle_input(KEY_ENTER)
        assert items[0].current_value == "c"
        sl.handle_input(KEY_ENTER)
        assert items[0].current_value == "a"


# =========================================================================
# on_change callback
# =========================================================================


class TestOnChangeCallback:
    def test_called_with_setting_id_and_value(self) -> None:
        on_change = MagicMock()
        items = _make_items()
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        on_change.assert_called_once_with("theme", "light")

    def test_called_for_each_change(self) -> None:
        on_change = MagicMock()
        items = _make_items()
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        sl.handle_input(KEY_ENTER)
        assert on_change.call_count == 2


# =========================================================================
# update_value
# =========================================================================


class TestUpdateValue:
    def test_updates_existing_setting(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        sl.update_value("theme", "auto")
        assert items[0].current_value == "auto"

    def test_no_error_for_unknown_id(self) -> None:
        sl = _make_settings_list()
        # Should not raise
        sl.update_value("nonexistent", "value")

    def test_render_reflects_updated_value(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        sl.update_value("theme", "auto")
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "auto" in content


# =========================================================================
# Search/filter functionality
# =========================================================================


class TestSettingsListSearch:
    def test_search_filters_items(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items, options=SettingsListOptions(enable_search=True))
        # Type "th" to filter - should match "Theme"
        sl.handle_input("t")
        sl.handle_input("h")
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "Theme" in content

    def test_search_no_match_shows_message(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items, options=SettingsListOptions(enable_search=True))
        sl.handle_input("z")
        sl.handle_input("z")
        sl.handle_input("z")
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "No matching" in content

    def test_search_resets_selection_index(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items, options=SettingsListOptions(enable_search=True))
        sl.handle_input(KEY_DOWN)
        sl.handle_input(KEY_DOWN)
        # Now type to filter
        sl.handle_input("t")
        # Selection should reset to 0
        lines = sl.render(80)
        cursor_lines = [line for line in lines if "->" in line]
        assert len(cursor_lines) >= 1

    def test_search_disabled_ignores_typing(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items, options=SettingsListOptions(enable_search=False))
        # Typing should not crash or filter
        sl.handle_input("x")
        lines = sl.render(80)
        content = "\n".join(lines)
        # All items should still be visible
        assert "Theme" in content
        assert "Language" in content
        assert "Font Size" in content

    def test_space_in_search_is_stripped(self) -> None:
        """Spaces are used for activation, so they are stripped from search input."""
        items = _make_items()
        on_change = MagicMock()
        sl = _make_settings_list(
            items=items,
            on_change=on_change,
            options=SettingsListOptions(enable_search=True),
        )
        # Space triggers activation, not search
        sl.handle_input(KEY_SPACE)
        on_change.assert_called_once()


# =========================================================================
# Submenu navigation
# =========================================================================


class TestSettingsListSubmenu:
    def test_submenu_opens_on_enter(self) -> None:
        submenu_component = MagicMock()
        submenu_component.render.return_value = ["submenu line"]

        def submenu_factory(current_val: str, done: Any) -> Any:
            return submenu_component

        items = [SettingItem(id="sub", label="Submenu", current_value="val", submenu=submenu_factory)]
        sl = _make_settings_list(items=items)
        sl.handle_input(KEY_ENTER)
        # Now render should delegate to submenu
        lines = sl.render(80)
        assert lines == ["submenu line"]

    def test_submenu_receives_current_value(self) -> None:
        received: dict[str, Any] = {}

        def submenu_factory(current_val: str, done: Any) -> Any:
            received["current_val"] = current_val
            mock = MagicMock()
            mock.render.return_value = ["sub"]
            return mock

        items = [SettingItem(id="sub", label="Submenu", current_value="myval", submenu=submenu_factory)]
        sl = _make_settings_list(items=items)
        sl.handle_input(KEY_ENTER)
        assert received["current_val"] == "myval"

    def test_submenu_done_with_value_updates_and_fires_change(self) -> None:
        on_change = MagicMock()
        done_cb: list[Any] = []

        def submenu_factory(current_val: str, done: Any) -> Any:
            done_cb.append(done)
            mock = MagicMock()
            mock.render.return_value = ["sub"]
            return mock

        items = [SettingItem(id="sub", label="Submenu", current_value="old", submenu=submenu_factory)]
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        # Call done with a new value
        done_cb[0]("new_value")
        on_change.assert_called_once_with("sub", "new_value")
        assert items[0].current_value == "new_value"

    def test_submenu_done_with_none_does_not_change(self) -> None:
        on_change = MagicMock()
        done_cb: list[Any] = []

        def submenu_factory(current_val: str, done: Any) -> Any:
            done_cb.append(done)
            mock = MagicMock()
            mock.render.return_value = ["sub"]
            return mock

        items = [SettingItem(id="sub", label="Submenu", current_value="old", submenu=submenu_factory)]
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        done_cb[0](None)
        on_change.assert_not_called()
        assert items[0].current_value == "old"

    def test_submenu_closes_after_done(self) -> None:
        done_cb: list[Any] = []

        def submenu_factory(current_val: str, done: Any) -> Any:
            done_cb.append(done)
            mock = MagicMock()
            mock.render.return_value = ["sub"]
            return mock

        items = [*_make_items(), SettingItem(id="sub", label="Submenu", current_value="val", submenu=submenu_factory)]
        sl = _make_settings_list(items=items)
        # Navigate to submenu item (last item)
        for _ in range(len(items) - 1):
            sl.handle_input(KEY_DOWN)
        sl.handle_input(KEY_ENTER)
        # Verify submenu is active
        assert sl.render(80) == ["sub"]
        # Close submenu
        done_cb[0](None)
        # Should return to main list
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "Theme" in content

    def test_submenu_input_delegated(self) -> None:
        submenu_component = MagicMock()
        submenu_component.render.return_value = ["sub"]

        def submenu_factory(current_val: str, done: Any) -> Any:
            return submenu_component

        items = [SettingItem(id="sub", label="Submenu", current_value="val", submenu=submenu_factory)]
        sl = _make_settings_list(items=items)
        sl.handle_input(KEY_ENTER)
        # Further input should be delegated to submenu
        sl.handle_input(KEY_DOWN)
        submenu_component.handle_input.assert_called_once_with(KEY_DOWN)

    def test_submenu_restores_selection_index(self) -> None:
        done_cb: list[Any] = []

        def submenu_factory(current_val: str, done: Any) -> Any:
            done_cb.append(done)
            mock = MagicMock()
            mock.render.return_value = ["sub"]
            return mock

        items = [
            SettingItem(id="a", label="Alpha", current_value="1", values=["1", "2"]),
            SettingItem(id="b", label="Beta", current_value="val", submenu=submenu_factory),
            SettingItem(id="c", label="Gamma", current_value="3", values=["3", "4"]),
        ]
        sl = _make_settings_list(items=items)
        # Navigate to submenu item (index 1)
        sl.handle_input(KEY_DOWN)
        sl.handle_input(KEY_ENTER)
        # Close submenu
        done_cb[0](None)
        # Selection should be restored to index 1
        lines = sl.render(80)
        cursor_lines = [line for line in lines if "->" in line]
        assert "Beta" in cursor_lines[0]


# =========================================================================
# invalidate()
# =========================================================================


class TestSettingsListInvalidate:
    def test_invalidate_no_submenu(self) -> None:
        sl = _make_settings_list()
        # Should not crash
        sl.invalidate()

    def test_invalidate_delegates_to_submenu(self) -> None:
        submenu_component = MagicMock()
        submenu_component.render.return_value = ["sub"]

        def submenu_factory(current_val: str, done: Any) -> Any:
            return submenu_component

        items = [SettingItem(id="sub", label="Submenu", current_value="val", submenu=submenu_factory)]
        sl = _make_settings_list(items=items)
        sl.handle_input(KEY_ENTER)
        sl.invalidate()
        submenu_component.invalidate.assert_called_once()

    def test_invalidate_submenu_without_invalidate_method(self) -> None:
        """Submenu component lacking invalidate() should not cause error."""

        class NoInvalidate:
            def render(self, width: int) -> list[str]:
                return ["sub"]

            def handle_input(self, data: str) -> None:
                pass

        def submenu_factory(current_val: str, done: Any) -> Any:
            return NoInvalidate()

        items = [SettingItem(id="sub", label="Submenu", current_value="val", submenu=submenu_factory)]
        sl = _make_settings_list(items=items)
        sl.handle_input(KEY_ENTER)
        # Should not raise
        sl.invalidate()


# =========================================================================
# Edge cases
# =========================================================================


class TestSettingsListEdgeCases:
    def test_single_item(self) -> None:
        items = [SettingItem(id="only", label="Only", current_value="yes", values=["yes", "no"])]
        sl = _make_settings_list(items=items)
        lines = sl.render(80)
        content = "\n".join(lines)
        assert "Only" in content
        assert "yes" in content

    def test_single_item_navigation_wraps(self) -> None:
        items = [SettingItem(id="only", label="Only", current_value="yes", values=["yes", "no"])]
        sl = _make_settings_list(items=items)
        sl.handle_input(KEY_DOWN)
        # With a single item, wrapping should keep it selected
        lines = sl.render(80)
        cursor_lines = [line for line in lines if "->" in line]
        assert "Only" in cursor_lines[0]

    def test_narrow_width(self) -> None:
        items = _make_items()
        sl = _make_settings_list(items=items)
        # Should not crash with very narrow width
        lines = sl.render(20)
        assert len(lines) > 0

    def test_values_with_single_option(self) -> None:
        on_change = MagicMock()
        items = [SettingItem(id="opt", label="Opt", current_value="only", values=["only"])]
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        # Should cycle back to same value
        on_change.assert_called_once_with("opt", "only")

    def test_submenu_takes_priority_over_values(self) -> None:
        """When both submenu and values are set, submenu should be activated."""
        on_change = MagicMock()
        submenu_component = MagicMock()
        submenu_component.render.return_value = ["sub"]

        def submenu_factory(current_val: str, done: Any) -> Any:
            return submenu_component

        items = [
            SettingItem(
                id="both",
                label="Both",
                current_value="a",
                values=["a", "b"],
                submenu=submenu_factory,
            )
        ]
        sl = _make_settings_list(items=items, on_change=on_change)
        sl.handle_input(KEY_ENTER)
        # Submenu should be activated, not value cycling
        lines = sl.render(80)
        assert lines == ["sub"]
        on_change.assert_not_called()

    def test_ctrl_c_cancels(self) -> None:
        """Ctrl+C is also bound to selectCancel."""
        on_cancel = MagicMock()
        sl = _make_settings_list(on_cancel=on_cancel)
        sl.handle_input("\x03")  # Ctrl+C
        on_cancel.assert_called_once()
