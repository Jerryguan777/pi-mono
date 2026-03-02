"""Model definitions for the 3 providers used in GAIA benchmark."""

from pi_ai.types import Cost, Model, ModelCost, Usage

# Only include models relevant to GAIA benchmark from 3 providers: openai, anthropic, google

MODELS: dict[str, dict[str, Model]] = {
    "openai": {
        "gpt-4o": Model(
            id="gpt-4o", name="GPT-4o", api="openai-responses", provider="openai",
            base_url="https://api.openai.com/v1", reasoning=False, input=["text", "image"],
            cost=ModelCost(input=2.5, output=10, cache_read=1.25, cache_write=0),
            context_window=128000, max_tokens=16384,
        ),
        "gpt-4o-mini": Model(
            id="gpt-4o-mini", name="GPT-4o mini", api="openai-responses", provider="openai",
            base_url="https://api.openai.com/v1", reasoning=False, input=["text", "image"],
            cost=ModelCost(input=0.15, output=0.6, cache_read=0.075, cache_write=0),
            context_window=128000, max_tokens=16384,
        ),
        "gpt-4.1": Model(
            id="gpt-4.1", name="GPT-4.1", api="openai-responses", provider="openai",
            base_url="https://api.openai.com/v1", reasoning=False, input=["text", "image"],
            cost=ModelCost(input=2, output=8, cache_read=0.5, cache_write=0),
            context_window=1047576, max_tokens=32768,
        ),
        "gpt-4.1-mini": Model(
            id="gpt-4.1-mini", name="GPT-4.1 mini", api="openai-responses", provider="openai",
            base_url="https://api.openai.com/v1", reasoning=False, input=["text", "image"],
            cost=ModelCost(input=0.4, output=1.6, cache_read=0.1, cache_write=0),
            context_window=1047576, max_tokens=32768,
        ),
        "gpt-4.1-nano": Model(
            id="gpt-4.1-nano", name="GPT-4.1 nano", api="openai-responses", provider="openai",
            base_url="https://api.openai.com/v1", reasoning=False, input=["text", "image"],
            cost=ModelCost(input=0.1, output=0.4, cache_read=0.03, cache_write=0),
            context_window=1047576, max_tokens=32768,
        ),
        "o3-mini": Model(
            id="o3-mini", name="o3-mini", api="openai-responses", provider="openai",
            base_url="https://api.openai.com/v1", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=1.1, output=4.4, cache_read=0.55, cache_write=0),
            context_window=200000, max_tokens=100000,
        ),
        "gpt-5": Model(
            id="gpt-5", name="GPT-5", api="openai-responses", provider="openai",
            base_url="https://api.openai.com/v1", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=1.25, output=10, cache_read=0.125, cache_write=0),
            context_window=400000, max_tokens=128000,
        ),
        "gpt-5-mini": Model(
            id="gpt-5-mini", name="GPT-5 Mini", api="openai-responses", provider="openai",
            base_url="https://api.openai.com/v1", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=0.25, output=2, cache_read=0.025, cache_write=0),
            context_window=400000, max_tokens=128000,
        ),
        "gpt-5.1": Model(
            id="gpt-5.1", name="GPT-5.1", api="openai-responses", provider="openai",
            base_url="https://api.openai.com/v1", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=1.25, output=10, cache_read=0.13, cache_write=0),
            context_window=400000, max_tokens=128000,
        ),
        "gpt-5.2": Model(
            id="gpt-5.2", name="GPT-5.2", api="openai-responses", provider="openai",
            base_url="https://api.openai.com/v1", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=1.75, output=14, cache_read=0.175, cache_write=0),
            context_window=400000, max_tokens=128000,
        ),
    },
    "anthropic": {
        "claude-3-5-haiku-20241022": Model(
            id="claude-3-5-haiku-20241022", name="Claude Haiku 3.5", api="anthropic-messages", provider="anthropic",
            base_url="https://api.anthropic.com", reasoning=False, input=["text", "image"],
            cost=ModelCost(input=0.8, output=4, cache_read=0.08, cache_write=1),
            context_window=200000, max_tokens=8192,
        ),
        "claude-3-5-sonnet-20241022": Model(
            id="claude-3-5-sonnet-20241022", name="Claude Sonnet 3.5 v2", api="anthropic-messages", provider="anthropic",
            base_url="https://api.anthropic.com", reasoning=False, input=["text", "image"],
            cost=ModelCost(input=3, output=15, cache_read=0.3, cache_write=3.75),
            context_window=200000, max_tokens=8192,
        ),
        "claude-3-7-sonnet-20250219": Model(
            id="claude-3-7-sonnet-20250219", name="Claude Sonnet 3.7", api="anthropic-messages", provider="anthropic",
            base_url="https://api.anthropic.com", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=3, output=15, cache_read=0.3, cache_write=3.75),
            context_window=200000, max_tokens=64000,
        ),
        "claude-haiku-4-5-20251001": Model(
            id="claude-haiku-4-5-20251001", name="Claude Haiku 4.5", api="anthropic-messages", provider="anthropic",
            base_url="https://api.anthropic.com", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=1, output=5, cache_read=0.1, cache_write=1.25),
            context_window=200000, max_tokens=64000,
        ),
        "claude-sonnet-4-5-20250514": Model(
            id="claude-sonnet-4-5-20250514", name="Claude Sonnet 4.5", api="anthropic-messages", provider="anthropic",
            base_url="https://api.anthropic.com", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=3, output=15, cache_read=0.3, cache_write=3.75),
            context_window=200000, max_tokens=64000,
        ),
        "claude-opus-4-0-20250514": Model(
            id="claude-opus-4-0-20250514", name="Claude Opus 4", api="anthropic-messages", provider="anthropic",
            base_url="https://api.anthropic.com", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=15, output=75, cache_read=1.5, cache_write=18.75),
            context_window=200000, max_tokens=32000,
        ),
        "claude-sonnet-4-6-20250610": Model(
            id="claude-sonnet-4-6-20250610", name="Claude Sonnet 4.6", api="anthropic-messages", provider="anthropic",
            base_url="https://api.anthropic.com", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=3, output=15, cache_read=0.3, cache_write=3.75),
            context_window=200000, max_tokens=64000,
        ),
        "claude-opus-4-6-20250723": Model(
            id="claude-opus-4-6-20250723", name="Claude Opus 4.6", api="anthropic-messages", provider="anthropic",
            base_url="https://api.anthropic.com", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=15, output=75, cache_read=1.5, cache_write=18.75),
            context_window=200000, max_tokens=32000,
        ),
    },
    "google": {
        "gemini-2.5-flash-preview-04-17": Model(
            id="gemini-2.5-flash-preview-04-17", name="Gemini 2.5 Flash", api="google-generative-ai", provider="google",
            base_url="", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=0.15, output=0.6, cache_read=0.0375, cache_write=0),
            context_window=1048576, max_tokens=65536,
        ),
        "gemini-2.5-pro-preview-05-06": Model(
            id="gemini-2.5-pro-preview-05-06", name="Gemini 2.5 Pro", api="google-generative-ai", provider="google",
            base_url="", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=1.25, output=10, cache_read=0.3125, cache_write=0),
            context_window=1048576, max_tokens=65536,
        ),
        "gemini-2.0-flash": Model(
            id="gemini-2.0-flash", name="Gemini 2.0 Flash", api="google-generative-ai", provider="google",
            base_url="", reasoning=False, input=["text", "image"],
            cost=ModelCost(input=0.1, output=0.4, cache_read=0.025, cache_write=0),
            context_window=1048576, max_tokens=8192,
        ),
        "gemini-3-flash": Model(
            id="gemini-3-flash", name="Gemini 3 Flash", api="google-generative-ai", provider="google",
            base_url="", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=0.15, output=0.6, cache_read=0.0375, cache_write=0),
            context_window=1048576, max_tokens=65536,
        ),
        "gemini-3-pro": Model(
            id="gemini-3-pro", name="Gemini 3 Pro", api="google-generative-ai", provider="google",
            base_url="", reasoning=True, input=["text", "image"],
            cost=ModelCost(input=1.25, output=10, cache_read=0.3125, cache_write=0),
            context_window=1048576, max_tokens=65536,
        ),
    },
}


def get_model(provider: str, model_id: str) -> Model:
    """Get a model by provider and model ID."""
    provider_models = MODELS.get(provider)
    if not provider_models:
        raise ValueError(f"Unknown provider: {provider}")
    model = provider_models.get(model_id)
    if not model:
        raise ValueError(f"Unknown model: {model_id} for provider {provider}")
    return model


def calculate_cost(model: Model, usage: Usage) -> Cost:
    """Calculate cost based on model pricing and token usage."""
    usage.cost.input = (model.cost.input / 1_000_000) * usage.input
    usage.cost.output = (model.cost.output / 1_000_000) * usage.output
    usage.cost.cache_read = (model.cost.cache_read / 1_000_000) * usage.cache_read
    usage.cost.cache_write = (model.cost.cache_write / 1_000_000) * usage.cache_write
    usage.cost.total = usage.cost.input + usage.cost.output + usage.cost.cache_read + usage.cost.cache_write
    return usage.cost
