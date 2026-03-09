"""Unit tests for pi_pods.commands.pods."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_pods.commands.pods import (
    list_pods,
    remove_pod_command,
    setup_pod,
    switch_active_pod,
)
from pi_pods.config import add_pod, load_config, save_config
from pi_pods.types import GPU, Config, Pod


def _make_pod(ssh: str = "ssh root@1.2.3.4") -> Pod:
    return Pod(
        ssh=ssh,
        gpus=[GPU(id=0, name="NVIDIA H100", memory="80 GiB")],
        models={},
        models_path="/mnt/models",
    )


@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PI_CONFIG_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def pod_config(config_dir: Path) -> None:
    cfg = Config(pods={"alpha": _make_pod()}, active="alpha")
    save_config(cfg)


# ---------------------------------------------------------------------------
# list_pods
# ---------------------------------------------------------------------------


class TestListPods:
    def test_no_pods_message(self, config_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        list_pods()
        captured = capsys.readouterr()
        assert "No pods configured" in captured.out

    def test_lists_pods(self, pod_config: None, capsys: pytest.CaptureFixture[str]) -> None:
        list_pods()
        captured = capsys.readouterr()
        assert "alpha" in captured.out

    def test_marks_active_pod(self, pod_config: None, capsys: pytest.CaptureFixture[str]) -> None:
        list_pods()
        captured = capsys.readouterr()
        assert "* " in captured.out


# ---------------------------------------------------------------------------
# switch_active_pod
# ---------------------------------------------------------------------------


class TestSwitchActivePod:
    def test_switches_pod(self, config_dir: Path) -> None:
        add_pod("a", _make_pod())
        add_pod("b", _make_pod("ssh root@2.2.2.2"))
        switch_active_pod("b")
        cfg = load_config()
        assert cfg.active == "b"

    def test_exits_for_unknown_pod(self, config_dir: Path) -> None:
        with pytest.raises(SystemExit):
            switch_active_pod("ghost")


# ---------------------------------------------------------------------------
# remove_pod_command
# ---------------------------------------------------------------------------


class TestRemovePodCommand:
    def test_removes_pod(self, pod_config: None) -> None:
        remove_pod_command("alpha")
        cfg = load_config()
        assert "alpha" not in cfg.pods

    def test_exits_for_unknown_pod(self, config_dir: Path) -> None:
        with pytest.raises(SystemExit):
            remove_pod_command("ghost")


# ---------------------------------------------------------------------------
# setup_pod
# ---------------------------------------------------------------------------


class TestSetupPod:
    async def test_exits_when_hf_token_missing(self, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("PI_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            await setup_pod("mypod", "ssh root@1.2.3.4", models_path="/mnt/models")

    async def test_exits_when_pi_api_key_missing(self, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HF_TOKEN", "tok")
        monkeypatch.delenv("PI_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            await setup_pod("mypod", "ssh root@1.2.3.4", models_path="/mnt/models")

    async def test_exits_when_no_models_path(self, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HF_TOKEN", "tok")
        monkeypatch.setenv("PI_API_KEY", "key")
        with pytest.raises(SystemExit):
            await setup_pod("mypod", "ssh root@1.2.3.4")

    async def test_exits_when_ssh_fails(self, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HF_TOKEN", "tok")
        monkeypatch.setenv("PI_API_KEY", "key")
        with patch("pi_pods.commands.pods.ssh_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MagicMock(stdout="", stderr="connection refused", exit_code=1)
            with pytest.raises(SystemExit):
                await setup_pod("mypod", "ssh root@1.2.3.4", models_path="/mnt/models")

    async def test_full_setup_success(self, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HF_TOKEN", "tok")
        monkeypatch.setenv("PI_API_KEY", "key")

        with (
            patch("pi_pods.commands.pods.ssh_exec", new_callable=AsyncMock) as mock_exec,
            patch("pi_pods.commands.pods.scp_file", new_callable=AsyncMock) as mock_scp,
            patch("pi_pods.commands.pods.ssh_exec_stream", new_callable=AsyncMock) as mock_stream,
            # Stub out importlib.resources so no real file I/O is needed
            patch("importlib.resources.files") as mock_files,
        ):
            mock_files.return_value.__truediv__.return_value.__truediv__.return_value.read_text.return_value = (
                "#!/bin/bash\necho done\n"
            )
            # SSH test passes, GPU detection returns one GPU
            mock_exec.side_effect = [
                MagicMock(stdout="SSH OK\n", stderr="", exit_code=0),
                MagicMock(
                    stdout="0, NVIDIA H100, 81559 MiB\n",
                    stderr="",
                    exit_code=0,
                ),
            ]
            mock_scp.return_value = True
            mock_stream.return_value = 0

            await setup_pod("mypod", "ssh root@1.2.3.4", models_path="/mnt/models")

        cfg = load_config()
        assert "mypod" in cfg.pods
        assert len(cfg.pods["mypod"].gpus) == 1
        assert cfg.pods["mypod"].gpus[0].name == "NVIDIA H100"
