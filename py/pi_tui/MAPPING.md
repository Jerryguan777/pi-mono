# pi_tui: TypeScript → Python Mapping

## File Mapping

| TS File | Python File | Status |
|---------|-------------|--------|
| `src/index.ts` | `__init__.py` | Done |
| `src/utils.ts` | `utils.py` | Done |
| `src/keys.ts` | `keys.py` | Done |
| `src/fuzzy.ts` | `fuzzy.py` | Done |
| `src/stdin-buffer.ts` | `stdin_buffer.py` | Done |
| `src/kill-ring.ts` | `kill_ring.py` | Done |
| `src/undo-stack.ts` | `undo_stack.py` | Done |
| `src/keybindings.ts` | `keybindings.py` | Done |
| `src/terminal.ts` | `terminal.py` | Done |
| `src/terminal-image.ts` | `terminal_image.py` | Done |
| `src/tui.ts` | `tui.py` | Done |
| `src/autocomplete.ts` | `autocomplete.py` | Done |
| `src/editor-component.ts` | `editor_component.py` | Done |
| `src/components/box.ts` | `components/box.py` | Done |
| `src/components/cancellable-loader.ts` | `components/cancellable_loader.py` | Done |
| `src/components/editor.ts` | `components/editor.py` | Done |
| `src/components/image.ts` | `components/image.py` | Done |
| `src/components/input.ts` | `components/input.py` | Done |
| `src/components/loader.ts` | `components/loader.py` | Done |
| `src/components/markdown.ts` | `components/markdown.py` | Done |
| `src/components/select-list.ts` | `components/select_list.py` | Done |
| `src/components/settings-list.ts` | `components/settings_list.py` | Done |
| `src/components/spacer.ts` | `components/spacer.py` | Done |
| `src/components/text.ts` | `components/text.py` | Done |
| `src/components/truncated-text.ts` | `components/truncated_text.py` | Done |

## API Mapping

### utils.ts → utils.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `getSegmenter()` | `get_segmenter()` | Done | Custom grapheme cluster iterator (no extra dependency) |
| `visibleWidth()` | `visible_width()` | Done | Uses `wcwidth`, LRU cache, ANSI stripping |
| `extractAnsiCode()` | `extract_ansi_code()` | Done | CSI/OSC/APC/DCS sequence extraction |
| `wrapTextWithAnsi()` | `wrap_text_with_ansi()` | Done | Word-wrapping preserving ANSI state |
| `AnsiCodeTracker` | `AnsiCodeTracker` | Done | SGR state tracking across line breaks |
| `truncateToWidth()` | `truncate_to_width()` | Done | |
| `sliceByColumn()` | `slice_by_column()` | Done | |
| `sliceWithWidth()` | `slice_with_width()` | Done | |
| `extractSegments()` | `extract_segments()` | Done | |
| `applyBackgroundToLine()` | `apply_background_to_line()` | Done | |
| `isWhitespaceChar()` | `is_whitespace_char()` | Done | |
| `isPunctuationChar()` | `is_punctuation_char()` | Done | |

### keys.ts → keys.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `Key` (const object) | `Key` (class with class methods) | Done | Static methods for special keys, modifier helpers |
| `KeyId` (type) | `KeyId` (TypeAlias) | Done | |
| `KeyEventType` (type) | `KeyEventType` (TypeAlias) | Done | |
| `parseKey()` | `parse_key()` | Done | Kitty protocol + legacy sequence parsing |
| `matchesKey()` | `matches_key()` | Done | |
| `setKittyProtocolActive()` | `set_kitty_protocol_active()` | Done | |
| `isKittyProtocolActive()` | `is_kitty_protocol_active()` | Done | |
| `isKeyRelease()` | `is_key_release()` | Done | |
| `isKeyRepeat()` | `is_key_repeat()` | Done | |

### fuzzy.ts → fuzzy.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `FuzzyMatch` (interface) | `FuzzyMatch` (dataclass) | Done | |
| `fuzzyMatch()` | `fuzzy_match()` | Done | Score-based matching with alpha-numeric swap |
| `fuzzyFilter()` | `fuzzy_filter()` | Done | Space-separated token support |

