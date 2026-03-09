"""Keyboard input handling for terminal applications.

Supports both legacy terminal sequences and Kitty keyboard protocol.
See: https://sw.kovidgoyal.net/kitty/keyboard-protocol/
Reference: https://github.com/sst/opentui/blob/7da92b4088aebfe27b9f691c04163a48821e49fd/packages/core/src/lib/parse.keypress.ts

Symbol keys are also supported, however some ctrl+symbol combos
overlap with ASCII codes, e.g. ctrl+[ = ESC.
See: https://sw.kovidgoyal.net/kitty/keyboard-protocol/#legacy-ctrl-mapping-of-ascii-keys
Those can still be used for ctrl+shift combos

API:
- matches_key(data, key_id) - Check if input matches a key identifier
- parse_key(data) - Parse input and return the key identifier
- Key - Helper class for creating typed key identifiers
- set_kitty_protocol_active(active) - Set global Kitty protocol state
- is_kitty_protocol_active() - Query global Kitty protocol state
"""

from __future__ import annotations

import re
from typing import Literal

# =============================================================================
# Type Aliases
# =============================================================================

KeyId = str
"""Union type of all valid key identifiers. In Python this is just str
(the TS type is a complex template literal for autocomplete)."""

KeyEventType = Literal["press", "repeat", "release"]

# =============================================================================
# Global Kitty Protocol State
# =============================================================================

_kitty_protocol_active: bool = False


def set_kitty_protocol_active(active: bool) -> None:
    """Set the global Kitty keyboard protocol state.
    Called by ProcessTerminal after detecting protocol support.
    """
    global _kitty_protocol_active
    _kitty_protocol_active = active


def is_kitty_protocol_active() -> bool:
    """Query whether Kitty keyboard protocol is currently active."""
    return _kitty_protocol_active


# =============================================================================
# Key Helper Class
# =============================================================================


class Key:
    """Helper object for creating typed key identifiers with autocomplete.

    Usage:
    - Key.escape, Key.enter, Key.tab, etc. for special keys
    - Key.backtick, Key.comma, Key.period, etc. for symbol keys
    - Key.ctrl("c"), Key.alt("x") for single modifier
    - Key.ctrl_shift("p"), Key.ctrl_alt("x") for combined modifiers
    """

    # Special keys
    escape: str = "escape"
    esc: str = "esc"
    enter: str = "enter"
    return_: str = "return"
    tab: str = "tab"
    space: str = "space"
    backspace: str = "backspace"
    delete: str = "delete"
    insert: str = "insert"
    clear: str = "clear"
    home: str = "home"
    end: str = "end"
    page_up: str = "pageUp"
    page_down: str = "pageDown"
    up: str = "up"
    down: str = "down"
    left: str = "left"
    right: str = "right"
    f1: str = "f1"
    f2: str = "f2"
    f3: str = "f3"
    f4: str = "f4"
    f5: str = "f5"
    f6: str = "f6"
    f7: str = "f7"
    f8: str = "f8"
    f9: str = "f9"
    f10: str = "f10"
    f11: str = "f11"
    f12: str = "f12"

    # Symbol keys
    backtick: str = "`"
    hyphen: str = "-"
    equals: str = "="
    leftbracket: str = "["
    rightbracket: str = "]"
    backslash: str = "\\"
    semicolon: str = ";"
    quote: str = "'"
    comma: str = ","
    period: str = "."
    slash: str = "/"
    exclamation: str = "!"
    at: str = "@"
    hash: str = "#"
    dollar: str = "$"
    percent: str = "%"
    caret: str = "^"
    ampersand: str = "&"
    asterisk: str = "*"
    leftparen: str = "("
    rightparen: str = ")"
    underscore: str = "_"
    plus: str = "+"
    pipe: str = "|"
    tilde: str = "~"
    leftbrace: str = "{"
    rightbrace: str = "}"
    colon: str = ":"
    lessthan: str = "<"
    greaterthan: str = ">"
    question: str = "?"

    # Single modifiers
    @staticmethod
    def ctrl(key: str) -> str:
        return f"ctrl+{key}"

    @staticmethod
    def shift(key: str) -> str:
        return f"shift+{key}"

    @staticmethod
    def alt(key: str) -> str:
        return f"alt+{key}"

    # Combined modifiers
    @staticmethod
    def ctrl_shift(key: str) -> str:
        return f"ctrl+shift+{key}"

    @staticmethod
    def shift_ctrl(key: str) -> str:
        return f"shift+ctrl+{key}"

    @staticmethod
    def ctrl_alt(key: str) -> str:
        return f"ctrl+alt+{key}"

    @staticmethod
    def alt_ctrl(key: str) -> str:
        return f"alt+ctrl+{key}"

    @staticmethod
    def shift_alt(key: str) -> str:
        return f"shift+alt+{key}"

    @staticmethod
    def alt_shift(key: str) -> str:
        return f"alt+shift+{key}"

    # Triple modifiers
    @staticmethod
    def ctrl_shift_alt(key: str) -> str:
        return f"ctrl+shift+alt+{key}"


