"""Theme loading, management, and color utilities.

Python port of packages/coding-agent/src/modes/interactive/theme/theme.ts.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# Data directory: py/pi_coding_agent/data/
_DATA_DIR: Path = Path(__file__).parent.parent.parent / "data"

# ===========================================================================
# Types
# ===========================================================================

ColorMode = Literal["truecolor", "256color"]

ThemeColor = Literal[
    "accent",
    "border",
    "borderAccent",
    "borderMuted",
    "success",
    "error",
    "warning",
    "muted",
    "dim",
    "text",
    "thinkingText",
    "userMessageText",
    "customMessageText",
    "customMessageLabel",
    "toolTitle",
    "toolOutput",
    "mdHeading",
    "mdLink",
    "mdLinkUrl",
    "mdCode",
    "mdCodeBlock",
    "mdCodeBlockBorder",
    "mdQuote",
    "mdQuoteBorder",
    "mdHr",
    "mdListBullet",
    "toolDiffAdded",
    "toolDiffRemoved",
    "toolDiffContext",
    "syntaxComment",
    "syntaxKeyword",
    "syntaxFunction",
    "syntaxVariable",
    "syntaxString",
    "syntaxNumber",
    "syntaxType",
    "syntaxOperator",
    "syntaxPunctuation",
    "thinkingOff",
    "thinkingMinimal",
    "thinkingLow",
    "thinkingMedium",
    "thinkingHigh",
    "thinkingXhigh",
    "bashMode",
]

ThemeBg = Literal[
    "selectedBg",
    "userMessageBg",
    "customMessageBg",
    "toolPendingBg",
    "toolSuccessBg",
    "toolErrorBg",
]

_BG_COLOR_KEYS: frozenset[str] = frozenset(
    {
        "selectedBg",
        "userMessageBg",
        "customMessageBg",
        "toolPendingBg",
        "toolSuccessBg",
        "toolErrorBg",
    }
)


@dataclass
class ThemeInfo:
    """Info about an available theme."""

    name: str
    path: str | None


# ===========================================================================
# Color Utilities
# ===========================================================================


def detect_color_mode() -> ColorMode:
    """Detect the terminal color mode from environment variables."""
    colorterm = os.environ.get("COLORTERM", "")
    if colorterm in ("truecolor", "24bit"):
        return "truecolor"
    # Windows Terminal supports truecolor
    if os.environ.get("WT_SESSION"):
        return "truecolor"
    term = os.environ.get("TERM", "")
    if term in ("dumb", "", "linux"):
        return "256color"
    if os.environ.get("TERM_PROGRAM") == "Apple_Terminal":
        return "256color"
    # Assume truecolor for everything else
    return "truecolor"


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex color string (#RRGGBB) to an (r, g, b) tuple."""
    cleaned = hex_color.lstrip("#")
    if len(cleaned) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    r = int(cleaned[0:2], 16)
    g = int(cleaned[2:4], 16)
    b = int(cleaned[4:6], 16)
    return r, g, b


# The 6x6x6 color cube channel values
_CUBE_VALUES: tuple[int, ...] = (0, 95, 135, 175, 215, 255)
# Grayscale ramp values (indices 232-255, 24 grays from 8 to 238)
_GRAY_VALUES: tuple[int, ...] = tuple(8 + i * 10 for i in range(24))


def _find_closest_cube_index(value: int) -> int:
    """Return the index in _CUBE_VALUES closest to value."""
    min_dist = float("inf")
    min_idx = 0
    for i, cube in enumerate(_CUBE_VALUES):
        dist = abs(value - cube)
        if dist < min_dist:
            min_dist = dist
            min_idx = i
    return min_idx


def _find_closest_gray_index(gray: int) -> int:
    """Return the index in _GRAY_VALUES closest to gray."""
    min_dist = float("inf")
    min_idx = 0
    for i, gv in enumerate(_GRAY_VALUES):
        dist = abs(gray - gv)
        if dist < min_dist:
            min_dist = dist
            min_idx = i
    return min_idx


def _color_distance(r1: int, g1: int, b1: int, r2: int, g2: int, b2: int) -> float:
    """Weighted Euclidean distance (human eye is more sensitive to green)."""
    dr = r1 - r2
    dg = g1 - g2
    db = b1 - b2
    return dr * dr * 0.299 + dg * dg * 0.587 + db * db * 0.114


