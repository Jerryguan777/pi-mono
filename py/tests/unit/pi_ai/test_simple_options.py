"""Tests for pi_ai.providers.simple_options."""

from __future__ import annotations

from pi_ai.providers.simple_options import (
    adjust_max_tokens_for_thinking,
    build_base_options,
    clamp_reasoning,
)
from pi_ai.types import Model, ModelCost, SimpleStreamOptions, ThinkingBudgets


def _make_model(max_tokens: int = 4096) -> Model:
    return Model(
        id="test",
        name="Test",
        api="test-api",
        provider="test",
        max_tokens=max_tokens,
        cost=ModelCost(),
    )


class TestBuildBaseOptions:
    def test_defaults(self) -> None:
        model = _make_model(max_tokens=8000)
        opts = build_base_options(model)
        assert opts.max_tokens == 8000  # min(8000, 32000)

    def test_defaults_capped(self) -> None:
        model = _make_model(max_tokens=100000)
        opts = build_base_options(model)
        assert opts.max_tokens == 32000

    def test_with_options(self) -> None:
        model = _make_model()
        simple = SimpleStreamOptions(temperature=0.7, max_tokens=2048)
        opts = build_base_options(model, simple)
        assert opts.temperature == 0.7
        assert opts.max_tokens == 2048

    def test_api_key_override(self) -> None:
        model = _make_model()
        simple = SimpleStreamOptions(api_key="from-options")
        opts = build_base_options(model, simple, api_key="override")
        assert opts.api_key == "override"

    def test_api_key_from_options(self) -> None:
        model = _make_model()
        simple = SimpleStreamOptions(api_key="from-options")
        opts = build_base_options(model, simple)
        assert opts.api_key == "from-options"


class TestClampReasoning:
    def test_xhigh_becomes_high(self) -> None:
        assert clamp_reasoning("xhigh") == "high"

    def test_high_stays(self) -> None:
        assert clamp_reasoning("high") == "high"

    def test_none_stays(self) -> None:
        assert clamp_reasoning(None) is None

    def test_other_levels(self) -> None:
        assert clamp_reasoning("minimal") == "minimal"
        assert clamp_reasoning("low") == "low"
        assert clamp_reasoning("medium") == "medium"


class TestAdjustMaxTokensForThinking:
    def test_default_budgets(self) -> None:
        max_tokens, budget = adjust_max_tokens_for_thinking(32000, 100000, "high")
        assert budget == 16384
        assert max_tokens == 32000 + 16384

    def test_minimal_budget(self) -> None:
        _max_tokens, budget = adjust_max_tokens_for_thinking(32000, 100000, "minimal")
        assert budget == 1024

    def test_model_max_caps(self) -> None:
        max_tokens, _budget = adjust_max_tokens_for_thinking(32000, 33000, "high")
        assert max_tokens == 33000  # capped at model max

    def test_small_max_tokens(self) -> None:
        max_tokens, budget = adjust_max_tokens_for_thinking(500, 2000, "high")
        # max_tokens = min(500 + 16384, 2000) = 2000
        # budget was 16384, but maxTokens(2000) <= budget(16384)
        # so budget = max(0, 2000 - 1024) = 976
        assert max_tokens == 2000
        assert budget == 976

    def test_custom_budgets(self) -> None:
        custom = ThinkingBudgets(high=32768)
        max_tokens, budget = adjust_max_tokens_for_thinking(32000, 100000, "high", custom)
        assert budget == 32768
        assert max_tokens == 32000 + 32768

    def test_xhigh_clamped_to_high(self) -> None:
        _max_tokens, budget = adjust_max_tokens_for_thinking(32000, 100000, "xhigh")
        assert budget == 16384  # xhigh -> high default
