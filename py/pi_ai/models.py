"""Model utilities — ported from packages/ai/src/models.ts (without catalog)."""

from __future__ import annotations

from pi_ai.types import CostBreakdown, Model, Usage


def calculate_cost(model: Model, usage: Usage) -> CostBreakdown:
    """Compute cost breakdown for a completed request and update usage.cost in place."""
    usage.cost.input = (model.cost.input / 1_000_000) * usage.input
    usage.cost.output = (model.cost.output / 1_000_000) * usage.output
    usage.cost.cache_read = (model.cost.cache_read / 1_000_000) * usage.cache_read
    usage.cost.cache_write = (model.cost.cache_write / 1_000_000) * usage.cache_write
    usage.cost.total = usage.cost.input + usage.cost.output + usage.cost.cache_read + usage.cost.cache_write
    return usage.cost


def supports_xhigh(model: Model) -> bool:
    """Check if a model supports xhigh thinking level.

    Supported today:
    - GPT-5.2 / GPT-5.3 model families
    - Anthropic Messages API Opus 4.6 models (xhigh maps to adaptive effort "max")
    """
    if "gpt-5.2" in model.id or "gpt-5.3" in model.id:
        return True
    if model.api == "anthropic-messages":
        return "opus-4-6" in model.id or "opus-4.6" in model.id
    return False


def models_are_equal(a: Model | None, b: Model | None) -> bool:
    """Check if two models are equal by comparing id and provider.

    Returns False if either model is None.
    """
    if a is None or b is None:
        return False
    return a.id == b.id and a.provider == b.provider