def rgb_to_256(r: int, g: int, b: int) -> int:
    """Find the closest 256-color palette index for an RGB color."""
    # Find closest color in the 6x6x6 cube
    r_idx = _find_closest_cube_index(r)
    g_idx = _find_closest_cube_index(g)
    b_idx = _find_closest_cube_index(b)
    cube_r = _CUBE_VALUES[r_idx]
    cube_g = _CUBE_VALUES[g_idx]
    cube_b = _CUBE_VALUES[b_idx]
    cube_index = 16 + 36 * r_idx + 6 * g_idx + b_idx
    cube_dist = _color_distance(r, g, b, cube_r, cube_g, cube_b)

    # Find closest grayscale
    gray = round(0.299 * r + 0.587 * g + 0.114 * b)
    gray_idx = _find_closest_gray_index(gray)
    gray_value = _GRAY_VALUES[gray_idx]
    gray_index = 232 + gray_idx
    gray_dist = _color_distance(r, g, b, gray_value, gray_value, gray_value)

    # Only prefer grayscale if color is nearly neutral (spread < 10)
    spread = max(r, g, b) - min(r, g, b)
    if spread < 10 and gray_dist < cube_dist:
        return gray_index

    return cube_index


def fg_ansi(color: str | int, mode: ColorMode) -> str:
    """Return the ANSI escape sequence to set the foreground color."""
    if color == "":
        return "\x1b[39m"  # Reset to default foreground
    if isinstance(color, int):
        return f"\x1b[38;5;{color}m"
    if isinstance(color, str) and color.startswith("#"):
        if mode == "truecolor":
            r, g, b = hex_to_rgb(color)
            return f"\x1b[38;2;{r};{g};{b}m"
        else:
            r, g, b = hex_to_rgb(color)
            index = rgb_to_256(r, g, b)
            return f"\x1b[38;5;{index}m"
    raise ValueError(f"Invalid color value: {color}")


def bg_ansi(color: str | int, mode: ColorMode) -> str:
    """Return the ANSI escape sequence to set the background color."""
    if color == "":
        return "\x1b[49m"  # Reset to default background
    if isinstance(color, int):
        return f"\x1b[48;5;{color}m"
    if isinstance(color, str) and color.startswith("#"):
        if mode == "truecolor":
            r, g, b = hex_to_rgb(color)
            return f"\x1b[48;2;{r};{g};{b}m"
        else:
            r, g, b = hex_to_rgb(color)
            index = rgb_to_256(r, g, b)
            return f"\x1b[48;5;{index}m"
    raise ValueError(f"Invalid color value: {color}")


def resolve_var_refs(
    value: str | int,
    vars_map: dict[str, str | int],
    visited: set[str] | None = None,
) -> str | int:
    """Resolve variable references in a color value.

    Args:
        value: A color value (hex string, 256-color index, empty string, or var name).
        vars_map: Map of variable names to color values.
        visited: Set of variable names already visited (to detect cycles).

    Returns:
        Resolved string or int color value.

    Raises:
        ValueError: On circular or missing variable references.
    """
    if visited is None:
        visited = set()

    if isinstance(value, int):
        return value
    if value == "" or value.startswith("#"):
        return value
    # Variable reference
    if value in visited:
        raise ValueError(f"Circular variable reference detected: {value}")
    if value not in vars_map:
        raise ValueError(f"Variable reference not found: {value}")
    visited.add(value)
    return resolve_var_refs(vars_map[value], vars_map, visited)


def resolve_theme_colors(
    colors: dict[str, str | int],
    vars_map: dict[str, str | int] | None = None,
) -> dict[str, str | int]:
    """Resolve all variable references in a color map.

    Args:
        colors: Raw color entries (may reference vars).
        vars_map: Optional variable definitions.

    Returns:
        A new dict with all values resolved to hex strings or ints.
    """
    if vars_map is None:
        vars_map = {}
    resolved: dict[str, str | int] = {}
    for key, value in colors.items():
        resolved[key] = resolve_var_refs(value, vars_map)
    return resolved


