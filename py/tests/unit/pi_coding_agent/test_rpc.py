"""Unit tests for pi_coding_agent RPC types and client."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pi_coding_agent.modes.rpc.rpc_types import (
    RpcAbortCommand,
    RpcBashCommand,
    RpcCompactCommand,
    RpcExportHtmlCommand,
    RpcForkCommand,
    RpcGetAvailableModelsCommand,
    RpcGetCommandsCommand,
    RpcGetForkMessagesCommand,
    RpcGetLastAssistantTextCommand,
    RpcGetMessagesCommand,
    RpcGetSessionStatsCommand,
    RpcGetStateCommand,
    RpcNewSessionCommand,
    RpcPromptCommand,
    RpcResponse,
    RpcSessionState,
    RpcSetAutoCompactionCommand,
    RpcSetFollowUpModeCommand,
    RpcSetModelCommand,
    RpcSetSessionNameCommand,
    RpcSetSteeringModeCommand,
    RpcSetThinkingLevelCommand,
    RpcSlashCommand,
    RpcSteerCommand,
    RpcSwitchSessionCommand,
    deserialize_rpc_command,
    deserialize_rpc_session_state,
    serialize_rpc_response,
    serialize_rpc_session_state,
)

# ---------------------------------------------------------------------------
# deserialize_rpc_command tests
# ---------------------------------------------------------------------------


class TestDeserializeRpcCommand:
    def test_prompt_minimal(self) -> None:
        cmd = deserialize_rpc_command({"type": "prompt", "message": "hello"})
        assert isinstance(cmd, RpcPromptCommand)
        assert cmd.message == "hello"
        assert cmd.images == []
        assert cmd.streaming_behavior is None
        assert cmd.id is None

    def test_prompt_full(self) -> None:
        cmd = deserialize_rpc_command(
            {
                "type": "prompt",
                "message": "hi",
                "images": [{"type": "image", "data": "abc", "mimeType": "image/png"}],
                "streamingBehavior": "steer",
                "id": "req-1",
            }
        )
        assert isinstance(cmd, RpcPromptCommand)
        assert cmd.streaming_behavior == "steer"
        assert len(cmd.images) == 1
        assert cmd.images[0].mime_type == "image/png"
        assert cmd.id == "req-1"

    def test_steer(self) -> None:
        cmd = deserialize_rpc_command({"type": "steer", "message": "steer me"})
        assert isinstance(cmd, RpcSteerCommand)
        assert cmd.message == "steer me"

    def test_abort(self) -> None:
        cmd = deserialize_rpc_command({"type": "abort"})
        assert isinstance(cmd, RpcAbortCommand)

    def test_new_session(self) -> None:
        cmd = deserialize_rpc_command({"type": "new_session", "parentSession": "old"})
        assert isinstance(cmd, RpcNewSessionCommand)
        assert cmd.parent_session == "old"

    def test_new_session_no_parent(self) -> None:
        cmd = deserialize_rpc_command({"type": "new_session"})
        assert isinstance(cmd, RpcNewSessionCommand)
        assert cmd.parent_session is None

    def test_get_state(self) -> None:
        cmd = deserialize_rpc_command({"type": "get_state"})
        assert isinstance(cmd, RpcGetStateCommand)

    def test_set_model(self) -> None:
        cmd = deserialize_rpc_command({"type": "set_model", "provider": "anthropic", "modelId": "claude-3"})
        assert isinstance(cmd, RpcSetModelCommand)
        assert cmd.provider == "anthropic"
        assert cmd.model_id == "claude-3"

    def test_get_available_models(self) -> None:
        cmd = deserialize_rpc_command({"type": "get_available_models"})
        assert isinstance(cmd, RpcGetAvailableModelsCommand)

    def test_set_thinking_level(self) -> None:
        cmd = deserialize_rpc_command({"type": "set_thinking_level", "level": "high"})
        assert isinstance(cmd, RpcSetThinkingLevelCommand)
        assert cmd.level == "high"

    def test_set_thinking_level_invalid_defaults_to_off(self) -> None:
        cmd = deserialize_rpc_command({"type": "set_thinking_level", "level": "ultra"})
        assert isinstance(cmd, RpcSetThinkingLevelCommand)
        assert cmd.level == "off"

    def test_set_steering_mode(self) -> None:
        cmd = deserialize_rpc_command({"type": "set_steering_mode", "mode": "one-at-a-time"})
        assert isinstance(cmd, RpcSetSteeringModeCommand)
        assert cmd.mode == "one-at-a-time"

    def test_set_follow_up_mode(self) -> None:
        cmd = deserialize_rpc_command({"type": "set_follow_up_mode", "mode": "all"})
        assert isinstance(cmd, RpcSetFollowUpModeCommand)
        assert cmd.mode == "all"

    def test_compact(self) -> None:
        cmd = deserialize_rpc_command({"type": "compact", "customInstructions": "be brief"})
        assert isinstance(cmd, RpcCompactCommand)
        assert cmd.custom_instructions == "be brief"

    def test_compact_no_instructions(self) -> None:
        cmd = deserialize_rpc_command({"type": "compact"})
        assert isinstance(cmd, RpcCompactCommand)
        assert cmd.custom_instructions is None

    def test_set_auto_compaction(self) -> None:
        cmd = deserialize_rpc_command({"type": "set_auto_compaction", "enabled": False})
        assert isinstance(cmd, RpcSetAutoCompactionCommand)
        assert cmd.enabled is False

    def test_bash(self) -> None:
        cmd = deserialize_rpc_command({"type": "bash", "command": "ls -la"})
        assert isinstance(cmd, RpcBashCommand)
        assert cmd.command == "ls -la"

    def test_get_session_stats(self) -> None:
        cmd = deserialize_rpc_command({"type": "get_session_stats"})
        assert isinstance(cmd, RpcGetSessionStatsCommand)

    def test_export_html(self) -> None:
        cmd = deserialize_rpc_command({"type": "export_html", "outputPath": "/tmp/out.html"})
        assert isinstance(cmd, RpcExportHtmlCommand)
        assert cmd.output_path == "/tmp/out.html"

    def test_switch_session(self) -> None:
        cmd = deserialize_rpc_command({"type": "switch_session", "sessionPath": "/sessions/abc"})
        assert isinstance(cmd, RpcSwitchSessionCommand)
        assert cmd.session_path == "/sessions/abc"

    def test_fork(self) -> None:
        cmd = deserialize_rpc_command({"type": "fork", "entryId": "entry-42"})
        assert isinstance(cmd, RpcForkCommand)
        assert cmd.entry_id == "entry-42"

    def test_get_fork_messages(self) -> None:
        cmd = deserialize_rpc_command({"type": "get_fork_messages"})
        assert isinstance(cmd, RpcGetForkMessagesCommand)

    def test_get_last_assistant_text(self) -> None:
        cmd = deserialize_rpc_command({"type": "get_last_assistant_text"})
        assert isinstance(cmd, RpcGetLastAssistantTextCommand)

    def test_set_session_name(self) -> None:
        cmd = deserialize_rpc_command({"type": "set_session_name", "name": "my session"})
        assert isinstance(cmd, RpcSetSessionNameCommand)
        assert cmd.name == "my session"

    def test_get_messages(self) -> None:
        cmd = deserialize_rpc_command({"type": "get_messages"})
        assert isinstance(cmd, RpcGetMessagesCommand)

    def test_get_commands(self) -> None:
        cmd = deserialize_rpc_command({"type": "get_commands"})
        assert isinstance(cmd, RpcGetCommandsCommand)

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown RPC command type"):
            deserialize_rpc_command({"type": "not_a_thing"})


# ---------------------------------------------------------------------------
# RpcSessionState serialization
# ---------------------------------------------------------------------------


class TestRpcSessionStateSerialization:
    def _make_state(self) -> RpcSessionState:
        return RpcSessionState(
            thinking_level="medium",
            is_streaming=True,
            is_compacting=False,
            steering_mode="all",
            follow_up_mode="one-at-a-time",
            session_id="sess-1",
            auto_compaction_enabled=True,
            message_count=5,
            pending_message_count=0,
        )

    def test_serialize_no_optional(self) -> None:
        state = self._make_state()
        data = serialize_rpc_session_state(state)
        assert data["thinkingLevel"] == "medium"
        assert data["isStreaming"] is True
        assert data["isCompacting"] is False
        assert data["steeringMode"] == "all"
        assert data["followUpMode"] == "one-at-a-time"
        assert data["sessionId"] == "sess-1"
        assert data["autoCompactionEnabled"] is True
        assert data["messageCount"] == 5
        assert "model" not in data
        assert "sessionFile" not in data
        assert "sessionName" not in data

    def test_serialize_with_session_file_and_name(self) -> None:
        state = self._make_state()
        state.session_file = "/sessions/sess-1.json"
        state.session_name = "My Session"
        data = serialize_rpc_session_state(state)
        assert data["sessionFile"] == "/sessions/sess-1.json"
        assert data["sessionName"] == "My Session"

    def test_roundtrip(self) -> None:
        state = self._make_state()
        serialized = serialize_rpc_session_state(state)
        restored = deserialize_rpc_session_state(serialized)
        assert restored.thinking_level == state.thinking_level
        assert restored.is_streaming == state.is_streaming
        assert restored.session_id == state.session_id
        assert restored.message_count == state.message_count


# ---------------------------------------------------------------------------
# RpcResponse serialization
# ---------------------------------------------------------------------------


class TestRpcResponseSerialization:
    def test_success_response(self) -> None:
        resp = RpcResponse(command="prompt", success=True, data={"text": "hi"}, id="req-1")
        data = serialize_rpc_response(resp)
        assert data["type"] == "response"
        assert data["command"] == "prompt"
        assert data["success"] is True
        assert data["data"] == {"text": "hi"}
        assert data["id"] == "req-1"
        assert "error" not in data

    def test_error_response(self) -> None:
        resp = RpcResponse(command="bash", success=False, error="command not found", id="req-2")
        data = serialize_rpc_response(resp)
        assert data["success"] is False
        assert data["error"] == "command not found"
        assert "data" not in data

    def test_no_id(self) -> None:
        resp = RpcResponse(command="abort", success=True)
        data = serialize_rpc_response(resp)
        assert "id" not in data


# ---------------------------------------------------------------------------
# RpcSlashCommand
# ---------------------------------------------------------------------------


class TestRpcSlashCommand:
    def test_defaults(self) -> None:
        cmd = RpcSlashCommand()
        assert cmd.source == "prompt"
        assert cmd.description is None
        assert cmd.location is None

    def test_with_values(self) -> None:
        cmd = RpcSlashCommand(name="deploy", source="skill", location="project", path="/skills/deploy")
        assert cmd.name == "deploy"
        assert cmd.source == "skill"
        assert cmd.location == "project"


# ---------------------------------------------------------------------------
# RpcClient tests (async, using mock subprocess)
# ---------------------------------------------------------------------------


class TestRpcClient:
    """Test RpcClient without spawning a real subprocess."""

    @pytest.mark.asyncio
    async def test_on_event_and_unsubscribe(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])
        events: list[dict[str, Any]] = []

        unsub = client.on_event(lambda e: events.append(e))
        # Simulate emitting an event directly
        client._emit_event({"type": "agent_start"})
        assert len(events) == 1

        unsub()
        client._emit_event({"type": "agent_end"})
        # Listener was removed, so still only 1 event
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_get_stderr_initially_empty(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])
        assert client.get_stderr() == ""

    @pytest.mark.asyncio
    async def test_prompt_and_wait_collects_events(self) -> None:
        """Verify prompt_and_wait resolves when agent_end event is emitted."""
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])

        # Patch _send so it doesn't try to use a real subprocess, and
        # immediately emit an agent_end event via the listener mechanism.
        _bg_tasks: list[asyncio.Task[None]] = []

        async def fake_send(cmd: dict[str, Any], timeout: float = 30.0) -> RpcResponse:
            # After prompt is "sent", emit agent_end asynchronously
            async def _emit_later() -> None:
                await asyncio.sleep(0)
                client._emit_event({"type": "agent_end"})

            _bg_tasks.append(asyncio.create_task(_emit_later()))
            return RpcResponse(command="prompt", success=True)

        client._send = fake_send  # type: ignore[method-assign]

        events = await client.prompt_and_wait("hello", timeout=5.0)
        assert any(e.get("type") == "agent_end" for e in events)

    @pytest.mark.asyncio
    async def test_wait_for_idle_timeout(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])
        # No events emitted, should time out after 0.05 s
        events = await client.wait_for_idle(timeout=0.05)
        assert events == []

    @pytest.mark.asyncio
    async def test_stop_resolves_pending_futures(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])
        # Manually inject a pending future
        loop = asyncio.get_event_loop()
        future: asyncio.Future[RpcResponse] = loop.create_future()
        client._pending["fake-id"] = future
        # Create a fake stopped process
        mock_proc = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)
        client._process = mock_proc
        await client.stop()
        assert future.done()
        with pytest.raises(RuntimeError, match="stopped"):
            future.result()

    @pytest.mark.asyncio
    async def test_read_stdout_handles_invalid_json(self) -> None:
        """_read_stdout should skip invalid JSON lines without crashing."""
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])
        events: list[dict[str, Any]] = []
        client.on_event(lambda e: events.append(e))

        # Feed a bad JSON line followed by a valid event line
        lines = b'not valid json\n{"type": "agent_start"}\n'
        reader = asyncio.StreamReader()
        reader.feed_data(lines)
        reader.feed_eof()

        mock_proc = MagicMock()
        mock_proc.stdout = reader
        mock_proc.stderr = None
        client._process = mock_proc
        await client._read_stdout()
        # Only the valid event should be emitted
        assert len(events) == 1
        assert events[0]["type"] == "agent_start"

    @pytest.mark.asyncio
    async def test_read_stdout_dispatches_response_to_pending(self) -> None:
        """Responses matching a pending future should resolve that future."""
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])
        loop = asyncio.get_event_loop()
        future: asyncio.Future[RpcResponse] = loop.create_future()
        client._pending["my-id"] = future

        response_line = (
            json.dumps(
                {
                    "type": "response",
                    "command": "prompt",
                    "success": True,
                    "id": "my-id",
                }
            ).encode()
            + b"\n"
        )
        reader = asyncio.StreamReader()
        reader.feed_data(response_line)
        reader.feed_eof()

        mock_proc = MagicMock()
        mock_proc.stdout = reader
        client._process = mock_proc
        await client._read_stdout()
        assert future.done()
        result = future.result()
        assert result.command == "prompt"

    @pytest.mark.asyncio
    async def test_read_stdout_emits_response_without_matching_pending(self) -> None:
        """Responses with unknown id should be emitted as events."""
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])
        events: list[dict[str, Any]] = []
        client.on_event(lambda e: events.append(e))

        response_line = (
            json.dumps(
                {
                    "type": "response",
                    "command": "prompt",
                    "success": True,
                    "id": "unknown-id",
                }
            ).encode()
            + b"\n"
        )
        reader = asyncio.StreamReader()
        reader.feed_data(response_line)
        reader.feed_eof()

        mock_proc = MagicMock()
        mock_proc.stdout = reader
        client._process = mock_proc
        await client._read_stdout()
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_read_stderr_collects_lines(self) -> None:
        """_read_stderr should accumulate lines into _stderr_lines."""
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])
        reader = asyncio.StreamReader()
        reader.feed_data(b"error line 1\nerror line 2\n")
        reader.feed_eof()

        mock_proc = MagicMock()
        mock_proc.stderr = reader
        client._process = mock_proc
        await client._read_stderr()
        assert "error line 1" in client.get_stderr()
        assert "error line 2" in client.get_stderr()

    @pytest.mark.asyncio
    async def test_send_raises_timeout_when_no_response(self) -> None:
        """_send should raise TimeoutError when subprocess never replies."""
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])
        # Fake a running process with a stdin that accepts writes but never responds
        mock_stdin = AsyncMock()
        mock_proc = MagicMock()
        mock_proc.stdin = mock_stdin
        mock_proc.stdin.write = MagicMock()
        mock_proc.stdin.drain = AsyncMock()
        client._process = mock_proc

        with pytest.raises(TimeoutError):
            await client._send({"type": "get_state"}, timeout=0.05)

    @pytest.mark.asyncio
    async def test_all_command_methods_send_correct_type(self) -> None:
        """Each command method should send the right type."""
        from pi_coding_agent.modes.rpc.rpc_client import RpcClient

        client = RpcClient(["echo"])
        sent: list[dict[str, Any]] = []

        async def capture_send(cmd: dict[str, Any], timeout: float = 30.0) -> RpcResponse:
            sent.append(cmd)
            return RpcResponse(command=cmd.get("type", ""), success=True)

        client._send = capture_send  # type: ignore[method-assign]

        # Call each method and verify the type
        await client.steer("msg")
        await client.follow_up("msg")
        await client.abort()
        await client.new_session()
        await client.new_session("parent")
        await client.get_state()
        await client.set_model("anthropic", "claude-3")
        await client.cycle_model()
        await client.get_available_models()
        await client.set_thinking_level("high")
        await client.cycle_thinking_level()
        await client.set_steering_mode("all")
        await client.set_follow_up_mode("one-at-a-time")
        await client.compact()
        await client.compact("instructions")
        await client.set_auto_compaction(True)
        await client.set_auto_retry(False)
        await client.abort_retry()
        await client.bash("ls")
        await client.abort_bash()
        await client.get_session_stats()
        await client.export_html()
        await client.export_html("/tmp/out.html")
        await client.switch_session("/sessions/abc")
        await client.fork("entry-1")
        await client.get_fork_messages()
        await client.get_last_assistant_text()
        await client.set_session_name("my session")
        await client.get_messages()
        await client.get_commands()
        await client.prompt("msg", streaming_behavior="steer")

        types_sent = [s["type"] for s in sent]
        assert "steer" in types_sent
        assert "follow_up" in types_sent
        assert "abort" in types_sent
        assert "new_session" in types_sent
        assert "get_state" in types_sent
        assert "set_model" in types_sent
        assert "bash" in types_sent
        assert "export_html" in types_sent


# ---------------------------------------------------------------------------
# rpc_mode dispatch tests
# ---------------------------------------------------------------------------


class _StubSession:
    """Minimal AgentSessionProtocol implementation for testing dispatch."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def prompt(self, message: str, images: list[Any], streaming_behavior: str | None) -> str:
        self.calls.append("prompt")
        return "response"

    async def steer(self, message: str, images: list[Any]) -> str:
        self.calls.append("steer")
        return "steered"

    async def follow_up(self, message: str, images: list[Any]) -> str:
        self.calls.append("follow_up")
        return "followed"

    async def abort(self) -> None:
        self.calls.append("abort")

    async def new_session(self, parent_session: str | None) -> str:
        self.calls.append("new_session")
        return "session-id"

    async def get_state(self) -> Any:
        from pi_coding_agent.modes.rpc.rpc_types import RpcSessionState

        self.calls.append("get_state")
        return RpcSessionState(session_id="s1")

    async def set_model(self, provider: str, model_id: str) -> None:
        self.calls.append("set_model")

    async def cycle_model(self) -> None:
        self.calls.append("cycle_model")

    async def get_available_models(self) -> list[str]:
        self.calls.append("get_available_models")
        return []

    async def set_thinking_level(self, level: str) -> None:
        self.calls.append("set_thinking_level")

    async def cycle_thinking_level(self) -> None:
        self.calls.append("cycle_thinking_level")

    async def set_steering_mode(self, mode: str) -> None:
        self.calls.append("set_steering_mode")

    async def set_follow_up_mode(self, mode: str) -> None:
        self.calls.append("set_follow_up_mode")

    async def compact(self, custom_instructions: str | None) -> None:
        self.calls.append("compact")

    async def set_auto_compaction(self, enabled: bool) -> None:
        self.calls.append("set_auto_compaction")

    async def set_auto_retry(self, enabled: bool) -> None:
        self.calls.append("set_auto_retry")

    async def abort_retry(self) -> None:
        self.calls.append("abort_retry")

    async def bash(self, command: str) -> str:
        self.calls.append("bash")
        return "output"

    async def abort_bash(self) -> None:
        self.calls.append("abort_bash")

    async def get_session_stats(self) -> dict[str, int]:
        self.calls.append("get_session_stats")
        return {}

    async def export_html(self, output_path: str | None) -> str:
        self.calls.append("export_html")
        return "/tmp/out.html"

    async def switch_session(self, session_path: str) -> None:
        self.calls.append("switch_session")

    async def fork(self, entry_id: str) -> str:
        self.calls.append("fork")
        return "fork-id"

    async def get_fork_messages(self) -> list[Any]:
        self.calls.append("get_fork_messages")
        return []

    async def get_last_assistant_text(self) -> str:
        self.calls.append("get_last_assistant_text")
        return "last text"

    async def set_session_name(self, name: str) -> None:
        self.calls.append("set_session_name")

    async def get_messages(self) -> list[Any]:
        self.calls.append("get_messages")
        return []

    async def get_commands(self) -> list[Any]:
        self.calls.append("get_commands")
        return []