# =============================================================================
# Constants
# =============================================================================

SYMBOL_KEYS: frozenset[str] = frozenset(
    [
        "`",
        "-",
        "=",
        "[",
        "]",
        "\\",
        ";",
        "'",
        ",",
        ".",
        "/",
        "!",
        "@",
        "#",
        "$",
        "%",
        "^",
        "&",
        "*",
        "(",
        ")",
        "_",
        "+",
        "|",
        "~",
        "{",
        "}",
        ":",
        "<",
        ">",
        "?",
    ]
)

MODIFIERS: dict[str, int] = {
    "shift": 1,
    "alt": 2,
    "ctrl": 4,
}

LOCK_MASK: int = 64 + 128  # Caps Lock + Num Lock

CODEPOINTS: dict[str, int] = {
    "escape": 27,
    "tab": 9,
    "enter": 13,
    "space": 32,
    "backspace": 127,
    "kp_enter": 57414,  # Numpad Enter (Kitty protocol)
}

ARROW_CODEPOINTS: dict[str, int] = {
    "up": -1,
    "down": -2,
    "right": -3,
    "left": -4,
}

FUNCTIONAL_CODEPOINTS: dict[str, int] = {
    "delete": -10,
    "insert": -11,
    "pageUp": -12,
    "pageDown": -13,
    "home": -14,
    "end": -15,
}

LEGACY_KEY_SEQUENCES: dict[str, list[str]] = {
    "up": ["\x1b[A", "\x1bOA"],
    "down": ["\x1b[B", "\x1bOB"],
    "right": ["\x1b[C", "\x1bOC"],
    "left": ["\x1b[D", "\x1bOD"],
    "home": ["\x1b[H", "\x1bOH", "\x1b[1~", "\x1b[7~"],
    "end": ["\x1b[F", "\x1bOF", "\x1b[4~", "\x1b[8~"],
    "insert": ["\x1b[2~"],
    "delete": ["\x1b[3~"],
    "pageUp": ["\x1b[5~", "\x1b[[5~"],
    "pageDown": ["\x1b[6~", "\x1b[[6~"],
    "clear": ["\x1b[E", "\x1bOE"],
    "f1": ["\x1bOP", "\x1b[11~", "\x1b[[A"],
    "f2": ["\x1bOQ", "\x1b[12~", "\x1b[[B"],
    "f3": ["\x1bOR", "\x1b[13~", "\x1b[[C"],
    "f4": ["\x1bOS", "\x1b[14~", "\x1b[[D"],
    "f5": ["\x1b[15~", "\x1b[[E"],
    "f6": ["\x1b[17~"],
    "f7": ["\x1b[18~"],
    "f8": ["\x1b[19~"],
    "f9": ["\x1b[20~"],
    "f10": ["\x1b[21~"],
    "f11": ["\x1b[23~"],
    "f12": ["\x1b[24~"],
}

LEGACY_SHIFT_SEQUENCES: dict[str, list[str]] = {
    "up": ["\x1b[a"],
    "down": ["\x1b[b"],
    "right": ["\x1b[c"],
    "left": ["\x1b[d"],
    "clear": ["\x1b[e"],
    "insert": ["\x1b[2$"],
    "delete": ["\x1b[3$"],
    "pageUp": ["\x1b[5$"],
    "pageDown": ["\x1b[6$"],
    "home": ["\x1b[7$"],
    "end": ["\x1b[8$"],
}

LEGACY_CTRL_SEQUENCES: dict[str, list[str]] = {
    "up": ["\x1bOa"],
    "down": ["\x1bOb"],
    "right": ["\x1bOc"],
    "left": ["\x1bOd"],
    "clear": ["\x1bOe"],
    "insert": ["\x1b[2^"],
    "delete": ["\x1b[3^"],
    "pageUp": ["\x1b[5^"],
    "pageDown": ["\x1b[6^"],
    "home": ["\x1b[7^"],
    "end": ["\x1b[8^"],
}

