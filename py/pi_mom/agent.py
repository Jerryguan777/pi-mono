"""Agent runner for pi_mom — port of packages/mom/src/agent.ts."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

import pi_mom.log as log
from pi_mom.context import sync_log_to_context
from pi_mom.sandbox import SandboxConfig, create_executor
from pi_mom.tools import AttachTool, create_mom_tools

if TYPE_CHECKING:
    from pi_mom.slack import ChannelInfo, SlackContext, UserInfo
    from pi_mom.store import ChannelStore

# Hardcoded model — configurable in the future
_DEFAULT_MODEL_PROVIDER = "anthropic"
_DEFAULT_MODEL_ID = "claude-sonnet-4-5"

_IMAGE_MIME_TYPES: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}

_SLACK_MAX_LENGTH = 40_000


@dataclass
class PendingMessage:
    """A pending message that was queued while the agent was busy."""

    user_name: str
    text: str
    attachments: list[dict[str, str]]
    timestamp: int


class AgentRunner(Protocol):
    """Protocol for agent runners that process Slack events."""

    async def run(
        self,
        ctx: SlackContext,
        store: ChannelStore,
        pending_messages: list[PendingMessage] | None = None,
    ) -> dict[str, Any]: ...

    def abort(self) -> None: ...


# Module-level cache: one runner per channel
_channel_runners: dict[str, _ConcreteRunner] = {}


def get_or_create_runner(
    sandbox_config: SandboxConfig,
    channel_id: str,
    channel_dir: str,
) -> AgentRunner:
    """Get or create an AgentRunner for a channel. Runners are cached."""
    existing = _channel_runners.get(channel_id)
    if existing is not None:
        return existing

    runner = _create_runner(sandbox_config, channel_id, channel_dir)
    _channel_runners[channel_id] = runner
    return runner


def _get_image_mime_type(filename: str) -> str | None:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    return _IMAGE_MIME_TYPES.get(ext)


def _get_memory(channel_dir: str) -> str:
    parts: list[str] = []

    workspace_memory_path = os.path.join(channel_dir, "..", "MEMORY.md")
    if os.path.exists(workspace_memory_path):
        try:
            with open(workspace_memory_path, encoding="utf-8") as _f:
                content = _f.read().strip()
            if content:
                parts.append(f"### Global Workspace Memory\n{content}")
        except Exception as exc:
            log.log_warning("Failed to read workspace memory", f"{workspace_memory_path}: {exc}")

    channel_memory_path = os.path.join(channel_dir, "MEMORY.md")
    if os.path.exists(channel_memory_path):
        try:
            with open(channel_memory_path, encoding="utf-8") as _f:
                content = _f.read().strip()
            if content:
                parts.append(f"### Channel-Specific Memory\n{content}")
        except Exception as exc:
            log.log_warning("Failed to read channel memory", f"{channel_memory_path}: {exc}")

    return "\n\n".join(parts) if parts else "(no working memory yet)"


def _load_mom_skills(channel_dir: str, workspace_path: str) -> list[dict[str, str]]:
    """Load skills from workspace and channel-specific skills directories."""
    skill_map: dict[str, dict[str, str]] = {}
    host_workspace_path = os.path.dirname(channel_dir)

    def translate_path(host_path: str) -> str:
        if host_path.startswith(host_workspace_path):
            return workspace_path + host_path[len(host_workspace_path) :]
        return host_path

    def _load_from_dir(skills_dir: str, source: str) -> list[dict[str, str]]:
        skills: list[dict[str, str]] = []
        if not os.path.isdir(skills_dir):
            return skills
        for entry in os.scandir(skills_dir):
            if not entry.is_dir():
                continue
            skill_file = os.path.join(entry.path, "SKILL.md")
            if not os.path.exists(skill_file):
                continue
            try:
                with open(skill_file, encoding="utf-8") as _sf:
                    content = _sf.read()
                name, description = _parse_skill_frontmatter(content)
                if name and description:
                    skills.append(
                        {
                            "name": name,
                            "description": description,
                            "filePath": translate_path(skill_file),
                            "baseDir": translate_path(entry.path),
                            "source": source,
                        }
                    )
            except Exception:
                pass
        return skills

    for skill in _load_from_dir(os.path.join(host_workspace_path, "skills"), "workspace"):
        skill_map[skill["name"]] = skill

    for skill in _load_from_dir(os.path.join(channel_dir, "skills"), "channel"):
        skill_map[skill["name"]] = skill

    return list(skill_map.values())


def _parse_skill_frontmatter(content: str) -> tuple[str, str]:
    """Parse SKILL.md YAML frontmatter for name and description."""
    import re

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return "", ""
    frontmatter = match.group(1)

    name = ""
    description = ""
    for line in frontmatter.split("\n"):
        if line.startswith("name:"):
            name = line[5:].strip()
        elif line.startswith("description:"):
            description = line[12:].strip()
    return name, description


def _format_skills_for_prompt(skills: list[dict[str, str]]) -> str:
    if not skills:
        return "(no skills installed yet)"
    lines: list[str] = []
    for skill in skills:
        lines.append(f"- **{skill['name']}**: {skill['description']}")
        lines.append(f"  Location: {skill['baseDir']}")
    return "\n".join(lines)


def _build_system_prompt(
    workspace_path: str,
    channel_id: str,
    memory: str,
    sandbox_config: SandboxConfig,
    channels: list[ChannelInfo],
    users: list[UserInfo],
    skills: list[dict[str, str]],
) -> str:
    from pi_mom.sandbox import DockerSandboxConfig

    channel_path = f"{workspace_path}/{channel_id}"
    is_docker = isinstance(sandbox_config, DockerSandboxConfig)

    channel_mappings = "\n".join(f"{c.id}\t#{c.name}" for c in channels) if channels else "(no channels loaded)"
    user_mappings = (
        "\n".join(f"{u.id}\t@{u.user_name}\t{u.display_name}" for u in users) if users else "(no users loaded)"
    )

    if is_docker:
        env_desc = (
            "You are running inside a Docker container (Alpine Linux).\n"
            "- Bash working directory: / (use cd or absolute paths)\n"
            "- Install tools with: apk add <package>\n"
            "- Your changes persist across sessions"
        )
    else:
        env_desc = (
            "You are running directly on the host machine.\n"
            f"- Bash working directory: {os.getcwd()}\n"
            "- Be careful with system modifications"
        )

    import datetime

    local_tz = datetime.datetime.now(datetime.UTC).astimezone().strftime("%Z")

    return f"""You are mom, a Slack bot assistant. Be concise. No emojis.