# ===========================================================================
# Theme Class
# ===========================================================================


class Theme:
    """A loaded theme with ANSI color helpers."""

    def __init__(
        self,
        fg_colors: dict[str, str | int],
        bg_colors: dict[str, str | int],
        mode: ColorMode,
        name: str | None = None,
        source_path: str | None = None,
    ) -> None:
        self.name: str | None = name
        self.source_path: str | None = source_path
        self._mode: ColorMode = mode
        self._fg_colors: dict[str, str] = {k: fg_ansi(v, mode) for k, v in fg_colors.items()}
        self._bg_colors: dict[str, str] = {k: bg_ansi(v, mode) for k, v in bg_colors.items()}

    def fg(self, color: str, text: str) -> str:
        """Wrap text with the foreground ANSI color sequence."""
        ansi = self._fg_colors.get(color)
        if ansi is None:
            raise ValueError(f"Unknown theme color: {color}")
        return f"{ansi}{text}\x1b[39m"  # Reset only foreground color

    def bg(self, color: str, text: str) -> str:
        """Wrap text with the background ANSI color sequence."""
        ansi = self._bg_colors.get(color)
        if ansi is None:
            raise ValueError(f"Unknown theme background color: {color}")
        return f"{ansi}{text}\x1b[49m"  # Reset only background color

    def bold(self, text: str) -> str:
        """Return text wrapped with bold ANSI sequences."""
        return f"\x1b[1m{text}\x1b[22m"

    def italic(self, text: str) -> str:
        """Return text wrapped with italic ANSI sequences."""
        return f"\x1b[3m{text}\x1b[23m"

    def underline(self, text: str) -> str:
        """Return text wrapped with underline ANSI sequences."""
        return f"\x1b[4m{text}\x1b[24m"

    def inverse(self, text: str) -> str:
        """Return text wrapped with inverse (reverse video) ANSI sequences."""
        return f"\x1b[7m{text}\x1b[27m"

    def strikethrough(self, text: str) -> str:
        """Return text wrapped with strikethrough ANSI sequences."""
        return f"\x1b[9m{text}\x1b[29m"

    def get_fg_ansi(self, color: str) -> str:
        """Return the raw foreground ANSI escape for the given color name."""
        ansi = self._fg_colors.get(color)
        if ansi is None:
            raise ValueError(f"Unknown theme color: {color}")
        return ansi

    def get_bg_ansi(self, color: str) -> str:
        """Return the raw background ANSI escape for the given color name."""
        ansi = self._bg_colors.get(color)
        if ansi is None:
            raise ValueError(f"Unknown theme background color: {color}")
        return ansi

    def get_color_mode(self) -> ColorMode:
        """Return the color mode used by this theme."""
        return self._mode

    def get_thinking_border_color(
        self,
        level: Literal["off", "minimal", "low", "medium", "high", "xhigh"],
    ) -> Callable[[str], str]:
        """Return a colorizer function for the given thinking level border."""
        mapping: dict[str, str] = {
            "off": "thinkingOff",
            "minimal": "thinkingMinimal",
            "low": "thinkingLow",
            "medium": "thinkingMedium",
            "high": "thinkingHigh",
            "xhigh": "thinkingXhigh",
        }
        color_key = mapping.get(level, "thinkingOff")
        return lambda s: self.fg(color_key, s)

    def get_bash_mode_border_color(self) -> Callable[[str], str]:
        """Return a colorizer function for bash mode borders."""
        return lambda s: self.fg("bashMode", s)


# ===========================================================================
# Theme Loading
# ===========================================================================

# Cache for built-in themes
_BUILTIN_THEMES: dict[str, dict[str, Any]] | None = None


def _get_builtin_themes() -> dict[str, dict[str, Any]]:
    """Load and cache the built-in dark/light theme JSON data."""
    global _BUILTIN_THEMES
    if _BUILTIN_THEMES is None:
        dark_path = _DATA_DIR / "dark.json"
        light_path = _DATA_DIR / "light.json"
        _BUILTIN_THEMES = {
            "dark": json.loads(dark_path.read_text(encoding="utf-8")),
            "light": json.loads(light_path.read_text(encoding="utf-8")),
        }
    return _BUILTIN_THEMES