LEGACY_SEQUENCE_KEY_IDS: dict[str, str] = {
    "\x1bOA": "up",
    "\x1bOB": "down",
    "\x1bOC": "right",
    "\x1bOD": "left",
    "\x1bOH": "home",
    "\x1bOF": "end",
    "\x1b[E": "clear",
    "\x1bOE": "clear",
    "\x1bOe": "ctrl+clear",
    "\x1b[e": "shift+clear",
    "\x1b[2~": "insert",
    "\x1b[2$": "shift+insert",
    "\x1b[2^": "ctrl+insert",
    "\x1b[3$": "shift+delete",
    "\x1b[3^": "ctrl+delete",
    "\x1b[[5~": "pageUp",
    "\x1b[[6~": "pageDown",
    "\x1b[a": "shift+up",
    "\x1b[b": "shift+down",
    "\x1b[c": "shift+right",
    "\x1b[d": "shift+left",
    "\x1bOa": "ctrl+up",
    "\x1bOb": "ctrl+down",
    "\x1bOc": "ctrl+right",
    "\x1bOd": "ctrl+left",
    "\x1b[5$": "shift+pageUp",
    "\x1b[6$": "shift+pageDown",
    "\x1b[7$": "shift+home",
    "\x1b[8$": "shift+end",
    "\x1b[5^": "ctrl+pageUp",
    "\x1b[6^": "ctrl+pageDown",
    "\x1b[7^": "ctrl+home",
    "\x1b[8^": "ctrl+end",
    "\x1bOP": "f1",
    "\x1bOQ": "f2",
    "\x1bOR": "f3",
    "\x1bOS": "f4",
    "\x1b[11~": "f1",
    "\x1b[12~": "f2",
    "\x1b[13~": "f3",
    "\x1b[14~": "f4",
    "\x1b[[A": "f1",
    "\x1b[[B": "f2",
    "\x1b[[C": "f3",
    "\x1b[[D": "f4",
    "\x1b[[E": "f5",
    "\x1b[15~": "f5",
    "\x1b[17~": "f6",
    "\x1b[18~": "f7",
    "\x1b[19~": "f8",
    "\x1b[20~": "f9",
    "\x1b[21~": "f10",
    "\x1b[23~": "f11",
    "\x1b[24~": "f12",
    "\x1bb": "alt+left",
    "\x1bf": "alt+right",
    "\x1bp": "alt+up",
    "\x1bn": "alt+down",
}


# =============================================================================
# Internal Helpers
# =============================================================================


def _matches_legacy_sequence(data: str, sequences: list[str]) -> bool:
    return data in sequences


def _matches_legacy_modifier_sequence(data: str, key: str, modifier: int) -> bool:
    if modifier == MODIFIERS["shift"]:
        seqs = LEGACY_SHIFT_SEQUENCES.get(key)
        if seqs is not None:
            return _matches_legacy_sequence(data, seqs)
        return False
    if modifier == MODIFIERS["ctrl"]:
        seqs = LEGACY_CTRL_SEQUENCES.get(key)
        if seqs is not None:
            return _matches_legacy_sequence(data, seqs)
        return False
    return False


# =============================================================================
# Kitty Protocol Parsing
# =============================================================================

# Compiled regex patterns for Kitty sequence parsing
_CSI_U_RE = re.compile(r"^\x1b\[(\d+)(?::(\d*))?(?::(\d+))?(?:;(\d+))?(?::(\d+))?u$")
_ARROW_RE = re.compile(r"^\x1b\[1;(\d+)(?::(\d+))?([ABCD])$")
_FUNC_RE = re.compile(r"^\x1b\[(\d+)(?:;(\d+))?(?::(\d+))?~$")
_HOME_END_RE = re.compile(r"^\x1b\[1;(\d+)(?::(\d+))?([HF])$")
_MODIFY_OTHER_KEYS_RE = re.compile(r"^\x1b\[27;(\d+);(\d+)~$")

# Store the last parsed event type for is_key_release() to query
_last_event_type: KeyEventType = "press"


class _ParsedKittySequence:
    """Parsed result from a Kitty keyboard protocol sequence."""

    __slots__ = ("base_layout_key", "codepoint", "event_type", "modifier", "shifted_key")

    def __init__(
        self,
        codepoint: int,
        modifier: int,
        event_type: KeyEventType,
        shifted_key: int | None = None,
        base_layout_key: int | None = None,
    ) -> None:
        self.codepoint = codepoint
        self.shifted_key = shifted_key
        self.base_layout_key = base_layout_key
        self.modifier = modifier
        self.event_type = event_type


def _parse_event_type(event_type_str: str | None) -> KeyEventType:
    if not event_type_str:
        return "press"
    event_type = int(event_type_str)
    if event_type == 2:
        return "repeat"
    if event_type == 3:
        return "release"
    return "press"


