"""Tests for SettingsManager."""

from __future__ import annotations

from pi_coding_agent.core.settings_manager import (
    CompactionSettings,
    InMemorySettingsStorage,
    RetrySettings,
    Settings,
    SettingsManager,
    _deep_merge_settings,
    _parse_settings_from_dict,
    _settings_to_dict,
)


class TestInMemorySettingsStorage:
    def test_initial_state_is_none(self) -> None:
        storage = InMemorySettingsStorage()
        received: list[str | None] = []

        def _capture(c: str | None) -> None:
            received.append(c)

        storage.with_lock("global", _capture)
        assert received == [None]

    def test_write_and_read_global(self) -> None:
        storage = InMemorySettingsStorage()
        storage.with_lock("global", lambda _: '{"defaultModel": "claude"}')
        received: list[str | None] = []

        def _capture(c: str | None) -> None:
            received.append(c)

        storage.with_lock("global", _capture)
        assert received[0] == '{"defaultModel": "claude"}'

    def test_write_and_read_project(self) -> None:
        storage = InMemorySettingsStorage()
        storage.with_lock("project", lambda _: '{"theme": "dark"}')
        received: list[str | None] = []

        def _capture(c: str | None) -> None:
            received.append(c)

        storage.with_lock("project", _capture)
        assert received[0] == '{"theme": "dark"}'

    def test_global_and_project_are_independent(self) -> None:
        storage = InMemorySettingsStorage()
        storage.with_lock("global", lambda _: '{"defaultModel": "claude"}')
        storage.with_lock("project", lambda _: '{"theme": "dark"}')

        global_received: list[str | None] = []
        project_received: list[str | None] = []

        def _capture_global(c: str | None) -> None:
            global_received.append(c)

        def _capture_project(c: str | None) -> None:
            project_received.append(c)

        storage.with_lock("global", _capture_global)
        storage.with_lock("project", _capture_project)

        assert global_received[0] == '{"defaultModel": "claude"}'
        assert project_received[0] == '{"theme": "dark"}'


class TestSettingsManagerInMemory:
    def test_empty_settings(self) -> None:
        sm = SettingsManager.in_memory()
        assert sm.get_default_provider() is None
        assert sm.get_default_model() is None
        assert sm.get_compaction_enabled() is True
        assert sm.get_transport() == "sse"

    def test_load_from_dict(self) -> None:
        sm = SettingsManager.in_memory({"defaultProvider": "anthropic", "defaultModel": "claude-opus-4-6"})
        assert sm.get_default_provider() == "anthropic"
        assert sm.get_default_model() == "claude-opus-4-6"

    def test_set_default_model_and_provider(self) -> None:
        sm = SettingsManager.in_memory()
        sm.set_default_model_and_provider("anthropic", "claude-sonnet")
        assert sm.get_default_provider() == "anthropic"
        assert sm.get_default_model() == "claude-sonnet"

    def test_compaction_settings_defaults(self) -> None:
        sm = SettingsManager.in_memory()
        settings = sm.get_compaction_settings()
        assert settings["enabled"] is True
        assert settings["reserve_tokens"] == 16384
        assert settings["keep_recent_tokens"] == 20000

    def test_set_compaction_enabled(self) -> None:
        sm = SettingsManager.in_memory()
        sm.set_compaction_enabled(False)
        assert sm.get_compaction_enabled() is False

    def test_retry_settings_defaults(self) -> None:
        sm = SettingsManager.in_memory()
        settings = sm.get_retry_settings()
        assert settings["enabled"] is True
        assert settings["max_retries"] == 3
        assert settings["base_delay_ms"] == 2000
        assert settings["max_delay_ms"] == 60000

    def test_thinking_level(self) -> None:
        sm = SettingsManager.in_memory()
        assert sm.get_default_thinking_level() is None
        sm.set_default_thinking_level("medium")
        assert sm.get_default_thinking_level() == "medium"

    def test_show_images_default(self) -> None:
        sm = SettingsManager.in_memory()
        assert sm.get_show_images() is True

    def test_enable_skill_commands_default(self) -> None:
        sm = SettingsManager.in_memory()
        assert sm.get_enable_skill_commands() is True

    def test_skill_paths_empty(self) -> None:
        sm = SettingsManager.in_memory()
        assert sm.get_skill_paths() == []

    def test_set_skill_paths(self) -> None:
        sm = SettingsManager.in_memory()
        sm.set_skill_paths(["/path/to/skills"])
        assert sm.get_skill_paths() == ["/path/to/skills"]

    def test_editor_padding_x_clamped(self) -> None:
        sm = SettingsManager.in_memory()
        sm.set_editor_padding_x(10)  # Should be clamped to 3
        assert sm.get_editor_padding_x() == 3

    def test_autocomplete_max_visible_clamped(self) -> None:
        sm = SettingsManager.in_memory()
        sm.set_autocomplete_max_visible(100)  # Should be clamped to 20
        assert sm.get_autocomplete_max_visible() == 20


