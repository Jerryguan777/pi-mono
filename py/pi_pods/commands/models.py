"""Model management commands for pi_pods."""

import asyncio
import contextlib
import importlib.resources
import os
import re
import signal
import sys

from pi_pods.config import get_active_pod, load_config, save_config
from pi_pods.model_configs import get_all_models_data, get_model_config, get_model_name, is_known_model
from pi_pods.ssh import parse_ssh_host, ssh_exec
from pi_pods.types import Pod

# Allowed characters for model deployment names: alphanumeric, dash, underscore.
_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_name(name: str) -> None:
    """Raise SystemExit if name contains characters unsafe for use in shell commands."""
    if not _NAME_RE.match(name):
        print(
            f"Invalid name '{name}': only letters, digits, hyphens and underscores are allowed.",
            file=sys.stderr,
        )
        sys.exit(1)


def _read_script(script_name: str) -> str:
    """Read a bundled shell script from the pi_pods.scripts package data."""
    package_ref = importlib.resources.files("pi_pods") / "scripts" / script_name
    return package_ref.read_text(encoding="utf-8")


def _get_pod(pod_override: str | None) -> tuple[str, Pod]:
    """Return (name, pod) for the named pod or the active pod.

    Prints an error to stderr and calls sys.exit(1) if no pod can be resolved.
    """
    if pod_override:
        config = load_config()
        pod = config.pods.get(pod_override)
        if pod is None:
            print(f"Pod '{pod_override}' not found", file=sys.stderr)
            sys.exit(1)
        return pod_override, pod

    active = get_active_pod()
    if active is None:
        print("No active pod. Use 'pi pods active <name>' to set one.", file=sys.stderr)
        sys.exit(1)
    return active


def _get_next_port(pod: Pod) -> int:
    """Return the next available port starting from 8001."""
    used_ports = {m.port for m in pod.models.values()}
    port = 8001
    while port in used_ports:
        port += 1
    return port


def _select_gpus(pod: Pod, count: int = 1) -> list[int]:
    """Select GPUs for model deployment using a least-used-first strategy."""
    if count == len(pod.gpus):
        return [g.id for g in pod.gpus]

    # Count GPU usage across all running models
    gpu_usage: dict[int, int] = {g.id: 0 for g in pod.gpus}
    for model in pod.models.values():
        for gpu_id in model.gpu:
            gpu_usage[gpu_id] = gpu_usage.get(gpu_id, 0) + 1

    # Sort by least used
    sorted_gpus = sorted(gpu_usage.items(), key=lambda x: x[1])
    return [gpu_id for gpu_id, _ in sorted_gpus[:count]]


