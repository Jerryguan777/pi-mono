"""API key storage — file-based auth.json + environment variable fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path

# Mapping from provider name to environment variable
PROVIDER_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "xai": "XAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


class AuthStorage:
    """API key storage with file persistence and env var fallback."""

    def __init__(self, auth_path: str | None = None, data: dict[str, str] | None = None):
        self._auth_path = auth_path
        self._data: dict[str, str] = data or {}
        self._runtime_overrides: dict[str, str] = {}

        if auth_path and os.path.exists(auth_path):
            self._load()

    @staticmethod
    def create(auth_path: str | None = None) -> AuthStorage:
        """Create an AuthStorage with file persistence."""
        if auth_path is None:
            auth_path = os.path.join(Path.home(), ".pi", "agent", "auth.json")
        return AuthStorage(auth_path=auth_path)

    @staticmethod
    def in_memory(data: dict[str, str] | None = None) -> AuthStorage:
        """Create an in-memory AuthStorage (no file persistence)."""
        return AuthStorage(data=data or {})

    async def get_api_key(self, provider: str) -> str | None:
        """Get API key for a provider.

        Resolution order: runtime override -> auth.json -> environment variable.
        """
        # 1. Runtime override
        if provider in self._runtime_overrides:
            return self._runtime_overrides[provider]

        # 2. File-based storage
        if provider in self._data:
            return self._data[provider]

        # 3. Environment variable
        env_var = PROVIDER_ENV_VARS.get(provider)
        if env_var:
            value = os.environ.get(env_var)
            if value:
                return value

        return None

    def set_api_key(self, provider: str, key: str) -> None:
        """Set an API key for a provider (persists to file)."""
        self._data[provider] = key
        self._save()

    def set_runtime_override(self, provider: str, key: str) -> None:
        """Set a runtime-only API key override (not persisted)."""
        self._runtime_overrides[provider] = key

    def _load(self) -> None:
        """Load auth data from file."""
        if not self._auth_path or not os.path.exists(self._auth_path):
            return
        try:
            with open(self._auth_path, encoding="utf-8") as f:
                self._data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._data = {}

    def _save(self) -> None:
        """Save auth data to file."""
        if not self._auth_path:
            return
        os.makedirs(os.path.dirname(self._auth_path), exist_ok=True)
        with open(self._auth_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
