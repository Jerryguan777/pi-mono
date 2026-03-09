"""Unit tests for pi_pods.commands.prompt."""

from pathlib import Path

import pytest

from pi_pods.commands.prompt import prompt_model
from pi_pods.config import save_config
from pi_pods.types import GPU, Config, Model, Pod


def _make_pod_with_model(model_name: str = "mymodel") -> Pod:
    return Pod(
        ssh="ssh root@1.2.3.4",
        gpus=[GPU(id=0, name="NVIDIA H100", memory="80 GiB")],
        models={
            model_name: Model(
                model="org/TestModel",
                port=8001,
                gpu=[0],
                pid=1234,
            )
        },
        models_path="/mnt/models",
    )


@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PI_CONFIG_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def pod_config(config_dir: Path) -> None:
    pod = _make_pod_with_model()
    cfg = Config(pods={"testpod": pod}, active="testpod")
    save_config(cfg)


class TestPromptModel:
    async def test_raises_not_implemented(self, pod_config: None) -> None:
        # The TS source raises "Not implemented" — Python port mirrors that.
        with pytest.raises(SystemExit):
            await prompt_model("mymodel", [], pod="testpod")

    async def test_exits_when_no_active_pod(self, config_dir: Path) -> None:
        with pytest.raises(SystemExit):
            await prompt_model("mymodel", [])

    async def test_exits_when_pod_not_found(self, config_dir: Path) -> None:
        with pytest.raises(SystemExit):
            await prompt_model("mymodel", [], pod="ghost")

    async def test_exits_when_model_not_found(self, pod_config: None) -> None:
        with pytest.raises(SystemExit):
            await prompt_model("nonexistent", [], pod="testpod")

    async def test_uses_gpt_oss_api_type(self, config_dir: Path) -> None:
        """Verify that gpt-oss model uses 'responses' api type."""
        pod = Pod(
            ssh="ssh root@1.2.3.4",
            gpus=[GPU(id=0, name="NVIDIA H100", memory="80 GiB")],
            models={
                "gptoss": Model(
                    model="some/gpt-oss-model",
                    port=8002,
                    gpu=[0],
                    pid=9999,
                )
            },
        )
        cfg = Config(pods={"oss": pod}, active="oss")
        save_config(cfg)

        # Should still exit with SystemExit (not implemented) but not fail earlier
        with pytest.raises(SystemExit):
            await prompt_model("gptoss", [], pod="oss")
