"""Tests for pi_ai.models."""

from __future__ import annotations

import pytest

from pi_ai.models import (
    calculate_cost,
    clear_model_registry,
    get_model,
    get_models,
    get_providers,
    models_are_equal,
    register_models,
    supports_xhigh,
)
from pi_ai.types import Model, ModelCost, Usage


def _make_model(
    model_id: str = "test-model",
    provider: str = "test",
    api: str = "test-api",
    cost: ModelCost | None = None,
    max_tokens: int = 4096,
    context_window: int = 128000,
) -> Model:
    return Model(
        id=model_id,
        name="Test",
        api=api,
        provider=provider,
        cost=cost or ModelCost(),
        max_tokens=max_tokens,
        context_window=context_window,
    )


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    clear_model_registry()


class TestModelRegistry:
    def test_register_and_get(self) -> None:
        m = _make_model("gpt-4")
        register_models("openai", {"gpt-4": m})
        result = get_model("openai", "gpt-4")
        assert result is not None
        assert result.id == "gpt-4"

    def test_get_nonexistent_provider(self) -> None:
        assert get_model("nonexistent", "any") is None

    def test_get_nonexistent_model(self) -> None:
        register_models("openai", {"gpt-4": _make_model("gpt-4")})
        assert get_model("openai", "gpt-5") is None

    def test_get_providers(self) -> None:
        register_models("openai", {"gpt-4": _make_model("gpt-4")})
        register_models("anthropic", {"claude-3": _make_model("claude-3")})
        providers = get_providers()
        assert set(providers) == {"openai", "anthropic"}

    def test_get_models(self) -> None:
        m1 = _make_model("gpt-4")
        m2 = _make_model("gpt-3.5")
        register_models("openai", {"gpt-4": m1, "gpt-3.5": m2})
        models = get_models("openai")
        assert len(models) == 2

    def test_get_models_empty(self) -> None:
        assert get_models("nonexistent") == []


class TestCalculateCost:
    def test_basic_cost(self) -> None:
        model = _make_model(cost=ModelCost(input=3.0, output=15.0, cache_read=0.3, cache_write=3.75))
        usage = Usage(input=1000, output=500, cache_read=200, cache_write=100)
        cost = calculate_cost(model, usage)
        assert abs(cost.input - 0.003) < 1e-10
        assert abs(cost.output - 0.0075) < 1e-10
        assert abs(cost.cache_read - 0.00006) < 1e-10
        assert abs(cost.cache_write - 0.000375) < 1e-10
        assert abs(cost.total - (cost.input + cost.output + cost.cache_read + cost.cache_write)) < 1e-10

    def test_zero_cost(self) -> None:
        model = _make_model(cost=ModelCost())
        usage = Usage(input=1000, output=500)
        cost = calculate_cost(model, usage)
        assert cost.total == 0.0


class TestSupportsXhigh:
    def test_gpt52(self) -> None:
        assert supports_xhigh(_make_model("gpt-5.2")) is True

    def test_gpt53(self) -> None:
        assert supports_xhigh(_make_model("gpt-5.3-turbo")) is True

    def test_anthropic_opus_46(self) -> None:
        assert supports_xhigh(_make_model("claude-opus-4-6", api="anthropic-messages")) is True

    def test_anthropic_opus_46_dot(self) -> None:
        assert supports_xhigh(_make_model("claude-opus-4.6", api="anthropic-messages")) is True

    def test_regular_model(self) -> None:
        assert supports_xhigh(_make_model("gpt-4")) is False


class TestModelsAreEqual:
    def test_same_model(self) -> None:
        m = _make_model("gpt-4", provider="openai")
        assert models_are_equal(m, m) is True

    def test_different_id(self) -> None:
        m1 = _make_model("gpt-4", provider="openai")
        m2 = _make_model("gpt-3.5", provider="openai")
        assert models_are_equal(m1, m2) is False

    def test_different_provider(self) -> None:
        m1 = _make_model("gpt-4", provider="openai")
        m2 = _make_model("gpt-4", provider="azure")
        assert models_are_equal(m1, m2) is False

    def test_none_args(self) -> None:
        m = _make_model("gpt-4")
        assert models_are_equal(None, m) is False
        assert models_are_equal(m, None) is False
        assert models_are_equal(None, None) is False
