#!/usr/bin/env python3
"""Extract public API from TypeScript source files.

Parses all `export` declarations (functions, classes, types, interfaces, constants)
and outputs a Markdown checklist with each export's name, kind, and signature.

Usage:
    python scripts/extract_public_api.py <ts_file_or_directory>
"""

import re
import sys
from pathlib import Path

# Map compound acronyms to single capitalized words before camelCase splitting
_ACRONYM_NORMALIZE: list[tuple[str, str]] = [
    ("OAuth", "Oauth"),
    ("GitHub", "Github"),
    ("OpenAI", "Openai"),
    ("iTerm", "Iterm"),
    ("ITerm", "Iterm"),
]


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case, handling known acronyms."""
    for acronym, normalized in _ACRONYM_NORMALIZE:
        name = name.replace(acronym, normalized)
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _suggest_python_name(name: str, kind: str) -> str:
    """Suggest a Python name based on the TS name and kind."""
    if kind in ("class", "interface", "type", "enum"):
        return name  # PascalCase stays
    return _camel_to_snake(name)


def _suggest_python_kind(kind: str) -> str:
    """Suggest a Python construct for a TS kind."""
    mapping = {
        "function": "def",
        "async function": "async def",
        "class": "class",
        "interface": "class/TypedDict",
        "type": "class/TypedDict",
        "const": "constant",
        "enum": "StrEnum/Literal",
    }
    return mapping.get(kind, kind)


# Patterns to match TS export declarations
_EXPORT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("async function", re.compile(r"^export\s+async\s+function\s+(\w+)")),
    ("function", re.compile(r"^export\s+function\s+(\w+)")),
    ("class", re.compile(r"^export\s+class\s+(\w+)")),
    ("interface", re.compile(r"^export\s+interface\s+(\w+)")),
    ("type", re.compile(r"^export\s+type\s+(\w+)")),
    ("enum", re.compile(r"^export\s+enum\s+(\w+)")),
    ("const", re.compile(r"^export\s+const\s+(\w+)")),
]


def extract_exports(source: str) -> list[tuple[str, str]]:
    """Extract exported names and their kinds from TS source code.

    Returns a list of (name, kind) tuples.
    """
    exports: list[tuple[str, str]] = []
    for line in source.splitlines():
        stripped = line.strip()
        for kind, pattern in _EXPORT_PATTERNS:
            m = pattern.match(stripped)
            if m:
                exports.append((m.group(1), kind))
                break
    return exports


def format_checklist(exports: list[tuple[str, str]], file_path: str) -> str:
    """Format exports as a Markdown checklist."""
    if not exports:
        return f"### {file_path}\n\nNo exports found.\n"

    lines = [f"### {file_path}\n"]
    for name, kind in exports:
        py_kind = _suggest_python_kind(kind)
        py_name = _suggest_python_name(name, kind)
        lines.append(f"- [ ] {kind} `{name}` -> {py_kind} `{py_name}`")
    lines.append("")
    return "\n".join(lines)


def process_path(path: Path) -> str:
    """Process a file or directory and return the Markdown checklist."""
    results: list[str] = []

    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = sorted(path.rglob("*.ts"))
        files = [f for f in files if not f.name.endswith(".d.ts") and not f.name.endswith(".test.ts")]
    else:
        print(f"Error: {path} is not a valid file or directory", file=sys.stderr)
        sys.exit(1)

    for ts_file in files:
        source = ts_file.read_text(encoding="utf-8")
        exports = extract_exports(source)
        if exports:
            results.append(format_checklist(exports, str(ts_file)))

    return "\n".join(results) if results else "No exports found."


def main() -> None:
    """Entry point."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <ts_file_or_directory>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    output = process_path(path)
    print(output)


if __name__ == "__main__":
    main()
