"""Terminal abstraction for TUI applications.

Port of terminal.ts. Provides a Terminal protocol and ProcessTerminal
implementation that handles raw mode, Kitty keyboard protocol negotiation,
bracketed paste, and ANSI escape sequence output.
"""

from __future__ import annotations

import asyncio
import os
import re
import select
import signal
import sys
import termios
import threading
import tty
from collections.abc import Callable
from typing import Any, Protocol

from pi_tui.keys import set_kitty_protocol_active
from pi_tui.stdin_buffer import StdinBuffer, StdinBufferOptions


class Terminal(Protocol):
    """Minimal terminal interface for TUI."""

    def start(self, on_input: Callable[[str], None], on_resize: Callable[[], None]) -> None:
        """Start the terminal with input and resize handlers."""
        ...

    def stop(self) -> None:
        """Stop the terminal and restore state."""
        ...

    async def drain_input(self, max_ms: int = 1000, idle_ms: int = 50) -> None:
        """Drain stdin before exiting to prevent Kitty key release events
        from leaking to the parent shell over slow SSH connections.

        Args:
            max_ms: Maximum time to drain (default: 1000ms).
            idle_ms: Exit early if no input arrives within this time (default: 50ms).
        """
        ...

    def write(self, data: str) -> None:
        """Write output to terminal."""
        ...

    @property
    def columns(self) -> int:
        """Get terminal width in columns."""
        ...

    @property
    def rows(self) -> int:
        """Get terminal height in rows."""
        ...

    @property
    def kitty_protocol_active(self) -> bool:
        """Whether Kitty keyboard protocol is active."""
        ...

    def move_by(self, lines: int) -> None:
        """Move cursor up (negative) or down (positive) by N lines."""
        ...

    def hide_cursor(self) -> None:
        """Hide the cursor."""
        ...

    def show_cursor(self) -> None:
        """Show the cursor."""
        ...

    def clear_line(self) -> None:
        """Clear current line."""
        ...

    def clear_from_cursor(self) -> None:
        """Clear from cursor to end of screen."""
        ...

    def clear_screen(self) -> None:
        """Clear entire screen and move cursor to (0,0)."""
        ...

    def set_title(self, title: str) -> None:
        """Set terminal window title."""
        ...


# Kitty protocol response pattern: ESC[?<flags>u
_KITTY_RESPONSE_RE = re.compile(r"^\x1b\[\?(\d+)u$")