### stdin-buffer.ts → stdin_buffer.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `StdinBufferOptions` (type) | `StdinBufferOptions` (dataclass) | Done | |
| `StdinBufferEventMap` (type) | N/A | Done | Replaced by `on_data`/`on_paste` callbacks |
| `StdinBuffer` (class) | `StdinBuffer` (class) | Done | `threading.Timer` replaces `setTimeout` |

### kill-ring.ts → kill_ring.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `KillRing` (class) | `KillRing` (class) | Done | |

### undo-stack.ts → undo_stack.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `UndoStack<S>` (generic class) | `UndoStack[S]` (generic class) | Done | Uses `copy.deepcopy` |

### keybindings.ts → keybindings.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `EditorAction` (type) | `EditorAction` (Literal type) | Done | |
| `EditorKeybindingsConfig` (type) | `EditorKeybindingsConfig` (TypeAlias) | Done | |
| `DEFAULT_EDITOR_KEYBINDINGS` (const) | `DEFAULT_EDITOR_KEYBINDINGS` (dict) | Done | |
| `EditorKeybindingsManager` (class) | `EditorKeybindingsManager` (class) | Done | |
| `getEditorKeybindings()` | `get_editor_keybindings()` | Done | |
| `setEditorKeybindings()` | `set_editor_keybindings()` | Done | |

### terminal.ts → terminal.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `Terminal` (interface) | `Terminal` (Protocol) | Done | |
| `ProcessTerminal` (class) | `ProcessTerminal` (class) | Done | `termios`/`tty.setraw`, background thread + `select.select` |

### terminal-image.ts → terminal_image.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `ImageProtocol` (type) | `ImageProtocol` (Literal) | Done | |
| `TerminalCapabilities` (interface) | `TerminalCapabilities` (dataclass) | Done | |
| `CellDimensions` (interface) | `CellDimensions` (dataclass) | Done | |
| `ImageDimensions` (interface) | `ImageDimensions` (dataclass) | Done | |
| `ImageRenderOptions` (interface) | `ImageRenderOptions` (dataclass) | Done | |
| `detectCapabilities()` | `detect_capabilities()` | Done | |
| `getCapabilities()` | `get_capabilities()` | Done | |
| `resetCapabilitiesCache()` | `reset_capabilities_cache()` | Done | |
| `getCellDimensions()` | `get_cell_dimensions()` | Done | |
| `setCellDimensions()` | `set_cell_dimensions()` | Done | |
| `isImageLine()` | `is_image_line()` | Done | |
| `allocateImageId()` | `allocate_image_id()` | Done | |
| `encodeKitty()` | `encode_kitty()` | Done | |
| `deleteKittyImage()` | `delete_kitty_image()` | Done | |
| `deleteAllKittyImages()` | `delete_all_kitty_images()` | Done | |
| `encodeITerm2()` | `encode_iterm2()` | Done | |
| `calculateImageRows()` | `calculate_image_rows()` | Done | |
| `getPngDimensions()` | `get_png_dimensions()` | Done | |
| `getJpegDimensions()` | `get_jpeg_dimensions()` | Done | |
| `getGifDimensions()` | `get_gif_dimensions()` | Done | |
| `getWebpDimensions()` | `get_webp_dimensions()` | Done | |
| `getImageDimensions()` | `get_image_dimensions()` | Done | |
| `renderImage()` | `render_image()` | Done | |
| `imageFallback()` | `image_fallback()` | Done | |

### tui.ts → tui.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `Component` (interface) | `Component` (Protocol) | Done | |
| `Focusable` (interface) | `Focusable` (Protocol) | Done | |
| `isFocusable()` | `is_focusable()` | Done | |
| `CURSOR_MARKER` (const) | `CURSOR_MARKER` (str) | Done | |
| `OverlayAnchor` (type) | `OverlayAnchor` (Literal) | Done | |
| `OverlayMargin` (interface) | `OverlayMargin` (dataclass) | Done | |
| `SizeValue` (type) | `SizeValue` (TypeAlias) | Done | |
| `OverlayOptions` (interface) | `OverlayOptions` (dataclass) | Done | |
| `OverlayHandle` (interface) | `OverlayHandle` (Protocol) | Done | |
| `Container` (class) | `Container` (class) | Done | |
| `TUI` (class) | `TUI` (class) | Done | Differential rendering, overlay system, focus management |

