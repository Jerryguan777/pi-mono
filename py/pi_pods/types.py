"""Core type definitions for pi_pods."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class GPU:
    """Represents a GPU device on a pod."""

    id: int
    name: str
    memory: str


@dataclass
class Model:
    """Represents a running model deployment."""

    model: str
    port: int
    gpu: list[int]  # Array of GPU IDs for multi-GPU deployment
    pid: int


@dataclass
class Pod:
    """Represents a remote GPU pod."""

    ssh: str
    gpus: list[GPU]
    models: dict[str, Model]
    models_path: str | None = None
    vllm_version: Literal["release", "nightly", "gpt-oss"] | None = None


@dataclass
class Config:
    """Top-level configuration."""

    pods: dict[str, Pod] = field(default_factory=dict)
    active: str | None = None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def gpu_to_dict(gpu: GPU) -> dict[str, object]:
    """Serialize GPU to a JSON-compatible dict."""
    return {"id": gpu.id, "name": gpu.name, "memory": gpu.memory}


def gpu_from_dict(data: dict[str, object]) -> GPU:
    """Deserialize GPU from a dict."""
    return GPU(
        id=int(str(data["id"])),
        name=str(data["name"]),
        memory=str(data["memory"]),
    )


def model_to_dict(model: Model) -> dict[str, object]:
    """Serialize Model to a JSON-compatible dict."""
    return {"model": model.model, "port": model.port, "gpu": model.gpu, "pid": model.pid}


def model_from_dict(data: dict[str, object]) -> Model:
    """Deserialize Model from a dict."""
    gpu_list = data.get("gpu", [])
    if not isinstance(gpu_list, list):
        raise ValueError("Model.gpu must be a list")
    return Model(
        model=str(data["model"]),
        port=int(str(data["port"])),
        gpu=[int(str(g)) for g in gpu_list],
        pid=int(str(data["pid"])),
    )


def pod_to_dict(pod: Pod) -> dict[str, object]:
    """Serialize Pod to a JSON-compatible dict."""
    result: dict[str, object] = {
        "ssh": pod.ssh,
        "gpus": [gpu_to_dict(g) for g in pod.gpus],
        "models": {name: model_to_dict(m) for name, m in pod.models.items()},
    }
    if pod.models_path is not None:
        result["modelsPath"] = pod.models_path
    if pod.vllm_version is not None:
        result["vllmVersion"] = pod.vllm_version
    return result


def pod_from_dict(data: dict[str, object]) -> Pod:
    """Deserialize Pod from a dict."""
    gpus_raw = data.get("gpus", [])
    if not isinstance(gpus_raw, list):
        raise ValueError("Pod.gpus must be a list")
    gpus = [gpu_from_dict(g) for g in gpus_raw if isinstance(g, dict)]

    models_raw = data.get("models", {})
    if not isinstance(models_raw, dict):
        raise ValueError("Pod.models must be a dict")
    models = {k: model_from_dict(v) for k, v in models_raw.items() if isinstance(v, dict)}

    models_path_raw = data.get("modelsPath")
    models_path = str(models_path_raw) if models_path_raw is not None else None

    vllm_version_raw = data.get("vllmVersion")
    vllm_version: Literal["release", "nightly", "gpt-oss"] | None = None
    if vllm_version_raw == "release":
        vllm_version = "release"
    elif vllm_version_raw == "nightly":
        vllm_version = "nightly"
    elif vllm_version_raw == "gpt-oss":
        vllm_version = "gpt-oss"

    return Pod(
        ssh=str(data["ssh"]),
        gpus=gpus,
        models=models,
        models_path=models_path,
        vllm_version=vllm_version,
    )


def config_to_dict(config: Config) -> dict[str, object]:
    """Serialize Config to a JSON-compatible dict."""
    result: dict[str, object] = {"pods": {name: pod_to_dict(p) for name, p in config.pods.items()}}
    if config.active is not None:
        result["active"] = config.active
    return result


def config_from_dict(data: dict[str, object]) -> Config:
    """Deserialize Config from a dict."""
    pods_raw = data.get("pods", {})
    if not isinstance(pods_raw, dict):
        raise ValueError("Config.pods must be a dict")
    pods = {k: pod_from_dict(v) for k, v in pods_raw.items() if isinstance(v, dict)}

    active_raw = data.get("active")
    active = str(active_raw) if active_raw is not None else None

    return Config(pods=pods, active=active)