def _validate_theme_json(label: str, data: dict[str, Any]) -> None:
    """Validate that a theme JSON dict has all required color keys.

    Raises:
        ValueError: If any required color is missing.
    """
    required_colors = {
        "accent",
        "border",
        "borderAccent",
        "borderMuted",
        "success",
        "error",
        "warning",
        "muted",
        "dim",
        "text",
        "thinkingText",
        "selectedBg",
        "userMessageBg",
        "userMessageText",
        "customMessageBg",
        "customMessageText",
        "customMessageLabel",
        "toolPendingBg",
        "toolSuccessBg",
        "toolErrorBg",
        "toolTitle",
        "toolOutput",
        "mdHeading",
        "mdLink",
        "mdLinkUrl",
        "mdCode",
        "mdCodeBlock",
        "mdCodeBlockBorder",
        "mdQuote",
        "mdQuoteBorder",
        "mdHr",
        "mdListBullet",
        "toolDiffAdded",
        "toolDiffRemoved",
        "toolDiffContext",
        "syntaxComment",
        "syntaxKeyword",
        "syntaxFunction",
        "syntaxVariable",
        "syntaxString",
        "syntaxNumber",
        "syntaxType",
        "syntaxOperator",
        "syntaxPunctuation",
        "thinkingOff",
        "thinkingMinimal",
        "thinkingLow",
        "thinkingMedium",
        "thinkingHigh",
        "thinkingXhigh",
        "bashMode",
    }
    if "colors" not in data:
        raise ValueError(f'Invalid theme "{label}": missing "colors" key')
    colors = data["colors"]
    missing = required_colors - set(colors.keys())
    if missing:
        missing_list = "\n".join(f"  - {c}" for c in sorted(missing))
        raise ValueError(
            f'Invalid theme "{label}":\n\nMissing required color tokens:\n'
            f'{missing_list}\n\nPlease add these colors to your theme\'s "colors" object.\n'
            "See the built-in themes (dark.json, light.json) for reference values."
        )


def _parse_theme_json_content(label: str, content: str) -> dict[str, Any]:
    """Parse and validate theme JSON content string."""
    try:
        data: dict[str, Any] = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(f"Failed to parse theme {label}: {error}") from error
    _validate_theme_json(label, data)
    return data


def _create_theme(
    theme_data: dict[str, Any],
    mode: ColorMode | None = None,
    source_path: str | None = None,
) -> Theme:
    """Create a Theme instance from parsed theme JSON data."""
    color_mode = mode if mode is not None else detect_color_mode()
    raw_vars: dict[str, str | int] = theme_data.get("vars", {})
    raw_colors: dict[str, str | int] = theme_data.get("colors", {})

    resolved = resolve_theme_colors(raw_colors, raw_vars)

    fg_colors: dict[str, str | int] = {}
    bg_colors: dict[str, str | int] = {}
    for key, value in resolved.items():
        if key in _BG_COLOR_KEYS:
            bg_colors[key] = value
        else:
            fg_colors[key] = value

    name: str | None = theme_data.get("name")
    return Theme(fg_colors, bg_colors, color_mode, name=name, source_path=source_path)


def _load_theme_json(name: str) -> dict[str, Any]:
    """Load theme JSON data by name (builtin or custom file)."""
    builtin = _get_builtin_themes()
    if name in builtin:
        return builtin[name]

    # Check registered themes with source path
    registered = _registered_themes.get(name)
    if registered is not None:
        if registered.source_path:
            content = Path(registered.source_path).read_text(encoding="utf-8")
            return _parse_theme_json_content(registered.source_path, content)
        raise ValueError(f'Theme "{name}" does not have a source path for export')

    # Check custom themes directory
    from pi_coding_agent.config import get_custom_themes_dir

    custom_dir = get_custom_themes_dir()
    theme_file = custom_dir / f"{name}.json"
    if not theme_file.exists():
        raise ValueError(f"Theme not found: {name}")
    return _parse_theme_json_content(name, theme_file.read_text(encoding="utf-8"))


def _load_theme(name: str, mode: ColorMode | None = None) -> Theme:
    """Load a named theme (checks registered themes first)."""
    registered = _registered_themes.get(name)
    if registered is not None:
        return registered

    theme_data = _load_theme_json(name)
    return _create_theme(theme_data, mode)


