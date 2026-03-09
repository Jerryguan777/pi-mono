"""Tests for the extension system."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pi_coding_agent.core.extensions.loader import (
    create_extension,
    create_extension_runtime,
    load_extension_from_factory,
)
from pi_coding_agent.core.extensions.runner import (
    ExtensionRunner,
    emit_session_shutdown_event,
)
from pi_coding_agent.core.extensions.types import (
    Extension,
    ExtensionAPI,
    ExtensionRuntime,
    RegisteredTool,
    ToolDefinition,
)

# ============================================================================
# Helpers
# ============================================================================


def _make_runner(extensions: list[Extension] | None = None) -> ExtensionRunner:
    """Create an ExtensionRunner with given extensions."""
    runtime = create_extension_runtime()
    return ExtensionRunner(
        extensions=extensions or [],
        runtime=runtime,
        cwd="/tmp",
    )


def _make_extension(
    path: str = "<test>",
    handlers: dict[str, Any] | None = None,
    tools: dict[str, Any] | None = None,
) -> Extension:
    return Extension(
        path=path,
        resolved_path=path,
        handlers=handlers or {},
        tools=tools or {},
        message_renderers={},
        commands={},
        flags={},
        shortcuts={},
    )


# ============================================================================
# Tests for create_extension_runtime
# ============================================================================


class TestCreateExtensionRuntime:
    def test_returns_extension_runtime(self) -> None:
        runtime = create_extension_runtime()
        assert isinstance(runtime, ExtensionRuntime)

    def test_stub_methods_raise(self) -> None:
        runtime = create_extension_runtime()
        with pytest.raises(RuntimeError):
            runtime.send_message("hello")


# ============================================================================
# Tests for create_extension
# ============================================================================


class TestCreateExtension:
    def test_creates_extension_with_empty_collections(self) -> None:
        ext = create_extension("<test>", "/abs/path")
        assert ext.path == "<test>"
        assert ext.resolved_path == "/abs/path"
        assert ext.handlers == {}
        assert ext.tools == {}
        assert ext.commands == {}
        assert ext.flags == {}
        assert ext.shortcuts == {}


# ============================================================================
# Tests for load_extension_from_factory
# ============================================================================


class TestLoadExtensionFromFactory:
    def test_factory_registers_tool(self) -> None:
        async def factory(api: ExtensionAPI) -> None:
            api.register_tool(
                ToolDefinition(
                    name="my-tool",
                    label="My Tool",
                    description="A test tool",
                    parameters={},
                    execute=lambda ctx, args: {"result": "ok"},
                ),
            )

        runtime = create_extension_runtime()
        ext = asyncio.get_event_loop().run_until_complete(load_extension_from_factory(factory, "/tmp", runtime))
        assert "my-tool" in ext.tools

    def test_factory_registers_handler(self) -> None:
        called: list[str] = []

        async def factory(api: ExtensionAPI) -> None:
            def on_session_start(event: Any, ctx: Any) -> None:
                called.append("session_start")

            api.on("session_start", on_session_start)

        runtime = create_extension_runtime()
        ext = asyncio.get_event_loop().run_until_complete(load_extension_from_factory(factory, "/tmp", runtime))
        assert "session_start" in ext.handlers

    def test_empty_factory(self) -> None:
        async def factory(api: ExtensionAPI) -> None:
            pass

        runtime = create_extension_runtime()
        ext = asyncio.get_event_loop().run_until_complete(load_extension_from_factory(factory, "/tmp", runtime))
        assert ext.tools == {}
        assert ext.handlers == {}


# ============================================================================
# Tests for ExtensionRunner
# ============================================================================


class TestExtensionRunnerHasHandlers:
    def test_no_extensions_returns_false(self) -> None:
        runner = _make_runner([])
        assert runner.has_handlers("session_start") is False

    def test_extension_with_handler_returns_true(self) -> None:
        ext = _make_extension(handlers={"session_start": [lambda e, ctx: None]})
        runner = _make_runner([ext])
        assert runner.has_handlers("session_start") is True

    def test_extension_with_different_handler_returns_false(self) -> None:
        ext = _make_extension(handlers={"agent_start": [lambda e, ctx: None]})
        runner = _make_runner([ext])
        assert runner.has_handlers("session_start") is False

    def test_empty_handlers_list_returns_false(self) -> None:
        ext = _make_extension(handlers={"session_start": []})
        runner = _make_runner([ext])
        assert runner.has_handlers("session_start") is False


class TestExtensionRunnerEmit:
    def test_emits_to_registered_handler(self) -> None:
        received: list[Any] = []

        async def factory(api: ExtensionAPI) -> None:
            def on_session_start(event: Any, ctx: Any) -> None:
                received.append(event)

            api.on("session_start", on_session_start)

        runtime = create_extension_runtime()
        ext = asyncio.get_event_loop().run_until_complete(load_extension_from_factory(factory, "/tmp", runtime))
        runner = ExtensionRunner(extensions=[ext], runtime=runtime, cwd="/tmp")

        asyncio.get_event_loop().run_until_complete(runner.emit({"type": "session_start"}))
        assert len(received) == 1
        assert received[0]["type"] == "session_start"

    def test_emit_with_no_handlers_does_not_raise(self) -> None:
        runner = _make_runner([])
        asyncio.get_event_loop().run_until_complete(runner.emit({"type": "session_start"}))


class TestExtensionRunnerGetAllRegisteredTools:
    def test_no_extensions_returns_empty(self) -> None:
        runner = _make_runner([])
        assert runner.get_all_registered_tools() == []

    def test_returns_tools_from_all_extensions(self) -> None:
        tool_a = RegisteredTool(
            definition=ToolDefinition(
                name="tool-a",
                label="Tool A",
                description="Tool A",
                parameters={},
                execute=lambda ctx, args: None,
            ),
            extension_path="<test>",
        )
        tool_b = RegisteredTool(
            definition=ToolDefinition(
                name="tool-b",
                label="Tool B",
                description="Tool B",
                parameters={},
                execute=lambda ctx, args: None,
            ),
            extension_path="<test>",
        )
        ext1 = _make_extension(tools={"tool-a": tool_a})
        ext2 = _make_extension(tools={"tool-b": tool_b})
        runner = _make_runner([ext1, ext2])
        tools = runner.get_all_registered_tools()
        assert len(tools) == 2
        tool_names = {t.definition.name for t in tools}
        assert "tool-a" in tool_names
        assert "tool-b" in tool_names


# ============================================================================
# Tests for emit_session_shutdown_event
# ============================================================================


class TestEmitSessionShutdownEvent:
    def test_none_runner_returns_false(self) -> None:
        result = asyncio.get_event_loop().run_until_complete(emit_session_shutdown_event(None))
        assert result is False

    def test_runner_without_handler_returns_false(self) -> None:
        runner = _make_runner([])
        result = asyncio.get_event_loop().run_until_complete(emit_session_shutdown_event(runner))
        assert result is False

    def test_runner_with_handler_returns_true(self) -> None:
        ext = _make_extension(handlers={"session_shutdown": [lambda e, ctx: None]})
        runner = _make_runner([ext])
        result = asyncio.get_event_loop().run_until_complete(emit_session_shutdown_event(runner))
        assert result is True