class TestDeepMergeSettings:
    def test_simple_merge(self) -> None:
        base = Settings(default_provider="anthropic")
        overrides = Settings(default_model="claude")
        merged = _deep_merge_settings(base, overrides)
        assert merged.default_provider == "anthropic"
        assert merged.default_model == "claude"

    def test_overrides_take_precedence(self) -> None:
        base = Settings(default_provider="anthropic")
        overrides = Settings(default_provider="openai")
        merged = _deep_merge_settings(base, overrides)
        assert merged.default_provider == "openai"

    def test_nested_merge(self) -> None:
        base = Settings(compaction=CompactionSettings(enabled=True, reserve_tokens=8192))
        overrides = Settings(compaction=CompactionSettings(keep_recent_tokens=10000))
        merged = _deep_merge_settings(base, overrides)
        assert merged.compaction is not None
        assert merged.compaction.enabled is True
        assert merged.compaction.reserve_tokens == 8192
        assert merged.compaction.keep_recent_tokens == 10000

    def test_none_override_keeps_base(self) -> None:
        base = Settings(default_provider="anthropic")
        overrides = Settings()  # all None
        merged = _deep_merge_settings(base, overrides)
        assert merged.default_provider == "anthropic"


class TestParseSettingsFromDict:
    def test_basic_fields(self) -> None:
        raw = {
            "defaultProvider": "anthropic",
            "defaultModel": "claude-opus",
            "transport": "sse",
        }
        s = _parse_settings_from_dict(raw)
        assert s.default_provider == "anthropic"
        assert s.default_model == "claude-opus"
        assert s.transport == "sse"

    def test_nested_compaction(self) -> None:
        raw = {"compaction": {"enabled": False, "reserveTokens": 8192}}
        s = _parse_settings_from_dict(raw)
        assert s.compaction is not None
        assert s.compaction.enabled is False
        assert s.compaction.reserve_tokens == 8192

    def test_nested_terminal(self) -> None:
        raw = {"terminal": {"showImages": False}}
        s = _parse_settings_from_dict(raw)
        assert s.terminal is not None
        assert s.terminal.show_images is False


class TestSettingsToDict:
    def test_basic_serialization(self) -> None:
        s = Settings(default_provider="anthropic", default_model="claude")
        d = _settings_to_dict(s)
        assert d["defaultProvider"] == "anthropic"
        assert d["defaultModel"] == "claude"

    def test_none_fields_excluded(self) -> None:
        s = Settings(default_provider="anthropic")
        d = _settings_to_dict(s)
        assert "defaultModel" not in d

    def test_nested_compaction_serialized(self) -> None:
        s = Settings(compaction=CompactionSettings(enabled=False, reserve_tokens=8000))
        d = _settings_to_dict(s)
        assert "compaction" in d
        assert d["compaction"]["enabled"] is False
        assert d["compaction"]["reserveTokens"] == 8000

    def test_roundtrip(self) -> None:
        s = Settings(
            default_provider="openai",
            transport="websocket",
            compaction=CompactionSettings(enabled=True, reserve_tokens=16384),
            retry=RetrySettings(enabled=True, max_retries=5),
        )
        d = _settings_to_dict(s)
        s2 = _parse_settings_from_dict(d)
        assert s2.default_provider == "openai"
        assert s2.transport == "websocket"
        assert s2.compaction is not None
        assert s2.compaction.reserve_tokens == 16384
        assert s2.retry is not None
        assert s2.retry.max_retries == 5
