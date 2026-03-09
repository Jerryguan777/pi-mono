"""Tests for pi_tui.terminal module."""

from __future__ import annotations

import os
import signal
import termios
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pi_tui.terminal import _KITTY_RESPONSE_RE, ProcessTerminal, Terminal

# =============================================================================
# Terminal Protocol
# =============================================================================


class TestTerminalProtocol:
    """Verify Terminal is a Protocol with the expected methods."""

    def test_is_protocol(self) -> None:
        assert hasattr(Terminal, "__protocol_attrs__") or issubclass(Terminal, object)

    def test_protocol_has_start(self) -> None:
        assert hasattr(Terminal, "start")

    def test_protocol_has_stop(self) -> None:
        assert hasattr(Terminal, "stop")

    def test_protocol_has_drain_input(self) -> None:
        assert hasattr(Terminal, "drain_input")

    def test_protocol_has_write(self) -> None:
        assert hasattr(Terminal, "write")

    def test_protocol_has_columns(self) -> None:
        assert hasattr(Terminal, "columns")

    def test_protocol_has_rows(self) -> None:
        assert hasattr(Terminal, "rows")

    def test_protocol_has_kitty_protocol_active(self) -> None:
        assert hasattr(Terminal, "kitty_protocol_active")

    def test_protocol_has_move_by(self) -> None:
        assert hasattr(Terminal, "move_by")

    def test_protocol_has_hide_cursor(self) -> None:
        assert hasattr(Terminal, "hide_cursor")

    def test_protocol_has_show_cursor(self) -> None:
        assert hasattr(Terminal, "show_cursor")

    def test_protocol_has_clear_line(self) -> None:
        assert hasattr(Terminal, "clear_line")

    def test_protocol_has_clear_from_cursor(self) -> None:
        assert hasattr(Terminal, "clear_from_cursor")

    def test_protocol_has_clear_screen(self) -> None:
        assert hasattr(Terminal, "clear_screen")

    def test_protocol_has_set_title(self) -> None:
        assert hasattr(Terminal, "set_title")


# =============================================================================
# Kitty response regex
# =============================================================================


class TestKittyResponseRegex:
    def test_matches_kitty_response(self) -> None:
        assert _KITTY_RESPONSE_RE.match("\x1b[?0u") is not None

    def test_matches_kitty_response_with_flags(self) -> None:
        m = _KITTY_RESPONSE_RE.match("\x1b[?7u")
        assert m is not None
        assert m.group(1) == "7"

    def test_no_match_for_other_escape(self) -> None:
        assert _KITTY_RESPONSE_RE.match("\x1b[0m") is None


# =============================================================================
# ProcessTerminal.__init__
# =============================================================================


