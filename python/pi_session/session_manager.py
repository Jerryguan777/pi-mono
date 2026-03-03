"""Session manager — append-only JSONL tree persistence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from pi_ai.types import Message

from pi_session.types import (
    BranchSummaryEntry,
    CompactionEntry,
    ModelChangeEntry,
    SessionContext,
    SessionEntry,
    SessionHeader,
    SessionMessageEntry,
    SessionTreeNode,
    ThinkingLevelChangeEntry,
    _gen_id,
    _timestamp,
    deserialize_entry,
    deserialize_message,
    serialize_entry,
    serialize_message,
)


class SessionManager:
    """Append-only tree-structured session in JSONL format."""

    def __init__(
        self,
        header: SessionHeader,
        entries: list[SessionEntry] | None = None,
        path: str | None = None,
    ):
        self._header = header
        self._entries: list[SessionEntry] = entries or []
        self._path = path
        self._leaf_id: str | None = None
        # Index entries by ID for fast lookup
        self._by_id: dict[str, SessionEntry] = {}
        for e in self._entries:
            self._by_id[e.id] = e
        # Set leaf to last entry
        if self._entries:
            self._leaf_id = self._entries[-1].id

    @property
    def header(self) -> SessionHeader:
        return self._header

    @property
    def path(self) -> str | None:
        return self._path

    @property
    def entries(self) -> list[SessionEntry]:
        return list(self._entries)

    @property
    def leaf_id(self) -> str | None:
        return self._leaf_id

    # --- Factory methods ---

    @staticmethod
    def create(cwd: str, session_dir: str | None = None) -> SessionManager:
        """Create a new session with JSONL persistence."""
        session_id = _gen_id()
        ts = _timestamp()

        if session_dir is None:
            session_dir = os.path.join(cwd, ".pi", "sessions")

        os.makedirs(session_dir, exist_ok=True)
        path = os.path.join(session_dir, f"{session_id}.jsonl")

        header = SessionHeader(
            id=session_id,
            timestamp=ts,
            cwd=cwd,
        )

        mgr = SessionManager(header=header, path=path)
        mgr._write_header()
        return mgr

    @staticmethod
    def open(path: str) -> SessionManager:
        """Open an existing session from a JSONL file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Session file not found: {path}")

        header: SessionHeader | None = None
        entries: list[SessionEntry] = []

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                obj = deserialize_entry(d)
                if isinstance(obj, SessionHeader):
                    header = obj
                else:
                    entries.append(obj)

        if header is None:
            raise ValueError(f"No session header found in: {path}")

        return SessionManager(header=header, entries=entries, path=path)

    @staticmethod
    def continue_recent(cwd: str, session_dir: str | None = None) -> SessionManager:
        """Resume the most recent session in the directory."""
        if session_dir is None:
            session_dir = os.path.join(cwd, ".pi", "sessions")

        if not os.path.isdir(session_dir):
            raise FileNotFoundError(f"No sessions directory: {session_dir}")

        jsonl_files = sorted(
            Path(session_dir).glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not jsonl_files:
            raise FileNotFoundError(f"No session files in: {session_dir}")

        return SessionManager.open(str(jsonl_files[0]))

    @staticmethod
    def in_memory(cwd: str = "/tmp") -> SessionManager:
        """Create an in-memory session (no persistence)."""
        header = SessionHeader(
            id=_gen_id(),
            timestamp=_timestamp(),
            cwd=cwd,
        )
        return SessionManager(header=header, path=None)

    # --- Append operations ---

    def append_message(self, message: Message) -> str:
        """Append a message entry. Returns the entry ID."""
        entry_id = _gen_id()
        entry = SessionMessageEntry(
            id=entry_id,
            parent_id=self._leaf_id,
            timestamp=_timestamp(),
            message=serialize_message(message),
        )
        self._append_entry(entry)
        return entry_id

    def append_compaction(
        self,
        summary: str,
        first_kept_id: str,
        tokens_before: int,
        details: dict | None = None,
    ) -> str:
        """Append a compaction entry. Returns the entry ID."""
        entry_id = _gen_id()
        entry = CompactionEntry(
            id=entry_id,
            parent_id=self._leaf_id,
            timestamp=_timestamp(),
            summary=summary,
            first_kept_entry_id=first_kept_id,
            tokens_before=tokens_before,
            details=details,
        )
        self._append_entry(entry)
        return entry_id

    def append_model_change(self, provider: str, model_id: str) -> str:
        """Append a model change entry. Returns the entry ID."""
        entry_id = _gen_id()
        entry = ModelChangeEntry(
            id=entry_id,
            parent_id=self._leaf_id,
            timestamp=_timestamp(),
            provider=provider,
            model_id=model_id,
        )
        self._append_entry(entry)
        return entry_id

    def append_thinking_level_change(self, thinking_level: str) -> str:
        """Append a thinking level change entry. Returns the entry ID."""
        entry_id = _gen_id()
        entry = ThinkingLevelChangeEntry(
            id=entry_id,
            parent_id=self._leaf_id,
            timestamp=_timestamp(),
            thinking_level=thinking_level,
        )
        self._append_entry(entry)
        return entry_id

    def append_branch_summary(
        self,
        from_id: str,
        summary: str,
        details: dict | None = None,
    ) -> str:
        """Append a branch summary entry. Returns the entry ID."""
        entry_id = _gen_id()
        entry = BranchSummaryEntry(
            id=entry_id,
            parent_id=self._leaf_id,
            timestamp=_timestamp(),
            from_id=from_id,
            summary=summary,
            details=details,
        )
        self._append_entry(entry)
        return entry_id

    # --- Navigation ---

    def get_branch(self, from_id: str | None = None) -> list[SessionEntry]:
        """Walk from entry back to root, return in root-first order."""
        if from_id is None:
            from_id = self._leaf_id
        if from_id is None:
            return []

        chain: list[SessionEntry] = []
        current_id: str | None = from_id
        visited: set[str] = set()

        while current_id is not None:
            if current_id in visited:
                break
            visited.add(current_id)
            entry = self._by_id.get(current_id)
            if entry is None:
                break
            chain.append(entry)
            current_id = entry.parent_id

        chain.reverse()
        return chain

    def branch(self, branch_from_id: str) -> None:
        """Move the leaf pointer to a different entry (for tree branching)."""
        if branch_from_id not in self._by_id:
            raise ValueError(f"Entry not found: {branch_from_id}")
        self._leaf_id = branch_from_id

    def build_session_context(self) -> SessionContext:
        """Reconstruct messages for LLM from current branch."""
        branch = self.get_branch()

        messages: list[Message] = []
        summary: str | None = None
        compaction_entry_id: str | None = None
        first_kept_id: str | None = None

        # Find the most recent compaction in the branch
        for entry in reversed(branch):
            if isinstance(entry, CompactionEntry):
                summary = entry.summary
                compaction_entry_id = entry.id
                first_kept_id = entry.first_kept_entry_id
                break

        # Collect messages from the kept portion
        keep = first_kept_id is None
        for entry in branch:
            if not keep:
                if entry.id == first_kept_id:
                    keep = True
                else:
                    continue

            if isinstance(entry, SessionMessageEntry):
                msg = deserialize_message(entry.message)
                messages.append(msg)

        return SessionContext(
            messages=messages,
            summary=summary,
            compaction_entry_id=compaction_entry_id,
        )

    def get_tree(self) -> list[SessionTreeNode]:
        """Build the full tree structure for UI display."""
        # Find root entries (no parent or parent not in entries)
        children_of: dict[str | None, list[SessionEntry]] = {}
        for entry in self._entries:
            pid = entry.parent_id
            if pid not in children_of:
                children_of[pid] = []
            children_of[pid].append(entry)

        def build_node(entry: SessionEntry) -> SessionTreeNode:
            kids = children_of.get(entry.id, [])
            return SessionTreeNode(
                entry=entry,
                children=[build_node(c) for c in kids],
            )

        # Root entries have parent_id None or parent not in _by_id
        roots: list[SessionEntry] = []
        for entry in self._entries:
            if entry.parent_id is None or entry.parent_id not in self._by_id:
                roots.append(entry)

        return [build_node(r) for r in roots]

    # --- Internal ---

    def _append_entry(self, entry: SessionEntry) -> None:
        """Append entry to in-memory list and persist to disk."""
        self._entries.append(entry)
        self._by_id[entry.id] = entry
        self._leaf_id = entry.id

        if self._path:
            self._write_entry(entry)

    def _write_header(self) -> None:
        """Write the session header to disk."""
        if not self._path:
            return
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(json.dumps(serialize_entry(self._header)) + "\n")

    def _write_entry(self, entry: SessionEntry) -> None:
        """Append a single entry to the JSONL file."""
        if not self._path:
            return
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(serialize_entry(entry)) + "\n")
