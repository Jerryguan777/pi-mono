"""CLI entry point for the Pi Coding Agent."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from pi_ai.api_registry import register_default_providers
from pi_ai.models import get_model
from pi_ai.types import Model
from pi_agent.agent import Agent

from pi_coding_agent.auth_storage import AuthStorage
from pi_coding_agent.model_registry import ModelRegistry
from pi_coding_agent.print_mode import run_print_mode
from pi_coding_agent.resource_loader import load_project_context_files
from pi_coding_agent.rpc_mode import run_rpc_mode
from pi_coding_agent.settings_manager import SettingsManager
from pi_coding_agent.system_prompt import build_system_prompt
from pi_session.agent_session import AgentSession, AgentSessionConfig
from pi_session.session_manager import SessionManager


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Pi Coding Agent — AI-powered coding assistant",
    )

    # Session
    parser.add_argument(
        "--continue", "-c",
        dest="continue_session",
        action="store_true",
        help="Continue the most recent session",
    )
    parser.add_argument(
        "--session",
        type=str,
        help="Session file to resume",
    )

    # Model
    parser.add_argument("--provider", type=str, help="LLM provider (openai, anthropic, google)")
    parser.add_argument("--model", type=str, help="Model ID")
    parser.add_argument("--reasoning", type=str, help="Thinking level (minimal, low, medium, high, xhigh)")
    parser.add_argument("--api-key", type=str, help="API key override")

    # Mode
    parser.add_argument(
        "--print",
        dest="print_mode",
        action="store_true",
        help="Run in print mode (non-interactive)",
    )
    parser.add_argument("--json", action="store_true", help="Output events as JSONL")
    parser.add_argument(
        "--mode",
        choices=["interactive", "print", "rpc"],
        help="Execution mode",
    )

    # Input
    parser.add_argument(
        "--message", "-m",
        type=str,
        action="append",
        help="Message to send (can be repeated)",
    )
    parser.add_argument("prompt", nargs="?", type=str, help="Prompt text")

    # Tools
    parser.add_argument("--no-tools", action="store_true", help="Disable all tools")
    parser.add_argument("--tools", type=str, nargs="*", help="Specific tools to enable")

    # System prompt
    parser.add_argument("--system-prompt", type=str, help="Custom system prompt")
    parser.add_argument("--no-agents-md", action="store_true", help="Skip loading AGENTS.md/CLAUDE.md")
    parser.add_argument("--append-system-prompt", type=str, help="Text to append to system prompt")

    # Session directory
    parser.add_argument("--session-dir", type=str, help="Directory for session files")

    return parser


def _resolve_mode(args: argparse.Namespace) -> str:
    """Determine which mode to run in."""
    if args.mode:
        return args.mode
    if args.print_mode or args.json:
        return "print"
    # If stdin is piped (not a TTY), default to print mode
    if not sys.stdin.isatty():
        return "print"
    # If messages provided, default to print mode
    if args.message or args.prompt:
        return "print"
    # Default to print mode (interactive TUI deferred)
    return "print"


def _resolve_messages(args: argparse.Namespace) -> list[str]:
    """Collect all prompt messages from args."""
    messages: list[str] = []

    if args.message:
        messages.extend(args.message)

    if args.prompt:
        messages.append(args.prompt)

    # Read from stdin if piped and no messages
    if not messages and not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            messages.append(stdin_text)

    return messages


def _load_tools(args: argparse.Namespace) -> list:
    """Load tool instances based on CLI args."""
    if args.no_tools:
        return []

    from pi_tools.bash_tool import BashTool
    from pi_tools.edit_tool import EditTool
    from pi_tools.find_tool import FindTool
    from pi_tools.grep_tool import GrepTool
    from pi_tools.ls_tool import LsTool
    from pi_tools.read_tool import ReadTool
    from pi_tools.write_tool import WriteTool

    all_tools = [
        BashTool(),
        ReadTool(),
        WriteTool(),
        EditTool(),
        FindTool(),
        GrepTool(),
        LsTool(),
    ]

    if args.tools:
        tool_names = set(args.tools)
        all_tools = [t for t in all_tools if t.name in tool_names]

    return all_tools


async def _run(args: argparse.Namespace) -> int:
    """Main async entry point."""
    register_default_providers()

    cwd = os.getcwd()
    settings_mgr = SettingsManager.create(cwd)
    auth = AuthStorage.create()

    # Resolve model
    provider = args.provider or settings_mgr.get_default_provider() or "anthropic"
    model_id = args.model or settings_mgr.get_default_model() or "claude-sonnet-4-6-20250610"
    reasoning = args.reasoning or settings_mgr.get_default_thinking_level()

    try:
        model = get_model(provider, model_id)
    except ValueError:
        # Try as custom model
        registry = ModelRegistry(auth)
        model = registry.find(provider, model_id)
        if model is None:
            sys.stderr.write(f"Error: Unknown model {model_id} for provider {provider}\n")
            return 1

    # API key
    api_key = args.api_key
    if not api_key:
        api_key = await auth.get_api_key(provider)

    # Tools
    tools = _load_tools(args)

    # System prompt
    context_files = None if args.no_agents_md else load_project_context_files(cwd)
    system_prompt = build_system_prompt(
        custom_prompt=args.system_prompt,
        tools=tools,
        context_files=context_files,
        cwd=cwd,
        append_system_prompt=args.append_system_prompt,
    )

    # Agent
    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        api_key=api_key,
        reasoning=reasoning,
        steering_mode=settings_mgr.get_steering_mode(),
        follow_up_mode=settings_mgr.get_follow_up_mode(),
    )

    # Session manager
    if args.session:
        session_mgr = SessionManager.open(args.session)
    elif args.continue_session:
        try:
            session_mgr = SessionManager.continue_recent(cwd, args.session_dir)
        except FileNotFoundError:
            session_mgr = SessionManager.create(cwd, args.session_dir)
    else:
        session_mgr = SessionManager.create(cwd, args.session_dir)

    # Agent session
    session = AgentSession(AgentSessionConfig(
        agent=agent,
        session_manager=session_mgr,
        compaction_settings=settings_mgr.get_compaction_settings(),
        retry_settings=settings_mgr.get_retry_settings(),
    ))

    # Run mode
    mode = _resolve_mode(args)
    messages = _resolve_messages(args)

    if mode == "rpc":
        await run_rpc_mode(session)
        return 0

    if mode == "print":
        if not messages:
            sys.stderr.write("Error: No prompt provided. Use --message/-m or provide a prompt argument.\n")
            return 1
        output_mode = "json" if args.json else "text"
        return await run_print_mode(session, messages, output_mode)

    # Interactive mode (deferred to Tier 4)
    sys.stderr.write("Error: Interactive mode not yet implemented. Use --print or --mode rpc.\n")
    return 1


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
