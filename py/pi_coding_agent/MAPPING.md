# pi_coding_agent Package Mapping

## TypeScript → Python Port

| TypeScript | Python |
|------------|--------|
| `packages/coding-agent/src/core/tools/truncate.ts` | `pi_coding_agent/core/tools/truncate.py` |
| `packages/coding-agent/src/core/tools/path-utils.ts` | `pi_coding_agent/core/tools/path_utils.py` |
| `packages/coding-agent/src/core/tools/edit-diff.ts` | `pi_coding_agent/core/tools/edit_diff.py` |
| `packages/coding-agent/src/core/tools/bash.ts` | `pi_coding_agent/core/tools/bash.py` |
| `packages/coding-agent/src/core/tools/read.ts` | `pi_coding_agent/core/tools/read.py` |
| `packages/coding-agent/src/core/tools/edit.ts` | `pi_coding_agent/core/tools/edit.py` |
| `packages/coding-agent/src/core/tools/write.ts` | `pi_coding_agent/core/tools/write.py` |
| `packages/coding-agent/src/core/tools/grep.ts` | `pi_coding_agent/core/tools/grep.py` |
| `packages/coding-agent/src/core/tools/find.ts` | `pi_coding_agent/core/tools/find.py` |
| `packages/coding-agent/src/core/tools/ls.ts` | `pi_coding_agent/core/tools/ls.py` |

## Key Differences

- TypeScript uses TypeBox JSON Schema; Python uses plain `dict[str, Any]` for JSON Schema.
- TypeScript uses `AbortSignal`; Python uses `asyncio.Event`.
- TypeScript uses `execa` for subprocess; Python uses `asyncio.create_subprocess_shell`.
- TypeScript uses `ripgrep` binary via `execa`; Python uses `subprocess.run` with fallback to `re`.
- TypeScript uses `fd` binary for find; Python uses `subprocess.run` with fallback to `glob.glob`.
- Image resizing (TypeScript uses `sharp`) is not implemented; images are returned as raw base64.
- TypeScript `stream.Readable` I/O; Python uses `asyncio.StreamReader`.
