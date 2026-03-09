"""Unit tests for pi_pods.commands.models — helper functions and async commands."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_pods.commands.models import (
    list_models,
    show_known_models,
    stop_all_models,
    stop_model,
    view_logs,
)
from pi_pods.config import save_config
from pi_pods.types import GPU, Config, Model, Pod


def _make_gpu(idx: int = 0, name: str = "NVIDIA H100") -> GPU:
    return GPU(id=idx, name=name, memory="80 GiB")


def _make_model(port: int = 8001, pid: int = 1234, gpu: list[int] | None = None) -> Model:
    return Model(model="org/TestModel", port=port, gpu=gpu or [0], pid=pid)


def _make_pod(models: dict[str, Model] | None = None) -> Pod:
    return Pod(
        ssh="ssh root@1.2.3.4",
        gpus=[_make_gpu(0), _make_gpu(1)],
        models=models or {},
        models_path="/mnt/models",
        vllm_version="release",
    )


@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PI_CONFIG_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def pod_config(config_dir: Path) -> None:
    """Write a config with one pod and one model."""
    pod = _make_pod(models={"mymodel": _make_model()})
    cfg = Config(pods={"testpod": pod}, active="testpod")
    save_config(cfg)


# ---------------------------------------------------------------------------
# stop_model
# ---------------------------------------------------------------------------


class TestStopModel:
    async def test_stops_model_and_removes_from_config(self, pod_config: None) -> None:
        with patch("pi_pods.commands.models.ssh_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MagicMock(stdout="", stderr="", exit_code=0)
            await stop_model("mymodel", pod="testpod")

        from pi_pods.config import load_config

        cfg = load_config()
        assert "mymodel" not in cfg.pods["testpod"].models

    async def test_exits_when_model_not_found(self, pod_config: None) -> None:
        with pytest.raises(SystemExit):
            await stop_model("nonexistent", pod="testpod")

    async def test_exits_when_pod_not_found(self, config_dir: Path) -> None:
        with pytest.raises(SystemExit):
            await stop_model("x", pod="ghost")


# ---------------------------------------------------------------------------
# stop_all_models
# ---------------------------------------------------------------------------


class TestStopAllModels:
    async def test_stops_all_models(self, pod_config: None) -> None:
        with patch("pi_pods.commands.models.ssh_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MagicMock(stdout="", stderr="", exit_code=0)
            await stop_all_models(pod="testpod")

        from pi_pods.config import load_config

        cfg = load_config()
        assert cfg.pods["testpod"].models == {}

    async def test_noop_when_no_models(self, config_dir: Path) -> None:
        pod = _make_pod()
        cfg = Config(pods={"empty": pod}, active="empty")
        save_config(cfg)
        # Should not call ssh at all
        with patch("pi_pods.commands.models.ssh_exec", new_callable=AsyncMock) as mock_exec:
            await stop_all_models(pod="empty")
        mock_exec.assert_not_called()


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestListModels:
    async def test_prints_no_models_message(self, config_dir: Path) -> None:
        pod = _make_pod()
        cfg = Config(pods={"mypod": pod}, active="mypod")
        save_config(cfg)
        # Should not raise
        await list_models(pod="mypod")

    async def test_verifies_process_status(self, pod_config: None) -> None:
        with patch("pi_pods.commands.models.ssh_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MagicMock(stdout="running\n", stderr="", exit_code=0)
            await list_models(pod="testpod")

        mock_exec.assert_called()

    async def test_shows_dead_process(self, pod_config: None, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("pi_pods.commands.models.ssh_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MagicMock(stdout="dead\n", stderr="", exit_code=0)
            await list_models(pod="testpod")

        captured = capsys.readouterr()
        assert "not running" in captured.out


# ---------------------------------------------------------------------------
# view_logs
# ---------------------------------------------------------------------------


class TestViewLogs:
    async def test_exits_when_model_not_found(self, pod_config: None) -> None:
        with pytest.raises(SystemExit):
            await view_logs("ghost", pod="testpod")

    async def test_launches_ssh_tail(self, pod_config: None) -> None:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=None)
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await view_logs("mymodel", pod="testpod")

        mock_create.assert_called_once()
        args = mock_create.call_args[0]
        # The command should contain 'tail -f'
        assert any("tail" in str(a) for a in args)


# ---------------------------------------------------------------------------
# show_known_models
# ---------------------------------------------------------------------------


class TestShowKnownModels:
    async def test_runs_without_error(self, config_dir: Path) -> None:
        # No active pod — should just list all models
        await show_known_models()

    async def test_runs_with_active_pod(self, pod_config: None) -> None:
        await show_known_models()
