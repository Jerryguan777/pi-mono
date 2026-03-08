"""Tests for pi_ai.providers.simple_options."""

from __future__ import annotations

from pi_ai.providers.simple_options import (
    adjust_max_tokens_for_thinking,
    build_base_options,
    clamp_reasoning,
)
from pi_ai.types import Model, SimpleStreamOptions, ThinkingBudgets


class TestClampReasoning:
    def test_xhigh_becomes_high(self) -> None:
        assert clamp_reasoning("xhigh") == "high"

    def test_high_stays_high(self) -> None:
        assert clamp_reasoning("high") == "high"

    def test_medium_stays_medium(self) -> None:
        assert clamp_reasoning("medium") == "medium"

    def test_low_stays_low(self) -> None:
        assert clamp_reasoning("low") == "low"

    def test_minimal_stays_minimal(self) -> None:
        assert clamp_reasoning("minimal") == "minimal"

    def test_none_stays_none(self) -> None:
        assert clamp_reasoning(None) is None


class TestBuildBaseOptions:
    def test_none_options_uses_defaults(self) -> None:
        model = Model(max_tokens=100_000)
        result = build_base_options(model)
        assert result.max_tokens == 32000
        assert result.api_key is None
        assert result.temperature is None

    def test_none_options_with_api_key(self) -> None:
        model = Model(max_tokens=100_000)
        result = build_base_options(model, api_key="sk-test")
        assert result.api_key == "sk-test"

    def test_none_options_small_model(self) -> None:
        model = Model(max_tokens=4096)
        result = build_base_options(model)
        assert result.max_tokens == 4096

    def test_with_options(self) -> None:
        model = Model(max_tokens=100_000)
        options = SimpleStreamOptions(temperature=0.5, max_tokens=8000, api_key="from-opts")
        result = build_base_options(model, options)
        assert result.temperature == 0.5
        assert result.max_tokens == 8000
        assert result.api_key == "from-opts"

    def test_options_api_key_override(self) -> None:
        model = Model(max_tokens=100_000)
        options = SimpleStreamOptions(api_key="from-opts")
        result = build_base_options(model, options, api_key="from-arg")
        # api_key arg takes precedence
        assert result.api_key == "from-arg"

    def test_options_no_max_tokens_uses_model_default(self) -> None:
        model = Model(max_tokens=16000)
        options = SimpleStreamOptions()
        result = build_base_options(model, options)
        assert result.max_tokens == 16000

    def test_options_no_max_tokens_capped_at_32000(self) -> None:
        model = Model(max_tokens=200_000)
        options = SimpleStreamOptions()
        result = build_base_options(model, options)
        assert result.max_tokens == 32000


class TestAdjustMaxTokensForThinking:
    def test_high_default_budget(self) -> None:
        max_tokens, budget = adjust_max_tokens_for_thinking(32000, 100_000, "high")
        assert budget == 16384
        assert max_tokens == 32000 + 16384

    def test_medium_default_budget(self) -> None:
        max_tokens, budget = adjust_max_tokens_for_thinking(32000, 100_000, "medium")
        assert budget == 8192
        assert max_tokens == 32000 + 8192

    def test_low_default_budget(self) -> None:
        _max_tokens, budget = adjust_max_tokens_for_thinking(32000, 100_000, "low")
        assert budget == 2048

    def test_minimal_default_budget(self) -> None:
        _max_tokens, budget = adjust_max_tokens_for_thinking(32000, 100_000, "minimal")
        assert budget == 1024

    def test_xhigh_clamped_to_high(self) -> None:
        _, budget = adjust_max_tokens_for_thinking(32000, 100_000, "xhigh")
        assert budget == 16384

    def test_model_max_tokens_cap(self) -> None:
        # model_max_tokens is small, so max_tokens gets capped
        max_tokens, budget = adjust_max_tokens_for_thinking(32000, 10000, "high")
        assert max_tokens == 10000
        # budget should be reduced since max_tokens <= budget would be true
        # 10000 <= 16384 is true, so budget = max(0, 10000 - 1024) = 8976
        assert budget == 8976

    def test_custom_budgets(self) -> None:
        custom = ThinkingBudgets(high=20000)
        max_tokens, budget = adjust_max_tokens_for_thinking(32000, 100_000, "high", custom)
        assert budget == 20000
        assert max_tokens == 32000 + 20000

    def test_custom_budgets_partial(self) -> None:
        custom = ThinkingBudgets(medium=4096)
        # Using "high" level, custom doesn't have high set
        _, budget = adjust_max_tokens_for_thinking(32000, 100_000, "high", custom)
        assert budget == 16384  # default

    def test_very_small_model(self) -> None:
        max_tokens, budget = adjust_max_tokens_for_thinking(1000, 2000, "high")
        assert max_tokens == 2000
        # 2000 <= 16384, so budget = max(0, 2000 - 1024) = 976
        assert budget == 976
