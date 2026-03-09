"""StdinBuffer buffers input and emits complete sequences.

This is necessary because stdin data events can arrive in partial chunks,
especially for escape sequences like mouse events. Without buffering,
partial sequences can be misinterpreted as regular keypresses.

For example, the mouse SGR sequence ``\\x1b[<35;20;5m`` might arrive as:

- Event 1: ``\\x1b``
- Event 2: ``[<35``
- Event 3: ``;20;5m``

The buffer accumulates these until a complete sequence is detected.
Call the ``process()`` method to feed input data.

Based on code from OpenTUI (https://github.com/anomalyco/opentui)
MIT License - Copyright (c) 2025 opentui
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypedDict

ESC = "\x1b"
BRACKETED_PASTE_START = "\x1b[200~"
BRACKETED_PASTE_END = "\x1b[201~"

_SGR_MOUSE_RE = re.compile(r"^<\d+;\d+;\d+[Mm]$")
_SGR_MOUSE_PARTS_RE = re.compile(r"^\d+$")


def _is_complete_sequence(data: str) -> Literal["complete", "incomplete", "not-escape"]:
    """Check if a string is a complete escape sequence or needs more data."""
    if not data.startswith(ESC):
        return "not-escape"

    if len(data) == 1:
        return "incomplete"

    after_esc = data[1:]

    # CSI sequences: ESC [
    if after_esc.startswith("["):
        # Check for old-style mouse sequence: ESC[M + 3 bytes
        if after_esc.startswith("[M"):
            # Old-style mouse needs ESC[M + 3 bytes = 6 total
            return "complete" if len(data) >= 6 else "incomplete"
        return _is_complete_csi_sequence(data)

    # OSC sequences: ESC ]
    if after_esc.startswith("]"):
        return _is_complete_osc_sequence(data)

    # DCS sequences: ESC P ... ESC \
    if after_esc.startswith("P"):
        return _is_complete_dcs_sequence(data)

    # APC sequences: ESC _ ... ESC \
    if after_esc.startswith("_"):
        return _is_complete_apc_sequence(data)

    # SS3 sequences: ESC O
    if after_esc.startswith("O"):
        # ESC O followed by a single character
        return "complete" if len(after_esc) >= 2 else "incomplete"

    # Meta key sequences: ESC followed by a single character
    if len(after_esc) == 1:
        return "complete"

    # Unknown escape sequence - treat as complete
    return "complete"


def _is_complete_csi_sequence(data: str) -> Literal["complete", "incomplete"]:
    """Check if CSI sequence is complete.

    CSI sequences: ESC [ ... followed by a final byte (0x40-0x7E).
    """
    if not data.startswith(f"{ESC}["):
        return "complete"

    # Need at least ESC [ and one more character
    if len(data) < 3:
        return "incomplete"

    payload = data[2:]

    # CSI sequences end with a byte in the range 0x40-0x7E (@-~)
    last_char = payload[-1]
    last_char_code = ord(last_char)

    if 0x40 <= last_char_code <= 0x7E:
        # Special handling for SGR mouse sequences
        # Format: ESC[<B;X;Ym or ESC[<B;X;YM
        if payload.startswith("<"):
            # Must have format: <digits;digits;digits[Mm]
            if _SGR_MOUSE_RE.match(payload):
                return "complete"
            # If it ends with M or m but doesn't match the pattern, still incomplete
            if last_char in ("M", "m"):
                # Check if we have the right structure
                parts = payload[1:-1].split(";")
                if len(parts) == 3 and all(_SGR_MOUSE_PARTS_RE.match(p) for p in parts):
                    return "complete"

            return "incomplete"

        return "complete"

    return "incomplete"


def _is_complete_osc_sequence(data: str) -> Literal["complete", "incomplete"]:
    """Check if OSC sequence is complete.

    OSC sequences: ESC ] ... ST (where ST is ESC \\ or BEL).
    """
    if not data.startswith(f"{ESC}]"):
        return "complete"

    # OSC sequences end with ST (ESC \) or BEL (\x07)
    if data.endswith(f"{ESC}\\") or data.endswith("\x07"):
        return "complete"

    return "incomplete"


def _is_complete_dcs_sequence(data: str) -> Literal["complete", "incomplete"]:
    """Check if DCS (Device Control String) sequence is complete.

    DCS sequences: ESC P ... ST (where ST is ESC \\).
    """
    if not data.startswith(f"{ESC}P"):
        return "complete"

    if data.endswith(f"{ESC}\\"):
        return "complete"

    return "incomplete"


def _is_complete_apc_sequence(data: str) -> Literal["complete", "incomplete"]:
    """Check if APC (Application Program Command) sequence is complete.

    APC sequences: ESC _ ... ST (where ST is ESC \\).
    """
    if not data.startswith(f"{ESC}_"):
        return "complete"

    if data.endswith(f"{ESC}\\"):
        return "complete"

    return "incomplete"


def _extract_complete_sequences(buffer: str) -> tuple[list[str], str]:
    """Split accumulated buffer into complete sequences.

    Returns a tuple of (sequences, remainder).
    """
    sequences: list[str] = []
    pos = 0

    while pos < len(buffer):
        remaining = buffer[pos:]

        # Try to extract a sequence starting at this position
        if remaining.startswith(ESC):
            # Find the end of this escape sequence
            seq_end = 1
            while seq_end <= len(remaining):
                candidate = remaining[:seq_end]
                status = _is_complete_sequence(candidate)

                if status == "complete":
                    sequences.append(candidate)
                    pos += seq_end
                    break
                elif status == "incomplete":
                    seq_end += 1
                else:
                    # Should not happen when starting with ESC
                    sequences.append(candidate)
                    pos += seq_end
                    break
            else:
                # seq_end > len(remaining) — incomplete sequence at end
                return sequences, remaining
        else:
            # Not an escape sequence - take a single character
            sequences.append(remaining[0])
            pos += 1

    return sequences, ""


class StdinBufferEventMap(TypedDict, total=False):
    """Event map for StdinBuffer.

    Maps event names to their argument types, mirroring the TS
    ``StdinBufferEventMap`` type used with ``EventEmitter``.
    In the Python port the buffer uses ``on_data`` / ``on_paste``
    callbacks instead of an emitter, but this type is kept for
    API parity.
    """

    data: tuple[str]
    paste: tuple[str]


@dataclass
class StdinBufferOptions:
    """Options for StdinBuffer."""

    timeout: int = 10
    """Maximum time to wait for sequence completion in milliseconds."""


class StdinBuffer:
    """Buffers stdin input and emits complete sequences.

    Handles partial escape sequences that arrive across multiple chunks.
    Uses callback attributes instead of EventEmitter:
    - ``on_data``: called with each complete sequence
    - ``on_paste``: called with pasted content (bracketed paste mode)
    """

    def __init__(self, options: StdinBufferOptions | None = None) -> None:
        opts = options or StdinBufferOptions()
        self._lock = threading.Lock()
        self._buffer: str = ""
        self._timer: threading.Timer | None = None
        self._timeout_ms: int = opts.timeout
        self._paste_mode: bool = False
        self._paste_buffer: str = ""

        self.on_data: Callable[[str], None] | None = None
        self.on_paste: Callable[[str], None] | None = None

    def _emit_data(self, data: str) -> None:
        if self.on_data is not None:
            self.on_data(data)

    def _emit_paste(self, data: str) -> None:
        if self.on_paste is not None:
            self.on_paste(data)

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _schedule_flush(self) -> None:
        def _on_timeout() -> None:
            with self._lock:
                flushed = self._flush_unlocked()
            for sequence in flushed:
                self._emit_data(sequence)

        self._timer = threading.Timer(self._timeout_ms / 1000.0, _on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def process(self, data: str) -> None:
        """Feed input data, emitting complete sequences via on_data callback."""
        with self._lock:
            self._process_unlocked(data)

    def _process_unlocked(self, data: str) -> None:
        """Internal process without lock — caller must hold self._lock."""
        # Clear any pending timeout
        self._cancel_timer()

        if len(data) == 0 and len(self._buffer) == 0:
            self._emit_data("")
            return

        self._buffer += data

        if self._paste_mode:
            self._paste_buffer += self._buffer
            self._buffer = ""

            end_index = self._paste_buffer.find(BRACKETED_PASTE_END)
            if end_index != -1:
                pasted_content = self._paste_buffer[:end_index]
                remaining = self._paste_buffer[end_index + len(BRACKETED_PASTE_END) :]

                self._paste_mode = False
                self._paste_buffer = ""

                self._emit_paste(pasted_content)

                if len(remaining) > 0:
                    self._process_unlocked(remaining)
            return

        start_index = self._buffer.find(BRACKETED_PASTE_START)
        if start_index != -1:
            if start_index > 0:
                before_paste = self._buffer[:start_index]
                sequences, _ = _extract_complete_sequences(before_paste)
                for sequence in sequences:
                    self._emit_data(sequence)

            self._buffer = self._buffer[start_index + len(BRACKETED_PASTE_START) :]
            self._paste_mode = True
            self._paste_buffer = self._buffer
            self._buffer = ""

            end_index = self._paste_buffer.find(BRACKETED_PASTE_END)
            if end_index != -1:
                pasted_content = self._paste_buffer[:end_index]
                remaining = self._paste_buffer[end_index + len(BRACKETED_PASTE_END) :]

                self._paste_mode = False
                self._paste_buffer = ""

                self._emit_paste(pasted_content)

                if len(remaining) > 0:
                    self._process_unlocked(remaining)
            return

        sequences, remainder = _extract_complete_sequences(self._buffer)
        self._buffer = remainder

        for sequence in sequences:
            self._emit_data(sequence)

        if len(self._buffer) > 0:
            self._schedule_flush()

    def flush(self) -> list[str]:
        """Flush remaining buffer, returning any buffered data as sequences."""
        with self._lock:
            return self._flush_unlocked()

    def _flush_unlocked(self) -> list[str]:
        """Internal flush without lock — caller must hold self._lock."""
        self._cancel_timer()

        if len(self._buffer) == 0:
            return []

        sequences = [self._buffer]
        self._buffer = ""
        return sequences

    def clear(self) -> None:
        """Clear buffer and all state."""
        with self._lock:
            self._cancel_timer()
            self._buffer = ""
            self._paste_mode = False
            self._paste_buffer = ""

    def get_buffer(self) -> str:
        """Get current buffer contents."""
        return self._buffer

    def destroy(self) -> None:
        """Clean up resources."""
        self.clear()
