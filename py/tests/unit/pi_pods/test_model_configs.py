"""Unit tests for pi_pods.model_configs."""

from contextlib import AbstractContextManager
from unittest.mock import patch

from pi_pods.model_configs import (
    get_known_models,
    get_model_config,
    get_model_name,
    is_known_model,
)
from pi_pods.types import GPU

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------


def _make_gpu(name: str = "NVIDIA H100") -> GPU:
    return GPU(id=0, name=name, memory="80 GiB")


# Minimal models.json data for patching
SAMPLE_MODELS_DATA: dict[str, object] = {
    "models": {
        "org/ModelA": {
            "name": "ModelA",
            "configs": [
                {
                    "gpuCount": 1,
                    "gpuTypes": ["H100", "H200"],
                    "args": ["--tool-call-parser", "hermes"],
                    "env": {"MY_VAR": "1"},
                    "notes": "Great on single GPU",
                },
                {
                    "gpuCount": 2,
                    "gpuTypes": ["H100"],
                    "args": ["--tensor-parallel-size", "2"],
                },
            ],
        },
        "org/ModelB": {
            "name": "ModelB",
            "configs": [
                {
                    "gpuCount": 4,
                    "gpuTypes": ["A100"],
                    "args": ["--tensor-parallel-size", "4"],
                    "notes": "Needs 4 A100s",
                }
            ],
        },
        "org/ModelNoType": {
            "name": "ModelNoType",
            "configs": [
                {
                    "gpuCount": 1,
                    "args": ["--simple-arg"],
                }
            ],
        },
    }
}


def _patch_models(data: dict[str, object] = SAMPLE_MODELS_DATA) -> AbstractContextManager[object]:
    """Return a context manager that patches _models_data in model_configs module."""
    import pi_pods.model_configs as mc

    return patch.object(mc, "_models_data", data)


# -------------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------------


class TestIsKnownModel:
    def test_known_model_returns_true(self) -> None:
        with _patch_models():
            assert is_known_model("org/ModelA") is True

    def test_unknown_model_returns_false(self) -> None:
        with _patch_models():
            assert is_known_model("org/Unknown") is False


class TestGetKnownModels:
    def test_returns_all_model_ids(self) -> None:
        with _patch_models():
            models = get_known_models()
        assert "org/ModelA" in models
        assert "org/ModelB" in models
        assert "org/ModelNoType" in models

    def test_returns_list_type(self) -> None:
        with _patch_models():
            result = get_known_models()
        assert isinstance(result, list)


class TestGetModelName:
    def test_returns_display_name(self) -> None:
        with _patch_models():
            assert get_model_name("org/ModelA") == "ModelA"

    def test_returns_model_id_when_not_found(self) -> None:
        with _patch_models():
            assert get_model_name("org/Ghost") == "org/Ghost"


class TestGetModelConfig:
    def test_returns_config_for_matching_gpu_type_and_count(self) -> None:
        with _patch_models():
            result = get_model_config("org/ModelA", [_make_gpu("NVIDIA H100")], 1)
        assert result is not None
        assert "--tool-call-parser" in result["args"]  # type: ignore[operator]

    def test_returns_none_for_unknown_model(self) -> None:
        with _patch_models():
            result = get_model_config("org/Ghost", [_make_gpu()], 1)
        assert result is None

    def test_returns_none_when_no_matching_gpu_count(self) -> None:
        with _patch_models():
            # ModelA has configs for 1 and 2, not 3
            result = get_model_config("org/ModelA", [_make_gpu()], 3)
        assert result is None

    def test_includes_env_when_present(self) -> None:
        with _patch_models():
            result = get_model_config("org/ModelA", [_make_gpu("NVIDIA H100")], 1)
        assert result is not None
        assert result.get("env") == {"MY_VAR": "1"}

    def test_includes_notes_when_present(self) -> None:
        with _patch_models():
            result = get_model_config("org/ModelA", [_make_gpu()], 1)
        assert result is not None
        assert result.get("notes") == "Great on single GPU"

    def test_falls_back_to_first_matching_count_when_type_mismatch(self) -> None:
        # H200 GPU, but config only lists H100 type for count=2.
        # Should still return the config as a fallback.
        with _patch_models():
            result = get_model_config("org/ModelA", [_make_gpu("NVIDIA H200")], 2)
        assert result is not None
        assert "--tensor-parallel-size" in result["args"]  # type: ignore[operator]

    def test_model_without_gpu_types_matches_any_gpu(self) -> None:
        with _patch_models():
            result = get_model_config("org/ModelNoType", [_make_gpu("NVIDIA A30")], 1)
        assert result is not None
        assert "--simple-arg" in result["args"]  # type: ignore[operator]

    def test_gpu_type_extraction_strips_nvidia_prefix(self) -> None:
        with _patch_models():
            # "NVIDIA H100" -> "H100"
            result = get_model_config("org/ModelA", [_make_gpu("NVIDIA H100 SXM5")], 1)
        assert result is not None

    def test_returns_none_for_wrong_gpu_type_no_fallback(self) -> None:
        # ModelB requires A100; we only have H100 for 4 GPUs,
        # so the first-pass type match fails, but count-only fallback should succeed.
        with _patch_models():
            h100_gpus = [GPU(id=i, name="NVIDIA H100", memory="80 GiB") for i in range(4)]
            result = get_model_config("org/ModelB", h100_gpus, 4)
        # Fallback by count should find the config
        assert result is not None

    def test_no_env_key_when_env_absent(self) -> None:
        with _patch_models():
            result = get_model_config("org/ModelA", [_make_gpu()], 2)
        assert result is not None
        assert "env" not in result