### autocomplete.ts → autocomplete.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `AutocompleteItem` (interface) | `AutocompleteItem` (alias for `SelectItem`) | Done | Unified with SelectItem |
| `SlashCommand` (interface) | `SlashCommand` (dataclass) | Done | |
| `AutocompleteProvider` (interface) | `AutocompleteProvider` (Protocol) | Done | |
| `CombinedAutocompleteProvider` (class) | `CombinedAutocompleteProvider` (class) | Done | `fd` integration via subprocess |

### editor-component.ts → editor_component.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `EditorComponent` (interface) | `EditorComponent` (Protocol) | Done | `@runtime_checkable` |

### components/box.ts → components/box.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `Box` (class) | `Box` (class) | Done | |

### components/cancellable-loader.ts → components/cancellable_loader.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `CancellableLoader` (class) | `CancellableLoader` (class) | Done | |

### components/editor.ts → components/editor.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `TextChunk` (interface) | `TextChunk` (dataclass) | Done | |
| `wordWrapLine()` | `word_wrap_line()` | Done | |
| `EditorTheme` (interface) | `EditorTheme` (dataclass) | Done | |
| `EditorOptions` (interface) | `EditorOptions` (dataclass) | Done | |
| `Editor` (class) | `Editor` (class) | Done | Multi-line editor with autocomplete, undo, kill ring |

### components/image.ts → components/image.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `ImageTheme` (interface) | `ImageTheme` (dataclass) | Done | |
| `ImageOptions` (interface) | `ImageOptions` (dataclass) | Done | |
| `Image` (class) | `Image` (class) | Done | |

### components/input.ts → components/input.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `Input` (class) | `Input` (class) | Done | |

### components/loader.ts → components/loader.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `Loader` (class) | `Loader` (class) | Done | |

### components/markdown.ts → components/markdown.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `DefaultTextStyle` (interface) | `DefaultTextStyle` (dataclass) | Done | |
| `MarkdownTheme` (interface) | `MarkdownTheme` (dataclass) | Done | |
| `Markdown` (class) | `Markdown` (class) | Done | Uses `mistune` instead of `marked` |

### components/select-list.ts → components/select_list.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `SelectItem` (interface) | `SelectItem` (dataclass) | Done | |
| `SelectListTheme` (interface) | `SelectListTheme` (dataclass) | Done | |
| `SelectList` (class) | `SelectList` (class) | Done | |

### components/settings-list.ts → components/settings_list.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `SettingItem` (interface) | `SettingItem` (dataclass) | Done | |
| `SettingsListTheme` (interface) | `SettingsListTheme` (dataclass) | Done | |
| `SettingsListOptions` (interface) | N/A | Done | Options passed directly to constructor |
| `SettingsList` (class) | `SettingsList` (class) | Done | |

### components/spacer.ts → components/spacer.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `Spacer` (class) | `Spacer` (class) | Done | |

### components/text.ts → components/text.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `Text` (class) | `Text` (class) | Done | |

### components/truncated-text.ts → components/truncated_text.py

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `TruncatedText` (class) | `TruncatedText` (class) | Done | |

## Key Design Decisions

1. **TS `interface` → Python `Protocol`**: Used for `Component`, `Focusable`, `Terminal`, `AutocompleteProvider`, `EditorComponent`, `OverlayHandle` — allows duck typing without inheritance.

2. **TS `interface` (data) → Python `@dataclass`**: Used for data-holding interfaces like `FuzzyMatch`, `OverlayOptions`, `EditorTheme`, etc.

3. **TS `EventEmitter` → Python callbacks**: `StdinBuffer` uses `on_data`/`on_paste` callback attributes instead of `EventEmitter.on()`.

4. **TS `setTimeout` → Python `threading.Timer`**: Used in `StdinBuffer` for escape sequence timeout flushing.

5. **TS `process.stdin` events → Python background thread**: `ProcessTerminal` uses `select.select` + `os.read` in a daemon thread.

6. **TS `AbortController` → Python `asyncio.Event`**: Not needed in current scope.

7. **Grapheme segmentation**: Custom implementation handles combining marks, ZWJ sequences, variation selectors, regional indicators — no extra dependency needed.

8. **`AutocompleteItem` = `SelectItem`**: Unified as a type alias since they have identical fields, resolving type mismatch between autocomplete and select list.

9. **Markdown**: Uses `mistune` (Python) instead of `marked` (JS) for AST parsing.
