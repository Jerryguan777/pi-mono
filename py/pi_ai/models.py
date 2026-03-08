"""Model registry and cost calculation.

Ported from packages/ai/src/models.ts.
"""

from __future__ import annotations

from pi_ai.types import Model, Usage


def calculate_cost(model: Model, usage: Usage) -> None:
    """Calculate token costs based on model pricing and update usage.cost in place."""
    usage.cost.input = (model.cost.input / 1_000_000) * usage.input
    usage.cost.output = (model.cost.output / 1_000_000) * usage.output
    usage.cost.cache_read = (model.cost.cache_read / 1_000_000) * usage.cache_read
    usage.cost.cache_write = (model.cost.cache_write / 1_000_000) * usage.cache_write
    usage.cost.total = usage.cost.input + usage.cost.output + usage.cost.cache_read + usage.cost.cache_write
