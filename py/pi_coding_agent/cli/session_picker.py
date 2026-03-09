"""Session picker for the --resume flag.

Python port of packages/coding-agent/src/cli/session-picker.ts.
Uses a simple CLI input() picker rather than the full TUI component,
because the TUI session selector depends on parallel tasks.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


async def select_session(
    current_sessions_loader: Callable[..., Any],
    all_sessions_loader: Callable[..., Any],
) -> str | None:
    """Show a session picker and return the selected session path, or None.

    Loads sessions from current project first, then all sessions.
    Presents a numbered list and prompts the user to pick one.

    Args:
        current_sessions_loader: Async callable that returns list of session info
            objects for the current project.
        all_sessions_loader: Async callable that returns list of session info
            objects across all projects.

    Returns:
        Selected session path string, or None if cancelled.
    """
    # Load current-project sessions first
    try:
        sessions: list[Any] = await current_sessions_loader()
    except (OSError, RuntimeError):
        sessions = []

    if not sessions:
        # Fall back to all sessions
        try:
            sessions = await all_sessions_loader()
        except (OSError, RuntimeError):
            sessions = []

    if not sessions:
        print("No sessions found.")
        return None

    # Display numbered list
    for idx, session in enumerate(sessions):
        label = getattr(session, "id", None) or getattr(session, "path", str(session))
        print(f"  {idx + 1}. {label}")

    # Prompt for selection
    try:
        raw = input("Select session (number, or Enter to cancel): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if not raw:
        return None

    try:
        choice = int(raw) - 1
    except ValueError:
        return None

    if 0 <= choice < len(sessions):
        session_obj = sessions[choice]
        path: str | None = getattr(session_obj, "path", None)
        return path

    return None
