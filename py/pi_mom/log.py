"""Logging utilities for pi_mom — port of packages/mom/src/log.ts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
DIM = "\033[2m"
RESET = "\033[0m"


@dataclass
class LogContext:
    """Context identifying a Slack channel + user for logging."""

    channel_id: str
    user_name: str | None = None
    channel_name: str | None = None


def _timestamp() -> str:
    now = datetime.now()
    return f"[{now.hour:02d}:{now.minute:02d}:{now.second:02d}]"


def _format_context(ctx: LogContext) -> str:
    """Format channel context as [DM:user] or [#channel:user]."""
    if ctx.channel_id.startswith("D"):
        return f"[DM:{ctx.user_name or ctx.channel_id}]"
    channel = ctx.channel_name or ctx.channel_id
    user = ctx.user_name or "unknown"
    display_channel = channel if channel.startswith("#") else f"#{channel}"
    return f"[{display_channel}:{user}]"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}\n(truncated at {max_len} chars)"


def _format_tool_args(args: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in args.items():
        if key == "label":
            continue
        if key == "path" and isinstance(value, str):
            offset = args.get("offset")
            limit = args.get("limit")
            if offset is not None and limit is not None:
                lines.append(f"{value}:{offset}-{offset + limit}")
            else:
                lines.append(value)
            continue
        if key in ("offset", "limit"):
            continue
        if isinstance(value, str):
            lines.append(value)
        else:
            lines.append(json.dumps(value))
    return "\n".join(lines)


def _indent(text: str, prefix: str = "           ") -> str:
    return "\n".join(f"{prefix}{line}" for line in text.split("\n"))


def log_user_message(ctx: LogContext, text: str) -> None:
    """Log an incoming user message."""
    print(f"{GREEN}{_timestamp()} {_format_context(ctx)} {text}{RESET}", flush=True)


def log_tool_start(ctx: LogContext, tool_name: str, label: str, args: dict[str, Any]) -> None:
    """Log the start of a tool execution."""
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \u2193 {tool_name}: {label}{RESET}", flush=True)
    formatted = _format_tool_args(args)
    if formatted:
        print(f"{DIM}{_indent(formatted)}{RESET}", flush=True)


def log_tool_success(ctx: LogContext, tool_name: str, duration_ms: float, result: str) -> None:
    """Log a successful tool execution."""
    duration = f"{duration_ms / 1000:.1f}"
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \u2713 {tool_name} ({duration}s){RESET}", flush=True)
    truncated = _truncate(result, 1000)
    if truncated:
        print(f"{DIM}{_indent(truncated)}{RESET}", flush=True)


def log_tool_error(ctx: LogContext, tool_name: str, duration_ms: float, error: str) -> None:
    """Log a failed tool execution."""
    duration = f"{duration_ms / 1000:.1f}"
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \u2717 {tool_name} ({duration}s){RESET}", flush=True)
    truncated = _truncate(error, 1000)
    print(f"{DIM}{_indent(truncated)}{RESET}", flush=True)


def log_response_start(ctx: LogContext) -> None:
    """Log the start of a streaming response."""
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \u2192 Streaming response...{RESET}", flush=True)


def log_thinking(ctx: LogContext, thinking: str) -> None:
    """Log model thinking/reasoning output."""
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \U0001f4ad Thinking{RESET}", flush=True)
    truncated = _truncate(thinking, 1000)
    print(f"{DIM}{_indent(truncated)}{RESET}", flush=True)


def log_response(ctx: LogContext, text: str) -> None:
    """Log a model response text."""
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \U0001f4ac Response{RESET}", flush=True)
    truncated = _truncate(text, 1000)
    print(f"{DIM}{_indent(truncated)}{RESET}", flush=True)


def log_download_start(ctx: LogContext, filename: str, local_path: str) -> None:
    """Log the start of an attachment download."""
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \u2193 Downloading attachment{RESET}", flush=True)
    print(f"{DIM}           {filename} \u2192 {local_path}{RESET}", flush=True)


def log_download_success(ctx: LogContext, size_kb: float) -> None:
    """Log a successful attachment download."""
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \u2713 Downloaded ({size_kb:,.0f} KB){RESET}", flush=True)


def log_download_error(ctx: LogContext, filename: str, error: str) -> None:
    """Log a failed attachment download."""
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \u2717 Download failed{RESET}", flush=True)
    print(f"{DIM}           {filename}: {error}{RESET}", flush=True)


def log_stop_request(ctx: LogContext) -> None:
    """Log a stop request from the user."""
    print(f"{GREEN}{_timestamp()} {_format_context(ctx)} stop{RESET}", flush=True)
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \u2297 Stop requested - aborting{RESET}", flush=True)


def log_info(message: str) -> None:
    """Log a general info message."""
    print(f"{BLUE}{_timestamp()} [system] {message}{RESET}", flush=True)


def log_warning(message: str, details: str | None = None) -> None:
    """Log a warning message with optional details."""
    print(f"{YELLOW}{_timestamp()} [system] \u26a0 {message}{RESET}", flush=True)
    if details:
        print(f"{DIM}{_indent(details)}{RESET}", flush=True)


def log_agent_error(ctx: LogContext | str, error: str) -> None:
    """Log an agent error. ctx can be a LogContext or the literal 'system'."""
    context_str = "[system]" if isinstance(ctx, str) else _format_context(ctx)
    print(f"{YELLOW}{_timestamp()} {context_str} \u2717 Agent error{RESET}", flush=True)
    print(f"{DIM}{_indent(error)}{RESET}", flush=True)


def _format_tokens(count: int) -> str:
    if count < 1000:
        return str(count)
    if count < 10000:
        return f"{count / 1000:.1f}k"
    if count < 1_000_000:
        return f"{round(count / 1000)}k"
    return f"{count / 1_000_000:.1f}M"


def log_usage_summary(
    ctx: LogContext,
    usage: dict[str, Any],
    context_tokens: int | None = None,
    context_window: int | None = None,
) -> str:
    """Log and return a usage summary string.

    The usage dict must have keys: input, output, cacheRead, cacheWrite, cost.
    cost must have keys: input, output, cacheRead, cacheWrite, total.
    """
    inp: int = usage.get("input", 0)
    out: int = usage.get("output", 0)
    cache_read: int = usage.get("cacheRead", 0)
    cache_write: int = usage.get("cacheWrite", 0)
    cost: dict[str, float] = usage.get("cost", {})
    cost_in: float = cost.get("input", 0.0)
    cost_out: float = cost.get("output", 0.0)
    cost_cr: float = cost.get("cacheRead", 0.0)
    cost_cw: float = cost.get("cacheWrite", 0.0)
    cost_total: float = cost.get("total", 0.0)

    lines: list[str] = []
    lines.append("*Usage Summary*")
    lines.append(f"Tokens: {inp:,} in, {out:,} out")
    if cache_read > 0 or cache_write > 0:
        lines.append(f"Cache: {cache_read:,} read, {cache_write:,} write")
    if context_tokens is not None and context_window is not None:
        pct = f"{(context_tokens / context_window * 100):.1f}"
        lines.append(f"Context: {_format_tokens(context_tokens)} / {_format_tokens(context_window)} ({pct}%)")

    cost_line = f"Cost: ${cost_in:.4f} in, ${cost_out:.4f} out"
    if cache_read > 0 or cache_write > 0:
        cost_line += f", ${cost_cr:.4f} cache read, ${cost_cw:.4f} cache write"
    lines.append(cost_line)
    lines.append(f"*Total: ${cost_total:.4f}*")

    summary = "\n".join(lines)

    # Log to console
    print(f"{YELLOW}{_timestamp()} {_format_context(ctx)} \U0001f4b0 Usage{RESET}", flush=True)
    cache_part = ""
    if cache_read > 0 or cache_write > 0:
        cache_part = f" ({cache_read:,} cache read, {cache_write:,} cache write)"
    print(
        f"{DIM}           {inp:,} in + {out:,} out{cache_part} = ${cost_total:.4f}{RESET}",
        flush=True,
    )

    return summary


def log_startup(working_dir: str, sandbox: str) -> None:
    """Log bot startup information."""
    print("Starting mom bot...", flush=True)
    print(f"  Working directory: {working_dir}", flush=True)
    print(f"  Sandbox: {sandbox}", flush=True)


def log_connected() -> None:
    """Log that the bot is connected and listening."""
    print("\u26a1\ufe0f Mom bot connected and listening!", flush=True)
    print("", flush=True)


def log_disconnected() -> None:
    """Log that the bot has disconnected."""
    print("Mom bot disconnected.", flush=True)


def log_backfill_start(channel_count: int) -> None:
    """Log the start of channel backfill."""
    print(f"{BLUE}{_timestamp()} [system] Backfilling {channel_count} channels...{RESET}", flush=True)


def log_backfill_channel(channel_name: str, message_count: int) -> None:
    """Log progress for a single channel backfill."""
    print(f"{BLUE}{_timestamp()} [system]   #{channel_name}: {message_count} messages{RESET}", flush=True)


def log_backfill_complete(total_messages: int, duration_ms: float) -> None:
    """Log completion of channel backfill."""
    duration = f"{duration_ms / 1000:.1f}"
    print(
        f"{BLUE}{_timestamp()} [system] Backfill complete: {total_messages} messages in {duration}s{RESET}",
        flush=True,
    )
