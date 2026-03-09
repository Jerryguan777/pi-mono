"""Footer component: shows pwd/branch/session, token stats, context usage, extension statuses."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any

from pi_coding_agent.modes.interactive.components._theme import theme
from pi_tui.utils import truncate_to_width, visible_width

if TYPE_CHECKING:
    pass


def _sanitize_status_text(text: str) -> str:
    """Replace control characters and collapse whitespace for single-line display."""
    return re.sub(r" +", " ", text.replace("\r", " ").replace("\n", " ").replace("\t", " ")).strip()


def _format_tokens(count: int) -> str:
    if count < 1000:
        return str(count)
    if count < 10_000:
        return f"{count / 1000:.1f}k"
    if count < 1_000_000:
        return f"{round(count / 1000)}k"
    if count < 10_000_000:
        return f"{count / 1_000_000:.1f}M"
    return f"{round(count / 1_000_000)}M"


class FooterComponent:
    """Renders a two-line footer with path, token stats, context usage, and extension statuses."""

    def __init__(self, session: Any, footer_data: Any) -> None:
        self._session = session
        self._footer_data = footer_data
        self._auto_compact_enabled = True

    def set_auto_compact_enabled(self, enabled: bool) -> None:
        self._auto_compact_enabled = enabled

    def invalidate(self) -> None:
        pass  # git branch cached/invalidated by provider

    def dispose(self) -> None:
        pass  # cleanup handled by provider

    def render(self, width: int) -> list[str]:
        session = self._session
        state = getattr(session, "state", None)

        total_input = 0
        total_output = 0
        total_cache_read = 0
        total_cache_write = 0
        total_cost = 0.0

        session_manager = getattr(session, "session_manager", None)
        if session_manager is not None:
            for entry in session_manager.get_entries():
                if getattr(entry, "type", None) == "message":
                    msg = getattr(entry, "message", None)
                    if msg is not None and getattr(msg, "role", None) == "assistant":
                        usage = getattr(msg, "usage", None)
                        if usage is not None:
                            total_input += getattr(usage, "input", 0)
                            total_output += getattr(usage, "output", 0)
                            total_cache_read += getattr(usage, "cache_read", 0)
                            total_cache_write += getattr(usage, "cache_write", 0)
                            cost = getattr(usage, "cost", None)
                            if cost is not None:
                                total_cost += getattr(cost, "total", 0.0)

        context_usage = getattr(session, "get_context_usage", lambda: None)()
        model = getattr(state, "model", None) if state is not None else None
        context_window = getattr(context_usage, "context_window", None) or getattr(model, "context_window", 0) or 0
        context_percent_value: float = getattr(context_usage, "percent", 0.0) or 0.0
        context_percent_known = getattr(context_usage, "percent", None) is not None

        # Build pwd with ~ substitution, optional branch and session name
        pwd = os.getcwd()
        home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or ""
        if home and pwd.startswith(home):
            pwd = f"~{pwd[len(home) :]}"

        branch = self._footer_data.get_git_branch() if hasattr(self._footer_data, "get_git_branch") else None
        if branch:
            pwd = f"{pwd} ({branch})"

        has_get_name = session_manager and hasattr(session_manager, "get_session_name")
        session_name = session_manager.get_session_name() if has_get_name else None  # type: ignore[union-attr]
        if session_name:
            pwd = f"{pwd} \u2022 {session_name}"

        if len(pwd) > width:
            half = width // 2 - 2
            pwd = f"{pwd[:half]}...{pwd[-(half - 1) :]}" if half > 1 else pwd[: max(1, width)]

        # Build stats left side
        stats_parts: list[str] = []
        if total_input:
            stats_parts.append(f"\u2191{_format_tokens(total_input)}")
        if total_output:
            stats_parts.append(f"\u2193{_format_tokens(total_output)}")
        if total_cache_read:
            stats_parts.append(f"R{_format_tokens(total_cache_read)}")
        if total_cache_write:
            stats_parts.append(f"W{_format_tokens(total_cache_write)}")

        model_registry = getattr(session, "model_registry", None)
        using_subscription = (
            model_registry.is_using_oauth(model)
            if model_registry and model and hasattr(model_registry, "is_using_oauth")
            else False
        )
        if total_cost or using_subscription:
            cost_str = f"${total_cost:.3f}" + (" (sub)" if using_subscription else "")
            stats_parts.append(cost_str)

        auto_indicator = " (auto)" if self._auto_compact_enabled else ""
        if not context_percent_known:
            ctx_display = f"?/{_format_tokens(context_window)}{auto_indicator}"
        else:
            ctx_display = f"{context_percent_value:.1f}%/{_format_tokens(context_window)}{auto_indicator}"

        if context_percent_value > 90:
            context_percent_str = theme.fg("error", ctx_display)
        elif context_percent_value > 70:
            context_percent_str = theme.fg("warning", ctx_display)
        else:
            context_percent_str = ctx_display
        stats_parts.append(context_percent_str)

        stats_left = " ".join(stats_parts)

        # Build right side
        model_name = getattr(model, "id", None) or "no-model"
        thinking_level = getattr(state, "thinking_level", None) if state is not None else None
        if model and getattr(model, "reasoning", False):
            level = thinking_level or "off"
            thinking_suffix = "thinking off" if level == "off" else level
            right_without_provider = f"{model_name} \u2022 {thinking_suffix}"
        else:
            right_without_provider = model_name

        right_side = right_without_provider
        footer_data = self._footer_data
        available_provider_count = (
            footer_data.get_available_provider_count() if hasattr(footer_data, "get_available_provider_count") else 1
        )
        if available_provider_count > 1 and model:
            provider = getattr(model, "provider", "")
            candidate = f"({provider}) {right_without_provider}"
            stats_left_width = visible_width(stats_left)
            if stats_left_width + 2 + visible_width(candidate) <= width:
                right_side = candidate

        stats_left_width = visible_width(stats_left)
        right_side_width = visible_width(right_side)
        total_needed = stats_left_width + 2 + right_side_width

        if total_needed <= width:
            padding = " " * (width - stats_left_width - right_side_width)
            stats_line = stats_left + padding + right_side
        elif width - stats_left_width - 2 > 3:
            available = width - stats_left_width - 2
            plain_right = re.sub(r"\x1b\[[0-9;]*m", "", right_side)
            truncated = plain_right[:available]
            padding = " " * (width - stats_left_width - len(truncated))
            stats_line = stats_left + padding + truncated
        else:
            stats_line = stats_left

        dim_stats_left = theme.fg("dim", stats_left)
        remainder = stats_line[len(stats_left) :]
        dim_remainder = theme.fg("dim", remainder)

        lines = [theme.fg("dim", pwd), dim_stats_left + dim_remainder]

        extension_statuses: dict[str, str] = {}
        if hasattr(footer_data, "get_extension_statuses"):
            statuses = footer_data.get_extension_statuses()
            if hasattr(statuses, "items"):
                extension_statuses = dict(statuses.items())

        if extension_statuses:
            sorted_statuses = [_sanitize_status_text(v) for _, v in sorted(extension_statuses.items())]
            status_line = " ".join(sorted_statuses)
            lines.append(truncate_to_width(status_line, width, theme.fg("dim", "...")))

        return lines
