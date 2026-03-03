"""Model registry — built-in models + custom models.json support."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from pi_ai.models import MODELS, get_model
from pi_ai.types import Model, ModelCost

from pi_coding_agent.auth_storage import AuthStorage


class ModelRegistry:
    """Registry for built-in and custom models with API key awareness."""

    def __init__(
        self,
        auth_storage: AuthStorage,
        models_json_path: str | None = None,
    ):
        self._auth_storage = auth_storage
        self._custom_models: dict[str, dict[str, Model]] = {}

        if models_json_path and os.path.exists(models_json_path):
            self._load_custom_models(models_json_path)

    def get_all(self) -> list[Model]:
        """Get all models (built-in + custom)."""
        models: list[Model] = []

        # Built-in models
        for provider_models in MODELS.values():
            models.extend(provider_models.values())

        # Custom models
        for provider_models in self._custom_models.values():
            models.extend(provider_models.values())

        return models

    async def get_available(self) -> list[Model]:
        """Get only models that have an API key available."""
        all_models = self.get_all()
        available: list[Model] = []

        # Group by provider and check once per provider
        checked_providers: dict[str, bool] = {}
        for model in all_models:
            if model.provider not in checked_providers:
                key = await self._auth_storage.get_api_key(model.provider)
                checked_providers[model.provider] = key is not None

            if checked_providers.get(model.provider, False):
                available.append(model)

        return available

    def find(self, provider: str, model_id: str) -> Model | None:
        """Find a model by provider and model ID."""
        # Check built-in first
        provider_models = MODELS.get(provider, {})
        if model_id in provider_models:
            return provider_models[model_id]

        # Check custom
        custom_provider = self._custom_models.get(provider, {})
        if model_id in custom_provider:
            return custom_provider[model_id]

        return None

    async def get_api_key(self, model: Model) -> str | None:
        """Get the API key for a model's provider."""
        return await self._auth_storage.get_api_key(model.provider)

    def _load_custom_models(self, path: str) -> None:
        """Load custom models from a JSON file."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        if not isinstance(data, dict):
            return

        for provider_name, models_data in data.items():
            if not isinstance(models_data, dict):
                continue
            self._custom_models[provider_name] = {}
            for model_id, model_data in models_data.items():
                if not isinstance(model_data, dict):
                    continue
                cost_data = model_data.get("cost", {})
                model = Model(
                    id=model_id,
                    name=model_data.get("name", model_id),
                    api=model_data.get("api", ""),
                    provider=provider_name,
                    base_url=model_data.get("base_url", ""),
                    reasoning=model_data.get("reasoning", False),
                    input=model_data.get("input", ["text"]),
                    cost=ModelCost(
                        input=cost_data.get("input", 0.0),
                        output=cost_data.get("output", 0.0),
                        cache_read=cost_data.get("cache_read", 0.0),
                        cache_write=cost_data.get("cache_write", 0.0),
                    ),
                    context_window=model_data.get("context_window", 0),
                    max_tokens=model_data.get("max_tokens", 0),
                )
                self._custom_models[provider_name][model_id] = model
