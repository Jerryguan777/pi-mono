"""Tests for pi_ai.models."""

from __future__ import annotations

from pi_ai.models import calculate_cost, models_are_equal, supports_xhigh
from pi_ai.types import Model, ModelCost, Usage


def _make_model(
    model_id: str = "gpt-4o",
    api: str = "openai-completions",
    provider: str = "openai",
    input_cost: float = 5.0,
    output_cost: float = 15.0,
    cache_read: float = 1.25,
    cache_write: float = 0.0,
    reasoning: bool = False,
) -> Model:
    return Model(
        id=model_id,
        name=model_id,
        api=api,
        provider=provider,
        base_url="https://api.openai.com/v1",
        reasoning=reasoning,
        cost=ModelCost(
            input=input_cost,
            output=output_cost,
            cache_read=cache_read,
            cache_write=cache_write,
        ),
    )


def test_calculate_cost_basic() -> None:
    model = _make_model(input_cost=5.0, output_cost=15.0)
    usage = Usage(input=1000, output=500)
    cost = calculate_cost(model, usage)
    assert abs(cost.input - 0.005) < 1e-9
    assert abs(cost.output - 0.0075) < 1e-9
    assert abs(cost.total - (cost.input + cost.output)) < 1e-9


def test_calculate_cost_with_cache() -> None:
    model = _make_model(cache_read=1.25, cache_write=6.25)
    usage = Usage(input=0, output=0, cache_read=2000, cache_write=1000)
    cost = calculate_cost(model, usage)
    assert abs(cost.cache_read - 0.0025) < 1e-9
    assert abs(cost.cache_write - 0.00625) < 1e-9


def test_calculate_cost_zero() -> None:
    model = _make_model(input_cost=0.0, output_cost=0.0)
    usage = Usage(input=100, output=200)
    cost = calculate_cost(model, usage)
    assert cost.total == 0.0


def test_calculate_cost_mutates_usage() -> None:
    model = _make_model(input_cost=3.0, output_cost=15.0)
    usage = Usage(input=1000, output=1000)
    calculate_cost(model, usage)
    assert usage.cost.input > 0
    assert usage.cost.output > 0


def test_supports_xhigh_gpt52() -> None:
    model = _make_model(model_id="gpt-5.2-mini", reasoning=True)
    assert supports_xhigh(model)


def test_supports_xhigh_gpt53() -> None:
    model = _make_model(model_id="gpt-5.3-turbo", reasoning=True)
    assert supports_xhigh(model)


def test_supports_xhigh_opus46() -> None:
    model = _make_model(
        model_id="claude-opus-4-6-20250514",
        api="anthropic-messages",
        provider="anthropic",
        reasoning=True,
    )
    assert supports_xhigh(model)


def test_supports_xhigh_opus46_dot() -> None:
    model = _make_model(
        model_id="claude-opus-4.6",
        api="anthropic-messages",
        provider="anthropic",
        reasoning=True,
    )
    assert supports_xhigh(model)


def test_supports_xhigh_false_for_regular_model() -> None:
    model = _make_model(model_id="gpt-4o")
    assert not supports_xhigh(model)


def test_supports_xhigh_false_for_claude3() -> None:
    model = _make_model(
        model_id="claude-3-sonnet-20240229",
        api="anthropic-messages",
        provider="anthropic",
    )
    assert not supports_xhigh(model)


def test_models_are_equal_same() -> None:
    m1 = _make_model(model_id="gpt-4o", provider="openai")
    m2 = _make_model(model_id="gpt-4o", provider="openai")
    assert models_are_equal(m1, m2)


def test_models_are_equal_different_id() -> None:
    m1 = _make_model(model_id="gpt-4o")
    m2 = _make_model(model_id="gpt-4o-mini")
    assert not models_are_equal(m1, m2)


def test_models_are_equal_different_provider() -> None:
    m1 = _make_model(provider="openai")
    m2 = _make_model(provider="openrouter")
    assert not models_are_equal(m1, m2)


def test_models_are_equal_none() -> None:
    model = _make_model()
    assert not models_are_equal(None, model)
    assert not models_are_equal(model, None)
    assert not models_are_equal(None, None)
