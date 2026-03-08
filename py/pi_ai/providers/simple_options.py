"""Simple option builders for provider stream functions.

Ported from packages/ai/src/providers/simple-options.ts.
"""

from __future__ import annotations

from pi_ai.types import Model, SimpleStreamOptions, StreamOptions, ThinkingBudgets, ThinkingLevel


def build_base_options(
    model: Model,
    options: SimpleStreamOptions | None = None,
    api_key: str | None = None,
) -> StreamOptions:
    """Build base StreamOptions from SimpleStreamOptions."""
    if options is None:
        return StreamOptions(
            max_tokens=min(model.max_tokens, 32000),
            api_key=api_key,
        )
    return StreamOptions(
        temperature=options.temperature,
        max_tokens=options.max_tokens or min(model.max_tokens, 32000),
        signal=options.signal,
        api_key=api_key or options.api_key,
        cache_retention=options.cache_retention,
        session_id=options.session_id,
        headers=options.headers,
        on_payload=options.on_payload,
        max_retry_delay_ms=options.max_retry_delay_ms,
        metadata=options.metadata,
    )


def clamp_reasoning(effort: ThinkingLevel | None) -> ThinkingLevel | None:
    """Clamp xhigh thinking level to high."""
    if effort == "xhigh":
        return "high"
    return effort


def adjust_max_tokens_for_thinking(
    base_max_tokens: int,
    model_max_tokens: int,
    reasoning_level: ThinkingLevel,
    custom_budgets: ThinkingBudgets | None = None,
) -> tuple[int, int]:
    """Adjust maxTokens to accommodate thinking budget.

    Returns (max_tokens, thinking_budget).
    """
    default_budgets: dict[str, int] = {
        "minimal": 1024,
        "low": 2048,
        "medium": 8192,
        "high": 16384,
    }

    level = clamp_reasoning(reasoning_level) or "high"
    budget = default_budgets.get(level, 16384)

    if custom_budgets is not None:
        custom_val = getattr(custom_budgets, level, None)
        if custom_val is not None:
            budget = custom_val

    min_output_tokens = 1024
    max_tokens = min(base_max_tokens + budget, model_max_tokens)

    if max_tokens <= budget:
        budget = max(0, max_tokens - min_output_tokens)

    return max_tokens, budget
