"""Generate py/pi_ai/models_generated.py from packages/ai/src/models.generated.ts.

Reads the TypeScript source, strips TS-specific syntax, evaluates the JS object
with Node.js, and outputs a Python module with all model definitions.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def strip_ts_syntax(ts_source: str) -> str:
    """Strip TypeScript-specific syntax to produce evaluable JavaScript."""
    # Remove import statements
    source = re.sub(r"^import type \{[^}]+\}[^\n]*\n", "", ts_source, flags=re.MULTILINE)
    # Remove 'export const' -> 'const'
    source = source.replace("export const ", "const ", 1)
    # Remove satisfies Model<"..."> annotations
    source = re.sub(r'\}\s*satisfies\s+Model<"[^"]*">', "}", source)
    # Remove 'as const' suffix
    source = re.sub(r"\bas\s+const\s*;", ";", source)
    return source


def build_node_script(ts_file: Path) -> str:
    """Build a Node.js script that evaluates the TS file and outputs JSON."""
    ts_source = ts_file.read_text(encoding="utf-8")
    js_source = strip_ts_syntax(ts_source)

    # The script will define MODELS and then print JSON
    script = js_source + "\nconsole.log(JSON.stringify(MODELS));\n"
    return script


def run_node_script(script: str) -> dict[str, Any]:
    """Write the script to a temp file, run it with node, parse JSON output."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".js",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(script)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["node", tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print("Node.js error:", result.stderr[:2000], file=sys.stderr)
            sys.exit(1)
        try:
            data: dict[str, Any] = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            print(f"Failed to parse Node.js output as JSON: {exc}", file=sys.stderr)
            print(f"Node.js stdout (first 500 chars): {result.stdout[:500]}", file=sys.stderr)
            sys.exit(1)
        return data
    finally:
        os.unlink(tmp_path)


# Fields that map from TS camelCase to Python snake_case
CAMEL_TO_SNAKE_FIELDS: dict[str, str] = {
    "baseUrl": "base_url",
    "contextWindow": "context_window",
    "maxTokens": "max_tokens",
    "cacheRead": "cache_read",
    "cacheWrite": "cache_write",
    "supportsStore": "supports_store",
    "supportsDeveloperRole": "supports_developer_role",
    "supportsReasoningEffort": "supports_reasoning_effort",
    "supportsUsageInStreaming": "supports_usage_in_streaming",
    "maxTokensField": "max_tokens_field",
    "requiresToolResultName": "requires_tool_result_name",
    "requiresAssistantAfterToolResult": "requires_assistant_after_tool_result",
    "requiresThinkingAsText": "requires_thinking_as_text",
    "requiresMistralToolIds": "requires_mistral_tool_ids",
    "thinkingFormat": "thinking_format",
    "openRouterRouting": "open_router_routing",
    "vercelGatewayRouting": "vercel_gateway_routing",
    "supportsStrictMode": "supports_strict_mode",
}

# Keys that belong to OpenAICompletionsCompat (and sub-objects)
OPENAI_COMPLETIONS_COMPAT_KEYS = {
    "supportsStore",
    "supportsDeveloperRole",
    "supportsReasoningEffort",
    "supportsUsageInStreaming",
    "maxTokensField",
    "requiresToolResultName",
    "requiresAssistantAfterToolResult",
    "requiresThinkingAsText",
    "requiresMistralToolIds",
    "thinkingFormat",
    "openRouterRouting",
    "vercelGatewayRouting",
    "supportsStrictMode",
}


def repr_float(value: float) -> str:
    """Return a clean Python float literal, avoiding floating-point noise.

    Uses %.15g which rounds off trailing noise (e.g. 0.09999999999999999 -> 0.1)
    while preserving enough precision for all model cost values.
    """
    formatted = f"{value:.15g}"
    # Ensure the result parses as float, not int
    if "." not in formatted and "e" not in formatted and "n" not in formatted:
        formatted += ".0"
    return formatted


