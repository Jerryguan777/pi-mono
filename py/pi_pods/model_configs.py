"""Model configuration lookup from models.json."""

import json
from pathlib import Path

from pi_pods.types import GPU

# Load models.json bundled alongside this module.
_MODELS_JSON_PATH = Path(__file__).parent / "models.json"

# Raw parsed data from models.json — loaded once at import time.
_models_data: dict[str, object] = {}

if _MODELS_JSON_PATH.exists():
    _models_data = json.loads(_MODELS_JSON_PATH.read_text(encoding="utf-8"))


def _get_models() -> dict[str, object]:
    """Return the models dict from the parsed JSON data."""
    raw = _models_data.get("models", {})
    if not isinstance(raw, dict):
        return {}
    return raw


def get_model_config(
    model_id: str,
    gpus: list[GPU],
    requested_gpu_count: int,
) -> dict[str, object] | None:
    """Find the best vLLM configuration for a model given the available GPUs.

    Matches on gpuCount == requested_gpu_count, then checks gpuTypes (any match).
    Falls back to the first config with the right GPU count if no type match.

    Args:
        model_id: The HuggingFace model identifier.
        gpus: List of GPU devices available on the pod.
        requested_gpu_count: Number of GPUs to use.

    Returns:
        A dict with keys "args", "env" (optional), "notes" (optional), or None.
    """
    models = _get_models()
    model_info = models.get(model_id)
    if not isinstance(model_info, dict):
        return None

    configs_raw = model_info.get("configs", [])
    if not isinstance(configs_raw, list):
        return None

    # Extract GPU type from the first GPU name (e.g. "NVIDIA H200" -> "H200")
    gpu_type = ""
    if gpus:
        raw_name = gpus[0].name.replace("NVIDIA", "").strip()
        gpu_type = raw_name.split(" ")[0] if raw_name else ""

    best_config: dict[str, object] | None = None

    # First pass: match both GPU count and GPU type
    for cfg in configs_raw:
        if not isinstance(cfg, dict):
            continue
        if cfg.get("gpuCount") != requested_gpu_count:
            continue
        gpu_types = cfg.get("gpuTypes", [])
        if isinstance(gpu_types, list) and gpu_types:
            type_matches = any(gpu_type in t or t in gpu_type for t in gpu_types if isinstance(t, str))
            if not type_matches:
                continue
        best_config = cfg
        break

    # Second pass: match GPU count only (fallback)
    if best_config is None:
        for cfg in configs_raw:
            if not isinstance(cfg, dict):
                continue
            if cfg.get("gpuCount") != requested_gpu_count:
                continue
            best_config = cfg
            break

    if best_config is None:
        return None

    args = best_config.get("args", [])
    if not isinstance(args, list):
        args = []

    env_raw = best_config.get("env")
    env: dict[str, str] | None = None
    if isinstance(env_raw, dict):
        env = {str(k): str(v) for k, v in env_raw.items()}

    notes_raw = best_config.get("notes") or model_info.get("notes")
    notes: str | None = str(notes_raw) if notes_raw is not None else None

    result: dict[str, object] = {"args": [str(a) for a in args]}
    if env is not None:
        result["env"] = env
    if notes is not None:
        result["notes"] = notes

    return result


def is_known_model(model_id: str) -> bool:
    """Return True if model_id is present in models.json."""
    return model_id in _get_models()


def get_known_models() -> list[str]:
    """Return a list of all known model IDs."""
    return list(_get_models().keys())


def get_model_name(model_id: str) -> str:
    """Return the display name for a model, or the model_id if not found."""
    models = _get_models()
    info = models.get(model_id)
    if isinstance(info, dict):
        name_raw = info.get("name")
        if name_raw is not None:
            return str(name_raw)
    return model_id


def get_all_models_data() -> dict[str, object]:
    """Return the full models dict from models.json (public API)."""
    return _get_models()