class TestRpcModeDispatch:
    """Test the _dispatch function in rpc_mode.py."""

    @pytest.mark.asyncio
    async def test_dispatch_prompt(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcPromptCommand

        session = _StubSession()
        cmd = RpcPromptCommand(message="hello", id="r1")
        resp = await _dispatch(session, cmd)
        assert resp.success is True
        assert "prompt" in session.calls

    @pytest.mark.asyncio
    async def test_dispatch_abort(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcAbortCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcAbortCommand(id="r2"))
        assert resp.success is True
        assert "abort" in session.calls

    @pytest.mark.asyncio
    async def test_dispatch_new_session(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcNewSessionCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcNewSessionCommand(id="r3"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_get_state(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcGetStateCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcGetStateCommand(id="r4"))
        assert resp.success is True
        assert resp.data is not None

    @pytest.mark.asyncio
    async def test_dispatch_bash(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcBashCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcBashCommand(command="ls", id="r5"))
        assert resp.success is True
        assert "bash" in session.calls

    @pytest.mark.asyncio
    async def test_dispatch_abort_retry(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcAbortRetryCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcAbortRetryCommand(id="r6"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_abort_bash(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcAbortBashCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcAbortBashCommand(id="r7"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_export_html_with_path(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcExportHtmlCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcExportHtmlCommand(output_path="/tmp/a.html", id="r8"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_set_model(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcSetModelCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcSetModelCommand(provider="anthropic", model_id="claude", id="r9"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_get_available_models(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcGetAvailableModelsCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcGetAvailableModelsCommand(id="r10"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_set_thinking_level(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcSetThinkingLevelCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcSetThinkingLevelCommand(level="medium", id="r11"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_set_steering_mode(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcSetSteeringModeCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcSetSteeringModeCommand(mode="all", id="r12"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_set_follow_up_mode(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcSetFollowUpModeCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcSetFollowUpModeCommand(mode="all", id="r13"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_compact(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcCompactCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcCompactCommand(id="r14"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_set_auto_compaction(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcSetAutoCompactionCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcSetAutoCompactionCommand(enabled=True, id="r15"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_set_auto_retry(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcSetAutoRetryCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcSetAutoRetryCommand(enabled=True, id="r16"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_switch_session(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcSwitchSessionCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcSwitchSessionCommand(session_path="/s", id="r17"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_fork(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcForkCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcForkCommand(entry_id="e1", id="r18"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_get_fork_messages(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcGetForkMessagesCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcGetForkMessagesCommand(id="r19"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_get_last_assistant_text(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcGetLastAssistantTextCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcGetLastAssistantTextCommand(id="r20"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_set_session_name(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcSetSessionNameCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcSetSessionNameCommand(name="my session", id="r21"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_get_messages(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcGetMessagesCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcGetMessagesCommand(id="r22"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_get_commands(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcGetCommandsCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcGetCommandsCommand(id="r23"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_get_session_stats(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcGetSessionStatsCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcGetSessionStatsCommand(id="r24"))
        assert resp.success is True

    @pytest.mark.asyncio
    async def test_dispatch_cycle_model(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcCycleModelCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcCycleModelCommand(id="r25"))
        assert resp.success is True
        assert "cycle_model" in session.calls

    @pytest.mark.asyncio
    async def test_dispatch_cycle_thinking_level(self) -> None:
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcCycleThinkingLevelCommand

        session = _StubSession()
        resp = await _dispatch(session, RpcCycleThinkingLevelCommand(id="r26"))
        assert resp.success is True
        # Must call cycle_thinking_level, NOT cycle_model
        assert "cycle_thinking_level" in session.calls
        assert "cycle_model" not in session.calls

    @pytest.mark.asyncio
    async def test_dispatch_exception_returns_error_response(self) -> None:
        """When a session method raises, _dispatch should return an error response."""
        from pi_coding_agent.modes.rpc.rpc_mode import _dispatch
        from pi_coding_agent.modes.rpc.rpc_types import RpcBashCommand

        class _ErrorSession(_StubSession):
            async def bash(self, command: str) -> str:
                raise RuntimeError("bash failed")

        resp = await _dispatch(_ErrorSession(), RpcBashCommand(command="bad", id="err"))
        assert resp.success is False
        assert "bash failed" in (resp.error or "")