## Context
- For current date/time, use: date
- You have access to previous conversation context including tool results from prior turns.
- For older history beyond your context, search log.jsonl
  (contains user messages and your final responses, but not tool results).

## Slack Formatting (mrkdwn, NOT Markdown)
Bold: *text*, Italic: _text_, Code: `code`, Block: ```code```, Links: <url|text>
Do NOT use **double asterisks** or [markdown](links).

## Slack IDs
Channels: {channel_mappings}

Users: {user_mappings}

When mentioning users, use <@username> format (e.g., <@mario>).

## Environment
{env_desc}

## Workspace Layout
{workspace_path}/
├── MEMORY.md                    # Global memory (all channels)
├── skills/                      # Global CLI tools you create
└── {channel_id}/                # This channel
    ├── MEMORY.md                # Channel-specific memory
    ├── log.jsonl                # Message history (no tool results)
    ├── attachments/             # User-shared files
    ├── scratch/                 # Your working directory
    └── skills/                  # Channel-specific tools

## Skills (Custom CLI Tools)
You can create reusable CLI tools for recurring tasks (email, APIs, data processing, etc.).

### Creating Skills
Store in `{workspace_path}/skills/<name>/` (global) or `{channel_path}/skills/<name>/` (channel-specific).
Each skill directory needs a `SKILL.md` with YAML frontmatter:

```markdown
---
name: skill-name
description: Short description of what this skill does
---

# Skill Name

Usage instructions, examples, etc.
Scripts are in: {{baseDir}}/
```

