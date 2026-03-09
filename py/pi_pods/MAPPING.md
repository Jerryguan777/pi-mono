# pi_pods TypeScript → Python Mapping

| TS Function/Class/File | Python Equivalent | Status | Notes |
|------------------------|-------------------|--------|-------|
| `types.ts` → `interface GPU` | `types.py` → `GPU` dataclass | Done | |
| `types.ts` → `interface Model` | `types.py` → `Model` dataclass | Done | |
| `types.ts` → `interface Pod` | `types.py` → `Pod` dataclass | Done | `modelsPath` → `models_path`, `vllmVersion` → `vllm_version` |
| `types.ts` → `interface Config` | `types.py` → `Config` dataclass | Done | |
| _(new)_ | `types.py` → `gpu_to_dict()` / `gpu_from_dict()` | Done | Serialization helpers |
| _(new)_ | `types.py` → `model_to_dict()` / `model_from_dict()` | Done | Serialization helpers |
| _(new)_ | `types.py` → `pod_to_dict()` / `pod_from_dict()` | Done | Serialization helpers |
| _(new)_ | `types.py` → `config_to_dict()` / `config_from_dict()` | Done | Serialization helpers |
| `config.ts` → `loadConfig()` | `config.py` → `load_config()` | Done | |
| `config.ts` → `saveConfig()` | `config.py` → `save_config()` | Done | |
| `config.ts` → `getActivePod()` | `config.py` → `get_active_pod()` | Done | Returns `tuple[str, Pod] \| None` instead of `{name, pod} \| null` |
| `config.ts` → `addPod()` | `config.py` → `add_pod()` | Done | |
| `config.ts` → `removePod()` | `config.py` → `remove_pod()` | Done | |
| `config.ts` → `setActivePod()` | `config.py` → `set_active_pod()` | Done | Raises `ValueError` instead of calling `process.exit(1)` |
| `ssh.ts` → `interface SSHResult` | `ssh.py` → `SSHResult` dataclass | Done | |
| `ssh.ts` → `sshExec()` | `ssh.py` → `ssh_exec()` | Done | async |
| `ssh.ts` → `sshExecStream()` | `ssh.py` → `ssh_exec_stream()` | Done | async |
| `ssh.ts` → `scpFile()` | `ssh.py` → `scp_file()` | Done | async |
| `model-configs.ts` → `getModelConfig()` | `model_configs.py` → `get_model_config()` | Done | |
| `model-configs.ts` → `isKnownModel()` | `model_configs.py` → `is_known_model()` | Done | |
| `model-configs.ts` → `getKnownModels()` | `model_configs.py` → `get_known_models()` | Done | |
| `model-configs.ts` → `getModelName()` | `model_configs.py` → `get_model_name()` | Done | |
| `commands/models.ts` → `startModel()` | `commands/models.py` → `start_model()` | Done | async |
| `commands/models.ts` → `stopModel()` | `commands/models.py` → `stop_model()` | Done | async |
| `commands/models.ts` → `stopAllModels()` | `commands/models.py` → `stop_all_models()` | Done | async |
| `commands/models.ts` → `listModels()` | `commands/models.py` → `list_models()` | Done | async |
| `commands/models.ts` → `viewLogs()` | `commands/models.py` → `view_logs()` | Done | async |
| `commands/models.ts` → `showKnownModels()` | `commands/models.py` → `show_known_models()` | Done | async |
| `commands/pods.ts` → `listPods()` | `commands/pods.py` → `list_pods()` | Done | |
| `commands/pods.ts` → `setupPod()` | `commands/pods.py` → `setup_pod()` | Done | async |
| `commands/pods.ts` → `switchActivePod()` | `commands/pods.py` → `switch_active_pod()` | Done | |
| `commands/pods.ts` → `removePodCommand()` | `commands/pods.py` → `remove_pod_command()` | Done | |
| `commands/prompt.ts` → `promptModel()` | `commands/prompt.py` → `prompt_model()` | Done | async; raises `RuntimeError("Not implemented")` like TS source |
| `cli.ts` | `cli.py` | Done | Uses `typer` instead of hand-parsed `process.argv` |
