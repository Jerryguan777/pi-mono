"""Unit tests for pi_pods.ssh."""

import asyncio
from unittest.mock import AsyncMock, patch

from pi_pods.ssh import SSHResult, scp_file, ssh_exec, ssh_exec_stream


class TestParseSshHost:
    def test_extracts_host_from_simple_command(self) -> None:
        from pi_pods.ssh import parse_ssh_host

        assert parse_ssh_host("ssh root@1.2.3.4") == "1.2.3.4"

    def test_extracts_host_with_port_flag(self) -> None:
        from pi_pods.ssh import parse_ssh_host

        assert parse_ssh_host("ssh -p 2222 root@host.example.com") == "host.example.com"

    def test_returns_localhost_when_no_user_at_host(self) -> None:
        from pi_pods.ssh import parse_ssh_host

        assert parse_ssh_host("ssh -o StrictHostKeyChecking=no") == "localhost"


class TestSSHResult:
    def test_dataclass_fields(self) -> None:
        result = SSHResult(stdout="out", stderr="err", exit_code=0)
        assert result.stdout == "out"
        assert result.stderr == "err"
        assert result.exit_code == 0


class TestSshExec:
    async def test_returns_stdout_stderr_exitcode(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"hello\n", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            result = await ssh_exec("ssh root@1.2.3.4", "echo hello")

        mock_create.assert_called_once()
        assert result.stdout == "hello\n"
        assert result.stderr == ""
        assert result.exit_code == 0

    async def test_keep_alive_prepends_options(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await ssh_exec("ssh root@1.2.3.4", "uptime", keep_alive=True)

        call_args = mock_create.call_args
        args = call_args[0]  # positional args: binary, *ssh_args
        # The full call: ssh, -o, ServerAliveInterval=30, -o, ServerAliveCountMax=120, root@1.2.3.4, uptime
        assert "-o" in args
        assert "ServerAliveInterval=30" in args
        assert "ServerAliveCountMax=120" in args

    async def test_returns_error_result_on_exception(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=OSError("no such file")):
            result = await ssh_exec("ssh root@1.2.3.4", "echo hi")

        assert result.exit_code == 1
        assert "no such file" in result.stderr

    async def test_handles_nonzero_exit_code(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
        mock_proc.returncode = 42

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await ssh_exec("ssh root@1.2.3.4", "false")

        assert result.exit_code == 42


class TestSshExecStream:
    async def test_returns_exit_code(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            code = await ssh_exec_stream("ssh root@1.2.3.4", "ls")

        assert code == 0

    async def test_silent_mode_uses_devnull(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await ssh_exec_stream("ssh root@1.2.3.4", "ls", silent=True)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs.get("stdout") == asyncio.subprocess.DEVNULL
        assert call_kwargs.get("stderr") == asyncio.subprocess.DEVNULL

    async def test_force_tty_prepends_t_flag(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await ssh_exec_stream("ssh root@1.2.3.4", "bash setup.sh", force_tty=True)

        args = mock_create.call_args[0]
        assert "-t" in args

    async def test_force_tty_not_duplicated(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            # ssh_cmd already contains -t
            await ssh_exec_stream("ssh -t root@1.2.3.4", "ls", force_tty=True)

        args = mock_create.call_args[0]
        assert args.count("-t") == 1

    async def test_returns_1_on_exception(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=OSError("nope")):
            code = await ssh_exec_stream("ssh root@1.2.3.4", "ls")

        assert code == 1


class TestScpFile:
    async def test_returns_true_on_success(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            result = await scp_file("ssh root@1.2.3.4", "/tmp/local.sh", "/tmp/remote.sh")

        assert result is True
        args = mock_create.call_args[0]
        # scp -P 22 /tmp/local.sh root@1.2.3.4:/tmp/remote.sh
        assert args[0] == "scp"
        assert "-P" in args
        assert "22" in args
        assert "/tmp/local.sh" in args
        assert "root@1.2.3.4:/tmp/remote.sh" in args

    async def test_returns_false_on_nonzero_exit(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await scp_file("ssh root@1.2.3.4", "/local", "/remote")

        assert result is False

    async def test_returns_false_when_host_not_parseable(self) -> None:
        result = await scp_file("ssh -o Option=val", "/local", "/remote")
        assert result is False

    async def test_uses_custom_port(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await scp_file("ssh -p 2222 root@1.2.3.4", "/local", "/remote")

        args = mock_create.call_args[0]
        port_idx = list(args).index("-P")
        assert args[port_idx + 1] == "2222"

    async def test_returns_false_on_exception(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=OSError("nope")):
            result = await scp_file("ssh root@1.2.3.4", "/local", "/remote")

        assert result is False
