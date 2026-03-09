"""Unit tests for pi_coding_agent HTML export."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from pi_agent.types import AgentMessage
from pi_ai.types import (
    AssistantMessage,
    ImageContent,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from pi_coding_agent.core.export_html.exporter import (
    ExportOptions,
    export_from_file,
    export_session_to_html,
)

# ---------------------------------------------------------------------------
# Helper: minimal SessionManager
# ---------------------------------------------------------------------------


class _FakeSession:
    def __init__(self, messages: list[AgentMessage], session_id: str = "sess-1", name: str | None = None) -> None:
        self._messages = messages
        self._session_id = session_id
        self._name = name

    def get_messages(self) -> list[AgentMessage]:
        return self._messages

    def get_session_id(self) -> str:
        return self._session_id

    def get_session_name(self) -> str | None:
        return self._name


# ---------------------------------------------------------------------------
# Tests: export_session_to_html
# ---------------------------------------------------------------------------


class TestExportSessionToHtml:
    def test_creates_file_when_no_output_path(self) -> None:
        sm = _FakeSession([])
        path = export_session_to_html(sm)
        assert Path(path).exists()
        content = Path(path).read_text()
        assert "<!DOCTYPE html>" in content
        Path(path).unlink(missing_ok=True)

    def test_writes_to_specified_output_path(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            out = tmp.name
        sm = _FakeSession([])
        returned = export_session_to_html(sm, options=ExportOptions(output_path=out))
        assert Path(returned).exists()
        content = Path(returned).read_text()
        assert "<!DOCTYPE html>" in content
        Path(out).unlink(missing_ok=True)

    def test_session_name_in_title(self) -> None:
        sm = _FakeSession([], name="My Coding Session")
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "My Coding Session" in content
        Path(path).unlink(missing_ok=True)

    def test_session_id_in_title_when_no_name(self) -> None:
        sm = _FakeSession([], session_id="abc-123")
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "abc-123" in content
        Path(path).unlink(missing_ok=True)

    def test_renders_user_message_text(self) -> None:
        msg = UserMessage(content="Please help me.")
        sm = _FakeSession([msg])
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "Please help me." in content
        Path(path).unlink(missing_ok=True)

    def test_renders_user_message_content_blocks(self) -> None:
        msg = UserMessage(content=[TextContent(text="Block content")])
        sm = _FakeSession([msg])
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "Block content" in content
        Path(path).unlink(missing_ok=True)

    def test_renders_assistant_message(self) -> None:
        msg = AssistantMessage(content=[TextContent(text="I can help with that.")])
        sm = _FakeSession([msg])
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "I can help with that." in content
        Path(path).unlink(missing_ok=True)

    def test_renders_thinking_block(self) -> None:
        msg = AssistantMessage(content=[ThinkingContent(thinking="let me think...")])
        sm = _FakeSession([msg])
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "let me think..." in content
        Path(path).unlink(missing_ok=True)

    def test_renders_tool_call(self) -> None:
        tool_call = ToolCall(id="tc-1", name="bash", arguments={"command": "ls"})
        msg = AssistantMessage(content=[tool_call])
        sm = _FakeSession([msg])
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "bash" in content
        Path(path).unlink(missing_ok=True)

    def test_renders_tool_result(self) -> None:
        result_msg = ToolResultMessage(
            tool_call_id="tc-1",
            tool_name="bash",
            content=[TextContent(text="file1.txt\nfile2.txt")],
        )
        sm = _FakeSession([result_msg])
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "file1.txt" in content
        Path(path).unlink(missing_ok=True)

    def test_renders_error_tool_result(self) -> None:
        result_msg = ToolResultMessage(
            tool_call_id="tc-2",
            tool_name="bash",
            content=[TextContent(text="command not found")],
            is_error=True,
        )
        sm = _FakeSession([result_msg])
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "command not found" in content
        assert "error" in content.lower()
        Path(path).unlink(missing_ok=True)

    def test_renders_image_content(self) -> None:
        img = ImageContent(data="abc123", mime_type="image/png")
        msg = UserMessage(content=[img])
        sm = _FakeSession([msg])
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "data:image/png;base64,abc123" in content
        Path(path).unlink(missing_ok=True)

    def test_escapes_html_in_text(self) -> None:
        msg = UserMessage(content="<script>alert('xss')</script>")
        sm = _FakeSession([msg])
        path = export_session_to_html(sm)
        content = Path(path).read_text()
        assert "<script>" not in content
        assert "&lt;script&gt;" in content
        Path(path).unlink(missing_ok=True)

    def test_custom_tool_renderer_call(self) -> None:
        class MyRenderer:
            def render_call(self, tool_name: str, args: dict[str, Any]) -> str | None:
                return f'<div class="custom-call">{tool_name}</div>'

            def render_result(self, tool_name: str, result: Any, details: Any, is_error: bool) -> str | None:
                return None

        tool_call = ToolCall(id="tc-1", name="custom_tool", arguments={})
        msg = AssistantMessage(content=[tool_call])
        sm = _FakeSession([msg])
        path = export_session_to_html(sm, options=ExportOptions(tool_renderer=MyRenderer()))
        content = Path(path).read_text()
        assert "custom-call" in content
        assert "custom_tool" in content
        Path(path).unlink(missing_ok=True)

    def test_custom_tool_renderer_result(self) -> None:
        class MyRenderer:
            def render_call(self, tool_name: str, args: dict[str, Any]) -> str | None:
                return None

            def render_result(self, tool_name: str, result: Any, details: Any, is_error: bool) -> str | None:
                return '<div class="custom-result">CUSTOM</div>'

        result_msg = ToolResultMessage(
            tool_call_id="tc-1",
            tool_name="my_tool",
            content=[TextContent(text="output")],
        )
        sm = _FakeSession([result_msg])
        path = export_session_to_html(sm, options=ExportOptions(tool_renderer=MyRenderer()))
        content = Path(path).read_text()
        assert "custom-result" in content
        Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tests: export_from_file
# ---------------------------------------------------------------------------


class TestExportFromFile:
    def _write_session_file(self, messages: list[Any]) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as tmp:
            json.dump(messages, tmp)
            return Path(tmp.name)

    def test_exports_empty_session(self) -> None:
        input_path = self._write_session_file([])
        try:
            out = export_from_file(str(input_path))
            assert Path(out).exists()
            Path(out).unlink(missing_ok=True)
        finally:
            input_path.unlink(missing_ok=True)

    def test_exports_user_message(self) -> None:
        messages = [{"role": "user", "content": "Hello from file", "timestamp": 0}]
        input_path = self._write_session_file(messages)
        try:
            out = export_from_file(str(input_path))
            content = Path(out).read_text()
            assert "Hello from file" in content
            Path(out).unlink(missing_ok=True)
        finally:
            input_path.unlink(missing_ok=True)

    def test_exports_to_specified_output_path(self) -> None:
        messages = [{"role": "user", "content": "test", "timestamp": 0}]
        input_path = self._write_session_file(messages)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as out_tmp:
            out_path = out_tmp.name
        try:
            returned = export_from_file(str(input_path), options=ExportOptions(output_path=out_path))
            assert Path(returned).exists()
            Path(out_path).unlink(missing_ok=True)
        finally:
            input_path.unlink(missing_ok=True)
