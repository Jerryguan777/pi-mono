"""Tests for pi_coding_agent.cli.list_models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from pi_coding_agent.cli.list_models import format_token_count, list_models

# ---------------------------------------------------------------------------
# format_token_count
# ---------------------------------------------------------------------------


def test_format_below_1k() -> None:
    assert format_token_count(500) == "500"
    assert format_token_count(0) == "0"
    assert format_token_count(999) == "999"


def test_format_thousands_exact() -> None:
    assert format_token_count(1_000) == "1K"
    assert format_token_count(200_000) == "200K"
    assert format_token_count(128_000) == "128K"


def test_format_thousands_fractional() -> None:
    assert format_token_count(1_500) == "1.5K"
    assert format_token_count(32_500) == "32.5K"


def test_format_millions_exact() -> None:
    assert format_token_count(1_000_000) == "1M"
    assert format_token_count(2_000_000) == "2M"


def test_format_millions_fractional() -> None:
    assert format_token_count(1_500_000) == "1.5M"


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


@dataclass
class FakeModel:
    provider: str
    id: str
    context_window: int
    max_tokens: int
    reasoning: bool
    input: list[str]


def make_registry(models: list[Any]) -> MagicMock:
    registry = MagicMock()
    registry.get_available.return_value = models
    return registry


@pytest.mark.asyncio
async def test_list_models_empty(capsys: pytest.CaptureFixture[str]) -> None:
    registry = make_registry([])
    await list_models(registry)
    captured = capsys.readouterr()
    assert "No models available" in captured.out


@pytest.mark.asyncio
async def test_list_models_basic(capsys: pytest.CaptureFixture[str]) -> None:
    models = [
        FakeModel("openai", "gpt-4o", 128_000, 16_000, False, ["text"]),
        FakeModel("anthropic", "claude-3-sonnet", 200_000, 8_192, True, ["text", "image"]),
    ]
    registry = make_registry(models)
    await list_models(registry)
    captured = capsys.readouterr()
    assert "gpt-4o" in captured.out
    assert "claude-3-sonnet" in captured.out
    assert "openai" in captured.out
    assert "anthropic" in captured.out
    # Header should appear
    assert "provider" in captured.out
    assert "model" in captured.out


@pytest.mark.asyncio
async def test_list_models_sorted(capsys: pytest.CaptureFixture[str]) -> None:
    models = [
        FakeModel("openai", "gpt-4o", 128_000, 16_000, False, ["text"]),
        FakeModel("anthropic", "claude-3", 200_000, 8_192, False, ["text"]),
    ]
    registry = make_registry(models)
    await list_models(registry)
    captured = capsys.readouterr()
    # anthropic should appear before openai (alphabetical sort)
    anthropic_pos = captured.out.index("anthropic")
    openai_pos = captured.out.index("openai")
    assert anthropic_pos < openai_pos


@pytest.mark.asyncio
async def test_list_models_no_match(capsys: pytest.CaptureFixture[str]) -> None:
    models = [FakeModel("openai", "gpt-4o", 128_000, 16_000, False, ["text"])]
    registry = make_registry(models)
    await list_models(registry, search_pattern="zzz-no-match-zzz")
    captured = capsys.readouterr()
    assert "No models matching" in captured.out


@pytest.mark.asyncio
async def test_list_models_with_search(capsys: pytest.CaptureFixture[str]) -> None:
    models = [
        FakeModel("openai", "gpt-4o", 128_000, 16_000, False, ["text"]),
        FakeModel("anthropic", "claude-3", 200_000, 8_192, True, ["text"]),
    ]
    registry = make_registry(models)
    # "claude" should only match claude-3
    await list_models(registry, search_pattern="claude")
    captured = capsys.readouterr()
    assert "claude-3" in captured.out


@pytest.mark.asyncio
async def test_list_models_reasoning_flag(capsys: pytest.CaptureFixture[str]) -> None:
    models = [
        FakeModel("anthropic", "claude-3-sonnet", 200_000, 8_192, True, ["text"]),
        FakeModel("openai", "gpt-4o", 128_000, 16_000, False, ["text"]),
    ]
    registry = make_registry(models)
    await list_models(registry)
    captured = capsys.readouterr()
    assert "yes" in captured.out  # reasoning = yes
    assert "no" in captured.out  # reasoning = no


@pytest.mark.asyncio
async def test_list_models_images_flag(capsys: pytest.CaptureFixture[str]) -> None:
    models = [
        FakeModel("openai", "gpt-4o", 128_000, 16_000, False, ["text", "image"]),
    ]
    registry = make_registry(models)
    await list_models(registry)
    captured = capsys.readouterr()
    # images = yes because "image" in input
    lines = [line for line in captured.out.splitlines() if "gpt-4o" in line]
    assert lines
    assert "yes" in lines[0]