async def start_model(
    model_id: str,
    name: str,
    pod: str | None = None,
    vllm_args: list[str] | None = None,
    memory: str | None = None,
    context: str | None = None,
    gpus: int | None = None,
) -> None:
    """Start a vLLM model deployment on a pod.

    Args:
        model_id: HuggingFace model identifier.
        name: Local name for this deployment.
        pod: Pod name override (uses active pod if None).
        vllm_args: Custom vLLM arguments (overrides all other options).
        memory: GPU memory utilization percentage (e.g. "80%").
        context: Context window size (e.g. "8k", "32768").
        gpus: Number of GPUs to use (predefined models only).
    """
    _validate_name(name)

    pod_name, pod_obj = _get_pod(pod)

    if not pod_obj.models_path:
        print("Pod does not have a models path configured", file=sys.stderr)
        sys.exit(1)

    if name in pod_obj.models:
        print(f"Model '{name}' already exists on pod '{pod_name}'", file=sys.stderr)
        sys.exit(1)

    port = _get_next_port(pod_obj)

    chosen_gpus: list[int] = []
    resolved_vllm_args: list[str] = []
    model_config: dict[str, object] | None = None

    if vllm_args:
        # Custom args override everything
        resolved_vllm_args = list(vllm_args)
        print("Using custom vLLM args, GPU allocation managed by vLLM")
    elif is_known_model(model_id):
        if gpus is not None:
            if gpus > len(pod_obj.gpus):
                print(
                    f"Error: Requested {gpus} GPUs but pod only has {len(pod_obj.gpus)}",
                    file=sys.stderr,
                )
                sys.exit(1)
            model_config = get_model_config(model_id, pod_obj.gpus, gpus)
            if model_config:
                chosen_gpus = _select_gpus(pod_obj, gpus)
                args_raw = model_config.get("args", [])
                resolved_vllm_args = [str(a) for a in args_raw] if isinstance(args_raw, list) else []
            else:
                print(
                    f"Model '{get_model_name(model_id)}' does not have a configuration for {gpus} GPU(s)",
                    file=sys.stderr,
                )
                print("Available configurations:", file=sys.stderr)
                for gpu_count in range(1, len(pod_obj.gpus) + 1):
                    if get_model_config(model_id, pod_obj.gpus, gpu_count) is not None:
                        print(f"  - {gpu_count} GPU(s)", file=sys.stderr)
                sys.exit(1)
        else:
            # Find best config for available hardware
            for gpu_count in range(len(pod_obj.gpus), 0, -1):
                model_config = get_model_config(model_id, pod_obj.gpus, gpu_count)
                if model_config:
                    chosen_gpus = _select_gpus(pod_obj, gpu_count)
                    args_raw = model_config.get("args", [])
                    resolved_vllm_args = [str(a) for a in args_raw] if isinstance(args_raw, list) else []
                    break
            if model_config is None:
                print(
                    f"Model '{get_model_name(model_id)}' not compatible with this pod's GPUs",
                    file=sys.stderr,
                )
                sys.exit(1)
    else:
        if gpus is not None:
            print("Error: --gpus can only be used with predefined models", file=sys.stderr)
            print(
                "For custom models, use --vllm with tensor-parallel-size or similar arguments",
                file=sys.stderr,
            )
            sys.exit(1)
        # Unknown model - single GPU default
        chosen_gpus = _select_gpus(pod_obj, 1)
        print("Unknown model, defaulting to single GPU")

    # Apply memory/context overrides
    if not vllm_args:
        if memory:
            fraction = float(memory.replace("%", "")) / 100
            resolved_vllm_args = [a for a in resolved_vllm_args if "gpu-memory-utilization" not in a]
            resolved_vllm_args += ["--gpu-memory-utilization", str(fraction)]
        if context:
            context_sizes: dict[str, int] = {
                "4k": 4096,
                "8k": 8192,
                "16k": 16384,
                "32k": 32768,
                "64k": 65536,
                "128k": 131072,
            }
            max_tokens = context_sizes.get(context.lower()) or int(context)
            resolved_vllm_args = [a for a in resolved_vllm_args if "max-model-len" not in a]
            resolved_vllm_args += ["--max-model-len", str(max_tokens)]

    # Show startup info
    print(f"Starting model '{name}' on pod '{pod_name}'...")
    print(f"Model: {model_id}")
    print(f"Port: {port}")
    gpu_str = ", ".join(str(g) for g in chosen_gpus) if chosen_gpus else "Managed by vLLM"
    print(f"GPU(s): {gpu_str}")
    if model_config:
        notes_raw = model_config.get("notes")
        if notes_raw:
            print(f"Note: {notes_raw}")
    print("")

    # Read and customize model_run.sh from bundled package data
    script_content = _read_script("model_run.sh")
    script_content = (
        script_content.replace("{{MODEL_ID}}", model_id)
        .replace("{{NAME}}", name)
        .replace("{{PORT}}", str(port))
        .replace("{{VLLM_ARGS}}", " ".join(resolved_vllm_args))
    )

    # Upload script to pod
    upload_cmd = f"cat > /tmp/model_run_{name}.sh << 'EOF'\n{script_content}\nEOF\nchmod +x /tmp/model_run_{name}.sh"
    await ssh_exec(pod_obj.ssh, upload_cmd)

    # Build environment variables
    hf_token = os.environ.get("HF_TOKEN", "")
    pi_api_key = os.environ.get("PI_API_KEY", "")

    env_lines = [
        f"export HF_TOKEN='{hf_token}'",
        f"export PI_API_KEY='{pi_api_key}'",
        "export HF_HUB_ENABLE_HF_TRANSFER=1",
        "export VLLM_NO_USAGE_STATS=1",
        "export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        "export FORCE_COLOR=1",
        "export TERM=xterm-256color",
    ]
    if len(chosen_gpus) == 1:
        env_lines.append(f"export CUDA_VISIBLE_DEVICES={chosen_gpus[0]}")

    if model_config:
        env_raw = model_config.get("env")
        if isinstance(env_raw, dict):
            for k, v in env_raw.items():
                env_lines.append(f"export {k}='{v}'")

    env_block = "\n".join(env_lines)

    start_cmd = f"""
{env_block}
mkdir -p ~/.vllm_logs
cat > /tmp/model_wrapper_{name}.sh << 'WRAPPER'
#!/bin/bash
script -q -f -c "/tmp/model_run_{name}.sh" ~/.vllm_logs/{name}.log
exit_code=$?
echo "Script exited with code $exit_code" >> ~/.vllm_logs/{name}.log
exit $exit_code
WRAPPER
chmod +x /tmp/model_wrapper_{name}.sh
setsid /tmp/model_wrapper_{name}.sh </dev/null >/dev/null 2>&1 &
echo $!
exit 0
"""

    pid_result = await ssh_exec(pod_obj.ssh, start_cmd)
    pid_str = pid_result.stdout.strip()
    if not pid_str or not pid_str.isdigit():
        print("Failed to start model runner", file=sys.stderr)
        sys.exit(1)

    pid = int(pid_str)

    # Save to config
    from pi_pods.types import Model

    config = load_config()
    config.pods[pod_name].models[name] = Model(model=model_id, port=port, gpu=chosen_gpus, pid=pid)
    save_config(config)

    print(f"Model runner started with PID: {pid}")
    print("Streaming logs... (waiting for startup)\n")

    # Small delay to ensure log file is created
    await asyncio.sleep(0.5)

    # Stream logs watching for startup/failure
    ssh_parts = pod_obj.ssh.split()
    ssh_command = ssh_parts[0]
    ssh_args = ssh_parts[1:]
    tail_cmd = f"tail -f ~/.vllm_logs/{name}.log"

    log_proc = await asyncio.create_subprocess_exec(
        ssh_command,
        *ssh_args,
        tail_cmd,
        stdin=None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "FORCE_COLOR": "1"},
    )

    if log_proc.stdout is None or log_proc.stderr is None:
        raise RuntimeError("Log subprocess streams unavailable")

    interrupted = False
    startup_complete = False
    startup_failed = False
    failure_reason = ""

    def sigint_handler() -> None:
        nonlocal interrupted
        interrupted = True
        log_proc.kill()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, sigint_handler)

    async def process_stream(stream: asyncio.StreamReader) -> None:
        nonlocal startup_complete, startup_failed, failure_reason
        while True:
            line_bytes = await stream.readline()
            if not line_bytes:
                break
            line = line_bytes.decode(errors="replace").rstrip("\n")
            if line:
                print(line)
                if "Application startup complete" in line:
                    startup_complete = True
                    log_proc.kill()
                if "Model runner exiting with code" in line and "code 0" not in line:
                    startup_failed = True
                    failure_reason = "Model runner failed to start"
                    log_proc.kill()
                if "Script exited with code" in line and "code 0" not in line:
                    startup_failed = True
                    failure_reason = "Script failed to execute"
                    log_proc.kill()
                if "torch.OutOfMemoryError" in line or "CUDA out of memory" in line:
                    startup_failed = True
                    failure_reason = "Out of GPU memory (OOM)"
                if "RuntimeError: Engine core initialization failed" in line:
                    startup_failed = True
                    failure_reason = "vLLM engine initialization failed"
                    log_proc.kill()

    await asyncio.gather(
        process_stream(log_proc.stdout),
        process_stream(log_proc.stderr),
        log_proc.wait(),
    )

    with contextlib.suppress(RuntimeError):
        loop.remove_signal_handler(signal.SIGINT)

    # Extract host for display
    host = parse_ssh_host(pod_obj.ssh)

    if startup_failed:
        print(f"\nModel failed to start: {failure_reason}", file=sys.stderr)
        # Remove failed model from config
        config = load_config()
        if pod_name in config.pods and name in config.pods[pod_name].models:
            del config.pods[pod_name].models[name]
            save_config(config)
        print("\nModel has been removed from configuration.", file=sys.stderr)
        if "OOM" in failure_reason or "memory" in failure_reason:
            print("\nSuggestions:", file=sys.stderr)
            print("  - Try reducing GPU memory utilization: --memory 50%", file=sys.stderr)
            print("  - Use a smaller context window: --context 4k", file=sys.stderr)
            print("  - Use a quantized version of the model (e.g., FP8)", file=sys.stderr)
            print("  - Use more GPUs with tensor parallelism", file=sys.stderr)
            print("  - Try a smaller model variant", file=sys.stderr)
        print(f'\nCheck full logs: pi ssh "tail -100 ~/.vllm_logs/{name}.log"', file=sys.stderr)
        sys.exit(1)
    elif startup_complete:
        print("\nModel started successfully!")
        print("\nConnection Details:")
        print("-" * 50)
        print(f"Base URL:    http://{host}:{port}/v1")
        print(f"Model:       {model_id}")
        print(f"API Key:     {os.environ.get('PI_API_KEY', '(not set)')}")
        print("-" * 50)
        print("\nExport for shell:")
        print(f'export OPENAI_BASE_URL="http://{host}:{port}/v1"')
        print(f'export OPENAI_API_KEY="{os.environ.get("PI_API_KEY", "your-api-key")}"')
        print(f'export OPENAI_MODEL="{model_id}"')
        print(f'\nChat with model:  pi agent {name} "Your message"')
        print(f"Interactive mode: pi agent {name} -i")
        print(f"Monitor logs:     pi logs {name}")
        print(f"Stop model:       pi stop {name}")
    elif interrupted:
        print("\n\nStopped monitoring. Model deployment continues in background.")
        print(f'Chat with model: pi agent {name} "Your message"')
        print(f"Check status: pi logs {name}")
        print(f"Stop model: pi stop {name}")
    else:
        print("\n\nLog stream ended. Model may still be running.")
        print(f'Chat with model: pi agent {name} "Your message"')
        print(f"Check status: pi logs {name}")
        print(f"Stop model: pi stop {name}")


