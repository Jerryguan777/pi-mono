"""Config management for pi_pods — load/save/get/add/remove/set."""

import json
import os
import sys
from pathlib import Path

from pi_pods.types import Config, Pod, config_from_dict, config_to_dict


def _get_config_dir() -> Path:
    """Return the config directory, creating it if necessary."""
    config_dir_env = os.environ.get("PI_CONFIG_DIR")
    config_dir = Path(config_dir_env) if config_dir_env else Path.home() / ".pi"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_config_path() -> Path:
    """Return the path to the pods config file."""
    return _get_config_dir() / "pods.json"


def load_config() -> Config:
    """Load config from $PI_CONFIG_DIR/pods.json or ~/.pi/pods.json.

    Returns an empty Config if the file does not exist.
    """
    config_path = _get_config_path()
    if not config_path.exists():
        return Config(pods={})
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return config_from_dict(data)
    except Exception as exc:
        print(f"Error reading config: {exc}", file=sys.stderr)
        return Config(pods={})


def save_config(config: Config) -> None:
    """Save config to $PI_CONFIG_DIR/pods.json or ~/.pi/pods.json."""
    config_path = _get_config_path()
    try:
        config_path.write_text(json.dumps(config_to_dict(config), indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"Error saving config: {exc}", file=sys.stderr)
        sys.exit(1)


def get_active_pod() -> tuple[str, Pod] | None:
    """Return (name, pod) for the active pod, or None if not set."""
    config = load_config()
    if not config.active or config.active not in config.pods:
        return None
    return config.active, config.pods[config.active]


def add_pod(name: str, pod: Pod) -> None:
    """Add a pod to the config. Sets it as active if no active pod is set."""
    config = load_config()
    config.pods[name] = pod
    if not config.active:
        config.active = name
    save_config(config)


def remove_pod(name: str) -> None:
    """Remove a pod from the config. Clears active if the removed pod was active."""
    config = load_config()
    if name in config.pods:
        del config.pods[name]
    if config.active == name:
        config.active = None
    save_config(config)


def set_active_pod(name: str) -> None:
    """Set the active pod by name.

    Raises:
        ValueError: If the pod does not exist in the config.
    """
    config = load_config()
    if name not in config.pods:
        raise ValueError(f"Pod '{name}' not found")
    config.active = name
    save_config(config)
