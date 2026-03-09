"""CLI argument parsing and help display.

Python port of packages/coding-agent/src/cli/args.ts.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Literal

from pi_coding_agent.config import APP_NAME, CONFIG_DIR_NAME, ENV_AGENT_DIR

Mode = Literal["text", "json", "rpc"]
ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]

VALID_THINKING_LEVELS: tuple[str, ...] = ("off", "minimal", "low", "medium", "high", "xhigh")


def is_valid_thinking_level(level: str) -> bool:
    """Return True if level is a valid thinking level string."""
    return level in VALID_THINKING_LEVELS


@dataclass
class Args:
    """Parsed CLI arguments."""

    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    system_prompt: str | None = None
    append_system_prompt: str | None = None
    thinking: ThinkingLevel | None = None
    continue_session: bool = False
    resume: bool = False
    help: bool = False
    version: bool = False
    mode: Mode | None = None
    no_session: bool = False
    session: str | None = None
    session_dir: str | None = None
    models: list[str] | None = None
    tools: list[str] | None = None
    no_tools: bool = False
    extensions: list[str] | None = None
    no_extensions: bool = False
    print_mode: bool = False
    export: str | None = None
    no_skills: bool = False
    skills: list[str] | None = None
    prompt_templates: list[str] | None = None
    no_prompt_templates: bool = False
    themes: list[str] | None = None
    no_themes: bool = False
    list_models: str | bool | None = None
    verbose: bool = False
    messages: list[str] = field(default_factory=list)
    file_args: list[str] = field(default_factory=list)
    # Unknown flags (potentially extension flags) - map of flag name to value
    unknown_flags: dict[str, bool | str] = field(default_factory=dict)


def parse_args(
    args: list[str],
    extension_flags: dict[str, dict[str, str]] | None = None,
) -> Args:
    """Parse command-line arguments into an Args dataclass.

    Args:
        args: Raw argument list (typically sys.argv[1:]).
        extension_flags: Optional map of flag name to {"type": "boolean"|"string"}
            for extension-registered flags.

    Returns:
        Populated Args dataclass.
    """
    result = Args()
    i = 0
    while i < len(args):
        arg = args[i]

        if arg in ("--help", "-h"):
            result.help = True
        elif arg in ("--version", "-v"):
            result.version = True
        elif arg == "--mode" and i + 1 < len(args):
            i += 1
            mode_val = args[i]
            if mode_val in ("text", "json", "rpc"):
                result.mode = mode_val  # type: ignore[assignment]
        elif arg in ("--continue", "-c"):
            result.continue_session = True
        elif arg in ("--resume", "-r"):
            result.resume = True
        elif arg == "--provider" and i + 1 < len(args):
            i += 1
            result.provider = args[i]
        elif arg == "--model" and i + 1 < len(args):
            i += 1
            result.model = args[i]
        elif arg == "--api-key" and i + 1 < len(args):
            i += 1
            result.api_key = args[i]
        elif arg == "--system-prompt" and i + 1 < len(args):
            i += 1
            result.system_prompt = args[i]
        elif arg == "--append-system-prompt" and i + 1 < len(args):
            i += 1
            result.append_system_prompt = args[i]
        elif arg == "--no-session":
            result.no_session = True
        elif arg == "--session" and i + 1 < len(args):
            i += 1
            result.session = args[i]
        elif arg == "--session-dir" and i + 1 < len(args):
            i += 1
            result.session_dir = args[i]
        elif arg == "--models" and i + 1 < len(args):
            i += 1
            result.models = [s.strip() for s in args[i].split(",")]
        elif arg == "--no-tools":
            result.no_tools = True
        elif arg == "--tools" and i + 1 < len(args):
            i += 1
            tool_names = [s.strip() for s in args[i].split(",")]
            result.tools = tool_names
        elif arg == "--thinking" and i + 1 < len(args):
            i += 1
            level = args[i]
            if is_valid_thinking_level(level):
                result.thinking = level  # type: ignore[assignment]
            else:
                print(
                    f'Warning: Invalid thinking level "{level}". Valid values: {", ".join(VALID_THINKING_LEVELS)}',
                    file=sys.stderr,
                )
        elif arg in ("--print", "-p"):
            result.print_mode = True
        elif arg == "--export" and i + 1 < len(args):
            i += 1
            result.export = args[i]
        elif arg in ("--extension", "-e") and i + 1 < len(args):
            i += 1
            if result.extensions is None:
                result.extensions = []
            result.extensions.append(args[i])
        elif arg in ("--no-extensions", "-ne"):
            result.no_extensions = True
        elif arg == "--skill" and i + 1 < len(args):
            i += 1
            if result.skills is None:
                result.skills = []
            result.skills.append(args[i])
        elif arg == "--prompt-template" and i + 1 < len(args):
            i += 1
            if result.prompt_templates is None:
                result.prompt_templates = []
            result.prompt_templates.append(args[i])
        elif arg == "--theme" and i + 1 < len(args):
            i += 1
            if result.themes is None:
                result.themes = []
            result.themes.append(args[i])
        elif arg in ("--no-skills", "-ns"):
            result.no_skills = True
        elif arg in ("--no-prompt-templates", "-np"):
            result.no_prompt_templates = True
        elif arg == "--no-themes":
            result.no_themes = True
        elif arg == "--list-models":
            # Check if next arg is a search pattern (not a flag or file arg)
            if i + 1 < len(args) and not args[i + 1].startswith("-") and not args[i + 1].startswith("@"):
                i += 1
                result.list_models = args[i]
            else:
                result.list_models = True
        elif arg == "--verbose":
            result.verbose = True
        elif arg.startswith("@"):
            result.file_args.append(arg[1:])  # Remove @ prefix
        elif arg.startswith("--") and extension_flags is not None:
            # Check if it's an extension-registered flag
            flag_name = arg[2:]
            ext_flag = extension_flags.get(flag_name)
            if ext_flag:
                if ext_flag.get("type") == "boolean":
                    result.unknown_flags[flag_name] = True
                elif ext_flag.get("type") == "string" and i + 1 < len(args):
                    i += 1
                    result.unknown_flags[flag_name] = args[i]
            # Unknown flags without extensionFlags are silently ignored (first pass)
        elif not arg.startswith("-"):
            result.messages.append(arg)

        i += 1

    return result


def print_help() -> None:
    """Print the help text to stdout."""
    print(
        f"""{APP_NAME} - AI coding assistant with read, bash, edit, write tools

