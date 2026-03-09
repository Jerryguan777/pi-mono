"""E2E test: Pods SSH command assembly.

Verifies that ssh_exec and scp_file build correct command-line arguments
by intercepting the actual arguments passed to asyncio.create_subprocess_exec.
No real SSH connections are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pi_pods.ssh import (
    _build_ssh_args,
    parse_ssh_host,
    scp_file,
    ssh_exec,
    ssh_exec_stream,
)


# ---------------------------------------------------------------------------
# Unit-level: _build_ssh_args
# ---------------------------------------------------------------------------


def test_build_ssh_args_basic() -> None:
    """Basic SSH command parsing."""
    binary, args = _build_ssh_args("ssh root@1.2.3.4")
    assert binary == "ssh"
    assert args == ["root@1.2.3.4"]


def test_build_ssh_args_with_port() -> None:
    """SSH command with -p port."""
    binary, args = _build_ssh_args("ssh -p 2222 root@1.2.3.4")
    assert binary == "ssh"
    assert args == ["-p", "2222", "root@1.2.3.4"]


def test_build_ssh_args_keep_alive() -> None:
    """keep_alive=True should prepend ServerAlive options."""
    binary, args = _build_ssh_args("ssh root@host.com", keep_alive=True)
    assert binary == "ssh"
    assert "-o" in args
    assert "ServerAliveInterval=30" in args
    assert "ServerAliveCountMax=120" in args
    # Host should still be in the args
    assert "root@host.com" in args


def test_build_ssh_args_force_tty() -> None:
    """force_tty=True should prepend -t."""
    _binary, args = _build_ssh_args("ssh root@host.com", force_tty=True)
    assert args[0] == "-t"
    assert "root@host.com" in args


def test_build_ssh_args_force_tty_not_duplicated() -> None:
    """If -t is already in the command, it should not be added again."""
    _binary, args = _build_ssh_args("ssh -t root@host.com", force_tty=True)
    assert args.count("-t") == 1


def test_build_ssh_args_keep_alive_and_tty() -> None:
    """Both keep_alive and force_tty together."""
    _binary, args = _build_ssh_args("ssh root@host.com", keep_alive=True, force_tty=True)
    assert "-t" in args
    assert "ServerAliveInterval=30" in args
    assert "root@host.com" in args


# ---------------------------------------------------------------------------
# parse_ssh_host
# ---------------------------------------------------------------------------


def test_parse_ssh_host_basic() -> None:
    assert parse_ssh_host("ssh root@1.2.3.4") == "1.2.3.4"


def test_parse_ssh_host_with_port() -> None:
    assert parse_ssh_host("ssh -p 22 root@host.com") == "host.com"


def test_parse_ssh_host_no_at() -> None:
    assert parse_ssh_host("ssh localhost") == "localhost"


# ---------------------------------------------------------------------------
# ssh_exec: verify full argument list passed to create_subprocess_exec
# ---------------------------------------------------------------------------


async def test_ssh_exec_command_args() -> None:
    """ssh_exec should pass the correct args to create_subprocess_exec."""
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"output", b""))
    mock_proc.returncode = 0

    with patch("pi_pods.ssh.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc

        result = await ssh_exec("ssh root@10.0.0.1", "ls -la")

        mock_exec.assert_called_once()
        call_args = mock_exec.call_args
        all_args = list(call_args[0])
        # First positional arg is the binary ("ssh")
        assert all_args[0] == "ssh"
        # Host and command should be in the args
        assert "root@10.0.0.1" in all_args
        assert all_args[-1] == "ls -la"
        assert result.stdout == "output"
        assert result.exit_code == 0


async def test_ssh_exec_with_keep_alive() -> None:
    """ssh_exec with keep_alive should include ServerAlive options."""
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))
    mock_proc.returncode = 0

    with patch("pi_pods.ssh.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc

        await ssh_exec("ssh root@10.0.0.1", "uptime", keep_alive=True)

        call_args = mock_exec.call_args[0]
        # Flatten to check ServerAlive is present
        all_args = list(call_args)
        assert "ServerAliveInterval=30" in all_args


async def test_ssh_exec_returns_stderr() -> None:
    """ssh_exec should capture stderr."""
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error msg"))
    mock_proc.returncode = 1

    with patch("pi_pods.ssh.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc

        result = await ssh_exec("ssh user@host", "bad_cmd")
        assert result.stderr == "error msg"
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# ssh_exec_stream: verify full argument list
# ---------------------------------------------------------------------------


async def test_ssh_exec_stream_args() -> None:
    """ssh_exec_stream should build correct args with force_tty and keep_alive."""
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=None)
    mock_proc.returncode = 0

    with patch("pi_pods.ssh.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc

        exit_code = await ssh_exec_stream(
            "ssh root@10.0.0.1",
            "nvidia-smi",
            force_tty=True,
            keep_alive=True,
        )

        call_args = mock_exec.call_args[0]
        all_args = list(call_args)
        # -t should be present (force_tty)
        assert "-t" in all_args
        # ServerAlive should be present (keep_alive)
        assert "ServerAliveInterval=30" in all_args
        # Command should be last
        assert all_args[-1] == "nvidia-smi"
        assert exit_code == 0


# ---------------------------------------------------------------------------
# scp_file: verify SCP argument construction
# ---------------------------------------------------------------------------


async def test_scp_file_args() -> None:
    """scp_file should construct correct SCP arguments."""
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=None)
    mock_proc.returncode = 0

    with patch("pi_pods.ssh.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc

        result = await scp_file("ssh root@10.0.0.1", "/tmp/local.txt", "/remote/path.txt")

        assert result is True
        call_args = mock_exec.call_args[0]
        all_args = list(call_args)
        assert all_args[0] == "scp"
        assert "-P" in all_args
        assert "22" in all_args  # default port
        assert "/tmp/local.txt" in all_args
        assert "root@10.0.0.1:/remote/path.txt" in all_args


async def test_scp_file_custom_port() -> None:
    """scp_file should use the port from the SSH command."""
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=None)
    mock_proc.returncode = 0

    with patch("pi_pods.ssh.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc

        await scp_file("ssh -p 2222 root@10.0.0.1", "/local/f.tar", "/remote/f.tar")

        call_args = mock_exec.call_args[0]
        all_args = list(call_args)
        assert "2222" in all_args


async def test_scp_file_failure() -> None:
    """scp_file should return False on non-zero exit code."""
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=None)
    mock_proc.returncode = 1

    with patch("pi_pods.ssh.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc

        result = await scp_file("ssh root@host", "/local", "/remote")
        assert result is False