def load_theme_from_path(theme_path: str, mode: ColorMode | None = None) -> Theme:
    """Load a theme from a JSON file path."""
    content = Path(theme_path).read_text(encoding="utf-8")
    theme_data = _parse_theme_json_content(theme_path, content)
    return _create_theme(theme_data, mode, source_path=theme_path)


def get_theme_by_name(name: str) -> Theme | None:
    """Return a Theme by name, or None if not found."""
    try:
        return _load_theme(name)
    except Exception:
        return None


def get_available_themes() -> list[str]:
    """Return a sorted list of all available theme names."""
    themes: set[str] = set(_get_builtin_themes().keys())

    from pi_coding_agent.config import get_custom_themes_dir

    custom_dir = get_custom_themes_dir()
    if custom_dir.exists():
        for f in custom_dir.iterdir():
            if f.suffix == ".json":
                themes.add(f.stem)

    for name in _registered_themes:
        themes.add(name)

    return sorted(themes)


def get_available_themes_with_paths() -> list[ThemeInfo]:
    """Return a sorted list of ThemeInfo for all available themes."""
    from pi_coding_agent.config import get_custom_themes_dir

    result: list[ThemeInfo] = []

    # Built-in themes
    for name in _get_builtin_themes():
        result.append(ThemeInfo(name=name, path=str(_DATA_DIR / f"{name}.json")))

    # Custom themes
    custom_dir = get_custom_themes_dir()
    if custom_dir.exists():
        for f in custom_dir.iterdir():
            if f.suffix == ".json":
                name = f.stem
                if not any(t.name == name for t in result):
                    result.append(ThemeInfo(name=name, path=str(f)))

    # Registered themes
    for name, registered_theme in _registered_themes.items():
        if not any(t.name == name for t in result):
            result.append(ThemeInfo(name=name, path=registered_theme.source_path))

    return sorted(result, key=lambda t: t.name)


# ===========================================================================
# Global Theme Instance
# ===========================================================================

# Global singleton theme
_global_theme: Theme | None = None
_current_theme_name: str | None = None
_theme_watcher: Any | None = None  # watchdog observer or None
_on_theme_change_callback: Callable[[], None] | None = None
_registered_themes: dict[str, Theme] = {}


def _set_global_theme(t: Theme) -> None:
    """Set the global theme singleton."""
    global _global_theme
    _global_theme = t


def _detect_terminal_background() -> Literal["dark", "light"]:
    """Detect terminal background color using COLORFGBG environment variable."""
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        parts = colorfgbg.split(";")
        if len(parts) >= 2:
            try:
                bg_val = int(parts[1])
                return "light" if bg_val >= 8 else "dark"
            except ValueError:
                pass
    return "dark"


def _get_default_theme() -> str:
    """Return the default theme name based on terminal background."""
    return _detect_terminal_background()


def set_registered_themes(themes: list[Theme]) -> None:
    """Register additional themes available for selection."""
    global _registered_themes
    _registered_themes = {}
    for t in themes:
        if t.name:
            _registered_themes[t.name] = t


def init_theme(theme_name: str | None = None, enable_watcher: bool = False) -> None:
    """Initialize the global theme singleton.

    Falls back to the dark theme if the named theme cannot be loaded.

    Args:
        theme_name: Name of the theme to load, or None for auto-detect.
        enable_watcher: If True, start watching the theme file for changes.
    """
    global _current_theme_name
    name = theme_name if theme_name is not None else _get_default_theme()
    _current_theme_name = name
    try:
        _set_global_theme(_load_theme(name))
        if enable_watcher:
            _start_theme_watcher()
    except Exception:
        # Fall back to dark theme silently
        _current_theme_name = "dark"
        _set_global_theme(_load_theme("dark"))
        # Do not start watcher for fallback theme


