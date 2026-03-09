"""Tests for pi_coding_agent.modes.interactive.theme."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pi_coding_agent.modes.interactive.theme import (
    _DATA_DIR,
    Theme,
    ThemeInfo,
    detect_color_mode,
    fg_ansi,
    get_available_themes,
    get_available_themes_with_paths,
    get_language_from_path,
    get_theme_by_name,
    hex_to_rgb,
    highlight_code,
    init_theme,
    is_light_theme,
    load_theme_from_path,
    resolve_theme_colors,
    resolve_var_refs,
    rgb_to_256,
    set_registered_themes,
    set_theme,
    set_theme_instance,
    stop_theme_watcher,
)

# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------


def test_hex_to_rgb_basic() -> None:
    r, g, b = hex_to_rgb("#ff0000")
    assert r == 255
    assert g == 0
    assert b == 0


def test_hex_to_rgb_with_hash() -> None:
    r, g, b = hex_to_rgb("#00ff00")
    assert r == 0
    assert g == 255
    assert b == 0


def test_hex_to_rgb_invalid() -> None:
    with pytest.raises(ValueError):
        hex_to_rgb("#gg0000")


def test_hex_to_rgb_wrong_length() -> None:
    with pytest.raises(ValueError):
        hex_to_rgb("#fff")


def test_rgb_to_256_pure_red() -> None:
    idx = rgb_to_256(255, 0, 0)
    assert 0 < idx < 256


def test_rgb_to_256_black() -> None:
    idx = rgb_to_256(0, 0, 0)
    assert 0 <= idx < 256


def test_rgb_to_256_white() -> None:
    idx = rgb_to_256(255, 255, 255)
    assert 0 <= idx < 256


def test_fg_ansi_truecolor() -> None:
    result = fg_ansi("#ff0000", "truecolor")
    assert "\x1b[38;2;" in result
    assert "255;0;0" in result


def test_fg_ansi_256color() -> None:
    result = fg_ansi("#ff0000", "256color")
    assert "\x1b[38;5;" in result


def test_fg_ansi_int() -> None:
    result = fg_ansi(196, "256color")
    assert result == "\x1b[38;5;196m"


def test_fg_ansi_empty_string() -> None:
    result = fg_ansi("", "truecolor")
    assert result == "\x1b[39m"


def test_detect_color_mode_returns_valid() -> None:
    mode = detect_color_mode()
    assert mode in ("truecolor", "256color")


# ---------------------------------------------------------------------------
# Theme JSON loading
# ---------------------------------------------------------------------------


def test_data_dir_exists() -> None:
    assert _DATA_DIR.exists()
    assert (_DATA_DIR / "dark.json").exists()
    assert (_DATA_DIR / "light.json").exists()


def test_resolve_var_refs_direct_hex() -> None:
    result = resolve_var_refs("#abcdef", {})
    assert result == "#abcdef"


def test_resolve_var_refs_number() -> None:
    result = resolve_var_refs(196, {})
    assert result == 196


def test_resolve_var_refs_empty_string() -> None:
    result = resolve_var_refs("", {})
    assert result == ""


def test_resolve_var_refs_variable() -> None:
    result = resolve_var_refs("mycolor", {"mycolor": "#123456"})
    assert result == "#123456"


def test_resolve_var_refs_chain() -> None:
    result = resolve_var_refs("a", {"a": "b", "b": "#ffffff"})
    assert result == "#ffffff"


def test_resolve_var_refs_missing() -> None:
    with pytest.raises(ValueError, match=r"[Nn]ot found"):
        resolve_var_refs("missing", {})


def test_resolve_var_refs_circular() -> None:
    with pytest.raises(ValueError, match=r"[Cc]ircular"):
        resolve_var_refs("a", {"a": "b", "b": "a"})


def test_resolve_theme_colors_basic() -> None:
    colors = {"accent": "#ff0000", "border": "#00ff00"}
    resolved = resolve_theme_colors(colors)
    assert resolved["accent"] == "#ff0000"
    assert resolved["border"] == "#00ff00"


def test_resolve_theme_colors_with_vars() -> None:
    colors = {"accent": "myVar", "border": "#000"}
    vars_ = {"myVar": "#aabbcc"}
    resolved = resolve_theme_colors(colors, vars_)
    assert resolved["accent"] == "#aabbcc"


# ---------------------------------------------------------------------------
# Theme class
# ---------------------------------------------------------------------------


def test_theme_fg() -> None:
    fg_colors = {"accent": "#ff0000"}
    bg_colors: dict[str, str | int] = {}
    t = Theme(fg_colors, bg_colors, "truecolor")  # type: ignore[arg-type]
    result = t.fg("accent", "hello")
    assert "hello" in result
    assert "\x1b[39m" in result  # foreground reset


def test_theme_fg_unknown_raises() -> None:
    t = Theme({}, {}, "truecolor")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Unknown theme color"):
        t.fg("accent", "x")  # type: ignore[arg-type]


def test_theme_bg() -> None:
    bg_colors = {"selectedBg": "#333333"}
    t = Theme({}, bg_colors, "truecolor")  # type: ignore[arg-type]
    result = t.bg("selectedBg", "hi")
    assert "hi" in result
    assert "\x1b[49m" in result  # background reset


def test_theme_bold_italic_underline() -> None:
    t = Theme({}, {}, "truecolor")  # type: ignore[arg-type]
    assert t.bold("text")
    assert t.italic("text")
    assert t.underline("text")


def test_theme_get_color_mode() -> None:
    t = Theme({}, {}, "256color")  # type: ignore[arg-type]
    assert t.get_color_mode() == "256color"


def test_theme_thinking_border_color() -> None:
    fg_colors = {
        "thinkingOff": "#111111",
        "thinkingMinimal": "#222222",
        "thinkingLow": "#333333",
        "thinkingMedium": "#444444",
        "thinkingHigh": "#555555",
        "thinkingXhigh": "#666666",
    }
    t = Theme(fg_colors, {}, "truecolor")  # type: ignore[arg-type]
    for level in ("off", "minimal", "low", "medium", "high", "xhigh"):
        fn = t.get_thinking_border_color(level)  # type: ignore[arg-type]
        result = fn("test")
        assert "test" in result


def test_theme_bash_mode_border_color() -> None:
    fg_colors = {"bashMode": "#ff6600"}
    t = Theme(fg_colors, {}, "truecolor")  # type: ignore[arg-type]
    fn = t.get_bash_mode_border_color()
    result = fn("cmd")
    assert "cmd" in result


# ---------------------------------------------------------------------------
# Theme loading
# ---------------------------------------------------------------------------


def test_load_theme_from_path(tmp_path: Path) -> None:
    dark_theme = json.loads((_DATA_DIR / "dark.json").read_text(encoding="utf-8"))
    theme_path = tmp_path / "custom.json"
    theme_path.write_text(json.dumps(dark_theme), encoding="utf-8")

    t = load_theme_from_path(str(theme_path))
    assert isinstance(t, Theme)


def test_get_available_themes_includes_builtins() -> None:
    themes = get_available_themes()
    assert "dark" in themes
    assert "light" in themes


def test_get_available_themes_with_paths() -> None:
    infos = get_available_themes_with_paths()
    names = [i.name for i in infos]
    assert "dark" in names
    assert "light" in names
    for info in infos:
        assert isinstance(info, ThemeInfo)


def test_get_theme_by_name_dark() -> None:
    t = get_theme_by_name("dark")
    assert t is not None
    assert isinstance(t, Theme)


def test_get_theme_by_name_light() -> None:
    t = get_theme_by_name("light")
    assert t is not None


def test_get_theme_by_name_missing() -> None:
    t = get_theme_by_name("nonexistent-theme-xyz")
    assert t is None


def test_init_theme_dark() -> None:
    init_theme("dark")
    # Should not raise


def test_init_theme_light() -> None:
    init_theme("light")


def test_init_theme_invalid_falls_back() -> None:
    # Invalid theme should silently fall back to dark
    init_theme("theme-that-does-not-exist")


def test_set_theme_valid() -> None:
    result = set_theme("dark")
    assert result["success"] is True
    assert result.get("error") is None


def test_set_theme_invalid() -> None:
    result = set_theme("nonexistent-theme-xyz")
    assert result["success"] is False
    assert result.get("error") is not None


def test_set_theme_instance() -> None:
    t = get_theme_by_name("dark")
    assert t is not None
    set_theme_instance(t)


def test_set_registered_themes() -> None:
    t = get_theme_by_name("dark")
    assert t is not None
    set_registered_themes([t])
    # Should not raise


def test_stop_theme_watcher() -> None:
    stop_theme_watcher()  # Should not raise


def test_is_light_theme() -> None:
    assert is_light_theme("light") is True
    assert is_light_theme("dark") is False
    assert is_light_theme(None) is False


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_get_language_from_path_ts() -> None:
    assert get_language_from_path("main.ts") == "typescript"


def test_get_language_from_path_py() -> None:
    assert get_language_from_path("script.py") == "python"


def test_get_language_from_path_json() -> None:
    assert get_language_from_path("config.json") == "json"


def test_get_language_from_path_unknown() -> None:
    assert get_language_from_path("file.xyz") is None


def test_get_language_from_path_no_ext() -> None:
    assert get_language_from_path("Makefile") is None


def test_highlight_code_python() -> None:
    lines = highlight_code("x = 1", "python")
    assert isinstance(lines, list)
    assert len(lines) >= 1


def test_highlight_code_no_lang() -> None:
    lines = highlight_code("hello world")
    assert isinstance(lines, list)
    assert "hello world" in "\n".join(lines)


def test_highlight_code_invalid_lang() -> None:
    # Should not raise even with invalid language
    lines = highlight_code("x = 1", "notareallanguage")
    assert isinstance(lines, list)