`name` and `description` are required. Use `{{baseDir}}` as placeholder for the skill's directory path.

### Available Skills
{_format_skills_for_prompt(skills)}

## Events
You can schedule events that wake you up at specific times or when external things happen.
Events are JSON files in `{workspace_path}/events/`.

### Event Types

**Immediate** - Triggers as soon as harness sees the file. Use in scripts/webhooks to signal external events.
```json
{{"type": "immediate", "channelId": "{channel_id}", "text": "New GitHub issue opened"}}
```

**One-shot** - Triggers once at a specific time. Use for reminders.
```json
{{"type": "one-shot", "channelId": "{channel_id}",
 "text": "Remind Mario about dentist", "at": "2025-12-15T09:00:00+01:00"}}
```

**Periodic** - Triggers on a cron schedule. Use for recurring tasks.
```json
{{"type": "periodic", "channelId": "{channel_id}",
 "text": "Check inbox and summarize", "schedule": "0 9 * * 1-5", "timezone": "{local_tz}"}}
```

### Cron Format
`minute hour day-of-month month day-of-week`
- `0 9 * * *` = daily at 9:00
- `0 9 * * 1-5` = weekdays at 9:00
- `30 14 * * 1` = Mondays at 14:30
- `0 0 1 * *` = first of each month at midnight

### Timezones
All `at` timestamps must include offset (e.g., `+01:00`). Periodic events use IANA timezone names.

### Creating Events
Use unique filenames to avoid overwriting existing events. Include a timestamp or random suffix:
```bash
cat > {workspace_path}/events/dentist-reminder-$(date +%s).json << 'EOF'
{{"type": "one-shot", "channelId": "{channel_id}", "text": "Dentist tomorrow", "at": "2025-12-14T09:00:00+01:00"}}
EOF
```

### Managing Events
- List: `ls {workspace_path}/events/`
- View: `cat {workspace_path}/events/foo.json`
- Delete/cancel: `rm {workspace_path}/events/foo.json`

### When Events Trigger
You receive a message like:
```
[EVENT:dentist-reminder.json:one-shot:2025-12-14T09:00:00+01:00] Dentist tomorrow
```
Immediate and one-shot events auto-delete after triggering. Periodic events persist until you delete them.

### Silent Completion
For periodic events where there's nothing to report, respond with just `[SILENT]` (no other text).
This deletes the status message and posts nothing to Slack.

### Limits
Maximum 5 events can be queued. Don't create excessive immediate or periodic events.

## Memory
Write to MEMORY.md files to persist context across conversations.
- Global ({workspace_path}/MEMORY.md): skills, preferences, project info
- Channel ({channel_path}/MEMORY.md): channel-specific decisions, ongoing work
Update when you learn something important or when asked to remember something.

### Current Memory
{memory}

## System Configuration Log
Maintain {workspace_path}/SYSTEM.md to log all environment modifications:
- Installed packages (apk add, npm install, pip install)
- Environment variables set
- Config files modified (~/.gitconfig, cron jobs, etc.)
- Skill dependencies installed

## Log Queries (for older history)
Format: `{{"date":"...","ts":"...","user":"...","userName":"...","text":"...","isBot":false}}`
The log contains user messages and your final responses (not tool calls/results).
{"Install jq: apk add jq" if is_docker else ""}

```bash
# Recent messages
tail -30 log.jsonl | jq -c '{{date: .date[0:19], user: (.userName // .user), text}}'

# Search for specific topic
grep -i "topic" log.jsonl | jq -c '{{date: .date[0:19], user: (.userName // .user), text}}'

# Messages from specific user
grep '"userName":"mario"' log.jsonl | tail -20 | jq -c '{{date: .date[0:19], text}}'
```

## Tools
- bash: Run shell commands (primary tool). Install packages as needed.
- read: Read files
- write: Create/overwrite files
- edit: Surgical file edits
- attach: Share files to Slack