def is_key_release(data: str) -> bool:
    """Check if the last parsed key event was a key release.
    Only meaningful when Kitty keyboard protocol with flag 2 is active.
    """
    # Don't treat bracketed paste content as key release
    if "\x1b[200~" in data:
        return False

    # Quick check: release events with flag 2 contain ":3"
    return any(suffix in data for suffix in (":3u", ":3~", ":3A", ":3B", ":3C", ":3D", ":3H", ":3F"))


def is_key_repeat(data: str) -> bool:
    """Check if the last parsed key event was a key repeat.
    Only meaningful when Kitty keyboard protocol with flag 2 is active.
    """
    # Don't treat bracketed paste content as key repeat
    if "\x1b[200~" in data:
        return False

    return any(suffix in data for suffix in (":2u", ":2~", ":2A", ":2B", ":2C", ":2D", ":2H", ":2F"))


def _parse_kitty_sequence(data: str) -> _ParsedKittySequence | None:
    """Parse a Kitty keyboard protocol sequence."""
    global _last_event_type

    # CSI u format with alternate keys (flag 4)
    m = _CSI_U_RE.match(data)
    if m:
        codepoint = int(m.group(1))
        shifted_key: int | None = None
        if m.group(2) is not None and len(m.group(2)) > 0:
            shifted_key = int(m.group(2))
        base_layout_key: int | None = None
        if m.group(3) is not None:
            base_layout_key = int(m.group(3))
        mod_value = int(m.group(4)) if m.group(4) else 1
        event_type = _parse_event_type(m.group(5))
        _last_event_type = event_type
        return _ParsedKittySequence(
            codepoint=codepoint,
            modifier=mod_value - 1,
            event_type=event_type,
            shifted_key=shifted_key,
            base_layout_key=base_layout_key,
        )

    # Arrow keys with modifier
    m = _ARROW_RE.match(data)
    if m:
        mod_value = int(m.group(1))
        event_type = _parse_event_type(m.group(2))
        arrow_codes: dict[str, int] = {"A": -1, "B": -2, "C": -3, "D": -4}
        _last_event_type = event_type
        return _ParsedKittySequence(
            codepoint=arrow_codes[m.group(3)],
            modifier=mod_value - 1,
            event_type=event_type,
        )

    # Functional keys
    m = _FUNC_RE.match(data)
    if m:
        key_num = int(m.group(1))
        mod_value = int(m.group(2)) if m.group(2) else 1
        event_type = _parse_event_type(m.group(3))
        func_codes: dict[int, int] = {
            2: FUNCTIONAL_CODEPOINTS["insert"],
            3: FUNCTIONAL_CODEPOINTS["delete"],
            5: FUNCTIONAL_CODEPOINTS["pageUp"],
            6: FUNCTIONAL_CODEPOINTS["pageDown"],
            7: FUNCTIONAL_CODEPOINTS["home"],
            8: FUNCTIONAL_CODEPOINTS["end"],
        }
        func_codepoint = func_codes.get(key_num)
        if func_codepoint is not None:
            _last_event_type = event_type
            return _ParsedKittySequence(
                codepoint=func_codepoint,
                modifier=mod_value - 1,
                event_type=event_type,
            )

    # Home/End with modifier
    m = _HOME_END_RE.match(data)
    if m:
        mod_value = int(m.group(1))
        event_type = _parse_event_type(m.group(2))
        codepoint = FUNCTIONAL_CODEPOINTS["home"] if m.group(3) == "H" else FUNCTIONAL_CODEPOINTS["end"]
        _last_event_type = event_type
        return _ParsedKittySequence(
            codepoint=codepoint,
            modifier=mod_value - 1,
            event_type=event_type,
        )

    return None


def _matches_kitty_sequence(data: str, expected_codepoint: int, expected_modifier: int) -> bool:
    """Match input against a Kitty protocol sequence."""
    parsed = _parse_kitty_sequence(data)
    if parsed is None:
        return False
    actual_mod = parsed.modifier & ~LOCK_MASK
    expected_mod = expected_modifier & ~LOCK_MASK

    # Check if modifiers match
    if actual_mod != expected_mod:
        return False

    # Primary match: codepoint matches directly
    if parsed.codepoint == expected_codepoint:
        return True

    # Alternate match: use base layout key for non-Latin keyboard layouts.
    if parsed.base_layout_key is not None and parsed.base_layout_key == expected_codepoint:
        cp = parsed.codepoint
        is_latin_letter = 97 <= cp <= 122  # a-z
        is_known_symbol = chr(cp) in SYMBOL_KEYS if 0 <= cp <= 0x10FFFF else False
        if not is_latin_letter and not is_known_symbol:
            return True

    return False