async def stop_model(name: str, pod: str | None = None) -> None:
    """Kill a model process and remove it from the config.

    Args:
        name: Local model name.
        pod: Pod name override.
    """
    pod_name, pod_obj = _get_pod(pod)

    model = pod_obj.models.get(name)
    if model is None:
        print(f"Model '{name}' not found on pod '{pod_name}'", file=sys.stderr)
        sys.exit(1)

    print(f"Stopping model '{name}' on pod '{pod_name}'...")

    kill_cmd = f"""
pkill -TERM -P {model.pid} 2>/dev/null || true
kill {model.pid} 2>/dev/null || true
"""
    await ssh_exec(pod_obj.ssh, kill_cmd)

    config = load_config()
    if pod_name in config.pods and name in config.pods[pod_name].models:
        del config.pods[pod_name].models[name]
        save_config(config)

    print(f"Model '{name}' stopped")


async def stop_all_models(pod: str | None = None) -> None:
    """Stop all models running on a pod.

    Args:
        pod: Pod name override.
    """
    pod_name, pod_obj = _get_pod(pod)

    model_names = list(pod_obj.models.keys())
    if not model_names:
        print(f"No models running on pod '{pod_name}'")
        return

    print(f"Stopping {len(model_names)} model(s) on pod '{pod_name}'...")

    pids = [str(m.pid) for m in pod_obj.models.values()]
    kill_cmd = f"""
for PID in {" ".join(pids)}; do
    pkill -TERM -P $PID 2>/dev/null || true
    kill $PID 2>/dev/null || true
done
"""
    await ssh_exec(pod_obj.ssh, kill_cmd)

    config = load_config()
    config.pods[pod_name].models = {}
    save_config(config)

    print(f"Stopped all models: {', '.join(model_names)}")