Usage:
  {APP_NAME} [options] [@files...] [messages...]

Commands:
  {APP_NAME} install <source> [-l]    Install extension source and add to settings
  {APP_NAME} remove <source> [-l]     Remove extension source from settings
  {APP_NAME} update [source]          Update installed extensions (skips pinned sources)
  {APP_NAME} list                     List installed extensions from settings
  {APP_NAME} config                   Open TUI to enable/disable package resources
  {APP_NAME} <command> --help         Show help for install/remove/update/list

Options:
  --provider <name>              Provider name (default: google)
  --model <pattern>              Model pattern or ID (supports "provider/id" and optional ":<thinking>")
  --api-key <key>                API key (defaults to env vars)
  --system-prompt <text>         System prompt (default: coding assistant prompt)
  --append-system-prompt <text>  Append text or file contents to the system prompt
  --mode <mode>                  Output mode: text (default), json, or rpc
  --print, -p                    Non-interactive mode: process prompt and exit
  --continue, -c                 Continue previous session
  --resume, -r                   Select a session to resume
  --session <path>               Use specific session file
  --session-dir <dir>            Directory for session storage and lookup
  --no-session                   Don't save session (ephemeral)
  --models <patterns>            Comma-separated model patterns for Ctrl+P cycling
                                 Supports globs (anthropic/*, *sonnet*) and fuzzy matching
  --no-tools                     Disable all built-in tools
  --tools <tools>                Comma-separated list of tools to enable (default: read,bash,edit,write)
                                 Available: read, bash, edit, write, grep, find, ls
  --thinking <level>             Set thinking level: off, minimal, low, medium, high, xhigh
  --extension, -e <path>         Load an extension file (can be used multiple times)
  --no-extensions, -ne           Disable extension discovery (explicit -e paths still work)
  --skill <path>                 Load a skill file or directory (can be used multiple times)
  --no-skills, -ns               Disable skills discovery and loading
  --prompt-template <path>       Load a prompt template file or directory (can be used multiple times)
  --no-prompt-templates, -np     Disable prompt template discovery and loading
  --theme <path>                 Load a theme file or directory (can be used multiple times)
  --no-themes                    Disable theme discovery and loading
  --export <file>                Export session file to HTML and exit
  --list-models [search]         List available models (with optional fuzzy search)
  --verbose                      Force verbose startup (overrides quietStartup setting)
  --help, -h                     Show this help
  --version, -v                  Show version number

Extensions can register additional flags (e.g., --plan from plan-mode extension).

Examples:
  # Interactive mode
  {APP_NAME}

  # Interactive mode with initial prompt
  {APP_NAME} "List all .ts files in src/"

  # Include files in initial message
  {APP_NAME} @prompt.md @image.png "What color is the sky?"

  # Non-interactive mode (process and exit)
  {APP_NAME} -p "List all .ts files in src/"

  # Multiple messages (interactive)
  {APP_NAME} "Read package.json" "What dependencies do we have?"

  # Continue previous session
  {APP_NAME} --continue "What did we discuss?"

  # Use different model
  {APP_NAME} --provider openai --model gpt-4o-mini "Help me refactor this code"

  # Use model with provider prefix (no --provider needed)
  {APP_NAME} --model openai/gpt-4o "Help me refactor this code"

  # Use model with thinking level shorthand
  {APP_NAME} --model sonnet:high "Solve this complex problem"

  # Limit model cycling to specific models
  {APP_NAME} --models claude-sonnet,claude-haiku,gpt-4o

  # Limit to a specific provider with glob pattern
  {APP_NAME} --models "github-copilot/*"

  # Cycle models with fixed thinking levels
  {APP_NAME} --models sonnet:high,haiku:low

  # Start with a specific thinking level
  {APP_NAME} --thinking high "Solve this complex problem"

  # Read-only mode (no file modifications possible)
  {APP_NAME} --tools read,grep,find,ls -p "Review the code in src/"

  # Export a session file to HTML
  {APP_NAME} --export ~/{CONFIG_DIR_NAME}/agent/sessions/--path--/session.jsonl
  {APP_NAME} --export session.jsonl output.html

Environment Variables:
  ANTHROPIC_API_KEY                - Anthropic Claude API key
  ANTHROPIC_OAUTH_TOKEN            - Anthropic OAuth token (alternative to API key)
  OPENAI_API_KEY                   - OpenAI GPT API key
  GEMINI_API_KEY                   - Google Gemini API key
  AWS_PROFILE                      - AWS profile for Amazon Bedrock
  AWS_ACCESS_KEY_ID                - AWS access key for Amazon Bedrock
  AWS_SECRET_ACCESS_KEY            - AWS secret key for Amazon Bedrock
  AWS_REGION                       - AWS region for Amazon Bedrock (e.g., us-east-1)
  {ENV_AGENT_DIR:<32} - Session storage directory (default: ~/{CONFIG_DIR_NAME}/agent)
  PI_PACKAGE_DIR                   - Override package directory (for Nix/Guix store paths)
  PI_SHARE_VIEWER_URL              - Base URL for /share command (default: https://pi.dev/session/)

Available Tools (default: read, bash, edit, write):
  read   - Read file contents
  bash   - Execute bash commands
  edit   - Edit files with find/replace
  write  - Write files (creates/overwrites)
  grep   - Search file contents (read-only, off by default)
  find   - Find files by glob pattern (read-only, off by default)
  ls     - List directory contents (read-only, off by default)
"""
    )
