"""CLI for vLLM deployments on GPU pods — Python port of @mariozechner/pi-pods."""

from pi_pods.config import (
    add_pod,
    get_active_pod,
    load_config,
    remove_pod,
    save_config,
    set_active_pod,
)
from pi_pods.model_configs import (
    get_all_models_data,
    get_known_models,
    get_model_config,
    get_model_name,
    is_known_model,
)
from pi_pods.ssh import SSHResult, parse_ssh_host, scp_file, ssh_exec, ssh_exec_stream
from pi_pods.types import (
    GPU,
    Config,
    Model,
    Pod,
    config_from_dict,
    config_to_dict,
    gpu_from_dict,
    gpu_to_dict,
    model_from_dict,
    model_to_dict,
    pod_from_dict,
    pod_to_dict,
)

__all__ = [
    "GPU",
    "Config",
    "Model",
    "Pod",
    "SSHResult",
    "add_pod",
    "config_from_dict",
    "config_to_dict",
    "get_active_pod",
    "get_all_models_data",
    "get_known_models",
    "get_model_config",
    "get_model_name",
    "gpu_from_dict",
    "gpu_to_dict",
    "is_known_model",
    "load_config",
    "model_from_dict",
    "model_to_dict",
    "parse_ssh_host",
    "pod_from_dict",
    "pod_to_dict",
    "remove_pod",
    "save_config",
    "scp_file",
    "set_active_pod",
    "ssh_exec",
    "ssh_exec_stream",
]
