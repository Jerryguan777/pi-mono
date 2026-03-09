"""Unit tests for pi_pods.config."""

import json
from pathlib import Path

import pytest

from pi_pods.config import (
    add_pod,
    get_active_pod,
    load_config,
    remove_pod,
    save_config,
    set_active_pod,
)
from pi_pods.types import GPU, Config, Pod


def _make_pod(ssh: str = "ssh root@1.2.3.4") -> Pod:
    """Helper: build a minimal Pod."""
    return Pod(
        ssh=ssh,
        gpus=[GPU(id=0, name="NVIDIA H100", memory="80 GiB")],
        models={},
    )


@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config to a temp directory."""
    monkeypatch.setenv("PI_CONFIG_DIR", str(tmp_path))
    return tmp_path


class TestLoadConfig:
    def test_returns_empty_config_when_file_missing(self, config_dir: Path) -> None:
        config = load_config()
        assert config.pods == {}
        assert config.active is None

    def test_loads_existing_config(self, config_dir: Path) -> None:
        data = {
            "pods": {
                "myPod": {
                    "ssh": "ssh root@1.2.3.4",
                    "gpus": [{"id": 0, "name": "NVIDIA H100", "memory": "80 GiB"}],
                    "models": {},
                }
            },
            "active": "myPod",
        }
        (config_dir / "pods.json").write_text(json.dumps(data))
        config = load_config()
        assert "myPod" in config.pods
        assert config.active == "myPod"
        assert config.pods["myPod"].ssh == "ssh root@1.2.3.4"

    def test_returns_empty_config_on_corrupt_json(self, config_dir: Path) -> None:
        (config_dir / "pods.json").write_text("not json {{")
        config = load_config()
        assert config.pods == {}


class TestSaveConfig:
    def test_writes_json_file(self, config_dir: Path) -> None:
        pod = _make_pod()
        config = Config(pods={"test": pod}, active="test")
        save_config(config)

        data = json.loads((config_dir / "pods.json").read_text())
        assert "test" in data["pods"]
        assert data["active"] == "test"

    def test_round_trip(self, config_dir: Path) -> None:
        pod = _make_pod()
        config = Config(pods={"alpha": pod}, active="alpha")
        save_config(config)
        loaded = load_config()
        assert loaded.active == "alpha"
        assert "alpha" in loaded.pods
        assert loaded.pods["alpha"].ssh == "ssh root@1.2.3.4"


class TestGetActivePod:
    def test_returns_none_when_no_active(self, config_dir: Path) -> None:
        assert get_active_pod() is None

    def test_returns_none_when_active_not_in_pods(self, config_dir: Path) -> None:
        config = Config(pods={}, active="missing")
        save_config(config)
        assert get_active_pod() is None

    def test_returns_active_pod(self, config_dir: Path) -> None:
        pod = _make_pod()
        config = Config(pods={"myPod": pod}, active="myPod")
        save_config(config)
        result = get_active_pod()
        assert result is not None
        name, active_pod = result
        assert name == "myPod"
        assert active_pod.ssh == "ssh root@1.2.3.4"


class TestAddPod:
    def test_adds_pod_and_sets_active(self, config_dir: Path) -> None:
        add_pod("first", _make_pod())
        config = load_config()
        assert "first" in config.pods
        assert config.active == "first"

    def test_does_not_change_active_if_already_set(self, config_dir: Path) -> None:
        add_pod("first", _make_pod())
        add_pod("second", _make_pod("ssh root@2.2.2.2"))
        config = load_config()
        assert config.active == "first"  # still first

    def test_adds_multiple_pods(self, config_dir: Path) -> None:
        add_pod("a", _make_pod())
        add_pod("b", _make_pod("ssh root@5.5.5.5"))
        config = load_config()
        assert "a" in config.pods
        assert "b" in config.pods


class TestRemovePod:
    def test_removes_pod(self, config_dir: Path) -> None:
        add_pod("toRemove", _make_pod())
        remove_pod("toRemove")
        config = load_config()
        assert "toRemove" not in config.pods

    def test_clears_active_if_removed(self, config_dir: Path) -> None:
        add_pod("toRemove", _make_pod())
        remove_pod("toRemove")
        config = load_config()
        assert config.active is None

    def test_does_not_clear_active_for_other_pod(self, config_dir: Path) -> None:
        add_pod("a", _make_pod())
        add_pod("b", _make_pod("ssh root@2.2.2.2"))
        # Manually set active to b
        cfg = load_config()
        cfg.active = "b"
        save_config(cfg)
        remove_pod("a")
        config = load_config()
        assert config.active == "b"

    def test_noop_for_nonexistent_pod(self, config_dir: Path) -> None:
        add_pod("a", _make_pod())
        remove_pod("does_not_exist")  # should not raise
        config = load_config()
        assert "a" in config.pods


class TestSetActivePod:
    def test_sets_active_pod(self, config_dir: Path) -> None:
        add_pod("a", _make_pod())
        add_pod("b", _make_pod("ssh root@2.2.2.2"))
        set_active_pod("b")
        config = load_config()
        assert config.active == "b"

    def test_raises_for_unknown_pod(self, config_dir: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            set_active_pod("nonexistent")