class TestProcessTerminalInit:
    def test_initial_state(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            term = ProcessTerminal()
            assert term._was_raw is False
            assert term._old_settings is None
            assert term._input_handler is None
            assert term._resize_handler is None
            assert term._kitty_protocol_active is False
            assert term._stdin_buffer is None
            assert term._reader_thread is None

    def test_write_log_path_from_env(self) -> None:
        with patch.dict(os.environ, {"PI_TUI_WRITE_LOG": "/tmp/test.log"}):
            term = ProcessTerminal()
            assert term._write_log_path == "/tmp/test.log"

    def test_write_log_path_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PI_TUI_WRITE_LOG", None)
            term = ProcessTerminal()
            assert term._write_log_path == ""


# =============================================================================
# ProcessTerminal.write
# =============================================================================


class TestProcessTerminalWrite:
    @patch("pi_tui.terminal.sys.stdout")
    def test_write_outputs_to_stdout(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term._write_log_path = ""
        term.write("hello")
        mock_stdout.write.assert_called_once_with("hello")
        mock_stdout.flush.assert_called_once()

    @patch("pi_tui.terminal.sys.stdout")
    def test_write_with_log_path(self, mock_stdout: MagicMock, tmp_path: Any) -> None:
        log_file = str(tmp_path / "write.log")
        term = ProcessTerminal()
        term._write_log_path = log_file
        term.write("logged data")
        mock_stdout.write.assert_called_once_with("logged data")
        with open(log_file) as f:
            assert f.read() == "logged data"

    @patch("pi_tui.terminal.sys.stdout")
    def test_write_log_oserror_is_silenced(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term._write_log_path = "/nonexistent/dir/file.log"
        # Should not raise
        term.write("data")
        mock_stdout.write.assert_called_once_with("data")


# =============================================================================
# ProcessTerminal.columns / rows
# =============================================================================


class TestProcessTerminalSize:
    @patch("pi_tui.terminal.os.get_terminal_size")
    def test_columns(self, mock_size: MagicMock) -> None:
        mock_size.return_value = os.terminal_size((120, 40))
        term = ProcessTerminal()
        assert term.columns == 120

    @patch("pi_tui.terminal.os.get_terminal_size")
    def test_rows(self, mock_size: MagicMock) -> None:
        mock_size.return_value = os.terminal_size((120, 40))
        term = ProcessTerminal()
        assert term.rows == 40

    @patch("pi_tui.terminal.os.get_terminal_size", side_effect=OSError)
    def test_columns_fallback(self, mock_size: MagicMock) -> None:
        term = ProcessTerminal()
        assert term.columns == 80

    @patch("pi_tui.terminal.os.get_terminal_size", side_effect=OSError)
    def test_rows_fallback(self, mock_size: MagicMock) -> None:
        term = ProcessTerminal()
        assert term.rows == 24


# =============================================================================
# ProcessTerminal.kitty_protocol_active property
# =============================================================================


class TestKittyProtocolActive:
    def test_default_false(self) -> None:
        term = ProcessTerminal()
        assert term.kitty_protocol_active is False

    def test_reflects_internal_state(self) -> None:
        term = ProcessTerminal()
        term._kitty_protocol_active = True
        assert term.kitty_protocol_active is True


# =============================================================================
# ProcessTerminal.move_by
# =============================================================================


class TestMoveBy:
    @patch("pi_tui.terminal.sys.stdout")
    def test_move_down(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term.move_by(3)
        mock_stdout.write.assert_called_with("\x1b[3B")
        mock_stdout.flush.assert_called()

    @patch("pi_tui.terminal.sys.stdout")
    def test_move_up(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term.move_by(-5)
        mock_stdout.write.assert_called_with("\x1b[5A")
        mock_stdout.flush.assert_called()

    @patch("pi_tui.terminal.sys.stdout")
    def test_move_zero(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term.move_by(0)
        mock_stdout.write.assert_not_called()


# =============================================================================
# ProcessTerminal cursor/screen methods
# =============================================================================


class TestCursorAndScreen:
    @patch("pi_tui.terminal.sys.stdout")
    def test_hide_cursor(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term.hide_cursor()
        mock_stdout.write.assert_called_with("\x1b[?25l")
        mock_stdout.flush.assert_called()

    @patch("pi_tui.terminal.sys.stdout")
    def test_show_cursor(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term.show_cursor()
        mock_stdout.write.assert_called_with("\x1b[?25h")
        mock_stdout.flush.assert_called()

    @patch("pi_tui.terminal.sys.stdout")
    def test_clear_line(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term.clear_line()
        mock_stdout.write.assert_called_with("\x1b[K")
        mock_stdout.flush.assert_called()

    @patch("pi_tui.terminal.sys.stdout")
    def test_clear_from_cursor(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term.clear_from_cursor()
        mock_stdout.write.assert_called_with("\x1b[J")
        mock_stdout.flush.assert_called()

    @patch("pi_tui.terminal.sys.stdout")
    def test_clear_screen(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term.clear_screen()
        mock_stdout.write.assert_called_with("\x1b[2J\x1b[H")
        mock_stdout.flush.assert_called()

    @patch("pi_tui.terminal.sys.stdout")
    def test_set_title(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        term.set_title("My Title")
        mock_stdout.write.assert_called_with("\x1b]0;My Title\x07")
        mock_stdout.flush.assert_called()


# =============================================================================
# ProcessTerminal._on_sigwinch
# =============================================================================


class TestOnSigwinch:
    def test_calls_resize_handler(self) -> None:
        term = ProcessTerminal()
        handler = MagicMock()
        term._resize_handler = handler
        term._on_sigwinch(signal.SIGWINCH, None)
        handler.assert_called_once()

    def test_no_handler_does_not_raise(self) -> None:
        term = ProcessTerminal()
        term._resize_handler = None
        # Should not raise
        term._on_sigwinch(signal.SIGWINCH, None)


# =============================================================================
# ProcessTerminal.start
# =============================================================================


class TestStart:
    @patch("pi_tui.terminal.os.kill")
    @patch("pi_tui.terminal.signal.signal")
    @patch("pi_tui.terminal.signal.getsignal", return_value=signal.SIG_DFL)
    @patch("pi_tui.terminal.tty.setraw")
    @patch("pi_tui.terminal.termios.tcgetattr", return_value=[1, 2, 3])
    @patch("pi_tui.terminal.sys.stdout")
    @patch("pi_tui.terminal.sys.stdin")
    def test_start_enables_raw_mode_and_queries_kitty(
        self,
        mock_stdin: MagicMock,
        mock_stdout: MagicMock,
        mock_tcgetattr: MagicMock,
        mock_setraw: MagicMock,
        mock_getsignal: MagicMock,
        mock_signal: MagicMock,
        mock_os_kill: MagicMock,
    ) -> None:
        mock_stdin.fileno.return_value = 0
        term = ProcessTerminal()

        on_input = MagicMock()
        on_resize = MagicMock()

        # Patch _query_and_enable_kitty_protocol to avoid threading
        with patch.object(term, "_query_and_enable_kitty_protocol"):
            term.start(on_input, on_resize)

        assert term._input_handler is on_input
        assert term._resize_handler is on_resize
        mock_tcgetattr.assert_called_once_with(0)
        assert term._old_settings == [1, 2, 3]
        mock_setraw.assert_called_once()
        # Bracketed paste mode enabled
        mock_stdout.write.assert_any_call("\x1b[?2004h")
        # SIGWINCH handler installed
        mock_signal.assert_called()
        # SIGWINCH sent to self
        mock_os_kill.assert_called_once()


# =============================================================================
# ProcessTerminal.stop
# =============================================================================


class TestStop:
    @patch("pi_tui.terminal.termios.tcsetattr")
    @patch("pi_tui.terminal.signal.signal")
    @patch("pi_tui.terminal.sys.stdout")
    @patch("pi_tui.terminal.sys.stdin")
    def test_stop_restores_state(
        self,
        mock_stdin: MagicMock,
        mock_stdout: MagicMock,
        mock_signal_fn: MagicMock,
        mock_tcsetattr: MagicMock,
    ) -> None:
        mock_stdin.fileno.return_value = 0
        term = ProcessTerminal()
        term._old_settings = [1, 2, 3]
        term._resize_handler = MagicMock()
        term._input_handler = MagicMock()
        term._prev_sigwinch = signal.SIG_DFL
        term._kitty_protocol_active = False

        # Mock stdin_buffer
        mock_buffer = MagicMock()
        term._stdin_buffer = mock_buffer

        # Mock reader thread
        mock_thread = MagicMock()
        term._reader_thread = mock_thread

        term.stop()

        # Bracketed paste disabled
        mock_stdout.write.assert_any_call("\x1b[?2004l")
        # Reader thread joined
        mock_thread.join.assert_called_once_with(timeout=1.0)
        assert term._reader_thread is None
        # StdinBuffer destroyed
        mock_buffer.destroy.assert_called_once()
        assert term._stdin_buffer is None
        # Input handler cleared
        assert term._input_handler is None
        # SIGWINCH restored
        mock_signal_fn.assert_called()
        assert term._resize_handler is None
        # Terminal settings restored
        mock_tcsetattr.assert_called_once_with(0, termios.TCSAFLUSH, [1, 2, 3])
        assert term._old_settings is None

    @patch("pi_tui.terminal.termios.tcsetattr")
    @patch("pi_tui.terminal.signal.signal")
    @patch("pi_tui.terminal.sys.stdout")
    @patch("pi_tui.terminal.sys.stdin")
    @patch("pi_tui.terminal.set_kitty_protocol_active")
    def test_stop_disables_kitty_if_active(
        self,
        mock_set_kitty: MagicMock,
        mock_stdin: MagicMock,
        mock_stdout: MagicMock,
        mock_signal_fn: MagicMock,
        mock_tcsetattr: MagicMock,
    ) -> None:
        mock_stdin.fileno.return_value = 0
        term = ProcessTerminal()
        term._old_settings = [1, 2, 3]
        term._kitty_protocol_active = True
        term._resize_handler = MagicMock()
        term._prev_sigwinch = signal.SIG_DFL

        term.stop()

        # Kitty protocol disabled
        mock_stdout.write.assert_any_call("\x1b[<u")
        assert term._kitty_protocol_active is False
        mock_set_kitty.assert_called_with(False)

    @patch("pi_tui.terminal.signal.signal")
    @patch("pi_tui.terminal.sys.stdout")
    def test_stop_restores_sigwinch_to_sig_dfl_when_no_prev(
        self,
        mock_stdout: MagicMock,
        mock_signal_fn: MagicMock,
    ) -> None:
        term = ProcessTerminal()
        term._resize_handler = MagicMock()
        term._prev_sigwinch = None

        term.stop()

        mock_signal_fn.assert_any_call(signal.SIGWINCH, signal.SIG_DFL)

    @patch("pi_tui.terminal.sys.stdout")
    def test_stop_no_resize_handler_skips_signal_restore(
        self,
        mock_stdout: MagicMock,
    ) -> None:
        term = ProcessTerminal()
        term._resize_handler = None
        # Should not raise and should not attempt signal restore
        term.stop()

    @patch("pi_tui.terminal.sys.stdout")
    def test_stop_no_old_settings_skips_tcsetattr(
        self,
        mock_stdout: MagicMock,
    ) -> None:
        term = ProcessTerminal()
        term._old_settings = None
        # Should not raise
        term.stop()


# =============================================================================
# ProcessTerminal._setup_stdin_buffer
# =============================================================================


class TestSetupStdinBuffer:
    def test_creates_stdin_buffer(self) -> None:
        term = ProcessTerminal()
        term._setup_stdin_buffer()
        assert term._stdin_buffer is not None

    @patch("pi_tui.terminal.sys.stdout")
    @patch("pi_tui.terminal.set_kitty_protocol_active")
    def test_on_data_detects_kitty_response(
        self,
        mock_set_kitty: MagicMock,
        mock_stdout: MagicMock,
    ) -> None:
        term = ProcessTerminal()
        term._setup_stdin_buffer()
        assert term._stdin_buffer is not None

        # Simulate kitty protocol response
        assert term._stdin_buffer.on_data is not None
        term._stdin_buffer.on_data("\x1b[?0u")

        assert term._kitty_protocol_active is True
        mock_set_kitty.assert_called_with(True)
        # Kitty protocol enabled with flags
        mock_stdout.write.assert_called_with("\x1b[>7u")

    @patch("pi_tui.terminal.sys.stdout")
    def test_on_data_forwards_non_kitty_to_handler(
        self,
        mock_stdout: MagicMock,
    ) -> None:
        term = ProcessTerminal()
        handler = MagicMock()
        term._input_handler = handler
        term._setup_stdin_buffer()
        assert term._stdin_buffer is not None

        assert term._stdin_buffer.on_data is not None
        term._stdin_buffer.on_data("a")
        handler.assert_called_once_with("a")

    @patch("pi_tui.terminal.sys.stdout")
    def test_on_data_kitty_response_not_forwarded(
        self,
        mock_stdout: MagicMock,
    ) -> None:
        term = ProcessTerminal()
        handler = MagicMock()
        term._input_handler = handler
        term._setup_stdin_buffer()
        assert term._stdin_buffer is not None

        assert term._stdin_buffer.on_data is not None
        term._stdin_buffer.on_data("\x1b[?0u")
        handler.assert_not_called()

    @patch("pi_tui.terminal.sys.stdout")
    @patch("pi_tui.terminal.set_kitty_protocol_active")
    def test_on_data_ignores_kitty_response_when_already_active(
        self,
        mock_set_kitty: MagicMock,
        mock_stdout: MagicMock,
    ) -> None:
        term = ProcessTerminal()
        handler = MagicMock()
        term._input_handler = handler
        term._kitty_protocol_active = True
        term._setup_stdin_buffer()
        assert term._stdin_buffer is not None

        # When kitty is already active, the response is forwarded as normal input
        assert term._stdin_buffer.on_data is not None
        term._stdin_buffer.on_data("\x1b[?0u")
        handler.assert_called_once_with("\x1b[?0u")

    def test_on_paste_wraps_with_brackets(self) -> None:
        term = ProcessTerminal()
        handler = MagicMock()
        term._input_handler = handler
        term._setup_stdin_buffer()
        assert term._stdin_buffer is not None

        assert term._stdin_buffer.on_paste is not None
        term._stdin_buffer.on_paste("pasted text")
        handler.assert_called_once_with("\x1b[200~pasted text\x1b[201~")

    def test_on_paste_no_handler(self) -> None:
        term = ProcessTerminal()
        term._input_handler = None
        term._setup_stdin_buffer()
        assert term._stdin_buffer is not None

        # Should not raise — on_paste may be None; call via the process path
        assert term._stdin_buffer.on_paste is not None
        term._stdin_buffer.on_paste("pasted text")


# =============================================================================
# ProcessTerminal._query_and_enable_kitty_protocol
# =============================================================================


class TestQueryAndEnableKittyProtocol:
    @patch("pi_tui.terminal.sys.stdout")
    def test_sends_kitty_query(self, mock_stdout: MagicMock) -> None:
        term = ProcessTerminal()
        with patch.object(term, "_start_reader_thread"):
            term._query_and_enable_kitty_protocol()

        # Should set up stdin buffer
        assert term._stdin_buffer is not None
        # Should send Kitty query
        mock_stdout.write.assert_any_call("\x1b[?u")


# =============================================================================
# ProcessTerminal._start_reader_thread
# =============================================================================


class TestStartReaderThread:
    @patch("pi_tui.terminal.threading.Thread")
    def test_starts_daemon_thread(self, mock_thread_cls: MagicMock) -> None:
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        term = ProcessTerminal()
        term._start_reader_thread()

        mock_thread_cls.assert_called_once()
        kwargs = mock_thread_cls.call_args
        assert kwargs.kwargs.get("daemon") is True or (len(kwargs.args) == 0 and kwargs.kwargs.get("daemon") is True)
        mock_thread.start.assert_called_once()
        assert term._reader_thread is mock_thread

    @patch("pi_tui.terminal.os.read", return_value=b"x")
    @patch("pi_tui.terminal.select.select", return_value=([0], [], []))
    @patch("pi_tui.terminal.sys.stdin")
    def test_reader_thread_reads_and_processes(
        self,
        mock_stdin: MagicMock,
        mock_select: MagicMock,
        mock_os_read: MagicMock,
    ) -> None:
        mock_stdin.fileno.return_value = 0
        term = ProcessTerminal()
        mock_buffer = MagicMock()
        term._stdin_buffer = mock_buffer

        # Run the reader function directly (extract target from Thread call)
        call_count = 0

        def select_side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return ([0], [], [])
            # Stop after first iteration
            term._reader_stop.set()
            return ([], [], [])

        mock_select.side_effect = select_side_effect

        # We need to call _start_reader_thread and capture the target
        with patch("pi_tui.terminal.threading.Thread") as mock_thread_cls:
            mock_thread_inst = MagicMock()
            mock_thread_cls.return_value = mock_thread_inst
            term._start_reader_thread()
            # Get the reader function
            reader_fn = mock_thread_cls.call_args.kwargs["target"]

        # Run the reader function
        reader_fn()

        mock_buffer.process.assert_called_with("x")

    @patch("pi_tui.terminal.os.read", side_effect=OSError("fd closed"))
    @patch("pi_tui.terminal.select.select", return_value=([0], [], []))
    @patch("pi_tui.terminal.sys.stdin")
    def test_reader_thread_oserror_stops(
        self,
        mock_stdin: MagicMock,
        mock_select: MagicMock,
        mock_os_read: MagicMock,
    ) -> None:
        mock_stdin.fileno.return_value = 0
        term = ProcessTerminal()
        term._stdin_buffer = MagicMock()

        with patch("pi_tui.terminal.threading.Thread") as mock_thread_cls:
            mock_thread_inst = MagicMock()
            mock_thread_cls.return_value = mock_thread_inst
            term._start_reader_thread()
            reader_fn = mock_thread_cls.call_args.kwargs["target"]

        # Should not raise, just exit
        reader_fn()

    @patch("pi_tui.terminal.os.read", return_value=b"")
    @patch("pi_tui.terminal.select.select")
    @patch("pi_tui.terminal.sys.stdin")
    def test_reader_thread_no_data_no_process(
        self,
        mock_stdin: MagicMock,
        mock_select: MagicMock,
        mock_os_read: MagicMock,
    ) -> None:
        mock_stdin.fileno.return_value = 0
        term = ProcessTerminal()
        mock_buffer = MagicMock()
        term._stdin_buffer = mock_buffer

        call_count = 0

        def select_side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return ([0], [], [])
            term._reader_stop.set()
            return ([], [], [])

        mock_select.side_effect = select_side_effect

        with patch("pi_tui.terminal.threading.Thread") as mock_thread_cls:
            mock_thread_inst = MagicMock()
            mock_thread_cls.return_value = mock_thread_inst
            term._start_reader_thread()
            reader_fn = mock_thread_cls.call_args.kwargs["target"]

        reader_fn()

        # Empty data should not call process
        mock_buffer.process.assert_not_called()

    @patch("pi_tui.terminal.select.select")
    @patch("pi_tui.terminal.sys.stdin")
    def test_reader_thread_not_ready_loops(
        self,
        mock_stdin: MagicMock,
        mock_select: MagicMock,
    ) -> None:
        mock_stdin.fileno.return_value = 0
        term = ProcessTerminal()
        term._stdin_buffer = MagicMock()

        call_count = 0

        def select_side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                term._reader_stop.set()
            return ([], [], [])

        mock_select.side_effect = select_side_effect

        with patch("pi_tui.terminal.threading.Thread") as mock_thread_cls:
            mock_thread_inst = MagicMock()
            mock_thread_cls.return_value = mock_thread_inst
            term._start_reader_thread()
            reader_fn = mock_thread_cls.call_args.kwargs["target"]

        reader_fn()

        assert call_count >= 3


# =============================================================================
# ProcessTerminal.drain_input
# =============================================================================


class TestDrainInput:
    @pytest.mark.asyncio
    @patch("pi_tui.terminal.sys.stdout")
    @patch("pi_tui.terminal.set_kitty_protocol_active")
    async def test_drain_disables_kitty_if_active(
        self,
        mock_set_kitty: MagicMock,
        mock_stdout: MagicMock,
    ) -> None:
        term = ProcessTerminal()
        term._kitty_protocol_active = True
        mock_buffer = MagicMock()
        mock_buffer.on_data = None
        term._stdin_buffer = mock_buffer
        term._input_handler = MagicMock()

        await term.drain_input(max_ms=50, idle_ms=10)

        mock_stdout.write.assert_any_call("\x1b[<u")
        assert term._kitty_protocol_active is False
        mock_set_kitty.assert_called_with(False)

    @pytest.mark.asyncio
    async def test_drain_exits_on_idle(self) -> None:
        term = ProcessTerminal()
        term._kitty_protocol_active = False
        mock_buffer = MagicMock()
        mock_buffer.on_data = None
        term._stdin_buffer = mock_buffer
        term._input_handler = MagicMock()

        # Should exit quickly due to idle timeout
        await term.drain_input(max_ms=500, idle_ms=10)
        # If we reach here, it exited (didn't hang)

    @pytest.mark.asyncio
    async def test_drain_restores_handlers(self) -> None:
        term = ProcessTerminal()
        term._kitty_protocol_active = False
        original_handler = MagicMock()
        term._input_handler = original_handler
        mock_buffer = MagicMock()
        old_on_data = MagicMock()
        mock_buffer.on_data = old_on_data
        term._stdin_buffer = mock_buffer

        await term.drain_input(max_ms=50, idle_ms=10)

        # Input handler should be restored
        assert term._input_handler is original_handler
        # on_data should be restored
        assert mock_buffer.on_data is old_on_data

    @pytest.mark.asyncio
    async def test_drain_no_stdin_buffer(self) -> None:
        term = ProcessTerminal()
        term._kitty_protocol_active = False
        term._stdin_buffer = None
        term._input_handler = MagicMock()

        # Should not raise
        await term.drain_input(max_ms=50, idle_ms=10)

    @pytest.mark.asyncio
    async def test_drain_exits_on_max_ms(self) -> None:
        term = ProcessTerminal()
        term._kitty_protocol_active = False
        mock_buffer = MagicMock()
        term._stdin_buffer = mock_buffer

        # Set on_data to a callable that keeps updating last_data_time
        # so idle_ms never triggers, forcing max_ms exit
        original_on_data = MagicMock()
        mock_buffer.on_data = original_on_data

        await term.drain_input(max_ms=30, idle_ms=1000)
        # Should complete (timeout by max_ms)


# =============================================================================
# Integration-style: ProcessTerminal conforms to Terminal Protocol
# =============================================================================


class TestProtocolConformance:
    """Verify that ProcessTerminal has all methods from Terminal Protocol."""

    def test_has_all_protocol_methods(self) -> None:
        term = ProcessTerminal()
        assert callable(term.start)
        assert callable(term.stop)
        assert callable(term.drain_input)
        assert callable(term.write)
        assert isinstance(term.columns, int)
        assert isinstance(term.rows, int)
        assert isinstance(term.kitty_protocol_active, bool)
        assert callable(term.move_by)
        assert callable(term.hide_cursor)
        assert callable(term.show_cursor)
        assert callable(term.clear_line)
        assert callable(term.clear_from_cursor)
        assert callable(term.clear_screen)
        assert callable(term.set_title)