def repr_value(value: object) -> str:
    """Return Python repr for a simple scalar or list value.

    Uses double-quoted strings to match ruff's quote-style = "double" setting.
    """
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr_float(value)
    if isinstance(value, str):
        # json.dumps always produces double-quoted strings
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(repr_value(v) for v in value) + "]"
    return repr(value)


def build_compat_repr(compat: dict[str, Any], used_types: set[str]) -> str:
    """Build a multi-line Python repr for a compat object.

    Always formats kwargs one-per-line to stay within the 120-char line limit.
    """
    compat_keys = set(compat.keys())
    if not (compat_keys & OPENAI_COMPLETIONS_COMPAT_KEYS):
        # Unknown compat type - skip
        return "None"

    used_types.add("OpenAICompletionsCompat")

    # 16 spaces: 12 for Model field indent + 4 for compat constructor body
    field_indent = " " * 16
    close_indent = " " * 12

    parts: list[str] = []
    for ts_key, value in compat.items():
        py_key = CAMEL_TO_SNAKE_FIELDS.get(ts_key, camel_to_snake(ts_key))

        if ts_key == "openRouterRouting" and isinstance(value, dict):
            used_types.add("OpenRouterRouting")
            routing_parts: list[str] = []
            if "only" in value:
                routing_parts.append(f"only={repr_value(value['only'])}")
            if "order" in value:
                routing_parts.append(f"order={repr_value(value['order'])}")
            val_repr = "OpenRouterRouting(" + ", ".join(routing_parts) + ")"
        elif ts_key == "vercelGatewayRouting" and isinstance(value, dict):
            used_types.add("VercelGatewayRouting")
            routing_parts = []
            if "only" in value:
                routing_parts.append(f"only={repr_value(value['only'])}")
            if "order" in value:
                routing_parts.append(f"order={repr_value(value['order'])}")
            val_repr = "VercelGatewayRouting(" + ", ".join(routing_parts) + ")"
        else:
            val_repr = repr_value(value)

        parts.append(f"{field_indent}{py_key}={val_repr},")

    inner = "\n".join(parts)
    return f"OpenAICompletionsCompat(\n{inner}\n{close_indent})"


def build_headers_repr(headers: dict[str, Any]) -> str:
    """Build a multi-line repr for a headers dict to stay within 120 chars."""
    indent = "                "  # 16 spaces (inside Model(...) field)
    close = "            }"  # 12 spaces
    items = [f"{indent}{json.dumps(k)}: {json.dumps(v)}," for k, v in headers.items()]
    return "{\n" + "\n".join(items) + "\n" + close


def build_model_repr(model: dict[str, Any], used_types: set[str]) -> str:
    """Build a Python Model(...) constructor call string."""
    cost = model.get("cost", {})
    cost_repr = (
        f"ModelCost("
        f"input={repr_value(cost.get('input', 0.0))}, "
        f"output={repr_value(cost.get('output', 0.0))}, "
        f"cache_read={repr_value(cost.get('cacheRead', 0.0))}, "
        f"cache_write={repr_value(cost.get('cacheWrite', 0.0))})"
    )

    compat = model.get("compat")
    compat_repr = build_compat_repr(compat, used_types) if compat and isinstance(compat, dict) else "None"

    headers = model.get("headers")
    headers_repr = build_headers_repr(headers) if headers and isinstance(headers, dict) else "None"

    input_val = model.get("input", ["text"])
    input_repr = repr_value(input_val)

    # json.dumps produces double-quoted strings matching ruff's quote-style = "double"
    lines = [
        f"            id={json.dumps(model.get('id', ''))},",
        f"            name={json.dumps(model.get('name', ''))},",
        f"            api={json.dumps(model.get('api', ''))},",
        f"            provider={json.dumps(model.get('provider', ''))},",
        f"            base_url={json.dumps(model.get('baseUrl', ''))},",
        f"            reasoning={repr_value(model.get('reasoning', False))},",
        f"            input={input_repr},",
        f"            cost={cost_repr},",
        f"            context_window={repr_value(model.get('contextWindow', 0))},",
        f"            max_tokens={repr_value(model.get('maxTokens', 0))},",
        f"            headers={headers_repr},",
        f"            compat={compat_repr},",
    ]
    return "Model(\n" + "\n".join(lines) + "\n        )"


