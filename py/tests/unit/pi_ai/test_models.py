"""Tests for pi_ai.models — cost calculation."""

from __future__ import annotations

from pi_ai.models import calculate_cost
from pi_ai.types import Model, ModelCost, Usage, UsageCost


class TestCalculateCost:
    def _model(self, **cost_kwargs: float) -> Model:
        return Model(
            id="test-model",
            provider="test",
            api="test",
            cost=ModelCost(**cost_kwargs),
        )

    def test_basic_cost(self) -> None:
        model = self._model(input=3.0, output=15.0)
        usage = Usage(input=1000, output=500)
        calculate_cost(model, usage)
        assert usage.cost.input == 3.0 / 1_000_000 * 1000
        assert usage.cost.output == 15.0 / 1_000_000 * 500
        assert usage.cost.total == usage.cost.input + usage.cost.output

    def test_zero_usage(self) -> None:
        model = self._model(input=3.0, output=15.0)
        usage = Usage(input=0, output=0)
        calculate_cost(model, usage)
        assert usage.cost.input == 0.0
        assert usage.cost.output == 0.0
        assert usage.cost.total == 0.0

    def test_zero_cost_model(self) -> None:
        model = self._model()
        usage = Usage(input=10000, output=5000)
        calculate_cost(model, usage)
        assert usage.cost.total == 0.0

    def test_cache_costs(self) -> None:
        model = self._model(
            input=3.0, output=15.0, cache_read=0.3, cache_write=3.75
        )
        usage = Usage(input=1000, output=500, cache_read=2000, cache_write=800)
        calculate_cost(model, usage)
        assert usage.cost.cache_read == 0.3 / 1_000_000 * 2000
        assert usage.cost.cache_write == 3.75 / 1_000_000 * 800
        expected_total = (
            usage.cost.input
            + usage.cost.output
            + usage.cost.cache_read
            + usage.cost.cache_write
        )
        assert usage.cost.total == expected_total

    def test_large_token_count(self) -> None:
        model = self._model(input=3.0, output=15.0)
        usage = Usage(input=1_000_000, output=1_000_000)
        calculate_cost(model, usage)
        assert usage.cost.input == 3.0
        assert usage.cost.output == 15.0
        assert usage.cost.total == 18.0

    def test_mutates_usage_in_place(self) -> None:
        model = self._model(input=3.0, output=15.0)
        usage = Usage(input=1000, output=500)
        calculate_cost(model, usage)
        # Verifies mutation happened on the same object
        assert usage.cost.input > 0

    def test_overwrites_existing_cost(self) -> None:
        model = self._model(input=3.0, output=15.0)
        usage = Usage(
            input=1000,
            output=500,
            cost=UsageCost(input=999.0, output=999.0, total=9999.0),
        )
        calculate_cost(model, usage)
        assert usage.cost.input == 3.0 / 1_000_000 * 1000
        assert usage.cost.total != 9999.0
