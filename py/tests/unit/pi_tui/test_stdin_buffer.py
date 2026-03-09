"""Tests for pi_tui.stdin_buffer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pi_tui.stdin_buffer import (
    BRACKETED_PASTE_END,
    BRACKETED_PASTE_START,
    ESC,
    StdinBuffer,
    StdinBufferOptions,
    _extract_complete_sequences,
    _is_complete_apc_sequence,
    _is_complete_csi_sequence,
    _is_complete_dcs_sequence,
    _is_complete_osc_sequence,
    _is_complete_sequence,
)


# ---------------------------------------------------------------------------
# StdinBufferOptions / construction
# ---------------------------------------------------------------------------


class TestStdinBufferOptions:
    def test_default_timeout(self) -> None:
        opts = StdinBufferOptions()
        assert opts.timeout == 10

    def test_custom_timeout(self) -> None:
        opts = StdinBufferOptions(timeout=50)
        assert opts.timeout == 50


class TestStdinBufferConstruction:
    def test_default_options(self) -> None:
        buf = StdinBuffer()
        assert buf._timeout_ms == 10
        assert buf._buffer == ""
        assert buf._paste_mode is False
        assert buf._paste_buffer == ""
        assert buf.on_data is None
        assert buf.on_paste is None

    def test_custom_options(self) -> None:
        opts = StdinBufferOptions(timeout=42)
        buf = StdinBuffer(options=opts)
        assert buf._timeout_ms == 42

    def test_callbacks_assignable(self) -> None:
        buf = StdinBuffer()
        cb = MagicMock()
        buf.on_data = cb
        buf.on_paste = cb
        assert buf.on_data is cb
        assert buf.on_paste is cb


# ---------------------------------------------------------------------------
# _is_complete_sequence  (public helper)
# ---------------------------------------------------------------------------


class TestIsCompleteSequence:
    def test_non_escape_data(self) -> None:
        assert _is_complete_sequence("a") == "not-escape"
        assert _is_complete_sequence("hello") == "not-escape"

    def test_lone_esc_is_incomplete(self) -> None:
        assert _is_complete_sequence(ESC) == "incomplete"

    # -- CSI sequences --
    def test_csi_simple_complete(self) -> None:
        # ESC [ A  (cursor up)
        assert _is_complete_sequence(f"{ESC}[A") == "complete"

    def test_csi_with_params_complete(self) -> None:
        # ESC [ 1 ; 5 A  (modified cursor up)
        assert _is_complete_sequence(f"{ESC}[1;5A") == "complete"

    def test_csi_incomplete_no_final(self) -> None:
        assert _is_complete_sequence(f"{ESC}[") == "incomplete"
        assert _is_complete_sequence(f"{ESC}[1;") == "incomplete"

    def test_csi_sgr_mouse_complete(self) -> None:
        assert _is_complete_sequence(f"{ESC}[<0;20;5M") == "complete"
        assert _is_complete_sequence(f"{ESC}[<35;20;5m") == "complete"

    def test_csi_sgr_mouse_incomplete(self) -> None:
        assert _is_complete_sequence(f"{ESC}[<35;20") == "incomplete"
        assert _is_complete_sequence(f"{ESC}[<35") == "incomplete"

    def test_csi_old_style_mouse_complete(self) -> None:
        # ESC [ M + 3 bytes = 6 total
        assert _is_complete_sequence(f"{ESC}[Mabc") == "complete"

    def test_csi_old_style_mouse_incomplete(self) -> None:
        assert _is_complete_sequence(f"{ESC}[Ma") == "incomplete"
        assert _is_complete_sequence(f"{ESC}[Mab") == "incomplete"

    # -- OSC sequences --
    def test_osc_complete_with_bel(self) -> None:
        assert _is_complete_sequence(f"{ESC}]0;title\x07") == "complete"

    def test_osc_complete_with_st(self) -> None:
        assert _is_complete_sequence(f"{ESC}]0;title{ESC}\\") == "complete"

    def test_osc_incomplete(self) -> None:
        assert _is_complete_sequence(f"{ESC}]0;title") == "incomplete"

    # -- DCS sequences --
    def test_dcs_complete(self) -> None:
        assert _is_complete_sequence(f"{ESC}Ppayload{ESC}\\") == "complete"

    def test_dcs_incomplete(self) -> None:
        assert _is_complete_sequence(f"{ESC}Ppayload") == "incomplete"

    # -- APC sequences --
    def test_apc_complete(self) -> None:
        assert _is_complete_sequence(f"{ESC}_payload{ESC}\\") == "complete"

    def test_apc_incomplete(self) -> None:
        assert _is_complete_sequence(f"{ESC}_payload") == "incomplete"

    # -- SS3 sequences --
    def test_ss3_complete(self) -> None:
        assert _is_complete_sequence(f"{ESC}OP") == "complete"

    def test_ss3_incomplete(self) -> None:
        assert _is_complete_sequence(f"{ESC}O") == "incomplete"

    # -- Meta key (ESC + char) --
    def test_meta_key_complete(self) -> None:
        assert _is_complete_sequence(f"{ESC}x") == "complete"

    # -- Unknown multi-char after ESC --
    def test_unknown_long_sequence_treated_complete(self) -> None:
        # Two chars after ESC that don't match known prefixes
        assert _is_complete_sequence(f"{ESC}##") == "complete"


# ---------------------------------------------------------------------------
# Individual sequence-type helpers
# ---------------------------------------------------------------------------


class TestIsCompleteCsiSequence:
    def test_non_csi_returns_complete(self) -> None:
        assert _is_complete_csi_sequence("abc") == "complete"

    def test_too_short(self) -> None:
        assert _is_complete_csi_sequence(f"{ESC}[") == "incomplete"

    def test_final_byte_range(self) -> None:
        # '@' = 0x40  (start of range)
        assert _is_complete_csi_sequence(f"{ESC}[@") == "complete"
        # '~' = 0x7E  (end of range)
        assert _is_complete_csi_sequence(f"{ESC}[~") == "complete"

    def test_sgr_mouse_partial_structure(self) -> None:
        # Ends with M but only 2 parts instead of 3
        assert _is_complete_csi_sequence(f"{ESC}[<1;2M") == "incomplete"


class TestIsCompleteOscSequence:
    def test_non_osc_returns_complete(self) -> None:
        assert _is_complete_osc_sequence("abc") == "complete"


class TestIsCompleteDcsSequence:
    def test_non_dcs_returns_complete(self) -> None:
        assert _is_complete_dcs_sequence("abc") == "complete"


class TestIsCompleteApcSequence:
    def test_non_apc_returns_complete(self) -> None:
        assert _is_complete_apc_sequence("abc") == "complete"


# ---------------------------------------------------------------------------
# _extract_complete_sequences
# ---------------------------------------------------------------------------


class TestExtractCompleteSequences:
    def test_empty_buffer(self) -> None:
        seqs, rem = _extract_complete_sequences("")
        assert seqs == []
        assert rem == ""

    def test_single_ascii_chars(self) -> None:
        seqs, rem = _extract_complete_sequences("abc")
        assert seqs == ["a", "b", "c"]
        assert rem == ""

    def test_complete_escape_sequence(self) -> None:
        seq = f"{ESC}[A"
        seqs, rem = _extract_complete_sequences(seq)
        assert seqs == [seq]
        assert rem == ""

    def test_mixed_ascii_and_escape(self) -> None:
        data = f"x{ESC}[Ay"
        seqs, rem = _extract_complete_sequences(data)
        assert seqs == ["x", f"{ESC}[A", "y"]
        assert rem == ""

    def test_incomplete_at_end(self) -> None:
        data = f"a{ESC}["
        seqs, rem = _extract_complete_sequences(data)
        assert seqs == ["a"]
        assert rem == f"{ESC}["

    def test_multiple_complete_sequences(self) -> None:
        data = f"{ESC}[A{ESC}[B"
        seqs, rem = _extract_complete_sequences(data)
        assert seqs == [f"{ESC}[A", f"{ESC}[B"]
        assert rem == ""


# ---------------------------------------------------------------------------
# StdinBuffer.process – simple ASCII
# ---------------------------------------------------------------------------


class TestStdinBufferProcessAscii:
    def test_single_char_triggers_on_data(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        buf.process("a")
        on_data.assert_called_once_with("a")

    def test_multiple_chars_emit_individually(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        buf.process("abc")
        assert on_data.call_count == 3
        on_data.assert_any_call("a")
        on_data.assert_any_call("b")
        on_data.assert_any_call("c")

    def test_empty_input_empty_buffer_emits_empty(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        buf.process("")
        on_data.assert_called_once_with("")

    def test_no_callback_no_error(self) -> None:
        buf = StdinBuffer()
        buf.process("a")  # should not raise


# ---------------------------------------------------------------------------
# StdinBuffer.process – complete escape sequences
# ---------------------------------------------------------------------------


class TestStdinBufferProcessEscapeSequences:
    def test_complete_csi_in_one_chunk(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        buf.process(f"{ESC}[A")
        on_data.assert_called_once_with(f"{ESC}[A")

    def test_complete_osc_in_one_chunk(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        buf.process(f"{ESC}]0;title\x07")
        on_data.assert_called_once_with(f"{ESC}]0;title\x07")

    def test_complete_ss3_in_one_chunk(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        buf.process(f"{ESC}OP")
        on_data.assert_called_once_with(f"{ESC}OP")

    def test_sgr_mouse_event(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        buf.process(f"{ESC}[<0;10;20M")
        on_data.assert_called_once_with(f"{ESC}[<0;10;20M")


# ---------------------------------------------------------------------------
# StdinBuffer.process – incomplete sequences / multi-write composition
# ---------------------------------------------------------------------------


class TestStdinBufferProcessIncomplete:
    def test_incomplete_waits_for_more_data(self) -> None:
        """An incomplete escape sequence should NOT emit immediately."""
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        with patch("pi_tui.stdin_buffer.threading.Timer") as MockTimer:
            mock_timer_instance = MagicMock()
            MockTimer.return_value = mock_timer_instance

            buf.process(ESC)

            on_data.assert_not_called()
            assert buf.get_buffer() == ESC
            # Timer should have been scheduled
            MockTimer.assert_called_once()
            mock_timer_instance.start.assert_called_once()

    def test_two_writes_compose_complete_sequence(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        with patch("pi_tui.stdin_buffer.threading.Timer") as MockTimer:
            mock_timer_instance = MagicMock()
            MockTimer.return_value = mock_timer_instance

            buf.process(ESC)
            on_data.assert_not_called()

            buf.process("[A")
            on_data.assert_called_once_with(f"{ESC}[A")
            assert buf.get_buffer() == ""

    def test_three_writes_compose_sgr_mouse(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        with patch("pi_tui.stdin_buffer.threading.Timer") as MockTimer:
            MockTimer.return_value = MagicMock()

            buf.process(ESC)
            assert on_data.call_count == 0

            buf.process("[<35")
            assert on_data.call_count == 0

            buf.process(";20;5m")
            on_data.assert_called_once_with(f"{ESC}[<35;20;5m")

    def test_timeout_flushes_incomplete_sequence(self) -> None:
        """When the timer fires, buffered data should be flushed via on_data."""
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        captured_callback = None

        def capture_timer(delay: float, fn: object) -> MagicMock:
            nonlocal captured_callback
            captured_callback = fn
            timer = MagicMock()
            return timer

        with patch("pi_tui.stdin_buffer.threading.Timer", side_effect=capture_timer):
            buf.process(ESC)
            on_data.assert_not_called()

        # Simulate the timer firing
        assert captured_callback is not None
        captured_callback()  # type: ignore[misc]

        on_data.assert_called_once_with(ESC)
        assert buf.get_buffer() == ""

    def test_timer_cancelled_when_new_data_arrives(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        buf.on_data = on_data

        with patch("pi_tui.stdin_buffer.threading.Timer") as MockTimer:
            mock_timer_instance = MagicMock()
            MockTimer.return_value = mock_timer_instance

            buf.process(ESC)
            mock_timer_instance.cancel.assert_not_called()

            # Second write should cancel the first timer
            buf.process("[A")
            mock_timer_instance.cancel.assert_called_once()


# ---------------------------------------------------------------------------
# Bracketed paste mode
# ---------------------------------------------------------------------------


class TestStdinBufferBracketedPaste:
    def test_simple_paste(self) -> None:
        buf = StdinBuffer()
        on_paste = MagicMock()
        on_data = MagicMock()
        buf.on_paste = on_paste
        buf.on_data = on_data

        buf.process(f"{BRACKETED_PASTE_START}hello world{BRACKETED_PASTE_END}")
        on_paste.assert_called_once_with("hello world")
        on_data.assert_not_called()

    def test_paste_across_multiple_writes(self) -> None:
        buf = StdinBuffer()
        on_paste = MagicMock()
        buf.on_paste = on_paste

        buf.process(BRACKETED_PASTE_START)
        on_paste.assert_not_called()

        buf.process("pasted text")
        on_paste.assert_not_called()

        buf.process(BRACKETED_PASTE_END)
        on_paste.assert_called_once_with("pasted text")

    def test_data_before_paste_is_emitted(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        on_paste = MagicMock()
        buf.on_data = on_data
        buf.on_paste = on_paste

        buf.process(f"x{BRACKETED_PASTE_START}text{BRACKETED_PASTE_END}")
        on_data.assert_called_once_with("x")
        on_paste.assert_called_once_with("text")

    def test_data_after_paste_is_emitted(self) -> None:
        buf = StdinBuffer()
        on_data = MagicMock()
        on_paste = MagicMock()
        buf.on_data = on_data
        buf.on_paste = on_paste

        buf.process(f"{BRACKETED_PASTE_START}text{BRACKETED_PASTE_END}y")
        on_paste.assert_called_once_with("text")
        on_data.assert_called_once_with("y")

    def test_paste_with_escape_sequences_in_content(self) -> None:
        """Escape sequences inside paste should be treated as literal text."""
        buf = StdinBuffer()
        on_paste = MagicMock()
        buf.on_paste = on_paste

        content = f"{ESC}[Afoo"
        buf.process(f"{BRACKETED_PASTE_START}{content}{BRACKETED_PASTE_END}")
        on_paste.assert_called_once_with(content)

    def test_no_paste_callback_no_error(self) -> None:
        buf = StdinBuffer()
        buf.process(f"{BRACKETED_PASTE_START}text{BRACKETED_PASTE_END}")


# ---------------------------------------------------------------------------
# flush / clear / destroy
# ---------------------------------------------------------------------------


class TestStdinBufferFlush:
    def test_flush_returns_buffered_data(self) -> None:
        buf = StdinBuffer()
        with patch("pi_tui.stdin_buffer.threading.Timer") as MockTimer:
            MockTimer.return_value = MagicMock()
            buf.process(ESC)

        result = buf.flush()
        assert result == [ESC]
        assert buf.get_buffer() == ""

    def test_flush_empty_returns_empty_list(self) -> None:
        buf = StdinBuffer()
        assert buf.flush() == []

    def test_flush_cancels_timer(self) -> None:
        buf = StdinBuffer()
        with patch("pi_tui.stdin_buffer.threading.Timer") as MockTimer:
            mock_timer = MagicMock()
            MockTimer.return_value = mock_timer
            buf.process(ESC)

        buf.flush()
        mock_timer.cancel.assert_called()


class TestStdinBufferClear:
    def test_clear_resets_all_state(self) -> None:
        buf = StdinBuffer()
        with patch("pi_tui.stdin_buffer.threading.Timer") as MockTimer:
            MockTimer.return_value = MagicMock()
            buf.process(ESC)

        buf.clear()
        assert buf.get_buffer() == ""
        assert buf._paste_mode is False
        assert buf._paste_buffer == ""


class TestStdinBufferDestroy:
    def test_destroy_clears_state(self) -> None:
        buf = StdinBuffer()
        with patch("pi_tui.stdin_buffer.threading.Timer") as MockTimer:
            MockTimer.return_value = MagicMock()
            buf.process(ESC)

        buf.destroy()
        assert buf.get_buffer() == ""