def _matches_modify_other_keys(data: str, expected_keycode: int, expected_modifier: int) -> bool:
    """Match xterm modifyOtherKeys format: CSI 27 ; modifiers ; keycode ~"""
    m = _MODIFY_OTHER_KEYS_RE.match(data)
    if not m:
        return False
    mod_value = int(m.group(1))
    keycode = int(m.group(2))
    actual_mod = mod_value - 1
    return keycode == expected_keycode and actual_mod == expected_modifier


# =============================================================================
# Generic Key Matching
# =============================================================================


def _raw_ctrl_char(key: str) -> str | None:
    """Get the control character for a key.
    Uses the universal formula: code & 0x1f (mask to lower 5 bits)
    """
    char = key.lower()
    code = ord(char)
    if (97 <= code <= 122) or char in ("[", "\\", "]", "_"):
        return chr(code & 0x1F)
    # Handle - as _ (same physical key on US keyboards)
    if char == "-":
        return chr(31)  # Same as Ctrl+_
    return None


def _parse_key_id(key_id: str) -> dict[str, object] | None:
    """Parse 'ctrl+shift+a' into {key, ctrl, shift, alt}."""
    parts = key_id.lower().split("+")
    key = parts[-1] if parts else None
    if not key:
        return None
    return {
        "key": key,
        "ctrl": "ctrl" in parts,
        "shift": "shift" in parts,
        "alt": "alt" in parts,
    }


