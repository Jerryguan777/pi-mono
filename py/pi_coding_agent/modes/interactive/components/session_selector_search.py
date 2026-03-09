"""Session search/filter utilities: query parsing, matching, and sorting."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pi_tui.fuzzy import fuzzy_match

SortMode = Literal["threaded", "recent", "relevance"]
NameFilter = Literal["all", "named"]


@dataclass
class ParsedSearchQuery:
    mode: Literal["tokens", "regex"]
    tokens: list[dict[str, str]] = field(default_factory=list)
    regex: re.Pattern[str] | None = None
    error: str | None = None


@dataclass
class MatchResult:
    matches: bool
    score: float = 0.0


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _get_session_search_text(session: Any) -> str:
    session_id = getattr(session, "id", "")
    name = getattr(session, "name", "") or ""
    messages_text = getattr(session, "all_messages_text", "") or ""
    cwd = getattr(session, "cwd", "") or ""
    return f"{session_id} {name} {messages_text} {cwd}"


def has_session_name(session: Any) -> bool:
    name = getattr(session, "name", None)
    return bool(name and name.strip())


def _matches_name_filter(session: Any, name_filter: NameFilter) -> bool:
    if name_filter == "all":
        return True
    return has_session_name(session)


def parse_search_query(query: str) -> ParsedSearchQuery:
    trimmed = query.strip()
    if not trimmed:
        return ParsedSearchQuery(mode="tokens", tokens=[], regex=None)

    if trimmed.startswith("re:"):
        pattern = trimmed[3:].strip()
        if not pattern:
            return ParsedSearchQuery(mode="regex", tokens=[], regex=None, error="Empty regex")
        try:
            return ParsedSearchQuery(mode="regex", tokens=[], regex=re.compile(pattern, re.IGNORECASE))
        except re.error as exc:
            return ParsedSearchQuery(mode="regex", tokens=[], regex=None, error=str(exc))

    # Token mode with quote support
    tokens: list[dict[str, str]] = []
    buf = ""
    in_quote = False
    had_unclosed = False

    def flush(kind: str) -> None:
        nonlocal buf
        v = buf.strip()
        buf = ""
        if v:
            tokens.append({"kind": kind, "value": v})

    for ch in trimmed:
        if ch == '"':
            if in_quote:
                flush("phrase")
                in_quote = False
            else:
                flush("fuzzy")
                in_quote = True
        elif not in_quote and ch.isspace():
            flush("fuzzy")
        else:
            buf += ch

    if in_quote:
        had_unclosed = True

    if had_unclosed:
        tokens = [{"kind": "fuzzy", "value": t} for t in trimmed.split() if t]
        return ParsedSearchQuery(mode="tokens", tokens=tokens, regex=None)

    flush("fuzzy" if not in_quote else "phrase")
    return ParsedSearchQuery(mode="tokens", tokens=tokens, regex=None)


def match_session(session: Any, parsed: ParsedSearchQuery) -> MatchResult:
    text = _get_session_search_text(session)

    if parsed.mode == "regex":
        if parsed.regex is None:
            return MatchResult(matches=False)
        m = parsed.regex.search(text)
        if m is None:
            return MatchResult(matches=False)
        return MatchResult(matches=True, score=m.start() * 0.1)

    if not parsed.tokens:
        return MatchResult(matches=True, score=0.0)

    total_score = 0.0
    normalized_text: str | None = None

    for token in parsed.tokens:
        if token["kind"] == "phrase":
            if normalized_text is None:
                normalized_text = _normalize(text)
            phrase = _normalize(token["value"])
            if not phrase:
                continue
            idx = normalized_text.find(phrase)
            if idx < 0:
                return MatchResult(matches=False)
            total_score += idx * 0.1
        else:
            result = fuzzy_match(token["value"], text)
            if not result.matches:
                return MatchResult(matches=False)
            total_score += result.score

    return MatchResult(matches=True, score=total_score)


def filter_and_sort_sessions(
    sessions: list[Any],
    query: str,
    sort_mode: SortMode,
    name_filter: NameFilter = "all",
) -> list[Any]:
    name_filtered = [s for s in sessions if _matches_name_filter(s, name_filter)]
    trimmed = query.strip()
    if not trimmed:
        return name_filtered

    parsed = parse_search_query(query)
    if parsed.error:
        return []

    if sort_mode == "recent":
        return [s for s in name_filtered if match_session(s, parsed).matches]

    scored = []
    for s in name_filtered:
        res = match_session(s, parsed)
        if res.matches:
            scored.append((s, res.score))

    def _sort_key(x: tuple[Any, float]) -> tuple[float, float]:
        modified = getattr(x[0], "modified", None)
        ts: float = -modified.timestamp() if hasattr(modified, "timestamp") else 0  # type: ignore[union-attr]
        return (x[1], ts)

    scored.sort(key=_sort_key)
    return [s for s, _ in scored]
