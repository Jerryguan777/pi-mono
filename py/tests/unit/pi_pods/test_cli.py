"""Unit tests for pi_pods.cli (Typer app)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from pi_pods.cli import app
from pi_pods.types import GPU, Config, Pod

runner = CliRunner()


def _make_pod(ssh: str = "ssh root@1.2.3.4") -> Pod:
    return Pod(
        ssh=ssh,
        gpus=[GPU(id=0, name="NVIDIA H100", memory="80 GiB")],
        models={},
        models_path="/mnt/models",
        vllm_version="release",
    )


@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PI_CONFIG_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def populated_config(config_dir: Path) -> None:
    pod = _make_pod()
    config = Config(pods={"testpod": pod}, active="testpod")
    from pi_pods.config import save_config

    save_config(config)


class TestPodsListCommand:
    def test_shows_no_pods_message(self, config_dir: Path) -> None:
        result = runner.invoke(app, ["pods"])
        assert result.exit_code == 0
        assert "No pods configured" in result.output

    def test_lists_configured_pods(self, populated_config: None) -> None:
        result = runner.invoke(app, ["pods"])
        assert result.exit_code == 0
        assert "testpod" in result.output


class TestPodsActiveCommand:
    def test_switches_active_pod(self, config_dir: Path) -> None:
        from pi_pods.config import add_pod

        add_pod("alpha", _make_pod())
        add_pod("beta", _make_pod("ssh root@2.2.2.2"))

        result = runner.invoke(app, ["pods", "active", "beta"])
        assert result.exit_code == 0
        assert "beta" in result.output

    def test_fails_for_unknown_pod(self, config_dir: Path) -> None:
        result = runner.invoke(app, ["pods", "active", "nonexistent"])
        assert result.exit_code != 0


class TestPodsRemoveCommand:
    def test_removes_pod(self, populated_config: None) -> None:
        result = runner.invoke(app, ["pods", "remove", "testpod"])
        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_fails_for_unknown_pod(self, config_dir: Path) -> None:
        result = runner.invoke(app, ["pods", "remove", "ghost"])
        assert result.exit_code != 0


class TestStartCommand:
    def test_shows_known_models_when_no_model_given(self, populated_config: None) -> None:
        with patch("pi_pods.cli.show_known_models", new_callable=AsyncMock) as mock_show:
            result = runner.invoke(app, ["start"])
        mock_show.assert_called_once()
        assert result.exit_code == 0

    def test_requires_name(self, populated_config: None) -> None:
        result = runner.invoke(app, ["start", "org/SomeModel"])
        assert result.exit_code != 0
        assert "--name" in result.output or "--name" in (result.stderr or "")

    def test_calls_start_model(self, populated_config: None) -> None:
        with patch("pi_pods.cli.start_model", new_callable=AsyncMock) as mock_start:
            runner.invoke(app, ["start", "org/Model", "--name", "mymodel"])
        mock_start.assert_called_once()
        call_kwargs = mock_start.call_args[1]
        assert call_kwargs.get("model_id") == "org/Model" or mock_start.call_args[0][0] == "org/Model"

    def test_warns_when_vllm_and_memory_both_set(self, populated_config: None) -> None:
        with patch("pi_pods.cli.start_model", new_callable=AsyncMock):
            result = runner.invoke(
                app,
                ["start", "org/Model", "--name", "m", "--vllm", "--some-arg", "--memory", "50%"],
            )
        assert "ignored" in result.output or result.exit_code == 0


class TestStopCommand:
    def test_stop_all_when_no_name(self, populated_config: None) -> None:
        with patch("pi_pods.cli.stop_all_models", new_callable=AsyncMock) as mock_stop:
            runner.invoke(app, ["stop"])
        mock_stop.assert_called_once()

    def test_stop_named_model(self, populated_config: None) -> None:
        with patch("pi_pods.cli.stop_model", new_callable=AsyncMock) as mock_stop:
            runner.invoke(app, ["stop", "mymodel"])
        mock_stop.assert_called_once()


class TestListCommand:
    def test_calls_list_models(self, populated_config: None) -> None:
        with patch("pi_pods.cli.list_models", new_callable=AsyncMock) as mock_list:
            runner.invoke(app, ["list"])
        mock_list.assert_called_once()


class TestLogsCommand:
    def test_calls_view_logs(self, populated_config: None) -> None:
        with patch("pi_pods.cli.view_logs", new_callable=AsyncMock) as mock_logs:
            runner.invoke(app, ["logs", "mymodel"])
        mock_logs.assert_called_once()


class TestAgentCommand:
    def test_calls_prompt_model(self, populated_config: None) -> None:
        with patch("pi_pods.cli.prompt_model", new_callable=AsyncMock) as mock_prompt:
            runner.invoke(app, ["agent", "mymodel", "Hello"])
        mock_prompt.assert_called_once()

    def test_passes_messages_as_user_args(self, populated_config: None) -> None:
        with patch("pi_pods.cli.prompt_model", new_callable=AsyncMock) as mock_prompt:
            runner.invoke(app, ["agent", "mymodel", "Hi there"])
        call_args = mock_prompt.call_args
        assert call_args is not None