def build_import_line(used_types: set[str]) -> str:
    """Build the import line for pi_ai.types based on which types are actually used."""
    always_imported = ["Model", "ModelCost"]
    optional = ["OpenAICompletionsCompat", "OpenRouterRouting", "VercelGatewayRouting"]
    names = always_imported + [t for t in optional if t in used_types]
    return f"from pi_ai.types import {', '.join(names)}"


def generate_python(models_data: dict[str, Any]) -> str:
    """Generate the Python models_generated.py content."""
    # Track which types are actually referenced in generated code
    used_types: set[str] = set()

    # Build all model reprs first (populates used_types)
    provider_blocks: list[str] = []
    for provider_name, provider_models in models_data.items():
        model_lines: list[str] = [f"    {json.dumps(provider_name)}: {{"]
        for model_id, model_data in provider_models.items():
            model_repr = build_model_repr(model_data, used_types)
            model_lines.append(f"        {json.dumps(model_id)}: {model_repr},")
        model_lines.append("    },")
        provider_blocks.append("\n".join(model_lines))

    import_line = build_import_line(used_types)

    lines: list[str] = [
        "# This file is auto-generated by scripts/generate_models.py",
        "# Do not edit manually.",
        "#",
        "# WARNING: This file is executed at import time by load_models().",
        "# The generator (scripts/generate_models.py) executes models.generated.ts via",
        "# Node.js. Only regenerate from a trusted, version-controlled source file.",
        "",
        "from __future__ import annotations",
        "",
        "from collections.abc import Mapping",
        "",
        "from pi_ai.models import register_models",
        import_line,
        "",
        # Mapping[str, Mapping[str, Model]] mirrors TS's `as const` readonly intent.
        # The underlying value is still a dict, but callers see a read-only interface.
        "MODELS: Mapping[str, Mapping[str, Model]] = {",
    ]

    lines.extend(provider_blocks)
    lines.append("}")
    lines.append("")
    lines.append("# Module-level flag — mirrors TS's module cache guarantee.")
    lines.append("# TS: modelRegistry is populated once in a private module-level loop.")
    lines.append("# Python: we use an explicit flag so load_models() is idempotent.")
    lines.append("_MODELS_LOADED: bool = False")
    lines.append("")
    lines.append("")
    lines.append("def load_models(*, force: bool = False) -> None:")
    lines.append('    """Register all models from MODELS into the model registry.')
    lines.append("")
    lines.append("    Idempotent by default: subsequent calls are no-ops unless force=True.")
    lines.append("    Pass force=True to reload after clear_model_registry(), e.g. in tests.")
    lines.append('    """')
    lines.append("    global _MODELS_LOADED")
    lines.append("    if _MODELS_LOADED and not force:")
    lines.append("        return")
    lines.append("    for provider, models in MODELS.items():")
    lines.append("        register_models(provider, models)")
    lines.append("    _MODELS_LOADED = True")
    lines.append("")
    lines.append("")
    lines.append("load_models()")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Entry point."""
    # Locate the TS source file relative to this script
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    ts_file = repo_root / "packages" / "ai" / "src" / "models.generated.ts"
    output_file = script_dir.parent / "pi_ai" / "models_generated.py"

    if not ts_file.exists():
        print(f"Error: TS file not found: {ts_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {ts_file} ...", flush=True)
    try:
        node_script = build_node_script(ts_file)
    except OSError as exc:
        print(f"Error reading TS source file: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Running Node.js to evaluate models ...", flush=True)
    models_data = run_node_script(node_script)

    provider_count = len(models_data)
    model_count = sum(len(v) for v in models_data.values())
    print(f"Found {provider_count} providers, {model_count} models.", flush=True)

    print(f"Generating {output_file} ...", flush=True)
    python_code = generate_python(models_data)
    try:
        output_file.write_text(python_code, encoding="utf-8")
    except OSError as exc:
        print(f"Error writing output file {output_file}: {exc}", file=sys.stderr)
        sys.exit(1)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
