"""Path utilities for tool implementations."""

from __future__ import annotations

import os


def expand_path(path: str) -> str:
    """Expand ~ and normalize path."""
    path = path.strip()
    if path.startswith("@"):
        path = path[1:]
    path = os.path.expanduser(path)
    return path


def resolve_to_cwd(path: str, cwd: str) -> str:
    """Resolve a path relative to the working directory."""
    expanded = expand_path(path)
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(cwd, expanded))
