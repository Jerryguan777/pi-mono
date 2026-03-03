"""Settings manager — global + project settings merge."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pi_session.compaction import CompactionSettings
from pi_session.agent_session import RetrySettings


SteeringMode = Literal["all", "one-at-a-time"]


@dataclass
class Settings:
    default_provider: str | None = None
    default_model: str | None = None
    default_thinking_level: str | None = None
    steering_mode: SteeringMode = "one-at-a-time"
    follow_up_mode: SteeringMode = "one-at-a-time"
    compaction: CompactionSettings = field(default_factory=CompactionSettings)
    retry: RetrySettings = field(default_factory=RetrySettings)


class SettingsManager:
    """Settings with global + project-level merge."""

    def __init__(self, settings: Settings, global_path: str | None = None, project_path: str | None = None):
        self._settings = settings
        self._global_path = global_path
        self._project_path = project_path

    @staticmethod
    def create(cwd: str | None = None) -> SettingsManager:
        """Create a SettingsManager loading from global + project files."""
        global_path = os.path.join(Path.home(), ".pi", "agent", "settings.json")
        project_path = os.path.join(cwd or os.getcwd(), ".pi", "settings.json")

        settings = Settings()

        # Load global settings first
        _merge_from_file(settings, global_path)

        # Override with project settings
        _merge_from_file(settings, project_path)

        return SettingsManager(settings, global_path=global_path, project_path=project_path)

    @staticmethod
    def in_memory(settings: Settings | None = None) -> SettingsManager:
        """Create an in-memory SettingsManager."""
        return SettingsManager(settings or Settings())

    @property
    def settings(self) -> Settings:
        return self._settings

    def get_compaction_settings(self) -> CompactionSettings:
        return self._settings.compaction

    def get_retry_settings(self) -> RetrySettings:
        return self._settings.retry

    def get_default_provider(self) -> str | None:
        return self._settings.default_provider

    def get_default_model(self) -> str | None:
        return self._settings.default_model

    def get_default_thinking_level(self) -> str | None:
        return self._settings.default_thinking_level

    def get_steering_mode(self) -> SteeringMode:
        return self._settings.steering_mode

    def get_follow_up_mode(self) -> SteeringMode:
        return self._settings.follow_up_mode

    def set_default_provider(self, provider: str | None) -> None:
        self._settings.default_provider = provider

    def set_default_model(self, model: str | None) -> None:
        self._settings.default_model = model

    def set_default_thinking_level(self, level: str | None) -> None:
        self._settings.default_thinking_level = level

    def save_global(self) -> None:
        """Save current settings to global file."""
        if self._global_path:
            _save_to_file(self._settings, self._global_path)

    def save_project(self) -> None:
        """Save current settings to project file."""
        if self._project_path:
            _save_to_file(self._settings, self._project_path)


def _merge_from_file(settings: Settings, path: str) -> None:
    """Merge settings from a JSON file into the given Settings object."""
    if not os.path.exists(path):
        return

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    if not isinstance(data, dict):
        return

    if "default_provider" in data:
        settings.default_provider = data["default_provider"]
    if "default_model" in data:
        settings.default_model = data["default_model"]
    if "default_thinking_level" in data:
        settings.default_thinking_level = data["default_thinking_level"]
    if "steering_mode" in data:
        settings.steering_mode = data["steering_mode"]
    if "follow_up_mode" in data:
        settings.follow_up_mode = data["follow_up_mode"]

    if "compaction" in data and isinstance(data["compaction"], dict):
        c = data["compaction"]
        if "enabled" in c:
            settings.compaction.enabled = c["enabled"]
        if "reserve_tokens" in c:
            settings.compaction.reserve_tokens = c["reserve_tokens"]
        if "keep_recent_tokens" in c:
            settings.compaction.keep_recent_tokens = c["keep_recent_tokens"]

    if "retry" in data and isinstance(data["retry"], dict):
        r = data["retry"]
        if "enabled" in r:
            settings.retry.enabled = r["enabled"]
        if "max_retries" in r:
            settings.retry.max_retries = r["max_retries"]
        if "base_delay" in r:
            settings.retry.base_delay = r["base_delay"]
        if "max_delay" in r:
            settings.retry.max_delay = r["max_delay"]


def _save_to_file(settings: Settings, path: str) -> None:
    """Save settings to a JSON file."""
    data = {
        "default_provider": settings.default_provider,
        "default_model": settings.default_model,
        "default_thinking_level": settings.default_thinking_level,
        "steering_mode": settings.steering_mode,
        "follow_up_mode": settings.follow_up_mode,
        "compaction": {
            "enabled": settings.compaction.enabled,
            "reserve_tokens": settings.compaction.reserve_tokens,
            "keep_recent_tokens": settings.compaction.keep_recent_tokens,
        },
        "retry": {
            "enabled": settings.retry.enabled,
            "max_retries": settings.retry.max_retries,
            "base_delay": settings.retry.base_delay,
            "max_delay": settings.retry.max_delay,
        },
    }

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