class ProcessTerminal:
    """Real terminal using sys.stdin/stdout."""

    def __init__(self) -> None:
        self._was_raw: bool = False
        self._old_settings: list[Any] | None = None
        self._input_handler: Callable[[str], None] | None = None
        self._resize_handler: Callable[[], None] | None = None
        self._kitty_protocol_active: bool = False
        self._stdin_buffer: StdinBuffer | None = None
        self._reader_thread: threading.Thread | None = None
        self._reader_stop: threading.Event = threading.Event()
        self._prev_sigwinch: Any = None
        self._write_log_path: str = os.environ.get("PI_TUI_WRITE_LOG", "")

    @property
    def kitty_protocol_active(self) -> bool:
        """Whether Kitty keyboard protocol is active."""
        return self._kitty_protocol_active

    def start(self, on_input: Callable[[str], None], on_resize: Callable[[], None]) -> None:
        """Start the terminal with input and resize handlers.

        Enables raw mode, bracketed paste, sets up resize handling via
        SIGWINCH, queries Kitty protocol support, and starts a background
        thread to read stdin.
        """
        self._input_handler = on_input
        self._resize_handler = on_resize

        fd = sys.stdin.fileno()

        # Save previous terminal settings
        self._old_settings = termios.tcgetattr(fd)
        self._was_raw = False  # We always restore from saved settings

        # Enable raw mode
        tty.setraw(fd, termios.TCSAFLUSH)

        # Enable bracketed paste mode
        sys.stdout.write("\x1b[?2004h")
        sys.stdout.flush()

        # Set up SIGWINCH handler for resize
        self._prev_sigwinch = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, self._on_sigwinch)

        # Refresh terminal dimensions -- they may be stale after suspend/resume
        # (SIGWINCH is lost while process is stopped).
        os.kill(os.getpid(), signal.SIGWINCH)

        # Set up stdin buffer and query Kitty protocol
        self._query_and_enable_kitty_protocol()

    def _on_sigwinch(self, signum: int, frame: Any) -> None:
        """Handle SIGWINCH (terminal resize)."""
        if self._resize_handler is not None:
            self._resize_handler()

    def _setup_stdin_buffer(self) -> None:
        """Set up StdinBuffer to split batched input into individual sequences.

        Also watches for Kitty protocol response and enables it when detected.
        This is done here (after stdinBuffer parsing) rather than on raw stdin
        to handle the case where the response arrives split across multiple events.
        """
        self._stdin_buffer = StdinBuffer(StdinBufferOptions(timeout=10))

        def on_data(sequence: str) -> None:
            # Check for Kitty protocol response (only if not already enabled)
            if not self._kitty_protocol_active:
                match = _KITTY_RESPONSE_RE.match(sequence)
                if match:
                    self._kitty_protocol_active = True
                    set_kitty_protocol_active(True)

                    # Enable Kitty keyboard protocol (push flags)
                    # Flag 1 = disambiguate escape codes
                    # Flag 2 = report event types (press/repeat/release)
                    # Flag 4 = report alternate keys (shifted key, base layout key)
                    # Base layout key enables shortcuts to work with non-Latin layouts
                    sys.stdout.write("\x1b[>7u")
                    sys.stdout.flush()
                    return  # Don't forward protocol response to TUI

            if self._input_handler is not None:
                self._input_handler(sequence)

        def on_paste(content: str) -> None:
            # Re-wrap paste content with bracketed paste markers
            if self._input_handler is not None:
                self._input_handler(f"\x1b[200~{content}\x1b[201~")

        self._stdin_buffer.on_data = on_data
        self._stdin_buffer.on_paste = on_paste

    def _query_and_enable_kitty_protocol(self) -> None:
        """Query terminal for Kitty keyboard protocol support and enable if available.

        Sends CSI ? u to query current flags. If terminal responds with
        CSI ? <flags> u, it supports the protocol and we enable it with CSI > 7 u.

        The response is detected in _setup_stdin_buffer's data handler, which
        properly handles the case where the response arrives split across
        multiple stdin events.
        """
        self._setup_stdin_buffer()
        self._start_reader_thread()

        # Query Kitty protocol support
        sys.stdout.write("\x1b[?u")
        sys.stdout.flush()

    def _start_reader_thread(self) -> None:
        """Start background thread that reads from stdin in raw mode."""
        self._reader_stop.clear()

        def reader() -> None:
            fd = sys.stdin.fileno()
            while not self._reader_stop.is_set():
                try:
                    # Use select with a short timeout so we can check the stop event
                    ready, _, _ = select.select([fd], [], [], 0.05)
                    if ready:
                        data = os.read(fd, 4096)
                        if data and self._stdin_buffer is not None:
                            self._stdin_buffer.process(data.decode("utf-8", errors="replace"))
                except OSError:
                    # fd closed or invalid -- stop the thread
                    break

        self._reader_thread = threading.Thread(target=reader, daemon=True)
        self._reader_thread.start()

    async def drain_input(self, max_ms: int = 1000, idle_ms: int = 50) -> None:
        """Drain stdin before exiting to prevent Kitty key release events
        from leaking to the parent shell over slow SSH connections.

        Args:
            max_ms: Maximum time to drain (default: 1000ms).
            idle_ms: Exit early if no input arrives within this time (default: 50ms).
        """
        if self._kitty_protocol_active:
            # Disable Kitty keyboard protocol first so any late key releases
            # do not generate new Kitty escape sequences.
            sys.stdout.write("\x1b[<u")
            sys.stdout.flush()
            self._kitty_protocol_active = False
            set_kitty_protocol_active(False)

        previous_handler = self._input_handler
        self._input_handler = None

        last_data_time = asyncio.get_event_loop().time()

        def on_data(_data: str) -> None:
            nonlocal last_data_time
            last_data_time = asyncio.get_event_loop().time()

        # Temporarily intercept data events
        old_on_data = self._stdin_buffer.on_data if self._stdin_buffer else None
        if self._stdin_buffer is not None:
            self._stdin_buffer.on_data = on_data

        end_time = asyncio.get_event_loop().time() + max_ms / 1000.0

        try:
            while True:
                now = asyncio.get_event_loop().time()
                time_left = end_time - now
                if time_left <= 0:
                    break
                if now - last_data_time >= idle_ms / 1000.0:
                    break
                await asyncio.sleep(min(idle_ms / 1000.0, time_left))
        finally:
            if self._stdin_buffer is not None:
                self._stdin_buffer.on_data = old_on_data
            self._input_handler = previous_handler

    def stop(self) -> None:
        """Stop the terminal and restore state.

        Disables bracketed paste, Kitty protocol, stops the reader thread,
        cleans up the stdin buffer, restores terminal settings and SIGWINCH
        handler.
        """
        # Disable bracketed paste mode
        sys.stdout.write("\x1b[?2004l")
        sys.stdout.flush()

        # Disable Kitty keyboard protocol if not already done by drain_input()
        if self._kitty_protocol_active:
            sys.stdout.write("\x1b[<u")
            sys.stdout.flush()
            self._kitty_protocol_active = False
            set_kitty_protocol_active(False)

        # Stop the reader thread
        self._reader_stop.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=1.0)
            self._reader_thread = None

        # Clean up StdinBuffer
        if self._stdin_buffer is not None:
            self._stdin_buffer.destroy()
            self._stdin_buffer = None

        # Clear handlers
        self._input_handler = None

        # Restore SIGWINCH handler
        if self._resize_handler is not None:
            if self._prev_sigwinch is not None:
                signal.signal(signal.SIGWINCH, self._prev_sigwinch)
            else:
                signal.signal(signal.SIGWINCH, signal.SIG_DFL)
            self._resize_handler = None

        # Restore terminal settings
        if self._old_settings is not None:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSAFLUSH, self._old_settings)
            self._old_settings = None

    def write(self, data: str) -> None:
        """Write output to terminal."""
        sys.stdout.write(data)
        sys.stdout.flush()
        if self._write_log_path:
            try:
                with open(self._write_log_path, "a") as f:
                    f.write(data)
            except OSError:
                pass

    @property
    def columns(self) -> int:
        """Get terminal width in columns."""
        try:
            size = os.get_terminal_size()
            return size.columns
        except OSError:
            return 80

    @property
    def rows(self) -> int:
        """Get terminal height in rows."""
        try:
            size = os.get_terminal_size()
            return size.lines
        except OSError:
            return 24

    def move_by(self, lines: int) -> None:
        """Move cursor up (negative) or down (positive) by N lines."""
        if lines > 0:
            sys.stdout.write(f"\x1b[{lines}B")
            sys.stdout.flush()
        elif lines < 0:
            sys.stdout.write(f"\x1b[{-lines}A")
            sys.stdout.flush()
        # lines == 0: no movement

    def hide_cursor(self) -> None:
        """Hide the cursor."""
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()

    def show_cursor(self) -> None:
        """Show the cursor."""
        sys.stdout.write("\x1b[?25h")
        sys.stdout.flush()

    def clear_line(self) -> None:
        """Clear current line."""
        sys.stdout.write("\x1b[K")
        sys.stdout.flush()

    def clear_from_cursor(self) -> None:
        """Clear from cursor to end of screen."""
        sys.stdout.write("\x1b[J")
        sys.stdout.flush()

    def clear_screen(self) -> None:
        """Clear entire screen and move cursor to (0,0)."""
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()

    def set_title(self, title: str) -> None:
        """Set terminal window title using OSC 0."""
        # Strip control characters to prevent OSC escape injection
        safe_title = title.replace("\x1b", "").replace("\x07", "")
        sys.stdout.write(f"\x1b]0;{safe_title}\x07")
        sys.stdout.flush()