def set_theme(name: str, enable_watcher: bool = False) -> dict[str, Any]:
    """Set the global theme by name.

    Args:
        name: Theme name.
        enable_watcher: If True, start watching the theme file for changes.

    Returns:
        {"success": bool, "error": str | None}
    """
    global _current_theme_name
    _current_theme_name = name
    try:
        _set_global_theme(_load_theme(name))
        if enable_watcher:
            _start_theme_watcher()
        if _on_theme_change_callback is not None:
            _on_theme_change_callback()
        return {"success": True, "error": None}
    except Exception as error:
        # Fall back to dark theme
        _current_theme_name = "dark"
        _set_global_theme(_load_theme("dark"))
        return {"success": False, "error": str(error)}


def set_theme_instance(theme_instance: Theme) -> None:
    """Set a pre-built Theme instance as the global theme."""
    global _current_theme_name
    _set_global_theme(theme_instance)
    _current_theme_name = "<in-memory>"
    stop_theme_watcher()
    if _on_theme_change_callback is not None:
        _on_theme_change_callback()


def on_theme_change(callback: Callable[[], None]) -> None:
    """Register a callback to be called whenever the theme changes."""
    global _on_theme_change_callback
    _on_theme_change_callback = callback


def stop_theme_watcher() -> None:
    """Stop the theme file watcher if running."""
    global _theme_watcher
    if _theme_watcher is not None:
        try:
            _theme_watcher.stop()
            _theme_watcher.join()
        except Exception:
            pass
        _theme_watcher = None


try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler

    class _ThemeFileHandler(FileSystemEventHandler):  # type: ignore[misc]
        """Watchdog event handler for a custom theme JSON file.

        Mirrors the TS fs.watch() callback with a 100ms debounce so that
        rapid saves (e.g. editor auto-save) don't trigger multiple reloads.
        """

        def __init__(self, theme_file: Path) -> None:
            super().__init__()
            self._theme_file = theme_file
            self._debounce_timer: threading.Timer | None = None

        def _debounce(self, action: Callable[[], None]) -> None:
            """Cancel any pending timer and schedule action after 100ms."""
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(0.1, action)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

        def on_modified(self, event: FileSystemEvent) -> None:
            if str(event.src_path) != str(self._theme_file):
                return

            def _reload() -> None:
                try:
                    _set_global_theme(_load_theme(_current_theme_name or "dark"))
                    if _on_theme_change_callback is not None:
                        _on_theme_change_callback()
                except (OSError, ValueError):
                    pass  # Ignore errors while file is being written

            self._debounce(_reload)

        def on_deleted(self, event: FileSystemEvent) -> None:
            if str(event.src_path) != str(self._theme_file):
                return
            global _current_theme_name
            _current_theme_name = "dark"
            _set_global_theme(_load_theme("dark"))
            stop_theme_watcher()
            if _on_theme_change_callback is not None:
                _on_theme_change_callback()

except ImportError:
    pass  # watchdog not installed - _ThemeFileHandler is not defined


def _start_theme_watcher() -> None:
    """Start watching the current custom theme file for changes."""
    global _theme_watcher

    stop_theme_watcher()

    # Only watch custom themes (not built-ins)
    if not _current_theme_name or _current_theme_name in ("dark", "light"):
        return

    from pi_coding_agent.config import get_custom_themes_dir

    custom_dir = get_custom_themes_dir()
    theme_file = custom_dir / f"{_current_theme_name}.json"

    if not theme_file.exists():
        return

    try:
        from watchdog.observers import Observer

        observer = Observer()
        observer.schedule(_ThemeFileHandler(theme_file), str(custom_dir), recursive=False)
        observer.start()
        _theme_watcher = observer
    except (ImportError, OSError):
        pass  # watchdog not installed or OS error - watcher is a no-op


# ===========================================================================
# HTML Export Helpers
# ===========================================================================

_BASIC_COLORS: tuple[str, ...] = (
    "#000000",
    "#800000",
    "#008000",
    "#808000",
    "#000080",
    "#800080",
    "#008080",
    "#c0c0c0",
    "#808080",
    "#ff0000",
    "#00ff00",
    "#ffff00",
    "#0000ff",
    "#ff00ff",
    "#00ffff",
    "#ffffff",
)