def matches_key(data: str, key_id: str) -> bool:
    """Match input data against a key identifier string.

    Supported key identifiers:
    - Single keys: "escape", "tab", "enter", "backspace", "delete", "home", "end", "space"
    - Arrow keys: "up", "down", "left", "right"
    - Ctrl combinations: "ctrl+c", "ctrl+z", etc.
    - Shift combinations: "shift+tab", "shift+enter"
    - Alt combinations: "alt+enter", "alt+backspace"
    - Combined modifiers: "shift+ctrl+p", "ctrl+alt+x"

    Use the Key helper for autocomplete: Key.ctrl("c"), Key.escape, Key.ctrl_shift("p")

    Args:
        data: Raw input data from terminal
        key_id: Key identifier (e.g., "ctrl+c", "escape", Key.ctrl("c"))
    """
    parsed = _parse_key_id(key_id)
    if parsed is None:
        return False

    key: str = parsed["key"]  # type: ignore[assignment]
    ctrl: bool = parsed["ctrl"]  # type: ignore[assignment]
    shift: bool = parsed["shift"]  # type: ignore[assignment]
    alt: bool = parsed["alt"]  # type: ignore[assignment]

    modifier = 0
    if shift:
        modifier |= MODIFIERS["shift"]
    if alt:
        modifier |= MODIFIERS["alt"]
    if ctrl:
        modifier |= MODIFIERS["ctrl"]

    # --- Special keys ---

    if key in ("escape", "esc"):
        if modifier != 0:
            return False
        return data == "\x1b" or _matches_kitty_sequence(data, CODEPOINTS["escape"], 0)

    if key == "space":
        if not _kitty_protocol_active:
            if ctrl and not alt and not shift and data == "\x00":
                return True
            if alt and not ctrl and not shift and data == "\x1b ":
                return True
        if modifier == 0:
            return data == " " or _matches_kitty_sequence(data, CODEPOINTS["space"], 0)
        return _matches_kitty_sequence(data, CODEPOINTS["space"], modifier)

    if key == "tab":
        if shift and not ctrl and not alt:
            return data == "\x1b[Z" or _matches_kitty_sequence(data, CODEPOINTS["tab"], MODIFIERS["shift"])
        if modifier == 0:
            return data == "\t" or _matches_kitty_sequence(data, CODEPOINTS["tab"], 0)
        return _matches_kitty_sequence(data, CODEPOINTS["tab"], modifier)

    if key in ("enter", "return"):
        if shift and not ctrl and not alt:
            # CSI u sequences (standard Kitty protocol)
            if _matches_kitty_sequence(data, CODEPOINTS["enter"], MODIFIERS["shift"]) or _matches_kitty_sequence(
                data, CODEPOINTS["kp_enter"], MODIFIERS["shift"]
            ):
                return True
            # xterm modifyOtherKeys format
            if _matches_modify_other_keys(data, CODEPOINTS["enter"], MODIFIERS["shift"]):
                return True
            # When Kitty protocol is active, legacy sequences are custom terminal mappings
            if _kitty_protocol_active:
                return data == "\x1b\r" or data == "\n"
            return False

        if alt and not ctrl and not shift:
            if _matches_kitty_sequence(data, CODEPOINTS["enter"], MODIFIERS["alt"]) or _matches_kitty_sequence(
                data, CODEPOINTS["kp_enter"], MODIFIERS["alt"]
            ):
                return True
            if _matches_modify_other_keys(data, CODEPOINTS["enter"], MODIFIERS["alt"]):
                return True
            if not _kitty_protocol_active:
                return data == "\x1b\r"
            return False

        if modifier == 0:
            return (
                data == "\r"
                or (not _kitty_protocol_active and data == "\n")
                or data == "\x1bOM"  # SS3 M (numpad enter in some terminals)
                or _matches_kitty_sequence(data, CODEPOINTS["enter"], 0)
                or _matches_kitty_sequence(data, CODEPOINTS["kp_enter"], 0)
            )
        return _matches_kitty_sequence(data, CODEPOINTS["enter"], modifier) or _matches_kitty_sequence(
            data, CODEPOINTS["kp_enter"], modifier
        )

    if key == "backspace":
        if alt and not ctrl and not shift:
            if data == "\x1b\x7f" or data == "\x1b\x08":
                return True
            return _matches_kitty_sequence(data, CODEPOINTS["backspace"], MODIFIERS["alt"])
        if modifier == 0:
            return data == "\x7f" or data == "\x08" or _matches_kitty_sequence(data, CODEPOINTS["backspace"], 0)
        return _matches_kitty_sequence(data, CODEPOINTS["backspace"], modifier)

    if key == "insert":
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["insert"]) or _matches_kitty_sequence(
                data, FUNCTIONAL_CODEPOINTS["insert"], 0
            )
        if _matches_legacy_modifier_sequence(data, "insert", modifier):
            return True
        return _matches_kitty_sequence(data, FUNCTIONAL_CODEPOINTS["insert"], modifier)

    if key == "delete":
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["delete"]) or _matches_kitty_sequence(
                data, FUNCTIONAL_CODEPOINTS["delete"], 0
            )
        if _matches_legacy_modifier_sequence(data, "delete", modifier):
            return True
        return _matches_kitty_sequence(data, FUNCTIONAL_CODEPOINTS["delete"], modifier)

    if key == "clear":
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["clear"])
        return _matches_legacy_modifier_sequence(data, "clear", modifier)

    if key == "home":
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["home"]) or _matches_kitty_sequence(
                data, FUNCTIONAL_CODEPOINTS["home"], 0
            )
        if _matches_legacy_modifier_sequence(data, "home", modifier):
            return True
        return _matches_kitty_sequence(data, FUNCTIONAL_CODEPOINTS["home"], modifier)

    if key == "end":
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["end"]) or _matches_kitty_sequence(
                data, FUNCTIONAL_CODEPOINTS["end"], 0
            )
        if _matches_legacy_modifier_sequence(data, "end", modifier):
            return True
        return _matches_kitty_sequence(data, FUNCTIONAL_CODEPOINTS["end"], modifier)

    if key == "pageup":
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["pageUp"]) or _matches_kitty_sequence(
                data, FUNCTIONAL_CODEPOINTS["pageUp"], 0
            )
        if _matches_legacy_modifier_sequence(data, "pageUp", modifier):
            return True
        return _matches_kitty_sequence(data, FUNCTIONAL_CODEPOINTS["pageUp"], modifier)

    if key == "pagedown":
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["pageDown"]) or _matches_kitty_sequence(
                data, FUNCTIONAL_CODEPOINTS["pageDown"], 0
            )
        if _matches_legacy_modifier_sequence(data, "pageDown", modifier):
            return True
        return _matches_kitty_sequence(data, FUNCTIONAL_CODEPOINTS["pageDown"], modifier)

    # --- Arrow keys ---

    if key == "up":
        if alt and not ctrl and not shift:
            return data == "\x1bp" or _matches_kitty_sequence(data, ARROW_CODEPOINTS["up"], MODIFIERS["alt"])
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["up"]) or _matches_kitty_sequence(
                data, ARROW_CODEPOINTS["up"], 0
            )
        if _matches_legacy_modifier_sequence(data, "up", modifier):
            return True
        return _matches_kitty_sequence(data, ARROW_CODEPOINTS["up"], modifier)

    if key == "down":
        if alt and not ctrl and not shift:
            return data == "\x1bn" or _matches_kitty_sequence(data, ARROW_CODEPOINTS["down"], MODIFIERS["alt"])
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["down"]) or _matches_kitty_sequence(
                data, ARROW_CODEPOINTS["down"], 0
            )
        if _matches_legacy_modifier_sequence(data, "down", modifier):
            return True
        return _matches_kitty_sequence(data, ARROW_CODEPOINTS["down"], modifier)

    if key == "left":
        if alt and not ctrl and not shift:
            return (
                data == "\x1b[1;3D"
                or (not _kitty_protocol_active and data == "\x1bB")
                or data == "\x1bb"
                or _matches_kitty_sequence(data, ARROW_CODEPOINTS["left"], MODIFIERS["alt"])
            )
        if ctrl and not alt and not shift:
            return (
                data == "\x1b[1;5D"
                or _matches_legacy_modifier_sequence(data, "left", MODIFIERS["ctrl"])
                or _matches_kitty_sequence(data, ARROW_CODEPOINTS["left"], MODIFIERS["ctrl"])
            )
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["left"]) or _matches_kitty_sequence(
                data, ARROW_CODEPOINTS["left"], 0
            )
        if _matches_legacy_modifier_sequence(data, "left", modifier):
            return True
        return _matches_kitty_sequence(data, ARROW_CODEPOINTS["left"], modifier)

    if key == "right":
        if alt and not ctrl and not shift:
            return (
                data == "\x1b[1;3C"
                or (not _kitty_protocol_active and data == "\x1bF")
                or data == "\x1bf"
                or _matches_kitty_sequence(data, ARROW_CODEPOINTS["right"], MODIFIERS["alt"])
            )
        if ctrl and not alt and not shift:
            return (
                data == "\x1b[1;5C"
                or _matches_legacy_modifier_sequence(data, "right", MODIFIERS["ctrl"])
                or _matches_kitty_sequence(data, ARROW_CODEPOINTS["right"], MODIFIERS["ctrl"])
            )
        if modifier == 0:
            return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES["right"]) or _matches_kitty_sequence(
                data, ARROW_CODEPOINTS["right"], 0
            )
        if _matches_legacy_modifier_sequence(data, "right", modifier):
            return True
        return _matches_kitty_sequence(data, ARROW_CODEPOINTS["right"], modifier)

    # --- Function keys ---

    if key in ("f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12"):
        if modifier != 0:
            return False
        return _matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES[key])

    # --- Single letter keys (a-z) and symbols ---

    if len(key) == 1 and ("a" <= key <= "z" or key in SYMBOL_KEYS):
        codepoint = ord(key)
        raw_ctrl = _raw_ctrl_char(key)

        if ctrl and alt and not shift and not _kitty_protocol_active and raw_ctrl:
            # Legacy: ctrl+alt+key is ESC followed by the control character
            return data == f"\x1b{raw_ctrl}"

        if alt and not ctrl and not shift and not _kitty_protocol_active and "a" <= key <= "z" and data == f"\x1b{key}":
            # Legacy: alt+letter is ESC followed by the letter
            return True

        if ctrl and not shift and not alt:
            # Legacy: ctrl+key sends the control character
            if raw_ctrl and data == raw_ctrl:
                return True
            return _matches_kitty_sequence(data, codepoint, MODIFIERS["ctrl"])

        if ctrl and shift and not alt:
            return _matches_kitty_sequence(data, codepoint, MODIFIERS["shift"] + MODIFIERS["ctrl"])

        if shift and not ctrl and not alt:
            # Legacy: shift+letter produces uppercase
            if data == key.upper():
                return True
            return _matches_kitty_sequence(data, codepoint, MODIFIERS["shift"])

        if modifier != 0:
            return _matches_kitty_sequence(data, codepoint, modifier)

        # Check both raw char and Kitty sequence (needed for release events)
        return data == key or _matches_kitty_sequence(data, codepoint, 0)

    return False


