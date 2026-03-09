"""Tests for model resolution utilities."""

from __future__ import annotations

from pi_coding_agent.core.model_resolver import (
    DEFAULT_MODEL_PER_PROVIDER,
    parse_model_pattern,
)


def _make_model(provider: str, model_id: str, name: str | None = None) -> object:
    """Create a minimal Model-like object for testing."""

    class FakeModel:
        def __init__(self, p: str, mid: str, n: str | None) -> None:
            self.provider = p
            self.id = mid
            self.name = n

    return FakeModel(provider, model_id, name)


class TestParseModelPattern:
    def test_exact_match(self) -> None:
        models = [_make_model("anthropic", "claude-opus-4-6")]
        result = parse_model_pattern("claude-opus-4-6", models)  # type: ignore[arg-type]
        assert result.model is not None
        assert result.model.id == "claude-opus-4-6"
        assert result.thinking_level is None
        assert result.warning is None

    def test_no_match(self) -> None:
        models = [_make_model("anthropic", "claude-opus-4-6")]
        result = parse_model_pattern("nonexistent-model", models)  # type: ignore[arg-type]
        assert result.model is None
        assert result.thinking_level is None

    def test_thinking_level_suffix(self) -> None:
        models = [_make_model("anthropic", "claude-opus-4-6")]
        result = parse_model_pattern("claude-opus-4-6:medium", models)  # type: ignore[arg-type]
        assert result.model is not None
        assert result.model.id == "claude-opus-4-6"
        assert result.thinking_level == "medium"

    def test_invalid_thinking_level_with_fallback(self) -> None:
        models = [_make_model("anthropic", "claude-opus-4-6")]
        result = parse_model_pattern("claude-opus-4-6:invalid", models)  # type: ignore[arg-type]
        assert result.model is not None
        assert result.thinking_level is None
        assert result.warning is not None
        assert "invalid" in result.warning.lower()

    def test_invalid_thinking_level_without_fallback(self) -> None:
        models = [_make_model("anthropic", "claude-opus-4-6")]
        result = parse_model_pattern(
            "claude-opus-4-6:invalid",
            models,  # type: ignore[arg-type]
            options={"allowInvalidThinkingLevelFallback": False},
        )
        assert result.model is None

    def test_provider_slash_model_format(self) -> None:
        models = [_make_model("anthropic", "claude-opus-4-6")]
        result = parse_model_pattern("anthropic/claude-opus-4-6", models)  # type: ignore[arg-type]
        assert result.model is not None
        assert result.model.provider == "anthropic"
        assert result.model.id == "claude-opus-4-6"

    def test_partial_match(self) -> None:
        models = [_make_model("anthropic", "claude-opus-4-6")]
        result = parse_model_pattern("opus", models)  # type: ignore[arg-type]
        assert result.model is not None
        assert result.model.id == "claude-opus-4-6"

    def test_prefers_alias_over_dated(self) -> None:
        # Aliases (no date suffix) should be preferred over dated versions
        models = [
            _make_model("anthropic", "claude-3-opus-20240229"),  # dated
            _make_model("anthropic", "claude-3-opus-latest"),  # alias
        ]
        result = parse_model_pattern("claude-3-opus", models)  # type: ignore[arg-type]
        assert result.model is not None
        assert result.model.id == "claude-3-opus-latest"

    def test_case_insensitive_match(self) -> None:
        models = [_make_model("anthropic", "Claude-Opus")]
        result = parse_model_pattern("claude-opus", models)  # type: ignore[arg-type]
        assert result.model is not None

    def test_empty_pattern_matches_first(self) -> None:
        # Empty string partial-matches all models; the first result is returned
        models = [_make_model("anthropic", "claude-opus")]
        result = parse_model_pattern("", models)  # type: ignore[arg-type]
        # Empty pattern matches via partial match (empty string is in any string)
        assert result.model is not None

    def test_all_valid_thinking_levels(self) -> None:
        models = [_make_model("anthropic", "claude-opus-4-6")]
        for level in ("off", "minimal", "low", "medium", "high", "xhigh"):
            result = parse_model_pattern(f"claude-opus-4-6:{level}", models)  # type: ignore[arg-type]
            assert result.model is not None
            assert result.thinking_level == level, f"Expected {level}, got {result.thinking_level}"


class TestDefaultModelPerProvider:
    def test_known_providers_present(self) -> None:
        assert "anthropic" in DEFAULT_MODEL_PER_PROVIDER
        assert "openai" in DEFAULT_MODEL_PER_PROVIDER
        assert "google" in DEFAULT_MODEL_PER_PROVIDER

    def test_values_are_strings(self) -> None:
        for provider, model_id in DEFAULT_MODEL_PER_PROVIDER.items():
            assert isinstance(provider, str)
            assert isinstance(model_id, str)
            assert len(model_id) > 0
