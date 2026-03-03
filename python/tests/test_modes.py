"""Tests for execution modes — print mode, RPC mode, CLI argument parsing."""

import asyncio
import io
import json
import sys

import pytest

from pi_ai.api_registry import register_provider
from pi_ai.types import (
    AssistantMessage,
    DoneEvent,
    Model,
    ModelCost,
    StartEvent,
    StreamOptions,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    Usage,
    UserMessage,
)
from pi_agent.agent import Agent
from pi_agent.types import AgentTool, AgentToolResult

from pi_coding_agent.cli import build_parser, _resolve_mode, _resolve_messages
from pi_coding_agent.print_mode import run_print_mode
from pi_coding_agent.rpc_mode import COMMAND_HANDLERS
from pi_session.agent_session import AgentSession, AgentSessionConfig
from pi_session.session_manager import SessionManager


MOCK_MODEL = Model(
    id="mock-model",
    name="Mock",
    api="mock-api",
    provider="mock",
    base_url="",
    reasoning=False,
    input=["text"],
    cost=ModelCost(),
    context_window=128000,
    max_tokens=4096,
)


async def mock_text_stream(model, context, options=None):
    """Mock stream returning a text response."""
    output = AssistantMessage(
        api="mock-api", provider="mock", model="mock-model",
        content=[TextContent(text="Mock response text")],
        usage=Usage(input=100, output=50, total_tokens=150),
        stop_reason="stop",
    )
    yield StartEvent(partial=output)
    yield TextStartEvent(content_index=0, partial=output)
    yield TextDeltaEvent(content_index=0, delta="Mock response text", partial=output)
    yield TextEndEvent(content_index=0, content="Mock response text", partial=output)
    yield DoneEvent(reason="stop", message=output)


async def mock_error_stream(model, context, options=None):
    """Mock stream returning an error."""
    output = AssistantMessage(
        api="mock-api", provider="mock", model="mock-model",
        content=[],
        usage=Usage(),
        stop_reason="error",
        error_message="Something went wrong",
    )
    yield StartEvent(partial=output)
    yield DoneEvent(reason="error", message=output)


def _make_session() -> AgentSession:
    """Create an AgentSession with mock model."""
    agent = Agent(model=MOCK_MODEL, system_prompt="test")
    mgr = SessionManager.in_memory()
    return AgentSession(AgentSessionConfig(agent=agent, session_manager=mgr))


# --- Print mode tests ---


