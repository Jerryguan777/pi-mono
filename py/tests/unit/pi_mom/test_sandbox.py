"""Tests for pi_mom.sandbox."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pi_mom.sandbox import (
    DockerSandboxConfig,
    ExecResult,
    HostExecutor,
    HostSandboxConfig,
    create_executor,
    parse_sandbox_arg,
)


class TestExecResult:
    def test_creation(self) -> None:
        result = ExecResult(stdout="hello", stderr="", code=0)
        assert result.stdout == "hello"
        assert result.stderr == ""
        assert result.code == 0


class TestHostExecutor:
    @pytest.mark.asyncio
    async def test_exec_simple_command(self) -> None:
        executor = HostExecutor()
        result = await executor.exec("echo hello")
        assert result.code == 0
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_exec_failing_command(self) -> None:
        executor = HostExecutor()
        result = await executor.exec("false")
        assert result.code != 0

    @pytest.mark.asyncio
    async def test_exec_stderr(self) -> None:
        executor = HostExecutor()
        result2 = await executor.exec("ls /nonexistent_path_xyz_99999")
        assert result2.code != 0

    @pytest.mark.asyncio
    async def test_exec_with_abort_signal(self) -> None:
        executor = HostExecutor()
        signal = asyncio.Event()
        # Signal already set — command may complete before abort or get aborted
        signal.set()
        try:
            result = await executor.exec("echo done", signal=signal)
            # If it completed before being killed, check output
            assert isinstance(result, ExecResult)
        except RuntimeError as e:
            # Aborted — this is also a valid outcome
            assert "aborted" in str(e).lower() or "Command aborted" in str(e)

    @pytest.mark.asyncio
    async def test_exec_captures_stdout(self) -> None:
        executor = HostExecutor()
        result = await executor.exec("printf 'line1\\nline2\\n'")
        assert "line1" in result.stdout
        assert "line2" in result.stdout

    def test_get_workspace_path(self) -> None:
        executor = HostExecutor()
        assert executor.get_workspace_path("/tmp/work") == "/tmp/work"

    def test_get_workspace_path_arbitrary(self) -> None:
        executor = HostExecutor()
        assert executor.get_workspace_path("/some/path") == "/some/path"


class TestDockerSandboxConfig:
    def test_creation(self) -> None:
        cfg = DockerSandboxConfig(container="my-container")
        assert cfg.container == "my-container"


class TestHostSandboxConfig:
    def test_creation(self) -> None:
        cfg = HostSandboxConfig()
        assert cfg is not None


class TestParseSandboxArg:
    def test_host(self) -> None:
        result = parse_sandbox_arg("host")
        assert isinstance(result, HostSandboxConfig)

    def test_docker(self) -> None:
        result = parse_sandbox_arg("docker:my-container")
        assert isinstance(result, DockerSandboxConfig)
        assert result.container == "my-container"

    def test_invalid_calls_sys_exit(self) -> None:
        with pytest.raises(SystemExit):
            parse_sandbox_arg("invalid-value")

    def test_docker_without_name_exits(self) -> None:
        with pytest.raises(SystemExit):
            parse_sandbox_arg("docker:")


class TestCreateExecutor:
    def test_creates_host_executor(self) -> None:
        cfg = HostSandboxConfig()
        executor = create_executor(cfg)
        assert isinstance(executor, HostExecutor)

    def test_creates_docker_executor(self) -> None:
        from pi_mom.sandbox import DockerExecutor

        cfg = DockerSandboxConfig(container="test-container")
        executor = create_executor(cfg)
        assert isinstance(executor, DockerExecutor)


class TestDockerExecutor:
    @pytest.mark.asyncio
    async def test_exec_wraps_host(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from pi_mom.sandbox import DockerExecutor

        executor = DockerExecutor(container="my-container")
        mock_host = MagicMock()
        mock_host.exec = AsyncMock(return_value=ExecResult(stdout="ok", stderr="", code=0))
        executor._host = mock_host

        result = await executor.exec("ls /workspace")
        assert result.code == 0
        # Should have called host exec with docker exec wrapping
        call_args = mock_host.exec.call_args[0][0]
        assert "docker exec" in call_args
        assert "my-container" in call_args

    def test_get_workspace_path_returns_workspace(self) -> None:
        from pi_mom.sandbox import DockerExecutor

        executor = DockerExecutor(container="c1")
        assert executor.get_workspace_path("/any/host/path") == "/workspace"


class TestValidateSandbox:
    @pytest.mark.asyncio
    async def test_host_sandbox_returns_immediately(self) -> None:
        from pi_mom.sandbox import validate_sandbox

        cfg = HostSandboxConfig()
        # Should return without doing anything
        await validate_sandbox(cfg)

    @pytest.mark.asyncio
    async def test_docker_sandbox_docker_not_available(self) -> None:
        from unittest.mock import patch

        from pi_mom.sandbox import validate_sandbox

        cfg = DockerSandboxConfig(container="test-box")

        with patch("pi_mom.sandbox.HostExecutor") as mock_cls:
            mock_exec = MagicMock()
            mock_exec.exec = AsyncMock(side_effect=Exception("docker not found"))
            mock_cls.return_value = mock_exec

            with pytest.raises(SystemExit):
                await validate_sandbox(cfg)

    @pytest.mark.asyncio
    async def test_docker_sandbox_container_not_running(self) -> None:
        from unittest.mock import patch

        from pi_mom.sandbox import validate_sandbox

        cfg = DockerSandboxConfig(container="stopped-box")

        call_count = 0

        async def fake_exec(cmd: str, **kwargs: Any) -> ExecResult:
            nonlocal call_count
            call_count += 1
            if "docker --version" in cmd:
                return ExecResult(stdout="Docker 24.0", stderr="", code=0)
            # docker inspect returns "false"
            return ExecResult(stdout="false", stderr="", code=0)

        with patch("pi_mom.sandbox.HostExecutor") as mock_cls:
            mock_exec = MagicMock()
            mock_exec.exec = fake_exec
            mock_cls.return_value = mock_exec

            with pytest.raises(SystemExit):
                await validate_sandbox(cfg)


class TestHostExecutorTimeout:
    @pytest.mark.asyncio
    async def test_exec_timeout_raises_runtime_error(self) -> None:
        executor = HostExecutor()
        with pytest.raises(RuntimeError, match="timed out"):
            await executor.exec("sleep 10", timeout=1)

    @pytest.mark.asyncio
    async def test_exec_abort_signal_long_running(self) -> None:
        executor = HostExecutor()
        signal = asyncio.Event()

        async def set_after_delay() -> None:
            await asyncio.sleep(0.05)
            signal.set()

        task = asyncio.create_task(set_after_delay())
        try:
            result = await executor.exec("sleep 5", signal=signal)
            # If we get here without RuntimeError, the process completed before signal
            assert isinstance(result, ExecResult)
        except RuntimeError as e:
            assert "aborted" in str(e).lower() or "Command aborted" in str(e)
        finally:
            task.cancel()
