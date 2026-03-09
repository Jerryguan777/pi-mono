"""Extended tests for pi_coding_agent.modes.interactive.theme — covers HTML export helpers,
registered themes, custom theme loading, TUI theme helpers, and environment-based detection.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pi_coding_agent.modes.interactive.theme import (
    _DATA_DIR,
    _detect_terminal_background,
    bg_ansi,
    detect_color_mode,
    get_available_themes,
    get_available_themes_with_paths,
    get_editor_theme,
    get_markdown_theme,
    get_resolved_theme_colors,
    get_select_list_theme,
    get_settings_list_theme,
    get_theme_by_name,
    get_theme_export_colors,
    init_theme,
    load_theme_from_path,
    on_theme_change,
    set_registered_themes,
    set_theme,
    set_theme_instance,
)

# ---------------------------------------------------------------------------
# detect_color_mode env-based branches
# ---------------------------------------------------------------------------


def test_detect_color_mode_truecolor_env() -> None:
    with patch.dict(os.environ, {"COLORTERM": "truecolor"}, clear=False):
        assert detect_color_mode() == "truecolor"


def test_detect_color_mode_24bit_env() -> None:
    with patch.dict(os.environ, {"COLORTERM": "24bit"}, clear=False):
        assert detect_color_mode() == "truecolor"


def test_detect_color_mode_wt_session() -> None:
    env = {"COLORTERM": "", "WT_SESSION": "1"}
    with patch.dict(os.environ, env, clear=False):
        assert detect_color_mode() == "truecolor"


def test_detect_color_mode_dumb_term() -> None:
    env = {"COLORTERM": "", "WT_SESSION": "", "TERM": "dumb"}
    with patch.dict(os.environ, env, clear=False):
        result = detect_color_mode()
        assert result == "256color"


def test_detect_color_mode_apple_terminal() -> None:
    env = {"COLORTERM": "", "WT_SESSION": "", "TERM": "xterm-256color", "TERM_PROGRAM": "Apple_Terminal"}
    with patch.dict(os.environ, env, clear=False):
        assert detect_color_mode() == "256color"


def test_detect_color_mode_generic_modern() -> None:
    env = {"COLORTERM": "", "WT_SESSION": "", "TERM": "xterm-256color", "TERM_PROGRAM": ""}
    with patch.dict(os.environ, env, clear=False):
        assert detect_color_mode() == "truecolor"


# ---------------------------------------------------------------------------
# bg_ansi
# ---------------------------------------------------------------------------


def test_bg_ansi_truecolor() -> None:
    result = bg_ansi("#00ff00", "truecolor")
    assert "\x1b[48;2;" in result
    assert "0;255;0" in result


def test_bg_ansi_256color() -> None:
    result = bg_ansi("#00ff00", "256color")
    assert "\x1b[48;5;" in result


def test_bg_ansi_int() -> None:
    result = bg_ansi(42, "256color")
    assert result == "\x1b[48;5;42m"


def test_bg_ansi_empty() -> None:
    result = bg_ansi("", "truecolor")
    assert result == "\x1b[49m"


# ---------------------------------------------------------------------------
# Theme validate / parse errors
# ---------------------------------------------------------------------------


def test_load_theme_from_path_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse theme"):
        load_theme_from_path(str(bad))


def test_load_theme_from_path_missing_colors(tmp_path: Path) -> None:
    incomplete = tmp_path / "inc.json"
    incomplete.write_text(json.dumps({"name": "inc", "colors": {"accent": "#fff"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required color tokens"):
        load_theme_from_path(str(incomplete))


# ---------------------------------------------------------------------------
# Custom themes directory integration
# ---------------------------------------------------------------------------


def test_get_available_themes_with_custom_dir(tmp_path: Path) -> None:
    # Create a custom theme file in a temp directory that mimics custom themes dir
    dark_data = json.loads((_DATA_DIR / "dark.json").read_text(encoding="utf-8"))
    custom_json = tmp_path / "mytheme.json"
    custom_json.write_text(json.dumps(dark_data), encoding="utf-8")

    with patch("pi_coding_agent.config.get_agent_dir", return_value=tmp_path):
        themes = get_available_themes()

    # mytheme should appear (custom_themes_dir = tmp_path / "themes" though)
    # Since we patched agent_dir, custom dir = tmp_path/themes, so mytheme won't be there
    # But built-ins should still appear
    assert "dark" in themes
    assert "light" in themes


def test_get_available_themes_with_paths_custom(tmp_path: Path) -> None:
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    dark_data = json.loads((_DATA_DIR / "dark.json").read_text(encoding="utf-8"))
    custom_json = themes_dir / "mycustom.json"
    custom_json.write_text(json.dumps(dark_data), encoding="utf-8")

    with patch("pi_coding_agent.config.get_agent_dir", return_value=tmp_path):
        infos = get_available_themes_with_paths()

    names = [i.name for i in infos]
    assert "dark" in names
    assert "light" in names
    assert "mycustom" in names


# ---------------------------------------------------------------------------
# Registered themes
# ---------------------------------------------------------------------------


def test_registered_theme_appears_in_available() -> None:
    dark = get_theme_by_name("dark")
    assert dark is not None

    # Give it a custom name by wrapping
    from pi_coding_agent.modes.interactive.theme import Theme

    named_theme = Theme(
        fg_colors={"accent": "#aabbcc"},
        bg_colors={},
        mode="truecolor",
        name="my-registered-theme",
    )
    set_registered_themes([named_theme])

    themes = get_available_themes()
    assert "my-registered-theme" in themes

    infos = get_available_themes_with_paths()
    names = [i.name for i in infos]
    assert "my-registered-theme" in names

    # Clean up
    set_registered_themes([])


# ---------------------------------------------------------------------------
# on_theme_change callback
# ---------------------------------------------------------------------------


def test_on_theme_change_called_on_set_theme() -> None:
    called: list[bool] = []
    on_theme_change(lambda: called.append(True))

    set_theme("dark")
    assert called, "Callback should have been called by set_theme"

    # Reset callback
    on_theme_change(lambda: None)


def test_on_theme_change_called_on_set_theme_instance() -> None:
    called: list[bool] = []
    on_theme_change(lambda: called.append(True))

    dark = get_theme_by_name("dark")
    assert dark is not None
    set_theme_instance(dark)
    assert called

    on_theme_change(lambda: None)


# ---------------------------------------------------------------------------
# Terminal background detection
# ---------------------------------------------------------------------------


def test_detect_terminal_background_dark() -> None:
    with patch.dict(os.environ, {"COLORFGBG": ""}, clear=False):
        assert _detect_terminal_background() == "dark"


def test_detect_terminal_background_from_env_light() -> None:
    with patch.dict(os.environ, {"COLORFGBG": "15;15"}, clear=False):
        assert _detect_terminal_background() == "light"


def test_detect_terminal_background_from_env_dark() -> None:
    with patch.dict(os.environ, {"COLORFGBG": "7;0"}, clear=False):
        assert _detect_terminal_background() == "dark"


def test_detect_terminal_background_invalid_colorfgbg() -> None:
    with patch.dict(os.environ, {"COLORFGBG": "bad;data"}, clear=False):
        # Should fall back to "dark" on parse error
        assert _detect_terminal_background() == "dark"


# ---------------------------------------------------------------------------
# get_resolved_theme_colors
# ---------------------------------------------------------------------------


def test_get_resolved_theme_colors_dark() -> None:
    init_theme("dark")
    colors = get_resolved_theme_colors("dark")
    assert isinstance(colors, dict)
    assert "accent" in colors
    assert all(isinstance(v, str) for v in colors.values())


def test_get_resolved_theme_colors_light() -> None:
    colors = get_resolved_theme_colors("light")
    assert isinstance(colors, dict)
    assert len(colors) > 0


def test_get_resolved_theme_colors_uses_current(tmp_path: Path) -> None:
    init_theme("dark")
    colors = get_resolved_theme_colors()
    assert isinstance(colors, dict)


# ---------------------------------------------------------------------------
# get_theme_export_colors
# ---------------------------------------------------------------------------


def test_get_theme_export_colors_dark() -> None:
    result = get_theme_export_colors("dark")
    assert isinstance(result, dict)
    assert "pageBg" in result


def test_get_theme_export_colors_invalid() -> None:
    result = get_theme_export_colors("does-not-exist-xyz")
    assert result == {"pageBg": None, "cardBg": None, "infoBg": None}


# ---------------------------------------------------------------------------
# TUI theme helpers (require theme to be initialized)
# ---------------------------------------------------------------------------


def test_get_markdown_theme() -> None:
    init_theme("dark")
    md = get_markdown_theme()
    assert md is not None
    # It should have callable attributes
    assert callable(md.heading)
    assert callable(md.bold)


def test_get_select_list_theme() -> None:
    init_theme("dark")
    sl = get_select_list_theme()
    assert sl is not None
    assert callable(sl.selected_prefix)


def test_get_editor_theme() -> None:
    init_theme("dark")
    et = get_editor_theme()
    assert et is not None
    assert callable(et.border_color)


def test_get_settings_list_theme() -> None:
    init_theme("dark")
    st = get_settings_list_theme()
    assert st is not None
    assert callable(st.label)
    assert callable(st.value)