@pytest.mark.asyncio
async def test_print_mode_text(capsys):
    """Print mode outputs final text to stdout."""
    register_provider("mock-api", mock_text_stream)
    session = _make_session()

    exit_code = await run_print_mode(session, ["hello"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Mock response text" in captured.out


@pytest.mark.asyncio
async def test_print_mode_json(capsys):
    """Print mode in JSON outputs JSONL events."""
    register_provider("mock-api", mock_text_stream)
    session = _make_session()

    exit_code = await run_print_mode(session, ["hello"], output_mode="json")
    assert exit_code == 0

    captured = capsys.readouterr()
    lines = [l for l in captured.out.strip().split("\n") if l]
    assert len(lines) > 0

    # Each line should be valid JSON
    for line in lines:
        parsed = json.loads(line)
        assert "_event_type" in parsed


@pytest.mark.asyncio
async def test_print_mode_error(capsys):
    """Print mode returns exit code 1 on error."""
    register_provider("mock-api", mock_error_stream)
    session = _make_session()

    exit_code = await run_print_mode(session, ["hello"])
    assert exit_code == 1


@pytest.mark.asyncio
async def test_print_mode_multiple_messages(capsys):
    """Print mode handles multiple messages."""
    register_provider("mock-api", mock_text_stream)
    session = _make_session()

    exit_code = await run_print_mode(session, ["first", "second"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Mock response text" in captured.out


# --- RPC mode tests ---


@pytest.mark.asyncio
async def test_rpc_get_state():
    """RPC get_state returns agent state."""
    session = _make_session()

    result = await COMMAND_HANDLERS["get_state"](session, {})
    assert result["is_streaming"] is False
    assert result["model"] == "mock-model"
    assert result["provider"] == "mock"


@pytest.mark.asyncio
async def test_rpc_prompt():
    """RPC prompt sends a message."""
    register_provider("mock-api", mock_text_stream)
    session = _make_session()

    result = await COMMAND_HANDLERS["prompt"](session, {"text": "hello"})
    assert result.get("ok") is True


@pytest.mark.asyncio
async def test_rpc_prompt_missing_text():
    """RPC prompt errors on missing text."""
    session = _make_session()

    result = await COMMAND_HANDLERS["prompt"](session, {})
    assert "error" in result


@pytest.mark.asyncio
async def test_rpc_abort():
    """RPC abort works."""
    session = _make_session()

    result = await COMMAND_HANDLERS["abort"](session, {})
    assert result.get("ok") is True


@pytest.mark.asyncio
async def test_rpc_get_session_stats():
    """RPC get_session_stats returns stats."""
    session = _make_session()

    result = await COMMAND_HANDLERS["get_session_stats"](session, {})
    assert "total_messages" in result
    assert "total_tokens" in result


@pytest.mark.asyncio
async def test_rpc_get_available_models():
    """RPC get_available_models returns model list."""
    session = _make_session()

    result = await COMMAND_HANDLERS["get_available_models"](session, {})
    assert "models" in result
    assert len(result["models"]) > 0
    assert "id" in result["models"][0]


@pytest.mark.asyncio
async def test_rpc_set_model():
    """RPC set_model changes the model."""
    session = _make_session()

    result = await COMMAND_HANDLERS["set_model"](session, {
        "provider": "openai",
        "model_id": "gpt-4o",
    })
    assert result.get("ok") is True
    assert session.agent.model.id == "gpt-4o"


@pytest.mark.asyncio
async def test_rpc_set_model_invalid():
    """RPC set_model errors on invalid model."""
    session = _make_session()

    result = await COMMAND_HANDLERS["set_model"](session, {
        "provider": "nonexistent",
        "model_id": "nope",
    })
    assert "error" in result


@pytest.mark.asyncio
async def test_rpc_set_thinking_level():
    """RPC set_thinking_level works."""
    session = _make_session()

    result = await COMMAND_HANDLERS["set_thinking_level"](session, {"level": "high"})
    assert result.get("ok") is True


# --- CLI argument parsing tests ---


def test_cli_parse_args_basic():
    """Parse basic CLI arguments."""
    parser = build_parser()
    args = parser.parse_args(["hello world"])
    assert args.prompt == "hello world"


def test_cli_parse_args_message():
    """Parse -m flag."""
    parser = build_parser()
    args = parser.parse_args(["-m", "first", "-m", "second"])
    assert args.message == ["first", "second"]


def test_cli_parse_args_model():
    """Parse model arguments."""
    parser = build_parser()
    args = parser.parse_args(["--provider", "openai", "--model", "gpt-5", "test"])
    assert args.provider == "openai"
    assert args.model == "gpt-5"


def test_cli_parse_args_flags():
    """Parse boolean flags."""
    parser = build_parser()
    args = parser.parse_args(["--print", "--json", "--no-tools", "test"])
    assert args.print_mode is True
    assert args.json is True
    assert args.no_tools is True


def test_cli_parse_args_continue():
    """Parse --continue flag."""
    parser = build_parser()
    args = parser.parse_args(["-c", "test"])
    assert args.continue_session is True


def test_cli_mode_selection_print():
    """Mode auto-detection: --print -> print mode."""
    parser = build_parser()
    args = parser.parse_args(["--print", "test"])
    assert _resolve_mode(args) == "print"


def test_cli_mode_selection_json():
    """Mode auto-detection: --json -> print mode."""
    parser = build_parser()
    args = parser.parse_args(["--json", "test"])
    assert _resolve_mode(args) == "print"


def test_cli_mode_selection_rpc():
    """Mode auto-detection: --mode rpc -> rpc mode."""
    parser = build_parser()
    args = parser.parse_args(["--mode", "rpc"])
    assert _resolve_mode(args) == "rpc"


def test_cli_mode_selection_explicit():
    """Explicit --mode overrides auto-detection."""
    parser = build_parser()
    args = parser.parse_args(["--mode", "print", "test"])
    assert _resolve_mode(args) == "print"


def test_cli_resolve_messages():
    """Messages resolved from -m and positional args."""
    parser = build_parser()
    args = parser.parse_args(["-m", "first", "positional"])
    messages = _resolve_messages(args)
    assert "first" in messages
    assert "positional" in messages


def test_cli_parse_args_system_prompt():
    """Parse system prompt args."""
    parser = build_parser()
    args = parser.parse_args(["--system-prompt", "You are helpful", "--no-agents-md", "test"])
    assert args.system_prompt == "You are helpful"
    assert args.no_agents_md is True


def test_cli_parse_args_tools():
    """Parse --tools flag."""
    parser = build_parser()
    args = parser.parse_args(["--tools", "read", "write", "-m", "test"])
    assert args.tools == ["read", "write"]
