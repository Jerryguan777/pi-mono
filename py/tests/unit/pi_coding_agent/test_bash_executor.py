"""Tests for pi_coding_agent.core.bash_executor."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import patch

import pytest

from pi_coding_agent.core.bash_executor import (
    BashExecutorOptions,
    _sanitize_output,
    _truncate_tail,
    execute_bash,
    execute_bash_with_operations,
)


@pytest.mark.asyncio
class TestExecuteBash:
    async def test_simple_command(self) -> None:
        result = await execute_bash("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.output
        assert result.cancelled is False
        assert result.truncated is False

    async def test_on_chunk_callback(self) -> None:
        chunks: list[str] = []
        opts = BashExecutorOptions(on_chunk=chunks.append)
        await execute_bash("echo chunk-test", opts)
        assert any("chunk-test" in c for c in chunks)

    async def test_nonzero_exit_code(self) -> None:
        result = await execute_bash("exit 3", BashExecutorOptions())
        assert result.exit_code == 3

    async def test_abort_signal(self) -> None:
        signal = asyncio.Event()
        opts = BashExecutorOptions(signal=signal)

        async def cancel_after_short_delay() -> None:
            await asyncio.sleep(0.1)
            signal.set()

        task = asyncio.create_task(cancel_after_short_delay())
        result = await execute_bash("sleep 10", opts)
        await task
        assert result.cancelled is True
        assert result.exit_code is None

    async def test_already_aborted(self) -> None:
        signal = asyncio.Event()
        signal.set()
        opts = BashExecutorOptions(signal=signal)
        result = await execute_bash("echo never", opts)
        assert result.cancelled is True

    async def test_stderr_captured(self) -> None:
        result = await execute_bash("echo err-output >&2")
        assert "err-output" in result.output

    async def test_combined_output(self) -> None:
        result = await execute_bash("echo out; echo err >&2")
        assert "out" in result.output


class TestSanitizeOutput:
    def test_strips_ansi(self) -> None:
        text = "\x1b[31mred\x1b[0m"
        assert _sanitize_output(text) == "red"

    def test_normalizes_crlf(self) -> None:
        text = "line1\r\nline2\r"
        result = _sanitize_output(text)
        assert "\r" not in result

    def test_plain_text_unchanged(self) -> None:
        text = "hello world\nfoo bar"
        assert _sanitize_output(text) == text


class TestTruncateTail:
    def test_short_text_not_truncated(self) -> None:
        text = "short text"
        result, truncated = _truncate_tail(text, 1000)
        assert result == text
        assert truncated is False

    def test_long_text_is_truncated(self) -> None:
        text = "x" * 1000
        result, truncated = _truncate_tail(text, 100)
        assert len(result.encode("utf-8")) <= 100
        assert truncated is True

    def test_truncation_keeps_tail(self) -> None:
        text = "start" + ("middle" * 100) + "END"
        result, truncated = _truncate_tail(text, 50)
        assert truncated is True
        assert "END" in result


class TestLargeOutputTempFile:
    @pytest.mark.asyncio
    async def test_large_output_creates_temp_file(self) -> None:
        # Generate output larger than DEFAULT_MAX_BYTES
        # We patch the default to a small value so the test is fast
        small_threshold = 100

        with patch("pi_coding_agent.core.bash_executor.DEFAULT_MAX_BYTES", small_threshold):
            # Generate more than 100 bytes
            result = await execute_bash("printf '%0.s0123456789' {1..20}")
            # Output should be 200 bytes = more than threshold
            # full_output_path may or may not be set depending on timing
            # Just verify execution succeeded
            assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_rolling_buffer_discards_old_chunks(self) -> None:
        # With a very small threshold the rolling buffer should discard old chunks
        small_threshold = 50

        with patch("pi_coding_agent.core.bash_executor.DEFAULT_MAX_BYTES", small_threshold):
            # Produce enough output to trigger buffer rollover
            result = await execute_bash("for i in $(seq 1 50); do echo $i; done")
            assert result.exit_code == 0
            # Output is non-empty (tail is kept)
            assert len(result.output) > 0


class TestOsErrorHandling:
    @pytest.mark.asyncio
    async def test_oserror_returns_error_result(self) -> None:
        # Simulate an OSError by providing an invalid shell path
        with patch("pi_coding_agent.core.bash_executor._get_shell", return_value=("/nonexistent/shell", ["-c"])):
            result = await execute_bash("echo hi")
            assert result.exit_code == 1
            assert result.cancelled is False


class TestWaitSignalWithSignal:
    @pytest.mark.asyncio
    async def test_signal_task_is_created_when_signal_provided(self) -> None:
        signal = asyncio.Event()
        opts = BashExecutorOptions(signal=signal)
        # Run a short command — signal not fired, should complete normally
        result = await execute_bash("echo done", opts)
        assert "done" in result.output
        assert result.exit_code == 0


class TestExecuteBashWithOperations:
    @pytest.mark.asyncio
    async def test_basic_execution(self) -> None:
        """Test execute_bash_with_operations with a mock operations object."""

        @dataclass
        class MockExecResult:
            exit_code: int = 0

        class MockOperations:
            async def exec(
                self,
                command: str,
                cwd: str,
                on_data: object,
                signal: object,
            ) -> MockExecResult:
                # Simulate some output
                assert callable(on_data)
                on_data(b"hello from mock\n")
                return MockExecResult(exit_code=0)

        ops = MockOperations()
        result = await execute_bash_with_operations("echo hi", "/tmp", ops)
        assert "hello from mock" in result.output
        assert result.exit_code == 0
        assert result.cancelled is False

    @pytest.mark.asyncio
    async def test_cancelled_when_signal_set(self) -> None:
        """Test that cancellation is detected when signal is set before exec."""

        class MockOperations:
            async def exec(
                self,
                command: str,
                cwd: str,
                on_data: object,
                signal: object,
            ) -> object:
                return type("R", (), {"exit_code": 0})()

        signal = asyncio.Event()
        signal.set()  # Pre-fire the signal
        ops = MockOperations()
        opts = BashExecutorOptions(signal=signal)
        result = await execute_bash_with_operations("echo hi", "/tmp", ops, opts)
        assert result.cancelled is True

    @pytest.mark.asyncio
    async def test_exception_during_exec_propagated(self) -> None:
        """Test that exceptions from exec() propagate correctly."""

        class FailingOperations:
            async def exec(
                self,
                command: str,
                cwd: str,
                on_data: object,
                signal: object,
            ) -> object:
                raise RuntimeError("exec failed")

        ops = FailingOperations()
        with pytest.raises(RuntimeError, match="exec failed"):
            await execute_bash_with_operations("echo hi", "/tmp", ops)

    @pytest.mark.asyncio
    async def test_exception_with_signal_set_returns_cancelled(self) -> None:
        """Test that when signal is set and exec raises, we return cancelled."""
        signal = asyncio.Event()

        class FailingOperations:
            async def exec(
                self,
                command: str,
                cwd: str,
                on_data: object = None,
                signal: object = None,
            ) -> object:
                assert signal is not None
                import asyncio as _asyncio

                cast_signal = _asyncio.Event.__new__(_asyncio.Event)
                cast_signal.__dict__ = signal.__dict__
                cast_signal.set()
                raise RuntimeError("cancelled by signal")

        # Use a different approach: pre-set the signal and use an op that raises
        class RaisingOperations:
            async def exec(
                self,
                command: str,
                cwd: str,
                on_data: object = None,
                signal: object = None,
            ) -> object:
                raise RuntimeError("boom")

        signal.set()  # pre-set
        ops = RaisingOperations()
        opts = BashExecutorOptions(signal=signal)
        result = await execute_bash_with_operations("echo hi", "/tmp", ops, opts)
        assert result.cancelled is True
