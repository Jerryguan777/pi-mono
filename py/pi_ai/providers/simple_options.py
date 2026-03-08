"""Simple stream option helpers — ported from packages/ai/src/providers/simple-options.ts."""

from __future__ import annotations

from pi_ai.types import Model, SimpleStreamOptions, StreamOptions, ThinkingBudgets, ThinkingLevel


def build_base_options(
    model: Model,
    options: SimpleStreamOptions | None = None,
    api_key: str | None = None,
) -> StreamOptions:
    """Build base StreamOptions from simple options, applying model defaults.

    Args:
        model: The target model.
        options: Optional simple stream options.
        api_key: Optional explicit API key (takes precedence over options.api_key).

    Returns:
        StreamOptions with resolved values.
    """
    return StreamOptions(
        temperature=options.temperature if options else None,
        max_tokens=(options.max_tokens if options and options.max_tokens else None) or min(model.max_tokens, 32000),
        signal=options.signal if options else None,
        api_key=api_key or (options.api_key if options else None),
        cache_retention=options.cache_retention if options else None,
        session_id=options.session_id if options else None,
        headers=options.headers if options else None,
        on_payload=options.on_payload if options else None,
        max_retry_delay_ms=options.max_retry_delay_ms if options else None,
        metadata=options.metadata if options else None,
    )


def clamp_reasoning(
    effort: ThinkingLevel | None,
) -> ThinkingLevel | None:
    """Clamp xhigh to high for models that don't support xhigh."""
    if effort == "xhigh":
        return "high"
    return effort


def adjust_max_tokens_for_thinking(
    base_max_tokens: int,
    model_max_tokens: int,
    reasoning_level: ThinkingLevel,
    custom_budgets: ThinkingBudgets | None = None,
) -> tuple[int, int]:
    """Compute (max_tokens, thinking_budget) for budget-based thinking models.

    Args:
        base_max_tokens: Desired output token budget (not including thinking).
        model_max_tokens: Hard limit from the model.
        reasoning_level: Desired thinking level.
        custom_budgets: Optional custom per-level token budgets.

    Returns:
        Tuple of (max_tokens, thinking_budget) to pass to the API.
    """
    default_budgets = ThinkingBudgets(
        minimal=1024,
        low=2048,
        medium=8192,
        high=16384,
    )

    # Merge custom budgets over defaults
    merged_minimal = (
        (custom_budgets.minimal if custom_budgets and custom_budgets.minimal is not None else None)
        or default_budgets.minimal
        or 1024
    )
    merged_low = (
        (custom_budgets.low if custom_budgets and custom_budgets.low is not None else None)
        or default_budgets.low
        or 2048
    )
    merged_medium = (
        (custom_budgets.medium if custom_budgets and custom_budgets.medium is not None else None)
        or default_budgets.medium
        or 8192
    )
    merged_high = (
        (custom_budgets.high if custom_budgets and custom_budgets.high is not None else None)
        or default_budgets.high
        or 16384
    )

    budgets: dict[str, int] = {
        "minimal": merged_minimal,
        "low": merged_low,
        "medium": merged_medium,
        "high": merged_high,
    }

    min_output_tokens = 1024
    # xhigh is clamped to high for budget-based models
    level = clamp_reasoning(reasoning_level) or "high"
    thinking_budget = budgets[level]
    max_tokens = min(base_max_tokens + thinking_budget, model_max_tokens)

    if max_tokens <= thinking_budget:
        thinking_budget = max(0, max_tokens - min_output_tokens)

    return max_tokens, thinking_budget
