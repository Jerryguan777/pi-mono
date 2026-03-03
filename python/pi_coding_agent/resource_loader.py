"""Resource loader — AGENTS.md/CLAUDE.md discovery from directory hierarchy."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# File names to search for
CONTEXT_FILE_NAMES = ["AGENTS.md", "CLAUDE.md"]


@dataclass
class ContextFile:
    path: str
    content: str


def load_project_context_files(cwd: str | None = None) -> list[ContextFile]:
    """Load AGENTS.md/CLAUDE.md from global + ancestor directories.

    Search order:
    1. Global: ~/.claude/AGENTS.md, ~/.claude/CLAUDE.md
    2. Walk up from cwd to filesystem root, collecting per-directory files
    """
    result: list[ContextFile] = []
    seen_paths: set[str] = set()

    # 1. Global context files
    global_dir = os.path.join(Path.home(), ".claude")
    _collect_context_files(global_dir, result, seen_paths)

    # 2. Walk up from cwd
    if cwd is None:
        cwd = os.getcwd()

    current = os.path.abspath(cwd)
    while True:
        _collect_context_files(current, result, seen_paths)

        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    return result


def _collect_context_files(
    directory: str,
    result: list[ContextFile],
    seen_paths: set[str],
) -> None:
    """Collect context files from a single directory."""
    for name in CONTEXT_FILE_NAMES:
        path = os.path.join(directory, name)
        real_path = os.path.realpath(path)

        if real_path in seen_paths:
            continue

        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                result.append(ContextFile(path=path, content=content))
                seen_paths.add(real_path)
            except OSError:
                pass