async def list_models(pod: str | None = None) -> None:
    """List all models on a pod and verify they are running.

    Args:
        pod: Pod name override.
    """
    pod_name, pod_obj = _get_pod(pod)

    model_names = list(pod_obj.models.keys())
    if not model_names:
        print(f"No models running on pod '{pod_name}'")
        return

    host = parse_ssh_host(pod_obj.ssh)

    print(f"Models on pod '{pod_name}':")
    for model_name in model_names:
        model = pod_obj.models[model_name]
        if len(model.gpu) > 1:
            gpu_str = f"GPUs {','.join(str(g) for g in model.gpu)}"
        elif len(model.gpu) == 1:
            gpu_str = f"GPU {model.gpu[0]}"
        else:
            gpu_str = "GPU unknown"
        print(f"  {model_name} - Port {model.port} - {gpu_str} - PID {model.pid}")
        print(f"    Model: {model.model}")
        print(f"    URL: http://{host}:{model.port}/v1")

    print("")
    print("Verifying processes...")
    any_dead = False
    for model_name in model_names:
        model = pod_obj.models[model_name]
        check_cmd = f"""
if ps -p {model.pid} > /dev/null 2>&1; then
    if curl -s -f http://localhost:{model.port}/health > /dev/null 2>&1; then
        echo "running"
    else
        if tail -n 20 ~/.vllm_logs/{model_name}.log 2>/dev/null | grep -q "ERROR\\|Failed\\|Cuda error\\|died"; then
            echo "crashed"
        else
            echo "starting"
        fi
    fi
else
    echo "dead"
fi
"""
        result = await ssh_exec(pod_obj.ssh, check_cmd)
        status = result.stdout.strip()
        if status == "dead":
            print(f"  {model_name}: Process {model.pid} is not running")
            any_dead = True
        elif status == "crashed":
            print(f"  {model_name}: vLLM crashed (check logs with 'pi logs {model_name}')")
            any_dead = True
        elif status == "starting":
            print(f"  {model_name}: Still starting up...")

    if any_dead:
        print("")
        print("Some models are not running. Clean up with:")
        print("  pi stop <name>")
    else:
        print("All processes verified")


