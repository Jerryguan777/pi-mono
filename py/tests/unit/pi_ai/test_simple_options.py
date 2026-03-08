"""Tests for pi_ai.providers.simple_options."""

from __future__ import annotations

from pi_ai.providers.simple_options import (
    adjust_max_tokens_for_thinking,
    build_base_options,
    clamp_reasoning,
)
from pi_ai.types import Model, ModelCost, SimpleStreamOptions, ThinkingBudgets


def _make_model(max_tokens: int = 8192) -> Model:
    return Model(
        id="claude-3-7-sonnet",
        name="Claude",
        api="anthropic-messages",
        provider="anthropic",
        base_url="https://api.anthropic.com",
        max_tokens=max_tokens,
        cost=ModelCost(),
    )


def test_build_base_options_defaults() -> None:
    model = _make_model(max_tokens=4096)
    opts = build_base_options(model)
    assert opts.temperature is None
    assert opts.max_tokens == min(4096, 32000)


def test_build_base_options_max_tokens_override() -> None:
    model = _make_model(max_tokens=100000)
    simple = SimpleStreamOptions(max_tokens=16000)
    opts = build_base_options(model, simple)
    assert opts.max_tokens == 16000


def test_build_base_options_max_tokens_capped_at_32000() -> None:
    model = _make_model(max_tokens=100000)
    opts = build_base_options(model)
    assert opts.max_tokens == 32000


def test_build_base_options_api_key_precedence() -> None:
    model = _make_model()
    simple = SimpleStreamOptions(api_key="from-options")
    opts = build_base_options(model, simple, api_key="explicit")
    assert opts.api_key == "explicit"


def test_build_base_options_api_key_from_options() -> None:
    model = _make_model()
    simple = SimpleStreamOptions(api_key="from-options")
    opts = build_base_options(model, simple)
    assert opts.api_key == "from-options"


def test_build_base_options_temperature() -> None:
    model = _make_model()
    simple = SimpleStreamOptions(temperature=0.7)
    opts = build_base_options(model, simple)
    assert opts.temperature == 0.7


def test_clamp_reasoning_xhigh() -> None:
    assert clamp_reasoning("xhigh") == "high"


def test_clamp_reasoning_high() -> None:
    assert clamp_reasoning("high") == "high"


def test_clamp_reasoning_medium() -> None:
    assert clamp_reasoning("medium") == "medium"


def test_clamp_reasoning_low() -> None:
    assert clamp_reasoning("low") == "low"


def test_clamp_reasoning_minimal() -> None:
    assert clamp_reasoning("minimal") == "minimal"


def test_clamp_reasoning_none() -> None:
    assert clamp_reasoning(None) is None


def test_adjust_max_tokens_basic() -> None:
    max_tokens, budget = adjust_max_tokens_for_thinking(
        base_max_tokens=4096,
        model_max_tokens=32000,
        reasoning_level="medium",
    )
    # Default medium budget is 8192
    assert max_tokens == 4096 + 8192
    assert budget == 8192


def test_adjust_max_tokens_high() -> None:
    max_tokens, budget = adjust_max_tokens_for_thinking(
        base_max_tokens=4096,
        model_max_tokens=32000,
        reasoning_level="high",
    )
    # Default high budget is 16384
    assert max_tokens == 4096 + 16384
    assert budget == 16384


def test_adjust_max_tokens_capped_by_model() -> None:
    max_tokens, budget = adjust_max_tokens_for_thinking(
        base_max_tokens=4096,
        model_max_tokens=5000,
        reasoning_level="high",
    )
    assert max_tokens == 5000
    # Budget should be reduced to fit within model limit with min output
    assert budget <= 5000 - 1024


def test_adjust_max_tokens_xhigh_clamped_to_high() -> None:
    max_tokens_xhigh, budget_xhigh = adjust_max_tokens_for_thinking(
        base_max_tokens=4096,
        model_max_tokens=32000,
        reasoning_level="xhigh",
    )
    max_tokens_high, budget_high = adjust_max_tokens_for_thinking(
        base_max_tokens=4096,
        model_max_tokens=32000,
        reasoning_level="high",
    )
    assert max_tokens_xhigh == max_tokens_high
    assert budget_xhigh == budget_high


def test_adjust_max_tokens_custom_budget() -> None:
    custom = ThinkingBudgets(medium=4000)
    max_tokens, budget = adjust_max_tokens_for_thinking(
        base_max_tokens=4096,
        model_max_tokens=32000,
        reasoning_level="medium",
        custom_budgets=custom,
    )
    assert budget == 4000
    assert max_tokens == 4096 + 4000
