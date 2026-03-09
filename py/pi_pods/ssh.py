"""SSH execution utilities for pi_pods."""

import asyncio
import sys
from dataclasses import dataclass


@dataclass
class SSHResult:
    """Result of an SSH command execution."""

    stdout: str
    stderr: str
    exit_code: int


def _build_ssh_args(
    ssh_cmd: str,
    *,
    keep_alive: bool = False,
    force_tty: bool = False,
) -> tuple[str, list[str]]:
    """Parse ssh_cmd and build the binary + args list.

    Returns (binary, args_without_command).
    """
    parts = [p for p in ssh_cmd.split(" ") if p]
    binary = parts[0]
    args = list(parts[1:])

    if force_tty and "-t" not in parts:
        args = ["-t", *args]

    if keep_alive:
        args = ["-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=120", *args]

    return binary, args


async def ssh_exec(
    ssh_cmd: str,
    command: str,
    *,
    keep_alive: bool = False,
) -> SSHResult:
    """Execute an SSH command and capture stdout/stderr.

    Args:
        ssh_cmd: Full SSH command string (e.g. "ssh root@1.2.3.4").
        command: Remote command to run.
        keep_alive: If True, add SSH keepalive options.

    Returns:
        SSHResult with stdout, stderr, and exit_code.
    """
    binary, args = _build_ssh_args(ssh_cmd, keep_alive=keep_alive)
    full_args = [*args, command]

    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            *full_args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return SSHResult(
            stdout=stdout_bytes.decode(errors="replace"),
            stderr=stderr_bytes.decode(errors="replace"),
            exit_code=proc.returncode if proc.returncode is not None else 0,
        )
    except Exception as exc:
        return SSHResult(stdout="", stderr=str(exc), exit_code=1)


async def ssh_exec_stream(
    ssh_cmd: str,
    command: str,
    *,
    silent: bool = False,
    force_tty: bool = False,
    keep_alive: bool = False,
) -> int:
    """Execute an SSH command with streaming output to the console.

    Args:
        ssh_cmd: Full SSH command string.
        command: Remote command to run.
        silent: If True, suppress all output.
        force_tty: If True, prepend -t to SSH args.
        keep_alive: If True, add SSH keepalive options.

    Returns:
        Exit code of the remote command.
    """
    binary, args = _build_ssh_args(ssh_cmd, keep_alive=keep_alive, force_tty=force_tty)
    full_args = [*args, command]

    if silent:
        stdin_mode = asyncio.subprocess.DEVNULL
        stdout_mode = asyncio.subprocess.DEVNULL
        stderr_mode = asyncio.subprocess.DEVNULL
    else:
        stdin_mode = None  # inherit
        stdout_mode = None  # inherit
        stderr_mode = None  # inherit

    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            *full_args,
            stdin=stdin_mode,
            stdout=stdout_mode,
            stderr=stderr_mode,
        )
        await proc.wait()
        return proc.returncode if proc.returncode is not None else 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


def parse_ssh_host(ssh_cmd: str) -> str:
    """Extract the hostname from an SSH command string.

    Examples:
        "ssh root@1.2.3.4"        -> "1.2.3.4"
        "ssh -p 22 root@host.com" -> "host.com"

    Returns "localhost" if no user@host part is found.
    """
    for part in ssh_cmd.split():
        if "@" in part:
            return part.split("@")[1]
    return "localhost"


async def scp_file(ssh_cmd: str, local_path: str, remote_path: str) -> bool:
    """Copy a local file to a remote host via SCP.

    Args:
        ssh_cmd: Full SSH command string (used to extract host and port).
        local_path: Path to the local file.
        remote_path: Destination path on the remote host.

    Returns:
        True if SCP succeeded, False otherwise.
    """
    parts = [p for p in ssh_cmd.split(" ") if p]
    host = ""
    port = "22"
    i = 1  # skip 'ssh'
    while i < len(parts):
        if parts[i] == "-p" and i + 1 < len(parts):
            port = parts[i + 1]
            i += 2
        elif not parts[i].startswith("-"):
            host = parts[i]
            break
        else:
            i += 1

    if not host:
        print("Could not parse host from SSH command", file=sys.stderr)
        return False

    scp_args = ["-P", port, local_path, f"{host}:{remote_path}"]

    try:
        proc = await asyncio.create_subprocess_exec(
            "scp",
            *scp_args,
            stdin=None,  # inherit
            stdout=None,  # inherit
            stderr=None,  # inherit
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return False
