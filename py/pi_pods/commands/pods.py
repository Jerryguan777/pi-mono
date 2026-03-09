"""Pod management commands for pi_pods."""

import importlib.resources
import os
import sys
import tempfile
from pathlib import Path
from typing import Literal

from pi_pods.config import add_pod, load_config, remove_pod, set_active_pod
from pi_pods.ssh import scp_file, ssh_exec, ssh_exec_stream
from pi_pods.types import GPU, Pod


def list_pods() -> None:
    """Print all configured pods to stdout."""
    config = load_config()
    pod_names = list(config.pods.keys())

    if not pod_names:
        print("No pods configured. Use 'pi pods setup' to add a pod.")
        return

    print("Configured pods:")
    for name in pod_names:
        pod_obj = config.pods[name]
        is_active = config.active == name
        marker = "* " if is_active else "  "
        gpu_count = len(pod_obj.gpus)
        gpu_info = f"{gpu_count}x {pod_obj.gpus[0].name}" if gpu_count > 0 else "no GPUs detected"
        vllm_info = f" (vLLM: {pod_obj.vllm_version})" if pod_obj.vllm_version else ""
        print(f"{marker}{name} - {gpu_info}{vllm_info} - {pod_obj.ssh}")
        if pod_obj.models_path:
            print(f"    Models: {pod_obj.models_path}")
        if pod_obj.vllm_version == "gpt-oss":
            print("    WARNING: GPT-OSS build - only for GPT-OSS models")


async def setup_pod(
    name: str,
    ssh_cmd: str,
    mount: str | None = None,
    models_path: str | None = None,
    vllm: Literal["release", "nightly", "gpt-oss"] = "release",
) -> None:
    """Set up a new GPU pod.

    Validates env vars (HF_TOKEN, PI_API_KEY), tests SSH, copies and runs
    the setup script, detects GPUs, and saves config.

    Args:
        name: Local name for the pod.
        ssh_cmd: SSH connection string (e.g. "ssh root@1.2.3.4").
        mount: Optional mount command; last path component used as models_path.
        models_path: Explicit models directory path on the remote pod.
        vllm: vLLM version to install ("release", "nightly", or "gpt-oss").
    """
    hf_token = os.environ.get("HF_TOKEN")
    pi_api_key = os.environ.get("PI_API_KEY")

    if not hf_token:
        print("ERROR: HF_TOKEN environment variable is required", file=sys.stderr)
        print("Get a token from: https://huggingface.co/settings/tokens", file=sys.stderr)
        print("Then run: export HF_TOKEN=your_token_here", file=sys.stderr)
        sys.exit(1)

    if not pi_api_key:
        print("ERROR: PI_API_KEY environment variable is required", file=sys.stderr)
        print("Set an API key: export PI_API_KEY=your_api_key_here", file=sys.stderr)
        sys.exit(1)

    # Resolve models path
    resolved_models_path = models_path
    if not resolved_models_path and mount:
        parts = mount.split()
        resolved_models_path = parts[-1] if parts else None

    if not resolved_models_path:
        print("ERROR: --models-path is required (or must be extractable from --mount)", file=sys.stderr)
        sys.exit(1)

    print(f"Setting up pod '{name}'...")
    print(f"SSH: {ssh_cmd}")
    print(f"Models path: {resolved_models_path}")
    vllm_label = " (GPT-OSS special build)" if vllm == "gpt-oss" else ""
    print(f"vLLM version: {vllm}{vllm_label}")
    if mount:
        print(f"Mount command: {mount}")
    print("")

    # Test SSH connection
    print("Testing SSH connection...")
    test_result = await ssh_exec(ssh_cmd, "echo 'SSH OK'")
    if test_result.exit_code != 0:
        print("Failed to connect via SSH", file=sys.stderr)
        print(test_result.stderr, file=sys.stderr)
        sys.exit(1)
    print("SSH connection successful")

    # Copy setup script.
    # Read via importlib.resources (works in both directory and zip installs),
    # then write to a named temp file so scp_file() gets a stable path.
    print("Copying setup script...")
    script_content = (importlib.resources.files("pi_pods") / "scripts" / "pod_setup.sh").read_text(encoding="utf-8")
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sh")
    try:
        Path(tmp_path).write_text(script_content, encoding="utf-8")
        os.close(tmp_fd)
        success = await scp_file(ssh_cmd, tmp_path, "/tmp/pod_setup.sh")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if not success:
        print("Failed to copy setup script", file=sys.stderr)
        sys.exit(1)
    print("Setup script copied")

    # Build setup command
    setup_cmd = (
        f"bash /tmp/pod_setup.sh --models-path '{resolved_models_path}' "
        f"--hf-token '{hf_token}' --vllm-api-key '{pi_api_key}'"
    )
    if mount:
        setup_cmd += f" --mount '{mount}'"
    setup_cmd += f" --vllm '{vllm}'"

    print("")
    print("Running setup (this will take 2-5 minutes)...")
    print("")

    exit_code = await ssh_exec_stream(ssh_cmd, setup_cmd, force_tty=True)
    if exit_code != 0:
        print("\nSetup failed. Check the output above for errors.", file=sys.stderr)
        sys.exit(1)

    # Detect GPUs
    print("")
    print("Detecting GPU configuration...")
    gpu_result = await ssh_exec(ssh_cmd, "nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader")

    gpus: list[GPU] = []
    if gpu_result.exit_code == 0 and gpu_result.stdout:
        for line in gpu_result.stdout.strip().splitlines():
            parts = [s.strip() for s in line.split(",")]
            if len(parts) >= 1 and parts[0].isdigit():
                gpu_id = int(parts[0])
                gpu_name = parts[1] if len(parts) > 1 else "Unknown"
                gpu_mem = parts[2] if len(parts) > 2 else "Unknown"
                gpus.append(GPU(id=gpu_id, name=gpu_name, memory=gpu_mem))

    print(f"Detected {len(gpus)} GPU(s)")
    for gpu in gpus:
        print(f"  GPU {gpu.id}: {gpu.name} ({gpu.memory})")

    # Save pod configuration
    pod_obj = Pod(
        ssh=ssh_cmd,
        gpus=gpus,
        models={},
        models_path=resolved_models_path,
        vllm_version=vllm,
    )
    add_pod(name, pod_obj)

    print("")
    print(f"Pod '{name}' setup complete and set as active pod")
    print("")
    print("You can now deploy models with:")
    print("  pi start <model> --name <name>")


def switch_active_pod(name: str) -> None:
    """Switch the active pod by name.

    Prints an error and exits if the pod is not found.
    """
    try:
        set_active_pod(name)
    except ValueError:
        config = load_config()
        print(f"Pod '{name}' not found", file=sys.stderr)
        print("\nAvailable pods:", file=sys.stderr)
        for pod_name in config.pods:
            print(f"  {pod_name}", file=sys.stderr)
        sys.exit(1)

    print(f"Switched active pod to '{name}'")


def remove_pod_command(name: str) -> None:
    """Remove a pod from the local config.

    Prints an error and exits if the pod is not found.
    """
    config = load_config()
    if name not in config.pods:
        print(f"Pod '{name}' not found", file=sys.stderr)
        sys.exit(1)

    remove_pod(name)
    print(f"Removed pod '{name}' from configuration")
    print("Note: This only removes the local configuration. The remote pod is not affected.")
