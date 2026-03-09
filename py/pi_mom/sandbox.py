"""Sandbox execution environment — port of packages/mom/src/sandbox.ts."""

from __future__ import annotations

import asyncio
import shlex
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class HostSandboxConfig:
    """Configuration for running commands directly on the host."""

    type: Literal["host"] = "host"


@dataclass
class DockerSandboxConfig:
    """Configuration for running commands inside a Docker container."""

    container: str
    type: Literal["docker"] = "docker"


SandboxConfig = HostSandboxConfig | DockerSandboxConfig


@dataclass
class ExecResult:
    """Result of a command execution."""

    stdout: str
    stderr: str
    code: int


@dataclass
class ExecOptions:
    """Options for command execution."""

    timeout: int | None = None
    signal: asyncio.Event | None = None


_MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB per stream


class Executor(ABC):
    """Abstract base class for command executors."""

    @abstractmethod
    async def exec(
        self,
        command: str,
        timeout: int | None = None,
        signal: asyncio.Event | None = None,
    ) -> ExecResult:
        """Execute a bash command and return the result."""
        ...

    @abstractmethod
    def get_workspace_path(self, host_path: str) -> str:
        """Translate a host filesystem path to the executor's path."""
        ...


class HostExecutor(Executor):
    """Runs commands directly on the host machine."""

    async def exec(
        self,
        command: str,
        timeout: int | None = None,
        signal: asyncio.Event | None = None,
    ) -> ExecResult:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )

        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []
        stdout_bytes = 0
        stderr_bytes = 0

        async def read_stdout() -> None:
            nonlocal stdout_bytes
            if proc.stdout is None:
                raise RuntimeError("subprocess stdout is None")
            async for chunk in proc.stdout:
                stdout_bytes += len(chunk)
                if stdout_bytes <= _MAX_OUTPUT_BYTES:
                    stdout_chunks.append(chunk)

        async def read_stderr() -> None:
            nonlocal stderr_bytes
            if proc.stderr is None:
                raise RuntimeError("subprocess stderr is None")
            async for chunk in proc.stderr:
                stderr_bytes += len(chunk)
                if stderr_bytes <= _MAX_OUTPUT_BYTES:
                    stderr_chunks.append(chunk)

        async def _read_all() -> None:
            await asyncio.gather(read_stdout(), read_stderr())

        async def wait_with_abort() -> int:
            read_task = asyncio.create_task(_read_all())
            wait_task = asyncio.create_task(proc.wait())

            if signal is not None:
                signal_task = asyncio.create_task(signal.wait())
                done, _ = await asyncio.wait(
                    {wait_task, signal_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if signal_task in done and signal.is_set():
                    # Kill the process group
                    try:
                        import os
                        import signal as os_signal

                        os.killpg(os.getpgid(proc.pid), os_signal.SIGKILL)
                    except Exception:
                        proc.kill()
                    await wait_task
                    read_task.cancel()
                    out = b"".join(stdout_chunks).decode("utf-8", errors="replace")
                    err = b"".join(stderr_chunks).decode("utf-8", errors="replace")
                    raise RuntimeError(f"{out}\n{err}\nCommand aborted".strip())
                signal_task.cancel()
            else:
                await wait_task

            await read_task
            return proc.returncode or 0

        try:
            if timeout is not None and timeout > 0:
                try:
                    code = await asyncio.wait_for(wait_with_abort(), timeout=float(timeout))
                except TimeoutError:
                    try:
                        import os
                        import signal as os_signal

                        os.killpg(os.getpgid(proc.pid), os_signal.SIGKILL)
                    except Exception:
                        proc.kill()
                    out = b"".join(stdout_chunks).decode("utf-8", errors="replace")
                    err = b"".join(stderr_chunks).decode("utf-8", errors="replace")
                    raise RuntimeError(f"{out}\n{err}\nCommand timed out after {timeout} seconds".strip()) from None
            else:
                code = await wait_with_abort()
        except RuntimeError:
            raise

        stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
        stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        return ExecResult(stdout=stdout, stderr=stderr, code=code)

    def get_workspace_path(self, host_path: str) -> str:
        return host_path


class DockerExecutor(Executor):
    """Runs commands inside a Docker container via `docker exec`."""

    def __init__(self, container: str) -> None:
        self._container = container
        self._host = HostExecutor()

    async def exec(
        self,
        command: str,
        timeout: int | None = None,
        signal: asyncio.Event | None = None,
    ) -> ExecResult:
        escaped = _shell_escape(command)
        docker_cmd = f"docker exec {shlex.quote(self._container)} sh -c {escaped}"
        return await self._host.exec(docker_cmd, timeout=timeout, signal=signal)

    def get_workspace_path(self, host_path: str) -> str:
        return "/workspace"


def parse_sandbox_arg(value: str) -> SandboxConfig:
    """Parse a sandbox argument string into a SandboxConfig."""
    if value == "host":
        return HostSandboxConfig()
    if value.startswith("docker:"):
        container = value[len("docker:") :]
        if not container:
            print("Error: docker sandbox requires container name (e.g., docker:mom-sandbox)", file=sys.stderr)
            sys.exit(1)
        return DockerSandboxConfig(container=container)
    print(f"Error: Invalid sandbox type '{value}'. Use 'host' or 'docker:<container-name>'", file=sys.stderr)
    sys.exit(1)


async def validate_sandbox(config: SandboxConfig) -> None:
    """Validate that the sandbox is accessible and ready."""
    if isinstance(config, HostSandboxConfig):
        return

    host = HostExecutor()

    # Check if Docker is available
    try:
        result = await host.exec("docker --version")
        if result.code != 0:
            raise RuntimeError("docker not available")
    except Exception:
        print("Error: Docker is not installed or not in PATH", file=sys.stderr)
        sys.exit(1)

    # Check if container exists and is running
    try:
        result = await host.exec(f"docker inspect -f '{{{{.State.Running}}}}' {shlex.quote(config.container)}")
        if result.stdout.strip() != "true":
            print(f"Error: Container '{config.container}' is not running.", file=sys.stderr)
            print(f"Start it with: docker start {config.container}", file=sys.stderr)
            sys.exit(1)
    except Exception:
        print(f"Error: Container '{config.container}' does not exist.", file=sys.stderr)
        print("Create it with: ./docker.sh create <data-dir>", file=sys.stderr)
        sys.exit(1)

    print(f"  Docker container '{config.container}' is running.", flush=True)


def create_executor(config: SandboxConfig) -> Executor:
    """Create an Executor for the given sandbox configuration."""
    if isinstance(config, HostSandboxConfig):
        return HostExecutor()
    return DockerExecutor(config.container)


def _shell_escape(s: str) -> str:
    """Escape a string for safe use in a shell command."""
    return shlex.quote(s)
