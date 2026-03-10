"""Tests for the model registry and cost calculation.

Ported from python-superpowers. Adapted to use register_models()
(which takes a provider + dict of models) instead of register_model().
"""

from __future__ import annotations

import pytest
from pi_ai.models import (
    _model_registry,
    calculate_cost,
    get_model,
    get_models,
    get_providers,
    register_models,
)
from pi_ai.types import Model, ModelCost, Usage


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Clear the global registry before each test."""
    _model_registry.clear()


def _make_model(
    provider: str = "anthropic",
    model_id: str = "claude-sonnet-4",
    **kwargs: object,
) -> Model:
    return Model(
        id=model_id,
        name=kwargs.get("name", model_id),
        api=kwargs.get("api", "anthropic-messages"),
        provider=provider,
        cost=kwargs.get("cost", ModelCost()),
    )


def _register(model: Model) -> None:
    """Register a single model via the batch register_models API."""
    existing = dict(_model_registry.get(model.provider, {}))
    existing[model.id] = model
    register_models(model.provider, existing)


class TestRegisterAndGetModel:
    def test_register_and_retrieve(self) -> None:
        model = _make_model()
        _register(model)
        result = get_model("anthropic", "claude-sonnet-4")
        assert result is not None
        assert result.id == "claude-sonnet-4"
        assert result.provider == "anthropic"

    def test_get_model_returns_none_for_unknown_model(self) -> None:
        assert get_model("anthropic", "nonexistent") is None

    def test_get_model_returns_none_for_unknown_provider(self) -> None:
        assert get_model("nonexistent", "claude-sonnet-4") is None

    def test_register_overwrites_existing(self) -> None:
        m1 = _make_model(name="v1")
        m2 = _make_model(name="v2")
        _register(m1)
        _register(m2)
        result = get_model("anthropic", "claude-sonnet-4")
        assert result is not None
        assert result.name == "v2"


class TestGetModels:
    def test_returns_all_models_for_provider(self) -> None:
        _register(_make_model(model_id="model-a"))
        _register(_make_model(model_id="model-b"))
        models = get_models("anthropic")
        assert len(models) == 2
        ids = {m.id for m in models}
        assert ids == {"model-a", "model-b"}

    def test_returns_empty_for_unknown_provider(self) -> None:
        assert get_models("nonexistent") == []


class TestGetProviders:
    def test_returns_registered_providers(self) -> None:
        _register(_make_model(provider="anthropic"))
        _register(_make_model(provider="openai", model_id="gpt-4o", api="openai-responses"))
        providers = get_providers()
        assert set(providers) == {"anthropic", "openai"}

    def test_returns_empty_when_none_registered(self) -> None:
        assert get_providers() == []


class TestCalculateCost:
    def test_basic_cost_calculation(self) -> None:
        model = _make_model(
            cost=ModelCost(input=3.0, output=15.0, cache_read=0.3, cache_write=3.75),
        )
        usage = Usage(
            input=1000,
            output=500,
            cache_read=2000,
            cache_write=100,
        )
        cost = calculate_cost(model, usage)

        assert cost.input == pytest.approx(3.0 / 1_000_000 * 1000)
        assert cost.output == pytest.approx(15.0 / 1_000_000 * 500)
        assert cost.cache_read == pytest.approx(0.3 / 1_000_000 * 2000)
        assert cost.cache_write == pytest.approx(3.75 / 1_000_000 * 100)
        assert cost.total == pytest.approx(cost.input + cost.output + cost.cache_read + cost.cache_write)

    def test_zero_usage_gives_zero_cost(self) -> None:
        model = _make_model(
            cost=ModelCost(input=3.0, output=15.0),
        )
        usage = Usage()
        cost = calculate_cost(model, usage)
        assert cost.total == pytest.approx(0.0)

    def test_zero_model_cost_gives_zero(self) -> None:
        model = _make_model()  # default ModelCost is all zeros
        usage = Usage(input=1_000_000, output=500_000)
        cost = calculate_cost(model, usage)
        assert cost.total == pytest.approx(0.0)
