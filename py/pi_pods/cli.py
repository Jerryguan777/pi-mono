"""CLI entry point for pi_pods using Typer."""

import asyncio
import os
from typing import Annotated

import typer

from pi_pods.commands.models import (
    list_models,
    show_known_models,
    start_model,
    stop_all_models,
    stop_model,
    view_logs,
)
from pi_pods.commands.pods import (
    list_pods,
    remove_pod_command,
    setup_pod,
    switch_active_pod,
)
from pi_pods.commands.prompt import prompt_model
from pi_pods.config import get_active_pod, load_config
from pi_pods.ssh import ssh_exec_stream

app = typer.Typer(
    name="pi",
    help="Manage vLLM deployments on GPU pods.",
    no_args_is_help=True,
    add_completion=False,
)

pods_app = typer.Typer(
    name="pods",
    help="Pod management commands.",
    no_args_is_help=False,
    invoke_without_command=True,
)
app.add_typer(pods_app, name="pods")


# ---------------------------------------------------------------------------
# pods sub-commands
# ---------------------------------------------------------------------------


@pods_app.callback(invoke_without_command=True)
def pods_callback(ctx: typer.Context) -> None:
    """List all pods or run a subcommand."""
    if ctx.invoked_subcommand is None:
        list_pods()


@pods_app.command("setup")
def pods_setup(
    name: Annotated[str, typer.Argument(help="Name for this pod")],
    ssh_cmd: Annotated[str, typer.Argument(help="SSH connection string, e.g. 'ssh root@1.2.3.4'")],
    mount: Annotated[str | None, typer.Option("--mount", help="Mount command; last path used as models-path")] = None,
    models_path: Annotated[str | None, typer.Option("--models-path", help="Explicit models directory path")] = None,
    vllm: Annotated[str, typer.Option("--vllm", help="vLLM version: release, nightly, gpt-oss")] = "release",
) -> None:
    """Set up a new GPU pod."""
    from typing import Literal

    vllm_version_map: dict[str, Literal["release", "nightly", "gpt-oss"]] = {
        "release": "release",
        "nightly": "nightly",
        "gpt-oss": "gpt-oss",
    }
    if vllm not in vllm_version_map:
        typer.echo(f"Invalid vLLM type: {vllm}. Valid options: release, nightly, gpt-oss", err=True)
        raise typer.Exit(1)

    asyncio.run(
        setup_pod(
            name=name,
            ssh_cmd=ssh_cmd,
            mount=mount,
            models_path=models_path,
            vllm=vllm_version_map[vllm],
        )
    )


@pods_app.command("active")
def pods_active(
    name: Annotated[str, typer.Argument(help="Pod name to set as active")],
) -> None:
    """Switch the active pod."""
    switch_active_pod(name)


@pods_app.command("remove")
def pods_remove(
    name: Annotated[str, typer.Argument(help="Pod name to remove")],
) -> None:
    """Remove a pod from local config."""
    remove_pod_command(name)


# ---------------------------------------------------------------------------
# shell / ssh
# ---------------------------------------------------------------------------


@app.command("shell")
def shell(
    pod_name: Annotated[str | None, typer.Argument(help="Pod name (uses active pod if omitted)")] = None,
) -> None:
    """Open an interactive SSH shell on a pod."""
    import subprocess

    if pod_name:
        config = load_config()
        pod_obj = config.pods.get(pod_name)
        if pod_obj is None:
            typer.echo(f"Pod '{pod_name}' not found", err=True)
            raise typer.Exit(1)
        pod_info = (pod_name, pod_obj)
    else:
        active = get_active_pod()
        if active is None:
            typer.echo("No active pod. Use 'pi pods active <name>' to set one.", err=True)
            raise typer.Exit(1)
        pod_info = active

    name_str, pod_obj = pod_info
    typer.echo(f"Connecting to pod '{name_str}'...")

    # Strip the leading 'ssh' from the command
    ssh_args = pod_obj.ssh.split()[1:]
    result = subprocess.run(["ssh", *ssh_args], check=False)
    raise typer.Exit(result.returncode)


