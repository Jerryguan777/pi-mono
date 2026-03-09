"""Context management for pi_mom — port of packages/mom/src/context.ts."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from pi_agent.types import AgentMessage
from pi_ai.types import UserMessage

# ============================================================================
# Sync log.jsonl to message list
# ============================================================================


@dataclass
class _LogMessage:
    date: str | None
    ts: str | None
    user: str | None
    user_name: str | None
    text: str | None
    is_bot: bool


def sync_log_to_context(
    context_messages: list[AgentMessage],
    channel_dir: str,
    exclude_slack_ts: str | None = None,
) -> list[AgentMessage]:
    """Read log.jsonl and return user messages not already in context_messages.

    Returns a list of new AgentMessage objects to append to the context.
    """
    log_file = os.path.join(channel_dir, "log.jsonl")
    if not os.path.exists(log_file):
        return []

    # Build set of existing message content from context
    existing_messages: set[str] = set()
    _ts_prefix_re = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}\] ")
    _attachments_marker = "\n\n<slack_attachments>\n"

    for msg in context_messages:
        if not hasattr(msg, "role"):
            continue
        if msg.role != "user":
            continue
        content = getattr(msg, "content", None)
        if content is None:
            continue
        if isinstance(content, str):
            normalized = _ts_prefix_re.sub("", content)
            idx = normalized.find(_attachments_marker)
            if idx != -1:
                normalized = normalized[:idx]
            existing_messages.add(normalized)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                    normalized = _ts_prefix_re.sub("", part["text"])
                    idx = normalized.find(_attachments_marker)
                    if idx != -1:
                        normalized = normalized[:idx]
                    existing_messages.add(normalized)
                elif hasattr(part, "type") and getattr(part, "type", None) == "text":
                    raw = getattr(part, "text", "")
                    normalized = _ts_prefix_re.sub("", raw)
                    idx = normalized.find(_attachments_marker)
                    if idx != -1:
                        normalized = normalized[:idx]
                    existing_messages.add(normalized)

    # Read log.jsonl and find user messages not in context
    with open(log_file, encoding="utf-8") as f:
        log_content = f.read()

    log_lines = [ln for ln in log_content.strip().split("\n") if ln]

    new_messages: list[tuple[int, UserMessage]] = []

    for line in log_lines:
        try:
            raw = json.loads(line)
            slack_ts: str | None = raw.get("ts")
            date: str | None = raw.get("date")
            if not slack_ts or not date:
                continue

            # Skip the current message being processed (will be added via prompt())
            if exclude_slack_ts and slack_ts == exclude_slack_ts:
                continue

            # Skip bot messages — added through agent flow
            if raw.get("isBot"):
                continue

            # Build the message text as it would appear in context
            user_name: str | None = raw.get("userName") or raw.get("user") or "unknown"
            text: str = raw.get("text") or ""
            message_text = f"[{user_name}]: {text}"

            # Skip if this exact message text is already in context
            if message_text in existing_messages:
                continue

            try:
                import datetime

                msg_time = int(datetime.datetime.fromisoformat(date).timestamp() * 1000)
            except Exception:
                import time

                msg_time = int(time.time() * 1000)

            from pi_ai.types import TextContent

            user_msg = UserMessage(
                content=[TextContent(text=message_text)],
                timestamp=float(msg_time),
            )

            new_messages.append((msg_time, user_msg))
            existing_messages.add(message_text)  # Track to avoid duplicates within this sync
        except Exception:
            continue

    if not new_messages:
        return []

    # Sort by timestamp and return
    new_messages.sort(key=lambda x: x[0])
    return [msg for _, msg in new_messages]


# ============================================================================
# MomSettingsManager
# ============================================================================


@dataclass
class MomCompactionSettings:
    """Settings for context compaction."""

    enabled: bool
    reserve_tokens: int
    keep_recent_tokens: int


@dataclass
class MomRetrySettings:
    """Settings for automatic retries on failure."""

    enabled: bool
    max_retries: int
    base_delay_ms: int


@dataclass
class MomSettings:
    """Top-level settings for mom."""

    default_provider: str | None = None
    default_model: str | None = None
    default_thinking_level: str | None = None  # "off" | "minimal" | "low" | "medium" | "high"
    compaction: MomCompactionSettings | None = None
    retry: MomRetrySettings | None = None


def sync_log_to_session_manager(
    context_messages: list[AgentMessage],
    channel_dir: str,
    exclude_slack_ts: str | None = None,
) -> list[AgentMessage]:
    """Alias for sync_log_to_context (matches TS export name syncLogToSessionManager)."""
    return sync_log_to_context(context_messages, channel_dir, exclude_slack_ts)


_DEFAULT_COMPACTION = MomCompactionSettings(
    enabled=True,
    reserve_tokens=16384,
    keep_recent_tokens=20000,
)

_DEFAULT_RETRY = MomRetrySettings(
    enabled=True,
    max_retries=3,
    base_delay_ms=2000,
)


class MomSettingsManager:
    """Manages mom settings stored in the workspace root directory."""

    def __init__(self, workspace_dir: str) -> None:
        self._settings_path = os.path.join(workspace_dir, "settings.json")
        self._settings: dict[str, object] = self._load()

    def _load(self) -> dict[str, object]:
        if not os.path.exists(self._settings_path):
            return {}
        try:
            with open(self._settings_path, encoding="utf-8") as f:
                data = json.load(f)
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self) -> None:
        try:
            dir_path = os.path.dirname(self._settings_path)
            os.makedirs(dir_path, exist_ok=True)
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as exc:
            print(f"Warning: Could not save settings file: {exc}")

    def get_compaction_settings(self) -> MomCompactionSettings:
        comp = self._settings.get("compaction")
        if isinstance(comp, dict):
            return MomCompactionSettings(
                enabled=bool(comp.get("enabled", _DEFAULT_COMPACTION.enabled)),
                reserve_tokens=int(comp.get("reserveTokens", _DEFAULT_COMPACTION.reserve_tokens)),
                keep_recent_tokens=int(comp.get("keepRecentTokens", _DEFAULT_COMPACTION.keep_recent_tokens)),
            )
        return MomCompactionSettings(
            enabled=_DEFAULT_COMPACTION.enabled,
            reserve_tokens=_DEFAULT_COMPACTION.reserve_tokens,
            keep_recent_tokens=_DEFAULT_COMPACTION.keep_recent_tokens,
        )

    def get_compaction_enabled(self) -> bool:
        comp = self._settings.get("compaction")
        if isinstance(comp, dict):
            return bool(comp.get("enabled", _DEFAULT_COMPACTION.enabled))
        return _DEFAULT_COMPACTION.enabled

    def set_compaction_enabled(self, enabled: bool) -> None:
        comp = self._settings.get("compaction")
        if not isinstance(comp, dict):
            comp = {}
        comp["enabled"] = enabled
        self._settings["compaction"] = comp
        self._save()

    def get_retry_settings(self) -> MomRetrySettings:
        retry = self._settings.get("retry")
        if isinstance(retry, dict):
            return MomRetrySettings(
                enabled=bool(retry.get("enabled", _DEFAULT_RETRY.enabled)),
                max_retries=int(retry.get("maxRetries", _DEFAULT_RETRY.max_retries)),
                base_delay_ms=int(retry.get("baseDelayMs", _DEFAULT_RETRY.base_delay_ms)),
            )
        return MomRetrySettings(
            enabled=_DEFAULT_RETRY.enabled,
            max_retries=_DEFAULT_RETRY.max_retries,
            base_delay_ms=_DEFAULT_RETRY.base_delay_ms,
        )

    def get_retry_enabled(self) -> bool:
        retry = self._settings.get("retry")
        if isinstance(retry, dict):
            return bool(retry.get("enabled", _DEFAULT_RETRY.enabled))
        return _DEFAULT_RETRY.enabled

    def set_retry_enabled(self, enabled: bool) -> None:
        retry = self._settings.get("retry")
        if not isinstance(retry, dict):
            retry = {}
        retry["enabled"] = enabled
        self._settings["retry"] = retry
        self._save()

    def get_default_model(self) -> str | None:
        v = self._settings.get("defaultModel")
        return str(v) if v is not None else None

    def get_default_provider(self) -> str | None:
        v = self._settings.get("defaultProvider")
        return str(v) if v is not None else None

    def set_default_model_and_provider(self, provider: str, model_id: str) -> None:
        self._settings["defaultProvider"] = provider
        self._settings["defaultModel"] = model_id
        self._save()

    def get_default_thinking_level(self) -> str:
        v = self._settings.get("defaultThinkingLevel")
        return str(v) if v is not None else "off"

    def set_default_thinking_level(self, level: str) -> None:
        self._settings["defaultThinkingLevel"] = level
        self._save()
