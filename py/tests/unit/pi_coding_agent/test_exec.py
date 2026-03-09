"""Tests for pi_coding_agent.core.exec."""

from __future__ import annotations

import asyncio

import pytest

from pi_coding_agent.core.exec import ExecOptions, exec_command


@pytest.mark.asyncio
class TestExecCommand:
    async def test_simple_echo(self) -> None:
        result = await exec_command("echo", ["hello"], "/tmp")
        assert result.code == 0
        assert "hello" in result.stdout
        assert result.killed is False

    async def test_stderr_captured(self) -> None:
        result = await exec_command("sh", ["-c", "echo err >&2"], "/tmp")
        assert "err" in result.stderr
        assert result.code == 0

    async def test_nonzero_exit_code(self) -> None:
        result = await exec_command("sh", ["-c", "exit 42"], "/tmp")
        assert result.code == 42

    async def test_timeout_kills_process(self) -> None:
        opts = ExecOptions(timeout=0.1)
        result = await exec_command("sleep", ["10"], "/tmp", opts)
        assert result.killed is True

    async def test_already_aborted_signal(self) -> None:
        signal = asyncio.Event()
        signal.set()
        opts = ExecOptions(signal=signal)
        result = await exec_command("echo", ["hi"], "/tmp", opts)
        assert result.killed is True

    async def test_nonexistent_command_returns_error(self) -> None:
        result = await exec_command("this-command-does-not-exist-xyzzy", [], "/tmp")
        assert result.code != 0

    async def test_cwd_used(self, tmp_path: object) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            result = await exec_command("pwd", [], d)
            assert result.code == 0
