"""Tests for pi_mom.context."""

from __future__ import annotations

import json
import os
from typing import Any

from pi_mom.context import (
    MomCompactionSettings,
    MomRetrySettings,
    MomSettingsManager,
    sync_log_to_context,
)


class TestMomSettingsManager:
    def test_defaults(self, tmp_path: Any) -> None:
        manager = MomSettingsManager(str(tmp_path))
        assert manager.get_compaction_enabled() is True
        assert manager.get_retry_enabled() is True
        assert manager.get_default_model() is None
        assert manager.get_default_provider() is None
        assert manager.get_default_thinking_level() == "off"

    def test_compaction_settings(self, tmp_path: Any) -> None:
        manager = MomSettingsManager(str(tmp_path))
        settings = manager.get_compaction_settings()
        assert isinstance(settings, MomCompactionSettings)
        assert settings.enabled is True
        assert settings.reserve_tokens > 0
        assert settings.keep_recent_tokens > 0

    def test_retry_settings(self, tmp_path: Any) -> None:
        manager = MomSettingsManager(str(tmp_path))
        settings = manager.get_retry_settings()
        assert isinstance(settings, MomRetrySettings)
        assert settings.enabled is True
        assert settings.max_retries > 0
        assert settings.base_delay_ms > 0

    def test_set_compaction_enabled(self, tmp_path: Any) -> None:
        manager = MomSettingsManager(str(tmp_path))
        manager.set_compaction_enabled(False)
        # Reload from disk
        manager2 = MomSettingsManager(str(tmp_path))
        assert manager2.get_compaction_enabled() is False

    def test_set_retry_enabled(self, tmp_path: Any) -> None:
        manager = MomSettingsManager(str(tmp_path))
        manager.set_retry_enabled(False)
        manager2 = MomSettingsManager(str(tmp_path))
        assert manager2.get_retry_enabled() is False

    def test_set_model_and_provider(self, tmp_path: Any) -> None:
        manager = MomSettingsManager(str(tmp_path))
        manager.set_default_model_and_provider("anthropic", "claude-3-opus")
        manager2 = MomSettingsManager(str(tmp_path))
        assert manager2.get_default_model() == "claude-3-opus"
        assert manager2.get_default_provider() == "anthropic"

    def test_set_thinking_level(self, tmp_path: Any) -> None:
        manager = MomSettingsManager(str(tmp_path))
        manager.set_default_thinking_level("high")
        manager2 = MomSettingsManager(str(tmp_path))
        assert manager2.get_default_thinking_level() == "high"

    def test_load_from_existing_file(self, tmp_path: Any) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"defaultModel": "gpt-4", "defaultProvider": "openai"}))
        manager = MomSettingsManager(str(tmp_path))
        assert manager.get_default_model() == "gpt-4"
        assert manager.get_default_provider() == "openai"

    def test_corrupted_file(self, tmp_path: Any) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("NOT VALID JSON!!!!")
        # Should not raise, should use defaults
        manager = MomSettingsManager(str(tmp_path))
        assert manager.get_default_model() is None


class TestSyncLogToContext:
    def _write_log(self, log_path: str, entries: list[dict[str, Any]]) -> None:
        with open(log_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    def test_no_log_file(self, tmp_path: Any) -> None:
        result = sync_log_to_context([], str(tmp_path))
        assert result == []

    def test_skips_bot_messages(self, tmp_path: Any) -> None:
        log_path = os.path.join(str(tmp_path), "log.jsonl")
        self._write_log(
            log_path,
            [
                {
                    "date": "2025-01-01T00:00:00Z",
                    "ts": "1000.0",
                    "user": "bot",
                    "text": "bot response",
                    "isBot": True,
                }
            ],
        )
        result = sync_log_to_context([], str(tmp_path))
        assert result == []

    def test_returns_user_messages(self, tmp_path: Any) -> None:
        log_path = os.path.join(str(tmp_path), "log.jsonl")
        self._write_log(
            log_path,
            [
                {
                    "date": "2025-01-01T10:00:00Z",
                    "ts": "1000.0",
                    "user": "U123",
                    "userName": "mario",
                    "text": "hello",
                    "isBot": False,
                }
            ],
        )
        result = sync_log_to_context([], str(tmp_path))
        assert len(result) == 1

    def test_skips_exclude_ts(self, tmp_path: Any) -> None:
        log_path = os.path.join(str(tmp_path), "log.jsonl")
        self._write_log(
            log_path,
            [
                {
                    "date": "2025-01-01T10:00:00Z",
                    "ts": "9999.0",
                    "user": "U123",
                    "userName": "mario",
                    "text": "current message",
                    "isBot": False,
                }
            ],
        )
        result = sync_log_to_context([], str(tmp_path), exclude_slack_ts="9999.0")
        assert result == []

    def test_skips_already_in_context(self, tmp_path: Any) -> None:
        from pi_ai.types import TextContent, UserMessage

        log_path = os.path.join(str(tmp_path), "log.jsonl")
        self._write_log(
            log_path,
            [
                {
                    "date": "2025-01-01T10:00:00Z",
                    "ts": "1000.0",
                    "user": "U123",
                    "userName": "mario",
                    "text": "hello",
                    "isBot": False,
                }
            ],
        )

        # Build existing message that matches log entry
        existing = UserMessage(
            content=[TextContent(text="[mario]: hello")],
            timestamp=1000.0,
        )
        result = sync_log_to_context([existing], str(tmp_path))
        assert result == []

    def test_returns_sorted_by_timestamp(self, tmp_path: Any) -> None:
        log_path = os.path.join(str(tmp_path), "log.jsonl")
        self._write_log(
            log_path,
            [
                {
                    "date": "2025-01-01T12:00:00Z",
                    "ts": "3000.0",
                    "user": "U1",
                    "userName": "c",
                    "text": "third",
                    "isBot": False,
                },
                {
                    "date": "2025-01-01T10:00:00Z",
                    "ts": "1000.0",
                    "user": "U1",
                    "userName": "a",
                    "text": "first",
                    "isBot": False,
                },
                {
                    "date": "2025-01-01T11:00:00Z",
                    "ts": "2000.0",
                    "user": "U1",
                    "userName": "b",
                    "text": "second",
                    "isBot": False,
                },
            ],
        )
        result = sync_log_to_context([], str(tmp_path))
        assert len(result) == 3
        # The first result should be from the earliest message (a)
        first_text = result[0].content[0].text  # type: ignore[union-attr]
        assert "first" in first_text