def parse_key(data: str) -> str | None:
    """Parse input data and return the key identifier if recognized.

    Args:
        data: Raw input data from terminal

    Returns:
        Key identifier string (e.g., "ctrl+c") or None
    """
    kitty = _parse_kitty_sequence(data)
    if kitty is not None:
        codepoint = kitty.codepoint
        base_layout_key = kitty.base_layout_key
        modifier = kitty.modifier
        mods: list[str] = []
        effective_mod = modifier & ~LOCK_MASK
        if effective_mod & MODIFIERS["shift"]:
            mods.append("shift")
        if effective_mod & MODIFIERS["ctrl"]:
            mods.append("ctrl")
        if effective_mod & MODIFIERS["alt"]:
            mods.append("alt")

        # Use base layout key only when codepoint is not a recognized Latin
        # letter (a-z) or symbol. For those, the codepoint is authoritative.
        is_latin_letter = 97 <= codepoint <= 122  # a-z
        is_known_symbol = chr(codepoint) in SYMBOL_KEYS if 0 <= codepoint <= 0x10FFFF else False
        effective_codepoint = (
            codepoint
            if is_latin_letter or is_known_symbol
            else (base_layout_key if base_layout_key is not None else codepoint)
        )

        key_name: str | None = None
        if effective_codepoint == CODEPOINTS["escape"]:
            key_name = "escape"
        elif effective_codepoint == CODEPOINTS["tab"]:
            key_name = "tab"
        elif effective_codepoint in (CODEPOINTS["enter"], CODEPOINTS["kp_enter"]):
            key_name = "enter"
        elif effective_codepoint == CODEPOINTS["space"]:
            key_name = "space"
        elif effective_codepoint == CODEPOINTS["backspace"]:
            key_name = "backspace"
        elif effective_codepoint == FUNCTIONAL_CODEPOINTS["delete"]:
            key_name = "delete"
        elif effective_codepoint == FUNCTIONAL_CODEPOINTS["insert"]:
            key_name = "insert"
        elif effective_codepoint == FUNCTIONAL_CODEPOINTS["home"]:
            key_name = "home"
        elif effective_codepoint == FUNCTIONAL_CODEPOINTS["end"]:
            key_name = "end"
        elif effective_codepoint == FUNCTIONAL_CODEPOINTS["pageUp"]:
            key_name = "pageUp"
        elif effective_codepoint == FUNCTIONAL_CODEPOINTS["pageDown"]:
            key_name = "pageDown"
        elif effective_codepoint == ARROW_CODEPOINTS["up"]:
            key_name = "up"
        elif effective_codepoint == ARROW_CODEPOINTS["down"]:
            key_name = "down"
        elif effective_codepoint == ARROW_CODEPOINTS["left"]:
            key_name = "left"
        elif effective_codepoint == ARROW_CODEPOINTS["right"]:
            key_name = "right"
        elif (97 <= effective_codepoint <= 122) or (
            0 <= effective_codepoint <= 0x10FFFF and chr(effective_codepoint) in SYMBOL_KEYS
        ):
            key_name = chr(effective_codepoint)

        if key_name is not None:
            return f"{'+'.join(mods)}+{key_name}" if mods else key_name

    # Mode-aware legacy sequences
    if _kitty_protocol_active and (data == "\x1b\r" or data == "\n"):
        return "shift+enter"

    legacy_key_id = LEGACY_SEQUENCE_KEY_IDS.get(data)
    if legacy_key_id is not None:
        return legacy_key_id

    # Legacy sequences
    if data == "\x1b":
        return "escape"
    if data == "\x1c":
        return "ctrl+\\"
    if data == "\x1d":
        return "ctrl+]"
    if data == "\x1f":
        return "ctrl+-"
    if data == "\x1b\x1b":
        return "ctrl+alt+["
    if data == "\x1b\x1c":
        return "ctrl+alt+\\"
    if data == "\x1b\x1d":
        return "ctrl+alt+]"
    if data == "\x1b\x1f":
        return "ctrl+alt+-"
    if data == "\t":
        return "tab"
    if data == "\r" or (not _kitty_protocol_active and data == "\n") or data == "\x1bOM":
        return "enter"
    if data == "\x00":
        return "ctrl+space"
    if data == " ":
        return "space"
    if data == "\x7f" or data == "\x08":
        return "backspace"
    if data == "\x1b[Z":
        return "shift+tab"
    if not _kitty_protocol_active and data == "\x1b\r":
        return "alt+enter"
    if not _kitty_protocol_active and data == "\x1b ":
        return "alt+space"
    if data == "\x1b\x7f" or data == "\x1b\x08":
        return "alt+backspace"
    if not _kitty_protocol_active and data == "\x1bB":
        return "alt+left"
    if not _kitty_protocol_active and data == "\x1bF":
        return "alt+right"
    if not _kitty_protocol_active and len(data) == 2 and data[0] == "\x1b":
        code = ord(data[1])
        if 1 <= code <= 26:
            return f"ctrl+alt+{chr(code + 96)}"
        # Legacy alt+letter (ESC followed by letter a-z)
        if 97 <= code <= 122:
            return f"alt+{chr(code)}"
    if data == "\x1b[A":
        return "up"
    if data == "\x1b[B":
        return "down"
    if data == "\x1b[C":
        return "right"
    if data == "\x1b[D":
        return "left"
    if data in ("\x1b[H", "\x1bOH"):
        return "home"
    if data in ("\x1b[F", "\x1bOF"):
        return "end"
    if data == "\x1b[3~":
        return "delete"
    if data == "\x1b[5~":
        return "pageUp"
    if data == "\x1b[6~":
        return "pageDown"

    # Raw Ctrl+letter
    if len(data) == 1:
        code = ord(data)
        if 1 <= code <= 26:
            return f"ctrl+{chr(code + 96)}"
        if 32 <= code <= 126:
            return data

    return None
