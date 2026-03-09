"""Generic undo stack with clone-on-push semantics."""

import copy
from typing import TypeVar

S = TypeVar("S")

DEFAULT_MAX_SIZE = 200


class UndoStack[S]:
    """Stores deep clones of state snapshots.

    Popped snapshots are returned directly (no re-cloning)
    since they are already detached.
    """

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE) -> None:
        self._stack: list[S] = []
        self._max_size = max_size

    def push(self, state: S) -> None:
        """Push a deep clone of the given state onto the stack."""
        self._stack.append(copy.deepcopy(state))
        if len(self._stack) > self._max_size:
            self._stack.pop(0)

    def pop(self) -> S | None:
        """Pop and return the most recent snapshot, or None if empty."""
        return self._stack.pop() if self._stack else None

    def clear(self) -> None:
        """Remove all snapshots."""
        self._stack.clear()

    @property
    def length(self) -> int:
        return len(self._stack)