def _ansi256_to_hex(index: int) -> str:
    """Convert a 256-color index to a hex color string."""
    if index < 16:
        return _BASIC_COLORS[index]
    if index < 232:
        cube_index = index - 16
        r_idx = cube_index // 36
        g_idx = (cube_index % 36) // 6
        b_idx = cube_index % 6

        def to_hex(n: int) -> str:
            return "00" if n == 0 else f"{55 + n * 40:02x}"

        return f"#{to_hex(r_idx)}{to_hex(g_idx)}{to_hex(b_idx)}"
    # Grayscale
    gray = 8 + (index - 232) * 10
    gray_hex = f"{gray:02x}"
    return f"#{gray_hex}{gray_hex}{gray_hex}"


def get_resolved_theme_colors(theme_name: str | None = None) -> dict[str, str]:
    """Get resolved theme colors as CSS-compatible hex strings.

    Used by HTML export to generate CSS custom properties.
    """
    name = theme_name or _current_theme_name or _get_default_theme()
    is_light = name == "light"
    theme_data = _load_theme_json(name)
    raw_vars: dict[str, str | int] = theme_data.get("vars", {})
    raw_colors: dict[str, str | int] = theme_data.get("colors", {})
    resolved = resolve_theme_colors(raw_colors, raw_vars)

    default_text = "#000000" if is_light else "#e5e5e7"
    css_colors: dict[str, str] = {}
    for key, value in resolved.items():
        if isinstance(value, int):
            css_colors[key] = _ansi256_to_hex(value)
        elif value == "":
            css_colors[key] = default_text
        else:
            css_colors[key] = str(value)
    return css_colors


def is_light_theme(theme_name: str | None = None) -> bool:
    """Return True if the given theme name is a light theme."""
    return theme_name == "light"


def get_theme_export_colors(
    theme_name: str | None = None,
) -> dict[str, str | None]:
    """Get explicit export colors from a theme's JSON export section.

    Returns a dict with keys pageBg, cardBg, infoBg (all may be None).
    """
    name = theme_name or _current_theme_name or _get_default_theme()
    try:
        theme_data = _load_theme_json(name)
        export_section: dict[str, Any] = theme_data.get("export", {})
        if not export_section:
            return {"pageBg": None, "cardBg": None, "infoBg": None}

        raw_vars: dict[str, str | int] = theme_data.get("vars", {})

        def resolve_export(value: str | int | None) -> str | None:
            if value is None:
                return None
            if isinstance(value, int):
                return _ansi256_to_hex(value)
            if isinstance(value, str) and value.startswith("$"):
                var_value = raw_vars.get(value)
                if var_value is None:
                    return None
                if isinstance(var_value, int):
                    return _ansi256_to_hex(var_value)
                return str(var_value)
            return str(value)

        return {
            "pageBg": resolve_export(export_section.get("pageBg")),
            "cardBg": resolve_export(export_section.get("cardBg")),
            "infoBg": resolve_export(export_section.get("infoBg")),
        }
    except Exception:
        return {"pageBg": None, "cardBg": None, "infoBg": None}


# ===========================================================================
# Syntax Highlighting
# ===========================================================================

_EXT_TO_LANG: dict[str, str] = {
    "ts": "typescript",
    "tsx": "typescript",
    "js": "javascript",
    "jsx": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "py": "python",
    "rb": "ruby",
    "rs": "rust",
    "go": "go",
    "java": "java",
    "kt": "kotlin",
    "swift": "swift",
    "c": "c",
    "h": "c",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "hpp": "cpp",
    "cs": "csharp",
    "php": "php",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "fish": "fish",
    "ps1": "powershell",
    "sql": "sql",
    "html": "html",
    "htm": "html",
    "css": "css",
    "scss": "scss",
    "sass": "sass",
    "less": "less",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "xml": "xml",
    "md": "markdown",
    "markdown": "markdown",
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "cmake": "cmake",
    "lua": "lua",
    "perl": "perl",
    "r": "r",
    "scala": "scala",
    "clj": "clojure",
    "ex": "elixir",
    "exs": "elixir",
    "erl": "erlang",
    "hs": "haskell",
    "ml": "ocaml",
    "vim": "vim",
    "graphql": "graphql",
    "proto": "protobuf",
    "tf": "hcl",
    "hcl": "hcl",
}


