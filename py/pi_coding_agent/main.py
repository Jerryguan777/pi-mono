"""Main entry point for the coding agent CLI.

Python port of packages/coding-agent/src/main.ts.

Handles CLI argument parsing and translates them into agent session options.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from pi_ai.providers.register_builtins import register_built_in_api_providers
from pi_coding_agent.cli.args import parse_args, print_help
from pi_coding_agent.cli.config_selector import ConfigSelectorOptions, select_config
from pi_coding_agent.cli.file_processor import ProcessFileOptions, process_file_arguments
from pi_coding_agent.config import APP_NAME, VERSION, get_agent_dir, get_models_path
from pi_coding_agent.core.auth_storage import AuthStorage
from pi_coding_agent.core.model_registry import ModelRegistry
from pi_coding_agent.core.model_resolver import ScopedModel, resolve_cli_model, resolve_model_scope
from pi_coding_agent.core.resource_loader import DefaultResourceLoader, DefaultResourceLoaderOptions
from pi_coding_agent.core.sdk import CreateAgentSessionOptions, create_agent_session
from pi_coding_agent.core.session_manager import SessionManager
from pi_coding_agent.core.settings_manager import SettingsManager
from pi_coding_agent.migrations import run_migrations, show_deprecation_warnings
from pi_coding_agent.modes.interactive.interactive_mode import (
    InteractiveMode,
    InteractiveModeOptions,
)
from pi_coding_agent.modes.interactive.theme import init_theme, stop_theme_watcher
from pi_coding_agent.modes.print_mode import PrintModeOptions, run_print_mode
from pi_coding_agent.modes.rpc.rpc_mode import run_rpc_mode

# ===========================================================================
# Package command handling
# ===========================================================================

_PACKAGE_COMMANDS = {"install", "remove", "update", "list"}


def _get_package_command_usage(command: str) -> str:
    """Return usage string for a package command."""
    usages = {
        "install": f"{APP_NAME} install <source> [-l]",
        "remove": f"{APP_NAME} remove <source> [-l]",
        "update": f"{APP_NAME} update [source]",
        "list": f"{APP_NAME} list",
    }
    return usages.get(command, f"{APP_NAME} {command}")


def _print_package_command_help(command: str) -> None:
    """Print help text for a package sub-command."""
    if command == "install":
        print(
            f"Usage:\n  {_get_package_command_usage('install')}\n\n"
            "Install a package and add it to settings.\n\n"
            "Options:\n"
            "  -l, --local    Install project-locally (.pi/settings.json)\n"
        )
    elif command == "remove":
        print(
            f"Usage:\n  {_get_package_command_usage('remove')}\n\n"
            "Remove a package and its source from settings.\n\n"
            "Options:\n"
            "  -l, --local    Remove from project settings (.pi/settings.json)\n"
        )
    elif command == "update":
        print(
            f"Usage:\n  {_get_package_command_usage('update')}\n\n"
            "Update installed packages.\n"
            "If <source> is provided, only that package is updated.\n"
        )
    elif command == "list":
        print(
            f"Usage:\n  {_get_package_command_usage('list')}\n\n"
            "List installed packages from user and project settings.\n"
        )


def _parse_package_command(
    args: list[str],
) -> dict[str, Any] | None:
    """Parse package sub-command arguments.

    Returns a dict with keys: command, source, local, help, invalid_option,
    or None if the first arg is not a package command.
    """
    if not args:
        return None
    command = args[0]
    if command not in _PACKAGE_COMMANDS:
        return None

    rest = args[1:]
    local = False
    help_flag = False
    invalid_option: str | None = None
    source: str | None = None

    for arg in rest:
        if arg in ("-h", "--help"):
            help_flag = True
        elif arg in ("-l", "--local"):
            if command in ("install", "remove"):
                local = True
            else:
                invalid_option = invalid_option or arg
        elif arg.startswith("-"):
            invalid_option = invalid_option or arg
        elif source is None:
            source = arg

    return {
        "command": command,
        "source": source,
        "local": local,
        "help": help_flag,
        "invalid_option": invalid_option,
    }


async def _handle_package_command(args: list[str]) -> bool:
    """Handle install/remove/update/list sub-commands.

    Returns True if a package command was handled (caller should return).
    """
    options = _parse_package_command(args)
    if options is None:
        return False

    command: str = options["command"]

    if options["help"]:
        _print_package_command_help(command)
        return True

    if options["invalid_option"]:
        print(
            f'Unknown option {options["invalid_option"]} for "{command}".\n'
            f'Use "{APP_NAME} --help" or "{_get_package_command_usage(command)}".',
            file=sys.stderr,
        )
        sys.exit(1)

    source: str | None = options["source"]
    if command in ("install", "remove") and source is None:
        print(
            f"Missing {command} source.\nUsage: {_get_package_command_usage(command)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Package manager operations are stubs
    if command == "install":
        print(f"Package install not yet implemented. Source: {source}")
    elif command == "remove":
        print(f"Package remove not yet implemented. Source: {source}")
    elif command == "update":
        print(f"Package update not yet implemented. Source: {source}")
    elif command == "list":
        print("Package list not yet implemented.")

    return True


async def _handle_config_command(args: list[str]) -> bool:
    """Handle the 'config' sub-command.

    Returns True if the config command was handled.
    """
    if not args or args[0] != "config":
        return False

    cwd = os.getcwd()
    agent_dir = str(get_agent_dir())
    await select_config(
        ConfigSelectorOptions(
            resolved_paths=None,
            settings_manager=None,
            cwd=cwd,
            agent_dir=agent_dir,
        )
    )
    sys.exit(0)


async def _read_piped_stdin() -> str | None:
    """Read all content from piped stdin.

    Returns None if stdin is a TTY (interactive terminal).
    """
    if sys.stdin.isatty():
        return None

    loop = asyncio.get_event_loop()
    content = await loop.run_in_executor(None, sys.stdin.read)
    return content.strip() or None


async def _prepare_initial_message(
    file_args: list[str],
    messages: list[str],
    auto_resize_images: bool = True,
) -> tuple[str | None, list[Any] | None, list[str]]:
    """Process @file arguments and return (initial_message, images, remaining_messages)."""
    if not file_args:
        return None, None, messages

    processed = await process_file_arguments(file_args, ProcessFileOptions(auto_resize_images=auto_resize_images))

    remaining = list(messages)
    initial_message = processed.text + remaining.pop(0) if remaining else processed.text

    images: list[Any] | None = processed.images if processed.images else None
    return initial_message, images, remaining


# ===========================================================================
# Main entry point
# ===========================================================================


async def main(args: list[str]) -> None:
    """Main entry point for the coding agent CLI.

    Args:
        args: Command-line arguments (typically sys.argv[1:]).
    """
    # Register all built-in API providers (TS does this at module scope)
    register_built_in_api_providers()

    if await _handle_package_command(args):
        return

    if await _handle_config_command(args):
        return

    # Run migrations
    migration_result = run_migrations(os.getcwd())
    migrated_providers = migration_result.migrated_auth_providers
    deprecation_warnings = migration_result.deprecation_warnings

    # First pass: parse args to discover --extension / --skill / --prompt-template
    # paths before loading extensions. Extension flags are not known yet.
    first_pass = parse_args(args)

    if first_pass.version:
        print(VERSION)
        sys.exit(0)

    if first_pass.help:
        print_help()
        sys.exit(0)

    # Create core services early so they can be reused
    cwd = os.getcwd()
    agent_dir = str(get_agent_dir())
    settings_manager = SettingsManager.create(Path(cwd), Path(agent_dir))
    auth_storage = AuthStorage.create()
    model_registry = ModelRegistry(auth_storage, get_models_path())

    # Load extensions so they can register custom CLI flags.
    extension_flags: dict[str, dict[str, str]] = {}
    extensions_result: Any = None

    resource_loader = DefaultResourceLoader(
        DefaultResourceLoaderOptions(
            cwd=cwd,
            agent_dir=agent_dir,
            settings_manager=settings_manager,
            additional_extension_paths=first_pass.extensions or [],
            additional_skill_paths=first_pass.skills or [],
            additional_prompt_template_paths=first_pass.prompt_templates or [],
            no_extensions=first_pass.no_extensions,
            no_skills=first_pass.no_skills,
            no_prompt_templates=first_pass.no_prompt_templates,
            system_prompt=first_pass.system_prompt,
            append_system_prompt=first_pass.append_system_prompt,
        )
    )
    await resource_loader.reload()

    extensions_result = resource_loader.get_extensions()
    for err in extensions_result.errors:
        print(
            f'Failed to load extension "{err["path"]}": {err["error"]}',
            file=sys.stderr,
        )

    # Collect CLI flags registered by extensions
    for ext in extensions_result.extensions:
        for flag_name, flag in ext.flags.items():
            extension_flags[flag_name] = {"type": flag.type}

    # Second pass: re-parse with extension flags so extension-registered flags
    # (e.g. --plan from a plan-mode extension) are captured in unknown_flags.
    parsed = parse_args(args, extension_flags)

    # Pass flag values back to extension runtime so extensions can read them.
    if extensions_result is not None:
        for flag_name, value in parsed.unknown_flags.items():
            extensions_result.runtime.flag_values[flag_name] = value

    if parsed.list_models is not None:
        search_pattern: str | None = parsed.list_models if isinstance(parsed.list_models, str) else None
        all_models = model_registry.get_all()
        for m in all_models:
            display = f"{m.provider}/{m.id}"
            if search_pattern and search_pattern.lower() not in display.lower():
                continue
            print(display)
        sys.exit(0)

    # Read piped stdin if not in RPC mode
    if parsed.mode != "rpc":
        stdin_content = await _read_piped_stdin()
        if stdin_content is not None:
            parsed.print_mode = True
            parsed.messages.insert(0, stdin_content)

    if parsed.export is not None:
        print("Export not yet implemented.", file=sys.stderr)
        sys.exit(1)

    if parsed.mode == "rpc" and parsed.file_args:
        print("Error: @file arguments are not supported in RPC mode", file=sys.stderr)
        sys.exit(1)

    initial_message, initial_images, remaining_messages = await _prepare_initial_message(
        parsed.file_args, parsed.messages
    )

    is_interactive = not parsed.print_mode and parsed.mode is None
    mode = parsed.mode or "text"

    init_theme(None, is_interactive)

    # Show deprecation warnings in interactive mode
    if is_interactive and deprecation_warnings:
        await show_deprecation_warnings(deprecation_warnings)

    # Resolve model from CLI flags
    resolved_model = None
    if parsed.model:
        cli_result = resolve_cli_model(parsed.provider, parsed.model, model_registry)
        if cli_result.error:
            print(cli_result.error, file=sys.stderr)
            sys.exit(1)
        resolved_model = cli_result.model

    # Resolve scoped models
    scoped_models: list[ScopedModel] = []
    model_patterns = parsed.models or settings_manager.get_enabled_models()
    if model_patterns:
        scoped_models = await resolve_model_scope(model_patterns, model_registry)

    # Create session manager
    session_manager: SessionManager | None = None
    if parsed.no_session:
        session_manager = SessionManager.in_memory()
    elif parsed.session:
        session_manager = SessionManager.open(parsed.session, parsed.session_dir)
    elif parsed.continue_session:
        session_manager = SessionManager.continue_recent(cwd, parsed.session_dir)
    elif parsed.session_dir:
        session_manager = SessionManager.create(cwd, parsed.session_dir)

    # Create agent session
    session_result = await create_agent_session(
        CreateAgentSessionOptions(
            cwd=cwd,
            agent_dir=agent_dir,
            model=resolved_model,
            thinking_level=parsed.thinking,
            session_manager=session_manager,
            settings_manager=settings_manager,
            auth_storage=auth_storage,
            model_registry=model_registry,
            resource_loader=resource_loader,
            scoped_models=scoped_models if scoped_models else None,
        )
    )
    session = session_result.session

    if not is_interactive:
        if session.model is None:
            print("No models available. Set an API key env var.", file=sys.stderr)
            sys.exit(1)

        if mode == "rpc":
            run_rpc_mode(session)  # type: ignore[arg-type]
        else:
            await run_print_mode(
                session,
                PrintModeOptions(
                    mode=mode,
                    messages=remaining_messages,
                    initial_message=initial_message,
                    initial_images=initial_images,
                ),
            )
            stop_theme_watcher()
            sys.exit(0)
    else:
        mode_obj = InteractiveMode(
            session=session,
            options=InteractiveModeOptions(
                migrated_providers=migrated_providers,
                model_fallback_message=session_result.model_fallback_message,
                initial_message=initial_message,
                initial_images=initial_images,
                initial_messages=remaining_messages,
                verbose=parsed.verbose,
            ),
        )
        await mode_obj.run()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