@app.command("ssh")
def ssh_command(
    command: Annotated[str, typer.Argument(help="Remote command to run")],
    pod_name: Annotated[str | None, typer.Option("--pod", help="Pod name override")] = None,
) -> None:
    """Run an SSH command on a pod."""
    if pod_name:
        config = load_config()
        pod_obj = config.pods.get(pod_name)
        if pod_obj is None:
            typer.echo(f"Pod '{pod_name}' not found", err=True)
            raise typer.Exit(1)
        pod_info = (pod_name, pod_obj)
    else:
        active = get_active_pod()
        if active is None:
            typer.echo("No active pod. Use 'pi pods active <name>' to set one.", err=True)
            raise typer.Exit(1)
        pod_info = active

    name_str, pod_obj = pod_info
    typer.echo(f"Running on pod '{name_str}': {command}")
    exit_code = asyncio.run(ssh_exec_stream(pod_obj.ssh, command))
    raise typer.Exit(exit_code)


# ---------------------------------------------------------------------------
# model management
# ---------------------------------------------------------------------------


@app.command("start")
def start(
    model_id: Annotated[str | None, typer.Argument(help="HuggingFace model ID")] = None,
    name: Annotated[str | None, typer.Option("--name", help="Local name for this deployment")] = None,
    pod_override: Annotated[str | None, typer.Option("--pod", help="Pod name override")] = None,
    memory: Annotated[str | None, typer.Option("--memory", help="GPU memory utilization (e.g. 80%)")] = None,
    context: Annotated[
        str | None, typer.Option("--context", help="Context window (4k, 8k, 16k, 32k, 64k, 128k)")
    ] = None,
    gpus: Annotated[int | None, typer.Option("--gpus", help="Number of GPUs (predefined models only)")] = None,
    vllm_args: Annotated[list[str] | None, typer.Option("--vllm", help="Custom vLLM arguments")] = None,
) -> None:
    """Start a model deployment on a pod."""
    if model_id is None:
        asyncio.run(show_known_models())
        return

    if name is None:
        typer.echo("--name is required", err=True)
        raise typer.Exit(1)

    if vllm_args and (memory or context or gpus):
        typer.echo(
            "Warning: --memory, --context, and --gpus are ignored when --vllm is specified",
            err=False,
        )
        typer.echo("  Using only custom vLLM arguments")
        typer.echo("")

    asyncio.run(
        start_model(
            model_id=model_id,
            name=name,
            pod=pod_override,
            vllm_args=vllm_args if vllm_args else None,
            memory=memory,
            context=context,
            gpus=gpus,
        )
    )


@app.command("stop")
def stop(
    name: Annotated[str | None, typer.Argument(help="Model name (stops all if omitted)")] = None,
    pod_override: Annotated[str | None, typer.Option("--pod", help="Pod name override")] = None,
) -> None:
    """Stop a model deployment (or all models if no name given)."""
    if name is None:
        asyncio.run(stop_all_models(pod=pod_override))
    else:
        asyncio.run(stop_model(name=name, pod=pod_override))


@app.command("list")
def list_cmd(
    pod_override: Annotated[str | None, typer.Option("--pod", help="Pod name override")] = None,
) -> None:
    """List running models on a pod."""
    asyncio.run(list_models(pod=pod_override))


@app.command("logs")
def logs(
    name: Annotated[str, typer.Argument(help="Model name")],
    pod_override: Annotated[str | None, typer.Option("--pod", help="Pod name override")] = None,
) -> None:
    """Stream logs for a model."""
    asyncio.run(view_logs(name=name, pod=pod_override))


@app.command("agent")
def agent(
    name: Annotated[str, typer.Argument(help="Model name")],
    message: Annotated[list[str] | None, typer.Argument(help="Message(s) to send")] = None,
    pod_override: Annotated[str | None, typer.Option("--pod", help="Pod name override")] = None,
) -> None:
    """Chat with a model using the pi-agent."""
    api_key = os.environ.get("PI_API_KEY")
    user_args: list[str] = list(message) if message else []
    asyncio.run(
        prompt_model(
            model_name=name,
            user_args=user_args,
            pod=pod_override,
            api_key=api_key,
        )
    )


def main() -> None:
    """Entry point for the pi_pods CLI."""
    app()


if __name__ == "__main__":
    main()
