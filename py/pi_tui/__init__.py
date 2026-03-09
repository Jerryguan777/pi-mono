"""Terminal UI with differential rendering — Python port of @mariozechner/pi-tui."""

# Autocomplete support
from pi_tui.autocomplete import (
    AutocompleteItem,
    AutocompleteProvider,
    CombinedAutocompleteProvider,
    SlashCommand,
)

# Components
from pi_tui.components.box import Box
from pi_tui.components.cancellable_loader import CancellableLoader
from pi_tui.components.editor import (
    Editor,
    EditorOptions,
    EditorTheme,
    TextChunk,
    word_wrap_line,
)
from pi_tui.components.image import Image, ImageOptions, ImageTheme
from pi_tui.components.input import Input
from pi_tui.components.loader import Loader
from pi_tui.components.markdown import DefaultTextStyle, Markdown, MarkdownTheme
from pi_tui.components.select_list import SelectItem, SelectList, SelectListTheme
from pi_tui.components.settings_list import SettingItem, SettingsList, SettingsListTheme
from pi_tui.components.spacer import Spacer
from pi_tui.components.text import Text
from pi_tui.components.truncated_text import TruncatedText

# Editor component interface (for custom editors)
from pi_tui.editor_component import EditorComponent

# Fuzzy matching
from pi_tui.fuzzy import FuzzyMatch, fuzzy_filter, fuzzy_match

# Keybindings
from pi_tui.keybindings import (
    DEFAULT_EDITOR_KEYBINDINGS,
    EditorAction,
    EditorKeybindingsConfig,
    EditorKeybindingsManager,
    get_editor_keybindings,
    set_editor_keybindings,
)

# Keyboard input handling
from pi_tui.keys import (
    Key,
    KeyEventType,
    KeyId,
    is_key_release,
    is_key_repeat,
    is_kitty_protocol_active,
    matches_key,
    parse_key,
    set_kitty_protocol_active,
)

# Kill ring and undo stack
from pi_tui.kill_ring import KillRing

# Input buffering for batch splitting
from pi_tui.stdin_buffer import StdinBuffer, StdinBufferOptions

# Terminal interface and implementations
from pi_tui.terminal import ProcessTerminal, Terminal

# Terminal image support
from pi_tui.terminal_image import (
    CellDimensions,
    ImageDimensions,
    ImageProtocol,
    ImageRenderOptions,
    TerminalCapabilities,
    allocate_image_id,
    calculate_image_rows,
    delete_all_kitty_images,
    delete_kitty_image,
    detect_capabilities,
    encode_iterm2,
    encode_kitty,
    get_capabilities,
    get_cell_dimensions,
    get_gif_dimensions,
    get_image_dimensions,
    get_jpeg_dimensions,
    get_png_dimensions,
    get_webp_dimensions,
    image_fallback,
    render_image,
    reset_capabilities_cache,
    set_cell_dimensions,
)

# TUI core
from pi_tui.tui import (
    CURSOR_MARKER,
    TUI,
    Component,
    Container,
    Focusable,
    OverlayAnchor,
    OverlayHandle,
    OverlayMargin,
    OverlayOptions,
    SizeValue,
    is_focusable,
)
from pi_tui.undo_stack import UndoStack

# Utilities
from pi_tui.utils import (
    apply_background_to_line,
    extract_ansi_code,
    extract_segments,
    get_segmenter,
    is_punctuation_char,
    is_whitespace_char,
    slice_by_column,
    slice_with_width,
    truncate_to_width,
    visible_width,
    wrap_text_with_ansi,
)

__all__ = [
    "CURSOR_MARKER",
    # Keybindings
    "DEFAULT_EDITOR_KEYBINDINGS",
    "TUI",
    # Autocomplete
    "AutocompleteItem",
    "AutocompleteProvider",
    # Components
    "Box",
    "CancellableLoader",
    # Terminal image
    "CellDimensions",
    "CombinedAutocompleteProvider",
    # TUI core
    "Component",
    "Container",
    "DefaultTextStyle",
    "Editor",
    "EditorAction",
    # Editor component
    "EditorComponent",
    "EditorKeybindingsConfig",
    "EditorKeybindingsManager",
    "EditorOptions",
    "EditorTheme",
    "Focusable",
    # Fuzzy matching
    "FuzzyMatch",
    "Image",
    "ImageDimensions",
    "ImageOptions",
    "ImageProtocol",
    "ImageRenderOptions",
    "ImageTheme",
    "Input",
    # Keys
    "Key",
    "KeyEventType",
    "KeyId",
    # Kill ring and undo stack
    "KillRing",
    "Loader",
    "Markdown",
    "MarkdownTheme",
    "OverlayAnchor",
    "OverlayHandle",
    "OverlayMargin",
    "OverlayOptions",
    # Terminal
    "ProcessTerminal",
    "SelectItem",
    "SelectList",
    "SelectListTheme",
    "SettingItem",
    "SettingsList",
    "SettingsListTheme",
    "SizeValue",
    "SlashCommand",
    "Spacer",
    # StdinBuffer
    "StdinBuffer",
    "StdinBufferOptions",
    "Terminal",
    "TerminalCapabilities",
    "Text",
    "TextChunk",
    "TruncatedText",
    "UndoStack",
    "allocate_image_id",
    # Utilities
    "apply_background_to_line",
    "calculate_image_rows",
    "delete_all_kitty_images",
    "delete_kitty_image",
    "detect_capabilities",
    "encode_iterm2",
    "encode_kitty",
    "extract_ansi_code",
    "extract_segments",
    "fuzzy_filter",
    "fuzzy_match",
    "get_capabilities",
    "get_cell_dimensions",
    "get_editor_keybindings",
    "get_gif_dimensions",
    "get_image_dimensions",
    "get_jpeg_dimensions",
    "get_png_dimensions",
    "get_segmenter",
    "get_webp_dimensions",
    "image_fallback",
    "is_focusable",
    "is_key_release",
    "is_key_repeat",
    "is_kitty_protocol_active",
    "is_punctuation_char",
    "is_whitespace_char",
    "matches_key",
    "parse_key",
    "render_image",
    "reset_capabilities_cache",
    "set_cell_dimensions",
    "set_editor_keybindings",
    "set_kitty_protocol_active",
    "slice_by_column",
    "slice_with_width",
    "truncate_to_width",
    "visible_width",
    "word_wrap_line",
    "wrap_text_with_ansi",
]