async def view_logs(name: str, pod: str | None = None) -> None:
    """Stream logs for a model deployment.

    Args:
        name: Local model name.
        pod: Pod name override.
    """
    pod_name, pod_obj = _get_pod(pod)

    model = pod_obj.models.get(name)
    if model is None:
        print(f"Model '{name}' not found on pod '{pod_name}'", file=sys.stderr)
        sys.exit(1)

    print(f"Streaming logs for '{name}' on pod '{pod_name}'...")
    print("Press Ctrl+C to stop")
    print("")

    ssh_parts = pod_obj.ssh.split()
    ssh_command = ssh_parts[0]
    ssh_args = ssh_parts[1:]
    tail_cmd = f"tail -f ~/.vllm_logs/{name}.log"

    log_proc = await asyncio.create_subprocess_exec(
        ssh_command,
        *ssh_args,
        tail_cmd,
        stdin=None,
        stdout=None,
        stderr=None,
        env={**os.environ, "FORCE_COLOR": "1"},
    )
    await log_proc.wait()


async def show_known_models() -> None:
    """Display all known models with their hardware requirements."""
    models = get_all_models_data()

    # Get active pod info if available
    active = get_active_pod()
    pod_gpu_count = 0
    pod_gpu_type = ""

    if active:
        active_name, active_pod = active
        pod_gpu_count = len(active_pod.gpus)
        if active_pod.gpus:
            raw = active_pod.gpus[0].name.replace("NVIDIA", "").strip()
            pod_gpu_type = raw.split(" ")[0] if raw else ""
        print(f"Known Models for {active_name} ({pod_gpu_count}x {pod_gpu_type or 'GPU'}):\n")
    else:
        print("Known Models:\n")
        print("No active pod. Use 'pi pods active <name>' to filter compatible models.\n")

    print("Usage: pi start <model> --name <name> [options]\n")

    compatible: dict[str, list[dict[str, str | None]]] = {}
    incompatible: dict[str, list[dict[str, str | None]]] = {}

    for model_id, info_raw in models.items():
        if not isinstance(info_raw, dict):
            continue
        model_name_raw = info_raw.get("name", model_id)
        model_name = str(model_name_raw)
        family = model_name.split("-")[0] if "-" in model_name else "Other"

        configs_raw = info_raw.get("configs", [])
        if not isinstance(configs_raw, list) or not configs_raw:
            entry: dict[str, str | None] = {"id": model_id, "name": model_name, "notes": None, "min_gpu": "Unknown"}
            incompatible.setdefault(family, []).append(entry)
            continue

        sorted_configs = sorted(
            [c for c in configs_raw if isinstance(c, dict)],
            key=lambda c: int(c.get("gpuCount", 1)),
        )
        min_config = sorted_configs[0]
        min_gpu_count = int(min_config.get("gpuCount", 1))
        gpu_types_raw = min_config.get("gpuTypes", [])
        gpu_types_str = "/".join(str(t) for t in gpu_types_raw) if isinstance(gpu_types_raw, list) else "H100/H200"
        min_gpu = f"{min_gpu_count}x {gpu_types_str}" if min_gpu_count > 1 else f"1x {gpu_types_str}"
        min_notes_raw = min_config.get("notes") or info_raw.get("notes")
        min_notes: str | None = str(min_notes_raw) if min_notes_raw is not None else None

        is_compatible = False
        compatible_config_str = ""

        if active and pod_gpu_count > 0:
            for cfg in sorted_configs:
                cfg_gpu_count = int(cfg.get("gpuCount", 1))
                cfg_gpu_types = cfg.get("gpuTypes", [])
                if cfg_gpu_count <= pod_gpu_count:
                    type_ok = (
                        not isinstance(cfg_gpu_types, list)
                        or not cfg_gpu_types
                        or any(pod_gpu_type in str(t) or str(t) in pod_gpu_type for t in cfg_gpu_types)
                    )
                    if type_ok:
                        is_compatible = True
                        compatible_config_str = (
                            f"{cfg_gpu_count}x {pod_gpu_type}" if cfg_gpu_count > 1 else f"1x {pod_gpu_type}"
                        )
                        cfg_notes_raw = cfg.get("notes") or info_raw.get("notes")
                        min_notes = str(cfg_notes_raw) if cfg_notes_raw is not None else None
                        break

        if active and is_compatible:
            compat_entry: dict[str, str | None] = {
                "id": model_id,
                "name": model_name,
                "notes": min_notes,
                "config": compatible_config_str,
            }
            compatible.setdefault(family, []).append(compat_entry)
        else:
            incompat_entry: dict[str, str | None] = {
                "id": model_id,
                "name": model_name,
                "notes": min_notes,
                "min_gpu": min_gpu,
            }
            incompatible.setdefault(family, []).append(incompat_entry)

    if active and compatible:
        print("Compatible Models:\n")
        for family_name in sorted(compatible.keys()):
            print(f"{family_name} Models:")
            for m in sorted(compatible[family_name], key=lambda x: str(x.get("name", ""))):
                print(f"  {m['id']}")
                print(f"    Name: {m['name']}")
                print(f"    Config: {m.get('config', '')}")
                if m.get("notes"):
                    print(f"    Note: {m['notes']}")
                print("")

    if incompatible:
        if active and compatible:
            print("Incompatible Models (need more/different GPUs):\n")
        for family_name in sorted(incompatible.keys()):
            print(f"{family_name} Models:")
            for m in sorted(incompatible[family_name], key=lambda x: str(x.get("name", ""))):
                print(f"  {m['id']}")
                print(f"    Name: {m['name']}")
                print(f"    Min Hardware: {m.get('min_gpu', 'Unknown')}")
                if m.get("notes") and not active:
                    print(f"    Note: {m['notes']}")
                print("")

    print("\nFor unknown models, defaults to single GPU deployment.")
    print("Use --vllm to pass custom arguments to vLLM.")


# Re-export get_known_models for CLI convenience
from pi_pods.model_configs import get_known_models  # noqa: E402

__all__ = [
    "get_known_models",
    "list_models",
    "show_known_models",
    "start_model",
    "stop_all_models",
    "stop_model",
    "view_logs",
]