Each tool requires a "label" parameter (shown to user).
"""


def _truncate_str(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _extract_tool_result_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if hasattr(result, "content") and isinstance(result.content, list):
        texts = [p.text for p in result.content if hasattr(p, "type") and p.type == "text" and hasattr(p, "text")]
        if texts:
            return "\n".join(texts)
    return json.dumps(result) if not isinstance(result, str) else result


def _format_tool_args_for_slack(tool_name: str, args: dict[str, Any]) -> str:
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


def _split_for_slack(text: str) -> list[str]:
    if len(text) <= _SLACK_MAX_LENGTH:
        return [text]
    parts: list[str] = []
    remaining = text
    part_num = 1
    while remaining:
        chunk = remaining[: _SLACK_MAX_LENGTH - 50]
        remaining = remaining[_SLACK_MAX_LENGTH - 50 :]
        suffix = f"\n_(continued {part_num}...)_" if remaining else ""
        parts.append(chunk + suffix)
        part_num += 1
    return parts


def _translate_to_host_path(
    container_path: str,
    channel_dir: str,
    workspace_path: str,
    channel_id: str,
) -> str:
    """Translate a container path back to a host path for file operations."""
    if workspace_path == "/workspace":
        prefix = f"/workspace/{channel_id}/"
        if container_path.startswith(prefix):
            return os.path.join(channel_dir, container_path[len(prefix) :])
        if container_path.startswith("/workspace/"):
            return os.path.join(channel_dir, "..", container_path[len("/workspace/") :])
    return container_path


class _ConcreteRunner:
    """Concrete AgentRunner implementation backed by pi_agent.Agent."""

    def __init__(
        self,
        sandbox_config: SandboxConfig,
        channel_id: str,
        channel_dir: str,
    ) -> None:
        from pi_agent.agent import Agent, AgentOptions
        from pi_agent.types import AgentState
        from pi_ai.models import get_model

        self._sandbox_config = sandbox_config
        self._channel_id = channel_id
        self._channel_dir = channel_dir

        executor = create_executor(sandbox_config)
        self._executor = executor
        self._workspace_path = executor.get_workspace_path(os.path.dirname(channel_dir))

        tools = create_mom_tools(executor, self._workspace_path)
        self._attach_tool = next(t for t in tools if isinstance(t, AttachTool))

        # Initial system prompt (updated each run)
        memory = _get_memory(channel_dir)
        skills = _load_mom_skills(channel_dir, self._workspace_path)
        system_prompt = _build_system_prompt(self._workspace_path, channel_id, memory, sandbox_config, [], [], skills)

        # Get configured model
        try:
            model = get_model(_DEFAULT_MODEL_PROVIDER, _DEFAULT_MODEL_ID)
            if model is None:
                from pi_ai.types import Model

                model = Model()
        except Exception:
            from pi_ai.types import Model

            model = Model()

        initial_state = AgentState(
            system_prompt=system_prompt,
            model=model,
            thinking_level="off",
            tools=tools,
            messages=[],
            is_streaming=False,
            stream_message=None,
            pending_tool_calls=set(),
        )

        self._agent = Agent(
            AgentOptions(
                initial_state=initial_state,
            )
        )

        # Load existing messages from context.jsonl
        context_file = os.path.join(channel_dir, "context.jsonl")
        self._context_file = context_file
        saved_messages = self._load_messages()
        if saved_messages:
            self._agent.replace_messages(saved_messages)
            log.log_info(f"[{channel_id}] Loaded {len(saved_messages)} messages from context.jsonl")

        # Per-run mutable state
        self._current_ctx: Any = None
        self._log_ctx: log.LogContext | None = None
        self._pending_tools: dict[str, dict[str, Any]] = {}
        self._total_usage: dict[str, Any] = _fresh_usage()
        self._stop_reason = "stop"
        self._error_message: str | None = None

        # Subscribe to agent events once
        self._agent.subscribe(self._on_event)

        # Queue chain for Slack API calls
        self._queue_chain: Any = None
        self._enqueue_fn: Any = None
        self._enqueue_message_fn: Any = None

    def _load_messages(self) -> list[Any]:
        """Load messages from context.jsonl."""
        if not os.path.exists(self._context_file):
            return []
        try:
            from pi_ai.types import UserMessage

            messages: list[Any] = []
            with open(self._context_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        role = data.get("role")
                        if role == "user":
                            from pi_ai.types import ImageContent, TextContent

                            content_raw = data.get("content", "")
                            msg_content: list[TextContent | ImageContent]
                            if isinstance(content_raw, str):
                                msg_content = [TextContent(text=content_raw)]
                            elif isinstance(content_raw, list):
                                msg_content = [
                                    TextContent(text=p.get("text", "")) for p in content_raw if isinstance(p, dict)
                                ]
                            else:
                                msg_content = []
                            msg = UserMessage(content=msg_content, timestamp=data.get("timestamp", time.time() * 1000))
                            messages.append(msg)
                        # Only load user messages for now to avoid complex reconstruction
                    except Exception:
                        pass
            return messages
        except Exception:
            return []

    def _save_messages(self) -> None:
        """Save current messages to context.jsonl."""
        try:
            dir_part = os.path.dirname(self._context_file) or "."
            os.makedirs(dir_part, exist_ok=True)
            with open(self._context_file, "w", encoding="utf-8") as f:
                for msg in self._agent.state.messages:
                    role = getattr(msg, "role", None)
                    content = getattr(msg, "content", None)
                    if role and content:
                        entry: dict[str, Any] = {"role": role}
                        if isinstance(content, str):
                            entry["content"] = content
                        elif isinstance(content, list):
                            serialized = []
                            for part in content:
                                if hasattr(part, "type") and hasattr(part, "text"):
                                    serialized.append({"type": part.type, "text": part.text})
                            entry["content"] = serialized
                        entry["timestamp"] = getattr(msg, "timestamp", time.time() * 1000)
                        f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            log.log_warning("Failed to save context.jsonl", str(exc))

    def _on_event(self, event: Any) -> None:
        """Handle agent events and post updates to Slack."""
        if self._current_ctx is None or self._log_ctx is None:
            return

        ctx = self._current_ctx
        log_ctx = self._log_ctx

        event_type: str = getattr(event, "type", "")

        if event_type == "tool_execution_start":
            args: dict[str, Any] = getattr(event, "args", {})
            label: str = str(args.get("label") or getattr(event, "tool_name", ""))
            tool_call_id: str = getattr(event, "tool_call_id", "")

            self._pending_tools[tool_call_id] = {
                "toolName": getattr(event, "tool_name", ""),
                "args": args,
                "startTime": time.time() * 1000,
            }

            log.log_tool_start(log_ctx, getattr(event, "tool_name", ""), label, args)
            if self._enqueue_fn:
                self._enqueue_fn(lambda _ctx=ctx, _lbl=label: _ctx.respond(f"_\u2192 {_lbl}_", False), "tool label")

        elif event_type == "tool_execution_end":
            result = getattr(event, "result", None)
            result_str = _extract_tool_result_text(result)
            tool_call_id = getattr(event, "tool_call_id", "")
            pending = self._pending_tools.pop(tool_call_id, None)
            duration_ms = (time.time() * 1000 - pending["startTime"]) if pending else 0

            is_error: bool = getattr(event, "is_error", False)
            tool_name: str = getattr(event, "tool_name", "")

            if is_error:
                log.log_tool_error(log_ctx, tool_name, duration_ms, result_str)
            else:
                log.log_tool_success(log_ctx, tool_name, duration_ms, result_str)

            # Post to thread
            label_str = (pending["args"].get("label") if pending else None) or ""
            args_formatted = _format_tool_args_for_slack(tool_name, pending["args"]) if pending else "(args not found)"
            duration_s = f"{duration_ms / 1000:.1f}"
            thread_msg = f"*{'✗' if is_error else '✓'} {tool_name}*"
            if label_str:
                thread_msg += f": {label_str}"
            thread_msg += f" ({duration_s}s)\n"
            if args_formatted:
                thread_msg += f"```\n{args_formatted}\n```\n"
            thread_msg += f"*Result:*\n```\n{result_str}\n```"

            if self._enqueue_message_fn:
                self._enqueue_message_fn(thread_msg, "thread", "tool result thread", False)

            if is_error and self._enqueue_fn:
                short_err = _truncate_str(result_str, 200)
                self._enqueue_fn(
                    lambda _ctx=ctx, _e=short_err: _ctx.respond(f"_Error: {_e}_", False),
                    "tool error",
                )

        elif event_type == "message_start":
            msg = getattr(event, "message", None)
            if msg and getattr(msg, "role", None) == "assistant":
                log.log_response_start(log_ctx)

        elif event_type == "message_end":
            msg = getattr(event, "message", None)
            if msg and getattr(msg, "role", None) == "assistant":
                stop_reason = getattr(msg, "stop_reason", None)
                if stop_reason:
                    self._stop_reason = stop_reason
                error_message = getattr(msg, "error_message", None)
                if error_message:
                    self._error_message = error_message

                usage = getattr(msg, "usage", None)
                if usage:
                    self._total_usage["input"] += getattr(usage, "input", 0)
                    self._total_usage["output"] += getattr(usage, "output", 0)
                    self._total_usage["cacheRead"] += getattr(usage, "cache_read", 0)
                    self._total_usage["cacheWrite"] += getattr(usage, "cache_write", 0)
                    cost = getattr(usage, "cost", None)
                    if cost:
                        self._total_usage["cost"]["input"] += getattr(cost, "input", 0)
                        self._total_usage["cost"]["output"] += getattr(cost, "output", 0)
                        self._total_usage["cost"]["cacheRead"] += getattr(cost, "cache_read", 0)
                        self._total_usage["cost"]["cacheWrite"] += getattr(cost, "cache_write", 0)
                        self._total_usage["cost"]["total"] += getattr(cost, "total", 0)

                content = getattr(msg, "content", [])
                thinking_parts: list[str] = []
                text_parts: list[str] = []
                for part in content:
                    if getattr(part, "type", None) == "thinking":
                        thinking_parts.append(getattr(part, "thinking", ""))
                    elif getattr(part, "type", None) == "text":
                        text_parts.append(getattr(part, "text", ""))

                text_combined = "\n".join(text_parts)

                for thinking in thinking_parts:
                    log.log_thinking(log_ctx, thinking)
                    if self._enqueue_message_fn:
                        self._enqueue_message_fn(f"_{thinking}_", "main", "thinking main")
                        self._enqueue_message_fn(f"_{thinking}_", "thread", "thinking thread", False)

                if text_combined.strip():
                    log.log_response(log_ctx, text_combined)
                    if self._enqueue_message_fn:
                        self._enqueue_message_fn(text_combined, "main", "response main")
                        self._enqueue_message_fn(text_combined, "thread", "response thread", False)

        elif event_type == "auto_compaction_start":
            reason = getattr(event, "reason", "unknown")
            log.log_info(f"Auto-compaction started (reason: {reason})")
            if self._enqueue_fn:
                self._enqueue_fn(
                    lambda _ctx=ctx: _ctx.respond("_Compacting context..._", False),
                    "compaction start",
                )

        elif event_type == "auto_compaction_end":
            result = getattr(event, "result", None)
            if result:
                log.log_info(f"Auto-compaction complete: {getattr(result, 'tokensBefore', '?')} tokens compacted")
            elif getattr(event, "aborted", False):
                log.log_info("Auto-compaction aborted")

        elif event_type == "auto_retry_start":
            attempt = getattr(event, "attempt", "?")
            max_attempts = getattr(event, "max_attempts", "?")
            err_msg = getattr(event, "error_message", "")
            log.log_warning(f"Retrying ({attempt}/{max_attempts})", err_msg)
            if self._enqueue_fn:
                self._enqueue_fn(
                    lambda _ctx=ctx, _a=attempt, _m=max_attempts: _ctx.respond(f"_Retrying ({_a}/{_m})..._", False),
                    "retry",
                )

    async def run(
        self,
        ctx: SlackContext,
        store: ChannelStore,
        pending_messages: list[PendingMessage] | None = None,
    ) -> dict[str, Any]:
        """Run the agent for one user turn."""
        os.makedirs(self._channel_dir, exist_ok=True)

        # Sync messages from log.jsonl that arrived while we were offline/busy
        current_messages = list(self._agent.state.messages)
        new_msgs = sync_log_to_context(current_messages, self._channel_dir, ctx.message.ts)
        if new_msgs:
            for m in new_msgs:
                self._agent.append_message(m)
            log.log_info(f"[{self._channel_id}] Synced {len(new_msgs)} messages from log.jsonl")

        # Update system prompt with fresh data
        memory = _get_memory(self._channel_dir)
        skills = _load_mom_skills(self._channel_dir, self._workspace_path)
        system_prompt = _build_system_prompt(
            self._workspace_path,
            self._channel_id,
            memory,
            self._sandbox_config,
            ctx.channels,
            ctx.users,
            skills,
        )
        self._agent.set_system_prompt(system_prompt)

        # Set up file upload function
        def _upload_fn(file_path: str, title: str | None = None) -> Any:
            host_path = _translate_to_host_path(file_path, self._channel_dir, self._workspace_path, self._channel_id)
            return ctx.upload_file(host_path, title)

        self._attach_tool.set_upload_fn(_upload_fn)

        # Reset per-run state
        self._current_ctx = ctx
        self._log_ctx = log.LogContext(
            channel_id=ctx.message.channel,
            user_name=ctx.message.user_name,
            channel_name=ctx.channel_name,
        )
        self._pending_tools.clear()
        self._total_usage = _fresh_usage()
        self._stop_reason = "stop"
        self._error_message = None

        async def _run_queued(fn: Any, error_context: str) -> None:
            try:
                await fn()
            except Exception as exc:
                import contextlib

                err_msg = str(exc)
                log.log_warning(f"Slack API error ({error_context})", err_msg)
                with contextlib.suppress(Exception):
                    await ctx.respond_in_thread(f"_Error: {err_msg}_")

        # We use an asyncio Queue to serialize Slack API calls
        slack_queue: asyncio.Queue[tuple[Any, str]] = asyncio.Queue()
        slack_queue_running = [False]

        async def _drain_slack_queue() -> None:
            if slack_queue_running[0]:
                return
            slack_queue_running[0] = True
            while not slack_queue.empty():
                fn, error_ctx = await slack_queue.get()
                try:
                    await _run_queued(fn, error_ctx)
                finally:
                    slack_queue.task_done()
            slack_queue_running[0] = False

        _drain_tasks: set[asyncio.Task[None]] = set()

        def _enqueue(fn: Any, error_ctx: str) -> None:
            slack_queue.put_nowait((fn, error_ctx))
            task = asyncio.create_task(_drain_slack_queue())
            _drain_tasks.add(task)
            task.add_done_callback(_drain_tasks.discard)

        def _enqueue_message(text: str, target: str, error_ctx: str, do_log: bool = True) -> None:
            for part in _split_for_slack(text):
                if target == "main":
                    _enqueue(lambda _p=part, _dl=do_log: ctx.respond(_p, _dl), error_ctx)
                else:
                    _enqueue(lambda _p=part: ctx.respond_in_thread(_p), error_ctx)

        self._enqueue_fn = _enqueue
        self._enqueue_message_fn = _enqueue_message

        log.log_info(f"Context sizes - system: {len(system_prompt)} chars, memory: {len(memory)} chars")
        log.log_info(f"Channels: {len(ctx.channels)}, Users: {len(ctx.users)}")

        # Build user message with timestamp and username prefix
        import datetime

        now_local = datetime.datetime.now().astimezone()
        ts_str = now_local.strftime("%Y-%m-%d %H:%M:%S%z")
        # Insert colon in timezone offset: +0100 -> +01:00
        if len(ts_str) > 5 and ts_str[-5] in ("+", "-"):
            ts_str = ts_str[:-2] + ":" + ts_str[-2:]

        user_name = ctx.message.user_name or "unknown"
        user_message_text = f"[{ts_str}] [{user_name}]: {ctx.message.text}"

        from pi_ai.types import ImageContent as AIImageContent

        image_attachments: list[AIImageContent] = []
        non_image_paths: list[str] = []

        for attach in ctx.message.attachments or []:
            local = attach.get("local", "")
            full_path = f"{self._workspace_path}/{local}"
            mime = _get_image_mime_type(local)
            if mime and os.path.exists(full_path):
                try:
                    with open(full_path, "rb") as f:
                        b64_data = base64.b64encode(f.read()).decode()
                    image_attachments.append(AIImageContent(data=b64_data, mime_type=mime))
                except Exception:
                    non_image_paths.append(full_path)
            else:
                non_image_paths.append(full_path)

        if non_image_paths:
            user_message_text += "\n\n<slack_attachments>\n" + "\n".join(non_image_paths) + "\n</slack_attachments>"

        # Debug: write context to last_prompt.jsonl
        try:
            debug_ctx = {
                "systemPrompt": system_prompt,
                "newUserMessage": user_message_text,
                "imageAttachmentCount": len(image_attachments),
            }
            with open(os.path.join(self._channel_dir, "last_prompt.jsonl"), "w", encoding="utf-8") as dbg_f:
                json.dump(debug_ctx, dbg_f, indent=2)
        except Exception:
            pass

        await self._agent.prompt(user_message_text, image_attachments if image_attachments else None)

        # Drain remaining queue
        await slack_queue.join()

        # Handle error case
        if self._stop_reason == "error" and self._error_message:
            try:
                await ctx.replace_message("_Sorry, something went wrong_")
                await ctx.respond_in_thread(f"_Error: {self._error_message}_")
            except Exception as exc:
                log.log_warning("Failed to post error message", str(exc))
        else:
            # Final message update
            messages = self._agent.state.messages
            last_assistant = next(
                (m for m in reversed(messages) if getattr(m, "role", None) == "assistant"),
                None,
            )
            final_text = ""
            if last_assistant:
                content = getattr(last_assistant, "content", [])
                texts = [getattr(p, "text", "") for p in content if getattr(p, "type", None) == "text"]
                final_text = "\n".join(texts)

            if final_text.strip() == "[SILENT]" or final_text.strip().startswith("[SILENT]"):
                try:
                    await ctx.delete_message()
                    log.log_info("Silent response - deleted message and thread")
                except Exception as exc:
                    log.log_warning("Failed to delete message for silent response", str(exc))
            elif final_text.strip():
                try:
                    main_text = (
                        final_text[: _SLACK_MAX_LENGTH - 50] + "\n\n_(see thread for full response)_"
                        if len(final_text) > _SLACK_MAX_LENGTH
                        else final_text
                    )
                    await ctx.replace_message(main_text)
                except Exception as exc:
                    log.log_warning("Failed to replace message with final text", str(exc))

        # Log usage summary
        if self._total_usage["cost"]["total"] > 0 and self._log_ctx:
            summary = log.log_usage_summary(self._log_ctx, self._total_usage)
            _enqueue(lambda _ctx=ctx, _s=summary: _ctx.respond_in_thread(_s), "usage summary")
            await slack_queue.join()

        # Save messages
        self._save_messages()

        # Clear run state
        self._current_ctx = None
        self._log_ctx = None
        self._enqueue_fn = None
        self._enqueue_message_fn = None

        return {"stopReason": self._stop_reason, "errorMessage": self._error_message}

    def abort(self) -> None:
        self._agent.abort()


def _fresh_usage() -> dict[str, Any]:
    return {
        "input": 0,
        "output": 0,
        "cacheRead": 0,
        "cacheWrite": 0,
        "cost": {"input": 0.0, "output": 0.0, "cacheRead": 0.0, "cacheWrite": 0.0, "total": 0.0},
    }


def _create_runner(
    sandbox_config: SandboxConfig,
    channel_id: str,
    channel_dir: str,
) -> _ConcreteRunner:
    return _ConcreteRunner(sandbox_config, channel_id, channel_dir)
