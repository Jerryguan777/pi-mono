"""List available models with optional fuzzy search.

Python port of packages/coding-agent/src/cli/list-models.ts.
"""

from __future__ import annotations

from typing import Any

from pi_tui import fuzzy_filter


def format_token_count(count: int) -> str:
    """Format a token count as a human-readable string.

    Examples:
        200000 -> "200K"
        1500000 -> "1.5M"
        500 -> "500"
    """
    if count >= 1_000_000:
        millions = count / 1_000_000
        if millions % 1 == 0:
            return f"{int(millions)}M"
        return f"{millions:.1f}M"
    if count >= 1_000:
        thousands = count / 1_000
        if thousands % 1 == 0:
            return f"{int(thousands)}K"
        return f"{thousands:.1f}K"
    return str(count)


async def list_models(
    model_registry: Any,
    search_pattern: str | None = None,
) -> None:
    """List available models, optionally filtered by a fuzzy search pattern.

    Args:
        model_registry: Object with a get_available() method returning a list of Model.
        search_pattern: Optional fuzzy search string.
    """
    models: list[Any] = model_registry.get_available()

    if not models:
        print("No models available. Set API keys in environment variables.")
        return

    # Apply fuzzy filter if search pattern provided
    filtered_models: list[Any] = models
    if search_pattern:
        filtered_models = fuzzy_filter(models, search_pattern, lambda m: f"{m.provider} {m.id}")

    if not filtered_models:
        print(f'No models matching "{search_pattern}"')
        return

    # Sort by provider, then by model id
    filtered_models = sorted(filtered_models, key=lambda m: (m.provider, m.id))

    # Build row data
    rows = [
        {
            "provider": m.provider,
            "model": m.id,
            "context": format_token_count(m.context_window),
            "max_out": format_token_count(m.max_tokens),
            "thinking": "yes" if m.reasoning else "no",
            "images": "yes" if "image" in m.input else "no",
        }
        for m in filtered_models
    ]

    headers = {
        "provider": "provider",
        "model": "model",
        "context": "context",
        "max_out": "max-out",
        "thinking": "thinking",
        "images": "images",
    }

    # Calculate column widths
    widths = {key: max(len(headers[key]), *(len(row[key]) for row in rows)) for key in headers}

    # Print header
    header_line = "  ".join(headers[k].ljust(widths[k]) for k in headers)
    print(header_line)

    # Print rows
    for row in rows:
        line = "  ".join(row[k].ljust(widths[k]) for k in headers)
        print(line)
