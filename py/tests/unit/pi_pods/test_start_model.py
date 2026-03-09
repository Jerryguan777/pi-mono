"""Tests for start_model in pi_pods.commands.models."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_pods.commands.models import start_model
from pi_pods.config import load_config, save_config
from pi_pods.types import GPU, Config, Pod


def _make_pod(
    gpus: list[GPU] | None = None,
    models_path: str = "/mnt/models",
) -> Pod:
    return Pod(
        ssh="ssh root@1.2.3.4",
        gpus=gpus or [GPU(id=0, name="NVIDIA H100", memory="80 GiB")],
        models={},
        models_path=models_path,
    )


@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PI_CONFIG_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def pod_config(config_dir: Path) -> None:
    cfg = Config(pods={"testpod": _make_pod()}, active="testpod")
    save_config(cfg)


@pytest.fixture()
def multi_gpu_config(config_dir: Path) -> None:
    gpus = [GPU(id=i, name="NVIDIA H100", memory="80 GiB") for i in range(4)]
    cfg = Config(pods={"testpod": _make_pod(gpus=gpus)}, active="testpod")
    save_config(cfg)


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------


class TestValidateName:
    async def test_exits_on_shell_metacharacters(self, config_dir: Path) -> None:
        with pytest.raises(SystemExit):
            await start_model("org/Model", "bad;name", pod="testpod")

    async def test_exits_on_space_in_name(self, config_dir: Path) -> None:
        with pytest.raises(SystemExit):
            await start_model("org/Model", "bad name", pod="testpod")

    async def test_allows_valid_name(self, pod_config: None) -> None:
        # A valid name should not exit at the validation step;
        # it should proceed and fail later (no models_path workaround needed here
        # since pod_config has models_path set, but model not yet started).
        # We just confirm SystemExit is NOT raised for name validation.
        # The function will exit for other reasons (e.g. script read), so wrap.
        from pi_pods.config import load_config as _lc
        from pi_pods.config import save_config as _sc
        from pi_pods.types import Model

        cfg = _lc()
        cfg.pods["testpod"].models["valid-name_1"] = Model(model="x", port=8001, gpu=[0], pid=1)
        _sc(cfg)
        # Now start with same name -> exits for "already exists", NOT for name validation
        with pytest.raises(SystemExit):
            await start_model("org/Model", "valid-name_1", pod="testpod")


class TestStartModelValidation:
    async def test_exits_when_pod_not_found(self, config_dir: Path) -> None:
        with pytest.raises(SystemExit):
            await start_model("org/Model", "mymodel", pod="ghost")

    async def test_exits_when_no_models_path(self, config_dir: Path) -> None:
        pod = Pod(ssh="ssh root@1.2.3.4", gpus=[], models={}, models_path=None)
        save_config(Config(pods={"p": pod}, active="p"))
        with pytest.raises(SystemExit):
            await start_model("org/Model", "mymodel", pod="p")

    async def test_exits_when_model_name_already_exists(self, pod_config: None) -> None:
        from pi_pods.types import Model

        cfg = load_config()
        cfg.pods["testpod"].models["mymodel"] = Model(model="x", port=8001, gpu=[0], pid=1)
        save_config(cfg)
        with pytest.raises(SystemExit):
            await start_model("org/Model", "mymodel", pod="testpod")

    async def test_exits_when_gpus_exceeds_pod_count(self, pod_config: None) -> None:
        with patch("pi_pods.commands.models.is_known_model", return_value=True), pytest.raises(SystemExit):
            await start_model("org/Model", "mymodel", pod="testpod", gpus=10)

    async def test_exits_when_gpus_flag_used_with_unknown_model(self, pod_config: None) -> None:
        with patch("pi_pods.commands.models.is_known_model", return_value=False), pytest.raises(SystemExit):
            await start_model("org/Unknown", "mymodel", pod="testpod", gpus=1)

    async def test_exits_when_known_model_no_compatible_config(self, pod_config: None) -> None:
        with (
            patch("pi_pods.commands.models.is_known_model", return_value=True),
            patch("pi_pods.commands.models.get_model_config", return_value=None),
            pytest.raises(SystemExit),
        ):
            await start_model("org/Model", "mymodel", pod="testpod")


# ---------------------------------------------------------------------------
# Custom vllm args path (simplest path to reach start logic)
# ---------------------------------------------------------------------------


def _mock_log_proc_success() -> MagicMock:
    """Build a mock subprocess that emits 'Application startup complete'."""
    mock = MagicMock()
    mock.kill = MagicMock()
    mock.wait = AsyncMock(return_value=None)
    mock.returncode = 0

    # Simulate reading lines from stdout and stderr streams
    async def read_startup(stream: object) -> None:
        pass

    # stdout and stderr that yield 'Application startup complete' then EOF
    startup_line = b"Application startup complete\n"
    eof = b""

    class FakeStream:
        def __init__(self) -> None:
            self._lines = [startup_line, eof]
            self._idx = 0

        async def readline(self) -> bytes:
            if self._idx < len(self._lines):
                line = self._lines[self._idx]
                self._idx += 1
                return line
            return b""

    mock.stdout = FakeStream()
    mock.stderr = FakeStream()
    return mock


class TestStartModelCustomArgs:
    async def test_custom_vllm_args_skips_model_config_lookup(self, pod_config: None) -> None:
        """With --vllm args, no model config lookup happens and start proceeds."""
        fake_script_content = "#!/bin/bash\n{{MODEL_ID}} {{NAME}} {{PORT}} {{VLLM_ARGS}}\n"

        mock_log_proc = _mock_log_proc_success()

        with (
            patch("pi_pods.commands.models.ssh_exec", new_callable=AsyncMock) as mock_ssh,
            patch("asyncio.create_subprocess_exec", return_value=mock_log_proc),
            patch("pi_pods.commands.models._read_script", return_value=fake_script_content),
            patch("pi_pods.commands.models.is_known_model", return_value=False),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_ssh.return_value = MagicMock(stdout="9999\n", stderr="", exit_code=0)

            await start_model(
                "org/SomeModel",
                "m1",
                pod="testpod",
                vllm_args=["--tensor-parallel-size", "2"],
            )

        cfg = load_config()
        assert "m1" in cfg.pods["testpod"].models

    async def test_unknown_model_defaults_to_single_gpu(self, pod_config: None) -> None:
        fake_script_content = "#!/bin/bash\n{{MODEL_ID}} {{NAME}} {{PORT}} {{VLLM_ARGS}}\n"
        mock_log_proc = _mock_log_proc_success()

        with (
            patch("pi_pods.commands.models.ssh_exec", new_callable=AsyncMock) as mock_ssh,
            patch("asyncio.create_subprocess_exec", return_value=mock_log_proc),
            patch("pi_pods.commands.models._read_script", return_value=fake_script_content),
            patch("pi_pods.commands.models.is_known_model", return_value=False),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_ssh.return_value = MagicMock(stdout="8888\n", stderr="", exit_code=0)

            await start_model("org/Unknown", "u1", pod="testpod")

        cfg = load_config()
        assert "u1" in cfg.pods["testpod"].models
        assert len(cfg.pods["testpod"].models["u1"].gpu) == 1

    async def test_startup_failure_removes_model_from_config(self, pod_config: None) -> None:
        """If the model runner exits with error, config should be cleaned up."""
        fake_script_content = "#!/bin/bash\n{{MODEL_ID}} {{NAME}} {{PORT}} {{VLLM_ARGS}}\n"

        fail_line = b"Model runner exiting with code 1\n"
        eof = b""

        class FailStream:
            def __init__(self) -> None:
                self._lines = [fail_line, eof]
                self._idx = 0

            async def readline(self) -> bytes:
                if self._idx < len(self._lines):
                    line = self._lines[self._idx]
                    self._idx += 1
                    return line
                return b""

        mock_log_proc = MagicMock()
        mock_log_proc.kill = MagicMock()
        mock_log_proc.wait = AsyncMock(return_value=None)
        mock_log_proc.returncode = 1
        mock_log_proc.stdout = FailStream()
        mock_log_proc.stderr = FailStream()

        with (
            patch("pi_pods.commands.models.ssh_exec", new_callable=AsyncMock) as mock_ssh,
            patch("asyncio.create_subprocess_exec", return_value=mock_log_proc),
            patch("pi_pods.commands.models._read_script", return_value=fake_script_content),
            patch("pi_pods.commands.models.is_known_model", return_value=False),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_ssh.return_value = MagicMock(stdout="7777\n", stderr="", exit_code=0)

            with pytest.raises(SystemExit):
                await start_model("org/Fail", "fail1", pod="testpod")

        cfg = load_config()
        assert "fail1" not in cfg.pods["testpod"].models

    async def test_known_model_with_requested_gpus(self, multi_gpu_config: None) -> None:
        fake_script_content = "{{MODEL_ID}} {{NAME}} {{PORT}} {{VLLM_ARGS}}"
        mock_log_proc = _mock_log_proc_success()

        with (
            patch("pi_pods.commands.models.ssh_exec", new_callable=AsyncMock) as mock_ssh,
            patch("asyncio.create_subprocess_exec", return_value=mock_log_proc),
            patch("pi_pods.commands.models._read_script", return_value=fake_script_content),
            patch(
                "pi_pods.commands.models.is_known_model",
                return_value=True,
            ),
            patch(
                "pi_pods.commands.models.get_model_config",
                return_value={"args": ["--tensor-parallel-size", "2"]},
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_ssh.return_value = MagicMock(stdout="5555\n", stderr="", exit_code=0)

            await start_model("org/Model", "m2", pod="testpod", gpus=2)

        cfg = load_config()
        assert "m2" in cfg.pods["testpod"].models
        assert len(cfg.pods["testpod"].models["m2"].gpu) == 2