def get_language_from_path(file_path: str) -> str | None:
    """Return a language identifier from a file path extension."""
    parts = file_path.rsplit(".", 1)
    if len(parts) < 2:
        return None
    ext = parts[1].lower()
    return _EXT_TO_LANG.get(ext)


def highlight_code(code: str, lang: str | None = None) -> list[str]:
    """Highlight code with syntax coloring.

    Returns a list of highlighted lines. Falls back to plain lines on error.
    """
    try:
        # Use Pygments if available
        from pygments import highlight as pyg_highlight
        from pygments.formatters import Terminal256Formatter
        from pygments.lexers import get_lexer_by_name
        from pygments.util import ClassNotFound

        if lang is None:
            return code.split("\n")

        try:
            lexer = get_lexer_by_name(lang)
            formatter = Terminal256Formatter()
            highlighted: str = str(pyg_highlight(code, lexer, formatter))
            return highlighted.split("\n")
        except ClassNotFound:
            return code.split("\n")
    except ImportError:
        # Pygments not installed - return plain lines
        return code.split("\n")


# ===========================================================================
# TUI Theme Helpers
# ===========================================================================


def get_markdown_theme() -> Any:
    """Return a MarkdownTheme dict/object for use with pi_tui's Markdown component."""
    from pi_tui import MarkdownTheme

    t = _get_current_theme()
    return MarkdownTheme(
        heading=lambda text: t.fg("mdHeading", text),
        link=lambda text: t.fg("mdLink", text),
        link_url=lambda text: t.fg("mdLinkUrl", text),
        code=lambda text: t.fg("mdCode", text),
        code_block=lambda text: t.fg("mdCodeBlock", text),
        code_block_border=lambda text: t.fg("mdCodeBlockBorder", text),
        quote=lambda text: t.fg("mdQuote", text),
        quote_border=lambda text: t.fg("mdQuoteBorder", text),
        hr=lambda text: t.fg("mdHr", text),
        list_bullet=lambda text: t.fg("mdListBullet", text),
        bold=lambda text: t.bold(text),
        italic=lambda text: t.italic(text),
        underline=lambda text: t.underline(text),
        strikethrough=lambda text: t.strikethrough(text),
        highlight_code=highlight_code,
    )


def get_select_list_theme() -> Any:
    """Return a SelectListTheme for use with pi_tui's SelectList component."""
    from pi_tui import SelectListTheme

    t = _get_current_theme()
    return SelectListTheme(
        selected_prefix=lambda text: t.fg("accent", text),
        selected_text=lambda text: t.fg("accent", text),
        description=lambda text: t.fg("muted", text),
        scroll_info=lambda text: t.fg("muted", text),
        no_match=lambda text: t.fg("muted", text),
    )


def get_editor_theme() -> Any:
    """Return an EditorTheme for use with pi_tui's Editor component."""
    from pi_tui import EditorTheme

    t = _get_current_theme()
    return EditorTheme(
        border_color=lambda text: t.fg("borderMuted", text),
        select_list=get_select_list_theme(),
    )


def get_settings_list_theme() -> Any:
    """Return a SettingsListTheme for use with pi_tui's SettingsList component."""
    from pi_tui import SettingsListTheme

    t = _get_current_theme()
    return SettingsListTheme(
        label=lambda text, selected: t.fg("accent", text) if selected else text,
        value=lambda text, selected: t.fg("accent", text) if selected else t.fg("muted", text),
        description=lambda text: t.fg("dim", text),
        cursor=t.fg("accent", "-> "),
        hint=lambda text: t.fg("dim", text),
    )


def _get_current_theme() -> Theme:
    """Return the current global theme, raising if not initialized."""
    if _global_theme is None:
        raise RuntimeError("Theme not initialized. Call init_theme() first.")
    return _global_theme


class _ThemeProxy:
    """Proxy that delegates all attribute access to the global theme singleton.

    This mirrors the TS Proxy pattern to share a single mutable reference.
    """

    def __getattr__(self, name: str) -> Any:
        t = _global_theme
        if t is None:
            raise RuntimeError("Theme not initialized. Call init_theme() first.")
        return getattr(t, name)


# Module-level theme proxy (mirrors TS `export const theme: Theme = new Proxy(...)`)
theme: Theme = _ThemeProxy()  # type: ignore[assignment]
