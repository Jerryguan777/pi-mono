"""Terminal UI utilities for visible width calculation, ANSI handling, and text wrapping."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from functools import lru_cache
from typing import NamedTuple

import wcwidth as _wcwidth_mod

# ---------------------------------------------------------------------------
# Grapheme segmentation
# ---------------------------------------------------------------------------


def _iter_grapheme_clusters(text: str) -> list[str]:
    """Iterate over grapheme clusters in *text*.

    This is a simplified segmenter that groups base characters with their
    subsequent combining marks, variation selectors, ZWJ sequences, and
    regional indicator pairs.  It is *not* a full UAX #29 implementation but
    covers the common terminal-relevant cases (emoji, accented chars, wide
    chars).
    """
    clusters: list[str] = []
    buf = ""
    i = 0
    length = len(text)
    while i < length:
        cp = ord(text[i])

        # Regional indicator sequence (flag pairs)
        if 0x1F1E6 <= cp <= 0x1F1FF:
            buf += text[i]
            i += 1
            if i < length:
                cp2 = ord(text[i])
                if 0x1F1E6 <= cp2 <= 0x1F1FF:
                    buf += text[i]
                    i += 1
            clusters.append(buf)
            buf = ""
            continue

        # Start a new cluster with this character
        if buf:
            clusters.append(buf)
        buf = text[i]
        i += 1

        # Absorb combining marks, variation selectors, ZWJ sequences, skin
        # tone modifiers, and enclosing keycaps.
        while i < length:
            nxt = text[i]
            ncp = ord(nxt)
            cat = unicodedata.category(nxt)

            is_combining = cat.startswith("M")  # Mark category
            is_zwj = ncp == 0x200D
            is_variation_selector = 0xFE00 <= ncp <= 0xFE0F or 0xE0100 <= ncp <= 0xE01EF
            is_skin_tone = 0x1F3FB <= ncp <= 0x1F3FF
            is_keycap = ncp == 0x20E3

            if is_combining or is_zwj or is_variation_selector or is_skin_tone or is_keycap:
                buf += nxt
                i += 1
                # After ZWJ, also absorb the next character (the joined emoji)
                if is_zwj and i < length:
                    buf += text[i]
                    i += 1
                continue
            break

    if buf:
        clusters.append(buf)
    return clusters


def get_segmenter() -> Callable[[str], list[str]]:
    """Return a grapheme segmenter function.

    The returned callable accepts a string and returns a list of grapheme
    cluster strings.
    """
    return _iter_grapheme_clusters


# ---------------------------------------------------------------------------
# Emoji / width helpers
# ---------------------------------------------------------------------------

_COULD_BE_EMOJI_RANGES = (
    (0x1F000, 0x1FBFF),  # Emoji and Pictograph
    (0x2300, 0x23FF),  # Misc technical
    (0x2600, 0x27BF),  # Misc symbols, dingbats
    (0x2B50, 0x2B55),  # Specific stars/circles
)


def _could_be_emoji(segment: str) -> bool:
    cp = ord(segment[0])
    for lo, hi in _COULD_BE_EMOJI_RANGES:
        if lo <= cp <= hi:
            return True
    if "\ufe0f" in segment:  # VS16 emoji presentation selector
        return True
    # Multi-codepoint sequences (ZWJ, skin tones, etc.)
    return len(segment) > 2


def _is_emoji_presentation(segment: str) -> bool:
    """Check whether *segment* is an emoji with presentation width 2.

    We use a heuristic: if the segment contains VS16 (\ufe0f), a ZWJ, or
    a skin-tone modifier, it's an emoji cluster.  Single codepoints in common
    emoji ranges also count.
    """
    if "\ufe0f" in segment or "\u200d" in segment:
        return True
    # Skin tone modifier present
    for ch in segment:
        cp = ord(ch)
        if 0x1F3FB <= cp <= 0x1F3FF:
            return True
    # Single codepoint in main emoji block
    cp = ord(segment[0])
    return 0x1F000 <= cp <= 0x1FBFF


def _grapheme_width(segment: str) -> int:
    """Calculate terminal width of a single grapheme cluster."""
    if not segment:
        return 0

    # Zero-width: control characters, combining marks only
    all_zero = True
    for ch in segment:
        cat = unicodedata.category(ch)
        if not (cat.startswith("M") or cat.startswith("C") or cat == "Cf"):
            all_zero = False
            break
    if all_zero:
        return 0

    # Emoji clusters
    if _could_be_emoji(segment) and _is_emoji_presentation(segment):
        return 2

    # Find base visible character (skip leading non-printing)
    base_cp: int | None = None
    for ch in segment:
        cat = unicodedata.category(ch)
        if cat.startswith("M") or cat.startswith("C") or cat == "Cf":
            continue
        base_cp = ord(ch)
        break

    if base_cp is None:
        return 0

    w: int = int(_wcwidth_mod.wcwidth(chr(base_cp)))
    if w < 0:
        w = 0

    # Trailing halfwidth/fullwidth forms
    if len(segment) > 1:
        for ch in segment[1:]:
            cp = ord(ch)
            if 0xFF00 <= cp <= 0xFFEF:
                cw: int = int(_wcwidth_mod.wcwidth(ch))
                if cw > 0:
                    w += cw

    return w


# ---------------------------------------------------------------------------
# ANSI stripping regex (used by visible_width)
# ---------------------------------------------------------------------------

_ANSI_STRIP_RE = re.compile(
    r"\x1b\[[0-9;]*[mGKHJ]"  # SGR and cursor codes
    r"|\x1b\]8;;[^\x07]*\x07"  # OSC 8 hyperlinks
    r"|\x1b_[^\x07\x1b]*(?:\x07|\x1b\\)"  # APC sequences
)

# Fast ASCII check
_ASCII_PRINTABLE = set(range(0x20, 0x7F))


# ---------------------------------------------------------------------------
# Width cache (LRU)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=512)
def _cached_visible_width(s: str) -> int:
    """Compute visible width for a (non-pure-ASCII) string, cached."""
    clean = s
    if "\t" in clean:
        clean = clean.replace("\t", "   ")
    if "\x1b" in clean:
        clean = _ANSI_STRIP_RE.sub("", clean)

    width = 0
    for cluster in _iter_grapheme_clusters(clean):
        width += _grapheme_width(cluster)
    return width


def visible_width(s: str) -> int:
    """Calculate the visible terminal width of *s* in columns.

    - Pure ASCII fast path returns ``len(s)``.
    - Strips ANSI escape codes before measurement.
    - Replaces tabs with 3 spaces.
    - Uses wcwidth for East Asian wide character handling.
    - Results for non-ASCII strings are LRU-cached (size 512).
    """
    if not s:
        return 0

    # Fast path: pure ASCII printable
    is_pure_ascii = True
    for ch in s:
        c = ord(ch)
        if c < 0x20 or c > 0x7E:
            is_pure_ascii = False
            break
    if is_pure_ascii:
        return len(s)

    return _cached_visible_width(s)


# ---------------------------------------------------------------------------
# ANSI code extraction
# ---------------------------------------------------------------------------


class AnsiCode(NamedTuple):
    """An extracted ANSI escape sequence."""

    code: str
    length: int


def extract_ansi_code(s: str, pos: int) -> AnsiCode | None:
    """Extract an ANSI escape sequence from *s* starting at *pos*.

    Returns an ``AnsiCode`` named-tuple ``(code, length)`` or ``None`` if no
    escape sequence starts at *pos*.  Recognises CSI, OSC and APC sequences.
    """
    if pos >= len(s) or s[pos] != "\x1b":
        return None

    if pos + 1 >= len(s):
        return None

    nxt = s[pos + 1]

    # CSI sequence: ESC [ ... m/G/K/H/J
    if nxt == "[":
        j = pos + 2
        while j < len(s) and s[j] not in "mGKHJ":
            j += 1
        if j < len(s):
            return AnsiCode(s[pos : j + 1], j + 1 - pos)
        return None

    # OSC sequence: ESC ] ... BEL  or  ESC ] ... ESC backslash
    if nxt == "]":
        j = pos + 2
        while j < len(s):
            if s[j] == "\x07":
                return AnsiCode(s[pos : j + 1], j + 1 - pos)
            if s[j] == "\x1b" and j + 1 < len(s) and s[j + 1] == "\\":
                return AnsiCode(s[pos : j + 2], j + 2 - pos)
            j += 1
        return None

    # APC sequence: ESC _ ... BEL  or  ESC _ ... ESC backslash
    if nxt == "_":
        j = pos + 2
        while j < len(s):
            if s[j] == "\x07":
                return AnsiCode(s[pos : j + 1], j + 1 - pos)
            if s[j] == "\x1b" and j + 1 < len(s) and s[j + 1] == "\\":
                return AnsiCode(s[pos : j + 2], j + 2 - pos)
            j += 1
        return None

    return None


# ---------------------------------------------------------------------------
# ANSI SGR state tracker
# ---------------------------------------------------------------------------


class AnsiCodeTracker:
    """Track active ANSI SGR codes to preserve styling across line breaks."""

    __slots__ = (
        "_bg_color",
        "_blink",
        "_bold",
        "_dim",
        "_fg_color",
        "_hidden",
        "_inverse",
        "_italic",
        "_strikethrough",
        "_underline",
    )

    def __init__(self) -> None:
        self._bold = False
        self._dim = False
        self._italic = False
        self._underline = False
        self._blink = False
        self._inverse = False
        self._hidden = False
        self._strikethrough = False
        self._fg_color: str | None = None
        self._bg_color: str | None = None

    # -- public API ----------------------------------------------------------

    def process(self, ansi_code: str) -> None:
        """Update state from an ANSI SGR code string."""
        if not ansi_code.endswith("m"):
            return

        m = re.match(r"\x1b\[([\d;]*)m", ansi_code)
        if not m:
            return

        params = m.group(1)
        if params == "" or params == "0":
            self._reset()
            return

        parts = params.split(";")
        i = 0
        while i < len(parts):
            code = int(parts[i])

            # 256-color and RGB extended colours
            if code in (38, 48):
                if i + 2 < len(parts) and parts[i + 1] == "5":
                    color_code = f"{parts[i]};{parts[i + 1]};{parts[i + 2]}"
                    if code == 38:
                        self._fg_color = color_code
                    else:
                        self._bg_color = color_code
                    i += 3
                    continue
                if i + 4 < len(parts) and parts[i + 1] == "2":
                    color_code = f"{parts[i]};{parts[i + 1]};{parts[i + 2]};{parts[i + 3]};{parts[i + 4]}"
                    if code == 38:
                        self._fg_color = color_code
                    else:
                        self._bg_color = color_code
                    i += 5
                    continue

            if code == 0:
                self._reset()
            elif code == 1:
                self._bold = True
            elif code == 2:
                self._dim = True
            elif code == 3:
                self._italic = True
            elif code == 4:
                self._underline = True
            elif code == 5:
                self._blink = True
            elif code == 7:
                self._inverse = True
            elif code == 8:
                self._hidden = True
            elif code == 9:
                self._strikethrough = True
            elif code == 21:
                self._bold = False
            elif code == 22:
                self._bold = False
                self._dim = False
            elif code == 23:
                self._italic = False
            elif code == 24:
                self._underline = False
            elif code == 25:
                self._blink = False
            elif code == 27:
                self._inverse = False
            elif code == 28:
                self._hidden = False
            elif code == 29:
                self._strikethrough = False
            elif code == 39:
                self._fg_color = None
            elif code == 49:
                self._bg_color = None
            elif (30 <= code <= 37) or (90 <= code <= 97):
                self._fg_color = str(code)
            elif (40 <= code <= 47) or (100 <= code <= 107):
                self._bg_color = str(code)

            i += 1

    def get_active_codes(self) -> str:
        """Return an ANSI escape string that re-applies current active state."""
        codes: list[str] = []
        if self._bold:
            codes.append("1")
        if self._dim:
            codes.append("2")
        if self._italic:
            codes.append("3")
        if self._underline:
            codes.append("4")
        if self._blink:
            codes.append("5")
        if self._inverse:
            codes.append("7")
        if self._hidden:
            codes.append("8")
        if self._strikethrough:
            codes.append("9")
        if self._fg_color:
            codes.append(self._fg_color)
        if self._bg_color:
            codes.append(self._bg_color)
        if not codes:
            return ""
        return f"\x1b[{';'.join(codes)}m"

    def has_active_codes(self) -> bool:
        """Return ``True`` if any SGR attribute is currently active."""
        return (
            self._bold
            or self._dim
            or self._italic
            or self._underline
            or self._blink
            or self._inverse
            or self._hidden
            or self._strikethrough
            or self._fg_color is not None
            or self._bg_color is not None
        )

    def get_line_end_reset(self) -> str:
        """Return a reset code for attributes that bleed into padding.

        Currently only underline causes visual bleeding.
        """
        if self._underline:
            return "\x1b[24m"
        return ""

    def clear(self) -> None:
        """Reset all tracked state."""
        self._reset()

    # -- private -------------------------------------------------------------

    def _reset(self) -> None:
        self._bold = False
        self._dim = False
        self._italic = False
        self._underline = False
        self._blink = False
        self._inverse = False
        self._hidden = False
        self._strikethrough = False
        self._fg_color = None
        self._bg_color = None


# ---------------------------------------------------------------------------
# Internal helpers for wrapping
# ---------------------------------------------------------------------------


def _update_tracker_from_text(text: str, tracker: AnsiCodeTracker) -> None:
    """Scan *text* for ANSI codes and update *tracker* accordingly."""
    i = 0
    while i < len(text):
        result = extract_ansi_code(text, i)
        if result is not None:
            tracker.process(result.code)
            i += result.length
        else:
            i += 1


def _split_into_tokens_with_ansi(text: str) -> list[str]:
    """Split *text* into word/whitespace tokens, keeping ANSI codes attached."""
    tokens: list[str] = []
    current = ""
    pending_ansi = ""
    in_whitespace = False
    i = 0

    while i < len(text):
        result = extract_ansi_code(text, i)
        if result is not None:
            pending_ansi += result.code
            i += result.length
            continue

        ch = text[i]
        char_is_space = ch == " "

        if char_is_space != in_whitespace and current:
            tokens.append(current)
            current = ""

        if pending_ansi:
            current += pending_ansi
            pending_ansi = ""

        in_whitespace = char_is_space
        current += ch
        i += 1

    if pending_ansi:
        current += pending_ansi

    if current:
        tokens.append(current)

    return tokens


def _segments_from_text(text: str) -> list[tuple[str, str]]:
    """Parse *text* into a list of ``(type, value)`` tuples.

    ``type`` is ``"ansi"`` or ``"grapheme"``.
    """
    segments: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        result = extract_ansi_code(text, i)
        if result is not None:
            segments.append(("ansi", result.code))
            i += result.length
        else:
            end = i
            while end < len(text) and extract_ansi_code(text, end) is None:
                end += 1
            portion = text[i:end]
            for cluster in _iter_grapheme_clusters(portion):
                segments.append(("grapheme", cluster))
            i = end
    return segments


def _break_long_word(
    word: str,
    width: int,
    tracker: AnsiCodeTracker,
) -> list[str]:
    """Break a long word into lines of at most *width* visible columns."""
    lines: list[str] = []
    current_line = tracker.get_active_codes()
    current_width = 0

    segments = _segments_from_text(word)

    for seg_type, seg_value in segments:
        if seg_type == "ansi":
            current_line += seg_value
            tracker.process(seg_value)
            continue

        grapheme = seg_value
        if not grapheme:
            continue

        gw = _grapheme_width(grapheme)

        if current_width + gw > width:
            line_end_reset = tracker.get_line_end_reset()
            if line_end_reset:
                current_line += line_end_reset
            lines.append(current_line)
            current_line = tracker.get_active_codes()
            current_width = 0

        current_line += grapheme
        current_width += gw

    if current_line:
        lines.append(current_line)

    return lines if lines else [""]


def _wrap_single_line(line: str, width: int) -> list[str]:
    """Wrap a single line (no embedded newlines) to *width* columns."""
    if not line:
        return [""]

    if visible_width(line) <= width:
        return [line]

    wrapped: list[str] = []
    tracker = AnsiCodeTracker()
    tokens = _split_into_tokens_with_ansi(line)

    current_line = ""
    current_visible_length = 0

    for token in tokens:
        token_visible_length = visible_width(token)
        is_whitespace = token.strip() == ""

        # Token itself is too long - break character by character
        if token_visible_length > width and not is_whitespace:
            if current_line:
                line_end_reset = tracker.get_line_end_reset()
                if line_end_reset:
                    current_line += line_end_reset
                wrapped.append(current_line)
                current_line = ""
                current_visible_length = 0

            broken = _break_long_word(token, width, tracker)
            wrapped.extend(broken[:-1])
            current_line = broken[-1]
            current_visible_length = visible_width(current_line)
            continue

        total_needed = current_visible_length + token_visible_length

        if total_needed > width and current_visible_length > 0:
            line_to_wrap = current_line.rstrip()
            line_end_reset = tracker.get_line_end_reset()
            if line_end_reset:
                line_to_wrap += line_end_reset
            wrapped.append(line_to_wrap)
            if is_whitespace:
                current_line = tracker.get_active_codes()
                current_visible_length = 0
            else:
                current_line = tracker.get_active_codes() + token
                current_visible_length = token_visible_length
        else:
            current_line += token
            current_visible_length += token_visible_length

        _update_tracker_from_text(token, tracker)

    if current_line:
        wrapped.append(current_line)

    if wrapped:
        return [ln.rstrip() for ln in wrapped]
    return [""]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def wrap_text_with_ansi(text: str, width: int) -> list[str]:
    """Word-wrap *text* preserving ANSI codes across line breaks.

    Only performs word wrapping -- no padding, no background colours.
    Returns lines where each line is ``<= width`` visible characters.
    Active ANSI codes are preserved across line breaks.
    """
    if not text:
        return [""]

    input_lines = text.split("\n")
    result: list[str] = []
    tracker = AnsiCodeTracker()

    for input_line in input_lines:
        prefix = tracker.get_active_codes() if result else ""
        result.extend(_wrap_single_line(prefix + input_line, width))
        _update_tracker_from_text(input_line, tracker)

    return result if result else [""]


def is_whitespace_char(char: str) -> bool:
    """Return ``True`` if *char* is a whitespace character."""
    return char.isspace()


_PUNCTUATION_RE = re.compile(r"[(){}\[\]<>.,;:'\"!?+\-=*/\\|&%^$#@~`]")


def is_punctuation_char(char: str) -> bool:
    """Return ``True`` if *char* is a punctuation character."""
    return _PUNCTUATION_RE.search(char) is not None


def apply_background_to_line(
    line: str,
    width: int,
    bg_fn: Callable[[str], str],
) -> str:
    """Apply *bg_fn* to *line*, padding with spaces to *width* columns."""
    visible_len = visible_width(line)
    padding_needed = max(0, width - visible_len)
    return bg_fn(line + " " * padding_needed)


def truncate_to_width(
    text: str,
    max_width: int,
    ellipsis: str = "...",
    pad: bool = False,
) -> str:
    """Truncate *text* to *max_width* visible columns, adding *ellipsis* if needed.

    If *pad* is ``True``, the result is right-padded with spaces to exactly
    *max_width* columns.  ANSI codes are handled correctly.
    """
    text_vw = visible_width(text)

    if text_vw <= max_width:
        if pad:
            return text + " " * (max_width - text_vw)
        return text

    ellipsis_width = visible_width(ellipsis)
    target_width = max_width - ellipsis_width

    if target_width <= 0:
        return ellipsis[:max_width]

    segments = _segments_from_text(text)

    result = ""
    current_width = 0

    for seg_type, seg_value in segments:
        if seg_type == "ansi":
            result += seg_value
            continue

        grapheme = seg_value
        if not grapheme:
            continue

        gw = _grapheme_width(grapheme)

        if current_width + gw > target_width:
            break

        result += grapheme
        current_width += gw

    truncated = f"{result}\x1b[0m{ellipsis}"
    if pad:
        tw = visible_width(truncated)
        return truncated + " " * max(0, max_width - tw)
    return truncated


class SliceResult(NamedTuple):
    """Result of ``slice_with_width``."""

    text: str
    width: int


def slice_by_column(
    line: str,
    start_col: int,
    length: int,
    strict: bool = False,
) -> str:
    """Extract a range of visible columns from *line*.

    If *strict* is ``True``, wide characters at the boundary that would extend
    past the range are excluded.
    """
    return slice_with_width(line, start_col, length, strict).text


def slice_with_width(
    line: str,
    start_col: int,
    length: int,
    strict: bool = False,
) -> SliceResult:
    """Like :func:`slice_by_column` but also returns the actual visible width."""
    if length <= 0:
        return SliceResult("", 0)

    end_col = start_col + length
    result = ""
    result_width = 0
    current_col = 0
    i = 0
    pending_ansi = ""

    while i < len(line):
        ansi = extract_ansi_code(line, i)
        if ansi is not None:
            if start_col <= current_col < end_col:
                result += ansi.code
            elif current_col < start_col:
                pending_ansi += ansi.code
            i += ansi.length
            continue

        # Find extent of non-ANSI text
        text_end = i
        while text_end < len(line) and extract_ansi_code(line, text_end) is None:
            text_end += 1

        portion = line[i:text_end]
        for cluster in _iter_grapheme_clusters(portion):
            w = _grapheme_width(cluster)
            in_range = start_col <= current_col < end_col
            fits = (not strict) or (current_col + w <= end_col)
            if in_range and fits:
                if pending_ansi:
                    result += pending_ansi
                    pending_ansi = ""
                result += cluster
                result_width += w
            current_col += w
            if current_col >= end_col:
                break

        i = text_end
        if current_col >= end_col:
            break

    return SliceResult(result, result_width)


class ExtractSegmentsResult(NamedTuple):
    """Result of :func:`extract_segments`."""

    before: str
    before_width: int
    after: str
    after_width: int


# Pooled tracker to avoid allocation per call
_pooled_style_tracker = AnsiCodeTracker()


def extract_segments(
    line: str,
    before_end: int,
    after_start: int,
    after_len: int,
    strict_after: bool = False,
) -> ExtractSegmentsResult:
    """Extract *before* and *after* segments from *line* in a single pass.

    Used for overlay compositing where we need content before and after the
    overlay region.  Preserves styling from before the overlay that should
    affect content after it.
    """
    before = ""
    before_width = 0
    after = ""
    after_width = 0
    current_col = 0
    i = 0
    pending_ansi_before = ""
    after_started = False
    after_end = after_start + after_len

    _pooled_style_tracker.clear()

    while i < len(line):
        ansi = extract_ansi_code(line, i)
        if ansi is not None:
            _pooled_style_tracker.process(ansi.code)
            if current_col < before_end:
                pending_ansi_before += ansi.code
            elif after_start <= current_col < after_end and after_started:
                after += ansi.code
            i += ansi.length
            continue

        text_end = i
        while text_end < len(line) and extract_ansi_code(line, text_end) is None:
            text_end += 1

        portion = line[i:text_end]
        for cluster in _iter_grapheme_clusters(portion):
            w = _grapheme_width(cluster)

            if current_col < before_end:
                if pending_ansi_before:
                    before += pending_ansi_before
                    pending_ansi_before = ""
                before += cluster
                before_width += w
            elif after_start <= current_col < after_end:
                fits = (not strict_after) or (current_col + w <= after_end)
                if fits:
                    if not after_started:
                        after += _pooled_style_tracker.get_active_codes()
                        after_started = True
                    after += cluster
                    after_width += w

            current_col += w
            done_col = before_end if after_len <= 0 else after_end
            if current_col >= done_col:
                break

        i = text_end
        done_col = before_end if after_len <= 0 else after_end
        if current_col >= done_col:
            break

    return ExtractSegmentsResult(before, before_width, after, after_width)


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "AnsiCode",
    "AnsiCodeTracker",
    "ExtractSegmentsResult",
    "SliceResult",
    "apply_background_to_line",
    "extract_ansi_code",
    "extract_segments",
    "get_segmenter",
    "is_punctuation_char",
    "is_whitespace_char",
    "slice_by_column",
    "slice_with_width",
    "truncate_to_width",
    "visible_width",
    "wrap_text_with_ansi",
]
