#!/usr/bin/env python3
"""Check API parity between TypeScript and Python packages.

Compares TS export list vs Python `__all__` / public API and reports
missing, extra, and name-mismatched items.

Usage:
    python scripts/check_parity.py <ts_package_path> <python_package_name>
    python scripts/check_parity.py  # check all known package pairs
"""

import importlib
import importlib.util
import re
import sys
import types
from collections.abc import Callable
from pathlib import Path


def _load_extract_module() -> types.ModuleType:
    """Load extract_public_api module from the same directory."""
    module_path = Path(__file__).resolve().parent / "extract_public_api.py"
    spec = importlib.util.spec_from_file_location("extract_public_api", module_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_extract_mod = _load_extract_module()
_extract_exports_fn: Callable[[str], list[tuple[str, str]]] = _extract_mod.extract_exports


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


def _expected_python_names(name: str, kind: str) -> list[str]:
    """Get possible Python names for a TS export.

    Returns a list of candidate names. For consts, includes both
    snake_case and UPPER_SNAKE_CASE variants.
    """
    if kind in ("class", "interface", "type", "enum"):
        return [name]
    snake = _camel_to_snake(name)
    if kind == "const":
        upper = snake.upper()
        # Also try keeping original if already UPPER_CASE
        candidates = [snake, upper]
        if name != snake and name != upper:
            candidates.append(name)
        return list(dict.fromkeys(candidates))  # dedupe preserving order
    return [snake]


# Default package pairs: (ts_src_path_relative_to_repo_root, python_package_name)
_DEFAULT_PAIRS: list[tuple[str, str]] = [
    ("packages/ai/src", "pi_ai"),
    ("packages/agent/src", "pi_agent"),
    ("packages/tui/src", "pi_tui"),
    ("packages/coding-agent/src", "pi_coding_agent"),
    ("packages/mom/src", "pi_mom"),
    ("packages/pods/src", "pi_pods"),
]


def get_ts_exports(ts_path: Path) -> list[tuple[str, str, list[str]]]:
    """Get all TS exports from a path.

    Returns list of (name, kind, expected_python_names) tuples.
    """
    results: list[tuple[str, str, list[str]]] = []
    if not ts_path.exists():
        return results

    files = sorted(ts_path.rglob("*.ts")) if ts_path.is_dir() else [ts_path]
    files = [f for f in files if not f.name.endswith(".d.ts") and not f.name.endswith(".test.ts")]

    for ts_file in files:
        source = ts_file.read_text(encoding="utf-8")
        for name, kind in _extract_exports_fn(source):
            py_names = _expected_python_names(name, kind)
            results.append((name, kind, py_names))

    return results


def get_python_public_api(package_name: str) -> set[str]:
    """Get Python package's public API from __all__ or public attributes."""
    try:
        mod = importlib.import_module(package_name)
    except ImportError:
        return set()

    if hasattr(mod, "__all__"):
        return set(mod.__all__)

    # Fall back to public attributes (no leading underscore)
    return {name for name in dir(mod) if not name.startswith("_")}


def check_parity(ts_path: Path, python_package: str) -> dict[str, list[str]]:
    """Compare TS exports vs Python public API.

    Returns a dict with keys: missing, extra, matched.
    """
    ts_exports = get_ts_exports(ts_path)
    py_api = get_python_public_api(python_package)

    matched_ts: set[str] = set()  # TS names that matched
    matched_py: set[str] = set()  # Python names that matched
    missing_names: list[str] = []

    for ts_name, _kind, py_candidates in ts_exports:
        found = False
        for candidate in py_candidates:
            if candidate in py_api:
                matched_ts.add(ts_name)
                matched_py.add(candidate)
                found = True
                break
        if not found:
            # Report the first (preferred) candidate name as missing
            missing_names.append(py_candidates[0])

    extra = sorted(py_api - matched_py)
    matched = sorted(matched_py)
    missing = sorted(set(missing_names))

    return {"missing": missing, "extra": extra, "matched": matched}


def format_report(ts_path: str, python_package: str, result: dict[str, list[str]]) -> str:
    """Format a parity check result as a readable report."""
    lines = [f"## {ts_path} -> {python_package}\n"]

    total = len(result["missing"]) + len(result["matched"])
    matched_count = len(result["matched"])
    lines.append(f"Coverage: {matched_count}/{total} ({matched_count * 100 // total if total else 0}%)\n")

    if result["missing"]:
        lines.append(f"### Missing ({len(result['missing'])})")
        for name in result["missing"]:
            lines.append(f"  - {name}")
        lines.append("")

    if result["extra"]:
        lines.append(f"### Extra ({len(result['extra'])})")
        for name in result["extra"]:
            lines.append(f"  - {name}")
        lines.append("")

    if result["matched"]:
        lines.append(f"### Matched ({len(result['matched'])})")
        for name in result["matched"]:
            lines.append(f"  - {name}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Entry point."""
    # Determine repo root (assume script is at py/scripts/)
    script_dir = Path(__file__).resolve().parent
    py_dir = script_dir.parent
    repo_root = py_dir.parent

    # Add py/ to sys.path so Python packages can be imported
    sys.path.insert(0, str(py_dir))

    if len(sys.argv) == 3:
        pairs = [(sys.argv[1], sys.argv[2])]
    elif len(sys.argv) == 1:
        pairs = [(str(repo_root / ts_path), py_pkg) for ts_path, py_pkg in _DEFAULT_PAIRS]
    else:
        print(f"Usage: {sys.argv[0]} [<ts_package_path> <python_package_name>]", file=sys.stderr)
        sys.exit(1)

    has_gaps = False
    for ts_path_str, py_pkg in pairs:
        ts_path = Path(ts_path_str)
        result = check_parity(ts_path, py_pkg)
        print(format_report(ts_path_str, py_pkg, result))
        if result["missing"]:
            has_gaps = True

    if has_gaps:
        sys.exit(1)


if __name__ == "__main__":
    main()
