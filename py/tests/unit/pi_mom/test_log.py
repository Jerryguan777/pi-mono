"""Tests for pi_mom.log."""

from __future__ import annotations

import pytest

from pi_mom.log import (
    LogContext,
    _format_context,
    _format_tool_args,
    _timestamp,
    _truncate,
    log_agent_error,
    log_backfill_channel,
    log_backfill_complete,
    log_backfill_start,
    log_connected,
    log_disconnected,
    log_download_error,
    log_download_start,
    log_download_success,
    log_info,
    log_response,
    log_response_start,
    log_stop_request,
    log_thinking,
    log_tool_error,
    log_tool_start,
    log_tool_success,
    log_usage_summary,
    log_user_message,
    log_warning,
)


class TestTimestamp:
    def test_format(self) -> None:
        ts = _timestamp()
        assert ts.startswith("[")
        assert ts.endswith("]")
        assert len(ts) == 10  # [HH:MM:SS]


class TestFormatContext:
    def test_dm_channel(self) -> None:
        ctx = LogContext(channel_id="D12345", user_name="mario")
        result = _format_context(ctx)
        assert result == "[DM:mario]"

    def test_dm_channel_no_username(self) -> None:
        ctx = LogContext(channel_id="D12345")
        result = _format_context(ctx)
        assert result == "[DM:D12345]"

    def test_regular_channel_with_name(self) -> None:
        ctx = LogContext(channel_id="C12345", user_name="mario", channel_name="dev-team")
        result = _format_context(ctx)
        assert result == "[#dev-team:mario]"

    def test_regular_channel_with_hash_prefix(self) -> None:
        ctx = LogContext(channel_id="C12345", user_name="mario", channel_name="#dev-team")
        result = _format_context(ctx)
        assert result == "[#dev-team:mario]"

    def test_regular_channel_no_name(self) -> None:
        ctx = LogContext(channel_id="C12345", user_name="mario")
        result = _format_context(ctx)
        assert result == "[#C12345:mario]"

    def test_no_username(self) -> None:
        ctx = LogContext(channel_id="C12345", channel_name="dev-team")
        result = _format_context(ctx)
        assert result == "[#dev-team:unknown]"


class TestTruncate:
    def test_no_truncation(self) -> None:
        assert _truncate("hello", 100) == "hello"

    def test_truncation(self) -> None:
        result = _truncate("a" * 200, 100)
        assert len(result) > 100  # includes truncation notice
        assert "truncated at 100 chars" in result

    def test_exact_limit(self) -> None:
        assert _truncate("a" * 50, 50) == "a" * 50


class TestFormatToolArgs:
    def test_skips_label(self) -> None:
        args = {"label": "Reading file", "path": "/foo/bar.py"}
        result = _format_tool_args(args)
        assert "label" not in result
        assert "/foo/bar.py" in result

    def test_path_with_offset_limit(self) -> None:
        args = {"label": "x", "path": "/foo.py", "offset": 10, "limit": 20}
        result = _format_tool_args(args)
        assert "/foo.py:10-30" in result
        assert "offset" not in result
        assert "limit" not in result

    def test_non_string_value(self) -> None:
        args = {"label": "x", "value": 42}
        result = _format_tool_args(args)
        assert "42" in result


class TestLogFunctions:
    """Smoke tests for log functions — verify they don't raise."""

    def test_log_user_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123", user_name="mario")
        log_user_message(ctx, "hello")
        captured = capsys.readouterr()
        assert "hello" in captured.out

    def test_log_tool_start(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123", user_name="mario")
        log_tool_start(ctx, "bash", "run tests", {"label": "run tests", "command": "pytest"})
        captured = capsys.readouterr()
        assert "bash" in captured.out

    def test_log_tool_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123")
        log_tool_success(ctx, "bash", 1500.0, "OK")
        captured = capsys.readouterr()
        assert "1.5s" in captured.out

    def test_log_tool_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123")
        log_tool_error(ctx, "bash", 500.0, "error!")
        captured = capsys.readouterr()
        assert "0.5s" in captured.out

    def test_log_response_start(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123")
        log_response_start(ctx)
        captured = capsys.readouterr()
        assert "Streaming" in captured.out

    def test_log_thinking(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123")
        log_thinking(ctx, "I am thinking...")
        captured = capsys.readouterr()
        assert "Thinking" in captured.out

    def test_log_response(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123")
        log_response(ctx, "Hello world")
        captured = capsys.readouterr()
        assert "Response" in captured.out

    def test_log_download_start(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123")
        log_download_start(ctx, "file.png", "/tmp/file.png")
        captured = capsys.readouterr()
        assert "Downloading" in captured.out

    def test_log_download_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123")
        log_download_success(ctx, 42.5)
        captured = capsys.readouterr()
        assert "Downloaded" in captured.out

    def test_log_download_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123")
        log_download_error(ctx, "file.png", "404 Not Found")
        captured = capsys.readouterr()
        assert "Download failed" in captured.out

    def test_log_stop_request(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123")
        log_stop_request(ctx)
        captured = capsys.readouterr()
        assert "stop" in captured.out.lower()

    def test_log_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info("system message")
        captured = capsys.readouterr()
        assert "system message" in captured.out

    def test_log_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_warning("watch out", "details here")
        captured = capsys.readouterr()
        assert "watch out" in captured.out
        assert "details here" in captured.out

    def test_log_agent_error_with_context(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = LogContext(channel_id="C123", user_name="mario")
        log_agent_error(ctx, "something broke")
        captured = capsys.readouterr()
        assert "Agent error" in captured.out

    def test_log_agent_error_system(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_agent_error("system", "something broke")
        captured = capsys.readouterr()
        assert "[system]" in captured.out

    def test_log_backfill_start(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_backfill_start(5)
        captured = capsys.readouterr()
        assert "5" in captured.out

    def test_log_backfill_channel(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_backfill_channel("dev-team", 42)
        captured = capsys.readouterr()
        assert "dev-team" in captured.out
        assert "42" in captured.out

    def test_log_backfill_complete(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_backfill_complete(100, 2500.0)
        captured = capsys.readouterr()
        assert "100" in captured.out
        assert "2.5s" in captured.out

    def test_log_connected(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_connected()
        captured = capsys.readouterr()
        assert "connected" in captured.out.lower()

    def test_log_disconnected(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_disconnected()
        captured = capsys.readouterr()
        assert "disconnected" in captured.out.lower()


class TestLogUsageSummary:
    def test_returns_string(self) -> None:
        ctx = LogContext(channel_id="C123", user_name="mario")
        usage = {
            "input": 1000,
            "output": 500,
            "cacheRead": 0,
            "cacheWrite": 0,
            "cost": {"input": 0.01, "output": 0.005, "cacheRead": 0.0, "cacheWrite": 0.0, "total": 0.015},
        }
        result = log_usage_summary(ctx, usage)
        assert "*Usage Summary*" in result
        assert "$0.0150" in result

    def test_with_context_window(self) -> None:
        ctx = LogContext(channel_id="C123", user_name="mario")
        usage = {
            "input": 50000,
            "output": 1000,
            "cacheRead": 0,
            "cacheWrite": 0,
            "cost": {"input": 0.5, "output": 0.01, "cacheRead": 0.0, "cacheWrite": 0.0, "total": 0.51},
        }
        result = log_usage_summary(ctx, usage, context_tokens=51000, context_window=200000)
        assert "Context:" in result

    def test_with_cache(self) -> None:
        ctx = LogContext(channel_id="C123", user_name="mario")
        usage = {
            "input": 1000,
            "output": 200,
            "cacheRead": 5000,
            "cacheWrite": 100,
            "cost": {"input": 0.01, "output": 0.002, "cacheRead": 0.005, "cacheWrite": 0.001, "total": 0.018},
        }
        result = log_usage_summary(ctx, usage)
        assert "Cache:" in result
