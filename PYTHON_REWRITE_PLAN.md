# Pi-Mono Python Rewrite Plan

## Project Overview

| Package | TS Files | LOC | Dependencies (internal) | Complexity |
|---------|----------|------|------------------------|------------|
| **tui** | 25 | 9,858 | none | Medium |
| **ai** | 38 | 23,022 | none | High |
| **agent** | 5 | 1,518 | ai | Low |
| **coding-agent** | 112 | 37,666 | ai, agent, tui | Very High |
| **web-ui** | 71 | 14,539 | ai, tui | High |
| **mom** | 16 | 4,120 | ai, agent, coding-agent | Medium |
| **pods** | 9 | 1,773 | agent | Low |

Dependency graph (bottom = no deps, top = most deps):

```
          mom
           |
     coding-agent      web-ui
      /    |    \      /    \
   agent  tui   ai   ai   tui
     |
    ai
```

---

## Part 1: Task Decomposition and Parallel Worktree Strategy

### Guiding Principles

1. **Bottom-up**: Start with leaf packages (no internal deps), then build up
2. **Interface-first**: Define Python interfaces/protocols before implementation
3. **Each worktree task ~2000-5000 LOC** to fit Claude Code context well
4. **Shared types package**: Create a `pi_types` module first as the contract layer

### Phase 0: Foundation (Sequential, Must Be Done First)

**Task 0.1: Project Scaffold and Shared Types**
- Create Python monorepo structure (using `uv` workspace or similar)
- Set up `pyproject.toml`, `ruff` (linting/formatting), `pytest`, `mypy`
- Define shared type definitions / protocols in `pi_types/`
- Translate `ai/src/types.ts` -> `pi_ai/types.py` (type definitions only)
- Translate `agent/src/types.ts` -> `pi_agent/types.py`
- Set up CI skeleton (GitHub Actions)
- **Estimated effort**: 1 session

### Phase 1: Leaf Packages (Fully Parallel)

These have no internal dependencies and can be done simultaneously in separate worktrees.

#### Task 1.1: `pi_tui` - Terminal UI Library
**Scope**: `packages/tui/src/` (25 files, ~9,858 LOC)
**Sub-tasks** (can be further split into 2 worktrees):

- **Task 1.1a: TUI Core** (~5,000 LOC)
  - `terminal.ts` -> terminal abstraction (use `blessed` or raw ANSI)
  - `keys.ts`, `keybindings.ts` -> key handling
  - `editor-component.ts`, `kill-ring.ts`, `undo-stack.ts` -> editor
  - `stdin-buffer.ts` -> input buffering
  - `tui.ts` -> main TUI framework
  - `utils.ts`, `fuzzy.ts`, `autocomplete.ts` -> utilities

- **Task 1.1b: TUI Components** (~5,000 LOC)
  - `components/` directory
  - `terminal-image.ts` -> terminal image rendering

#### Task 1.2: `pi_ai` - AI/LLM Abstraction Layer
**Scope**: `packages/ai/src/` (38 files, ~23,022 LOC, but ~323K is generated models)
**Sub-tasks** (split into 3 worktrees):

- **Task 1.2a: AI Core Types and Stream** (~3,000 LOC)
  - `types.ts` -> Pydantic models / TypedDicts / dataclasses
  - `stream.ts` -> async generator based streaming
  - `models.ts` -> model registry
  - `api-registry.ts` -> API registry
  - `env-api-keys.ts` -> env key detection
  - `index.ts` -> public API
  - `cli.ts` -> CLI entry point (use `click` or `typer`)

- **Task 1.2b: AI Providers - OpenAI-compatible** (~5,000 LOC)
  - `providers/openai-responses.ts`
  - `providers/openai-responses-shared.ts`
  - `providers/openai-completions.ts`
  - `providers/openai-codex-responses.ts`
  - `providers/azure-openai-responses.ts`
  - `providers/github-copilot-headers.ts`
  - `providers/transform-messages.ts`
  - `providers/simple-options.ts`
  - `providers/register-builtins.ts`
  - Use `openai` Python SDK

- **Task 1.2c: AI Providers - Non-OpenAI** (~5,000 LOC)
  - `providers/anthropic.ts` -> use `anthropic` Python SDK
  - `providers/google.ts`, `google-shared.ts`, `google-vertex.ts`, `google-gemini-cli.ts` -> use `google-genai`
  - `providers/amazon-bedrock.ts` -> use `boto3`

- **Task 1.2d: AI Utilities** (~3,000 LOC)
  - `utils/event-stream.ts` -> async event stream
  - `utils/http-proxy.ts` -> proxy support
  - `utils/json-parse.ts` -> partial JSON parsing
  - `utils/oauth/` -> OAuth flow
  - `utils/overflow.ts` -> context overflow handling
  - `utils/sanitize-unicode.ts` -> unicode sanitization
  - `utils/validation.ts` -> schema validation (use Pydantic)
  - `utils/typebox-helpers.ts` -> adapt to Pydantic

### Phase 2: Mid-Level Packages (After Phase 1)

#### Task 2.1: `pi_agent` - Agent Core
**Scope**: `packages/agent/src/` (5 files, ~1,518 LOC)
**Dependencies**: `pi_ai` (from Phase 1)
- `agent.ts`, `agent-loop.ts` -> async agent loop
- `proxy.ts` -> agent proxy
- `types.ts` -> already done in Phase 0
- **Single worktree, 1 session**

#### Task 2.2: `pi_coding_agent` - Coding Agent
**Scope**: `packages/coding-agent/src/` (112 files, ~37,666 LOC)
**Dependencies**: `pi_ai`, `pi_agent`, `pi_tui`
**Sub-tasks** (split into 6 worktrees):

- **Task 2.2a: Core - Tools** (~4,000 LOC)
  - `core/tools/` -> bash, edit, find, grep, ls, read, write, etc.
  - Each tool as a separate module with consistent interface

- **Task 2.2b: Core - Session and Config** (~5,000 LOC)
  - `core/agent-session.ts` -> session management
  - `core/session-manager.ts` -> session persistence
  - `core/settings-manager.ts` -> settings
  - `core/auth-storage.ts` -> auth storage
  - `config.ts` -> configuration
  - `migrations.ts` -> data migrations

- **Task 2.2c: Core - Agent Logic** (~6,000 LOC)
  - `core/model-resolver.ts`, `core/model-registry.ts` -> model selection
  - `core/system-prompt.ts` -> prompt construction
  - `core/prompt-templates.ts` -> templates
  - `core/messages.ts` -> message handling
  - `core/compaction/` -> context compaction
  - `core/skills.ts`, `core/slash-commands.ts` -> skills/commands
  - `core/event-bus.ts` -> event system
  - `core/diagnostics.ts`, `core/timings.ts` -> diagnostics

- **Task 2.2d: Core - Extensions and SDK** (~3,000 LOC)
  - `core/extensions/` -> extension system
  - `core/sdk.ts` -> SDK interface
  - `core/exec.ts`, `core/bash-executor.ts` -> execution
  - `core/resource-loader.ts` -> resource loading

- **Task 2.2e: CLI and Utils** (~4,000 LOC)
  - `cli/` -> CLI interface (use `typer` or `click`)
  - `cli.ts`, `main.ts` -> entry points
  - `utils/` -> git, clipboard, image, shell utilities

- **Task 2.2f: Modes - Interactive and RPC** (~6,000 LOC)
  - `modes/interactive/` -> TUI interactive mode
  - `modes/rpc/` -> RPC mode (JSON-RPC or similar)
  - `modes/print-mode.ts` -> simple print mode
  - `core/export-html/` -> HTML export

### Phase 3: Top-Level Packages (After Phase 2)

#### Task 3.1: `pi_web_ui` - Web UI Components
**Scope**: `packages/web-ui/src/` (71 files, ~14,539 LOC)
**Dependencies**: `pi_ai`, `pi_tui`
**Sub-tasks** (split into 2-3 worktrees):

- **Task 3.1a: Web UI Backend/API**
  - Storage, tools, utilities -> FastAPI or similar
  - Adapt web component architecture to Python backend + JS frontend approach

- **Task 3.1b: Web UI Components**
  - Chat panel, dialogs, prompts -> likely keep as JS/TS frontend
  - Python serves as API backend
  - Note: web-ui may keep TS frontend, with Python backend replacing Node server

#### Task 3.2: `pi_mom` - Slack Bot / Manager
**Scope**: `packages/mom/src/` (16 files, ~4,120 LOC)
**Dependencies**: `pi_ai`, `pi_agent`, `pi_coding_agent`
- `agent.ts` -> agent logic
- `slack.ts` -> Slack integration (use `slack-bolt`)
- `sandbox.ts` -> sandbox management
- `store.ts` -> data store
- `tools/` -> tools
- **Single worktree, 1-2 sessions**

#### Task 3.3: `pi_pods` - Pod Management
**Scope**: `packages/pods/src/` (9 files, ~1,773 LOC)
**Dependencies**: `pi_agent`
- `commands/` -> CLI commands
- `ssh.ts` -> SSH management (use `paramiko` or `asyncssh`)
- `config.ts`, `model-configs.ts` -> configuration
- **Single worktree, 1 session**

### Parallel Execution Summary

```
Time ->

Phase 0:  [=== Foundation/Types ===]
               |
Phase 1:  [= tui-core =] [= tui-components =] [= ai-core =] [= ai-openai =] [= ai-non-openai =] [= ai-utils =]
               |                                     |
Phase 2:  [= agent =] [= ca-tools =] [= ca-session =] [= ca-logic =] [= ca-ext =] [= ca-cli =] [= ca-modes =]
               |
Phase 3:  [= web-ui-be =] [= web-ui-fe =] [= mom =] [= pods =]
```

Maximum parallelism: **6 worktrees in Phase 1**, **7 in Phase 2**.

---

## Part 2: Quality Assurance Strategy

### 2.1 Interface Contract Verification

For every module, before coding starts:

1. **Extract TS interfaces** -> Generate a `contracts.py` file with:
   - All public function signatures (as Python `Protocol` classes)
   - All public types (as Pydantic models or dataclasses)
   - All exported constants
2. **Create a checklist**: Auto-generate from TS source using a script:
   ```bash
   # Script: scripts/extract_public_api.py
   # Parses TS exports and generates a checklist of functions/classes/types
   # that must exist in the Python version
   ```
3. **Interface tests**: Write tests that verify the Python module exports match the contract

### 2.2 Feature Parity Verification

For each module conversion:

1. **Function mapping document**: Create `MAPPING.md` in each Python package:
   ```markdown
   | TS Function/Class | Python Equivalent | Status | Notes |
   |-------------------|-------------------|--------|-------|
   | streamAnthropic() | stream_anthropic() | Done | Uses anthropic SDK |
   | transformMessages() | transform_messages() | Done | |
   ```

2. **Automated parity check** (CI step):
   - Script that parses TS exports and Python `__all__` / public API
   - Flags any TS export without a Python counterpart
   - Stored as `scripts/check_parity.py`

3. **Behavioral tests**: For each TS test file, create a corresponding Python test:
   - `packages/ai/test/stream.test.ts` -> `tests/ai/test_stream.py`
   - Tests must cover the same scenarios
   - Use `pytest-asyncio` for async tests

### 2.3 Test Coverage Requirements

| Level | Coverage Target | Tool |
|-------|----------------|------|
| Unit tests | >= 80% line coverage | `pytest-cov` |
| Type checking | Strict mode | `mypy --strict` or `pyright` |
| Linting | Zero warnings | `ruff check` |
| Formatting | Enforced | `ruff format` |

### 2.4 Per-Module Review Checklist (Before Merge)

```
[ ] All public APIs from TS version have Python equivalents
[ ] MAPPING.md is complete with all functions/classes
[ ] Unit tests pass (pytest)
[ ] Test coverage >= 80% (pytest-cov)
[ ] Type checking passes (mypy --strict)
[ ] Linting passes (ruff check)
[ ] Formatting passes (ruff format)
[ ] Interface contracts verified
[ ] No hardcoded values that were configurable in TS
[ ] Error handling follows Python conventions (exceptions, not error codes)
[ ] Async code uses asyncio properly
[ ] Dependencies are declared in pyproject.toml
```

---

## Part 3: Integration Testing After Merge

### 3.1 Merge Strategy

Use a **main Python branch** (`python-rewrite`) as integration target:

```
main (TS)
  |
  +-- python-rewrite (integration branch)
        |
        +-- python/phase1-ai-core
        +-- python/phase1-ai-providers-openai
        +-- python/phase1-ai-providers-other
        +-- python/phase1-tui-core
        +-- ...
```

Merge order follows the dependency graph:
1. Phase 0 (types) -> merge first
2. Phase 1 (leaf packages) -> merge in any order
3. Phase 2 (mid-level) -> merge after Phase 1 dependencies are in
4. Phase 3 (top-level) -> merge last

### 3.2 Integration Test Tiers

**Tier 1: Cross-module import tests** (automated, runs on every merge)
```python
# tests/integration/test_imports.py
def test_all_packages_importable():
    import pi_ai
    import pi_agent
    import pi_tui
    import pi_coding_agent
    # ... verify no circular imports, no missing deps
```

**Tier 2: Cross-module integration tests** (automated)
```python
# tests/integration/test_ai_agent.py
async def test_agent_uses_ai_stream():
    """Agent should be able to stream from AI layer"""
    # Mock LLM response, verify agent loop processes it correctly

# tests/integration/test_coding_agent_tools.py
async def test_coding_agent_edit_tool():
    """Coding agent edit tool should work end-to-end"""
    # Create temp file, run edit tool, verify changes
```

**Tier 3: End-to-end tests** (semi-automated)
```python
# tests/e2e/test_cli.py
def test_cli_help():
    result = subprocess.run(["python", "-m", "pi_coding_agent", "--help"])
    assert result.returncode == 0

# tests/e2e/test_interactive_session.py
async def test_basic_conversation():
    """Start agent, send message, get response"""
    # Uses mock LLM, verifies full pipeline
```

**Tier 4: Behavior comparison tests** (for critical paths)
```python
# tests/comparison/test_ai_output_parity.py
# Run same prompts through TS and Python versions
# Compare structured outputs (not exact text, but structure/types)
```

### 3.3 CI Pipeline for Integration

```yaml
# .github/workflows/python-integration.yml
on:
  pull_request:
    branches: [python-rewrite]

jobs:
  test:
    steps:
      - uses: actions/setup-python@v5
      - run: uv sync
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy --strict .
      - run: pytest tests/unit/ --cov --cov-fail-under=80
      - run: pytest tests/integration/
      - run: pytest tests/e2e/

  parity-check:
    steps:
      - run: python scripts/check_parity.py
```

---

## Part 4: GitHub Projects and Automation

### 4.1 GitHub Project Setup

Create a GitHub Project board with these views:

**View 1: Kanban Board**
- Columns: `Backlog` | `Ready` | `In Progress` | `In Review` | `Done`

**View 2: By Phase**
- Group by custom field `Phase`: Phase 0, 1, 2, 3

**View 3: By Package**
- Group by label: `pkg:ai`, `pkg:agent`, `pkg:tui`, etc.

### 4.2 Issue Structure

Each task from Part 1 becomes a GitHub Issue:

```markdown
Title: [Python Rewrite] pi_ai: Core Types and Stream (Task 1.2a)

## Scope
Convert the following TS files to Python:
- `packages/ai/src/types.ts` -> `pi_ai/types.py`
- `packages/ai/src/stream.ts` -> `pi_ai/stream.py`
- ...

## Acceptance Criteria
- [ ] All public types defined as Pydantic models
- [ ] Async streaming with Python async generators
- [ ] Unit tests with >= 80% coverage
- [ ] MAPPING.md complete
- [ ] mypy --strict passes
- [ ] ruff check/format passes

## Dependencies
- Blocked by: #<phase0-issue-number>
- Blocks: #<task-2.1-issue-number>

## Labels
`python-rewrite`, `phase:1`, `pkg:ai`, `size:M`

## Metadata
- Phase: 1
- Package: ai
- Estimated LOC: ~3,000
- Worktree branch: `python/phase1-ai-core`
```

### 4.3 Automation with GitHub Actions

#### A. Pre-commit / Pre-push Quality Gate

```yaml
# .github/workflows/python-quality.yml
name: Python Quality Check
on:
  push:
    paths: ['py/**', 'tests/**']
  pull_request:
    paths: ['py/**', 'tests/**']

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - name: Lint
        run: ruff check .
      - name: Format check
        run: ruff format --check .
      - name: Type check
        run: mypy --strict .
      - name: Tests
        run: pytest --cov --cov-fail-under=80
      - name: Parity check
        run: python scripts/check_parity.py
```

#### B. Auto-label and Move Issues

```yaml
# .github/workflows/project-automation.yml
name: Project Automation
on:
  issues:
    types: [opened, closed]
  pull_request:
    types: [opened, closed, merged]

jobs:
  auto-move:
    runs-on: ubuntu-latest
    steps:
      - name: Move to In Progress when PR opened
        if: github.event_name == 'pull_request' && github.event.action == 'opened'
        uses: actions/github-script@v7
        with:
          script: |
            // Move linked issue to "In Progress" in project board

      - name: Move to Done when PR merged
        if: github.event_name == 'pull_request' && github.event.action == 'closed' && github.event.pull_request.merged
        uses: actions/github-script@v7
        with:
          script: |
            // Move linked issue to "Done" in project board
```

#### C. Claude Task Assignment via GitHub Actions

To let Claude pick up tasks from GitHub Projects:

```yaml
# .github/workflows/claude-task-runner.yml
# Triggered manually or on schedule
name: Claude Task Runner
on:
  workflow_dispatch:
    inputs:
      issue_number:
        description: 'Issue number to work on'
        required: true

jobs:
  run-claude:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Fetch issue details
        id: issue
        run: |
          gh issue view ${{ inputs.issue_number }} --json title,body,labels
      - name: Run Claude Code
        # Use Claude Code CLI or API to process the issue
        # Claude reads the issue, creates worktree, implements, tests, pushes
```

Alternatively, use a **CLAUDE.md convention** where Claude reads the project board:

```bash
# Claude workflow for picking up tasks:
# 1. gh project item-list <project-number> --owner <owner> --format json
# 2. Filter for items in "Ready" column
# 3. Pick the highest priority unblocked item
# 4. Move to "In Progress"
# 5. Create worktree branch
# 6. Implement
# 7. Push and create PR
# 8. Move to "In Review"
```

### 4.4 Local Git Hooks (via Husky equivalent for Python)

```bash
# .husky/pre-commit (or use pre-commit framework)
# For Python files:
ruff check --fix py/
ruff format py/
mypy --strict py/
```

Or use `pre-commit` framework:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.0
    hooks:
      - id: mypy
        args: [--strict]
```

---

## Part 5: Recommended Python Tech Stack

| Purpose | TS Library | Python Equivalent |
|---------|-----------|-------------------|
| Package management | npm workspaces | `uv` workspace |
| Type checking | TypeScript | `mypy` (strict) or `pyright` |
| Linting/Formatting | Biome | `ruff` (check + format) |
| Testing | Vitest | `pytest` + `pytest-asyncio` |
| Coverage | Vitest | `pytest-cov` |
| Schema validation | TypeBox + Ajv | `pydantic` |
| CLI | custom | `typer` or `click` |
| HTTP client | undici/fetch | `httpx` |
| Async | Node async | `asyncio` |
| OpenAI SDK | `openai` npm | `openai` pip |
| Anthropic SDK | `@anthropic-ai/sdk` | `anthropic` pip |
| Google AI | `@google/genai` | `google-genai` pip |
| AWS Bedrock | `@aws-sdk` | `boto3` |
| Slack | `@slack/web-api` | `slack-bolt` |
| SSH | custom | `asyncssh` or `paramiko` |
| Terminal UI | custom | `textual` or `prompt-toolkit` |
| JSON streaming | `partial-json` | `partial-json-parser` or custom |
| Glob/file matching | `glob`, `minimatch` | `pathlib.glob`, `fnmatch` |
| Git operations | custom shell | `gitpython` or subprocess |
| Pre-commit hooks | Husky | `pre-commit` |

---

## Part 6: Estimated Timeline and Priority

| Task ID | Task | Phase | Parallel Group | Est. Sessions |
|---------|------|-------|----------------|---------------|
| 0.1 | Foundation/Types | 0 | - | 1 |
| 1.1a | TUI Core | 1 | A | 2 |
| 1.1b | TUI Components | 1 | A | 2 |
| 1.2a | AI Core Types/Stream | 1 | B | 1 |
| 1.2b | AI Providers OpenAI | 1 | B | 2 |
| 1.2c | AI Providers Non-OpenAI | 1 | B | 2 |
| 1.2d | AI Utilities | 1 | B | 1 |
| 2.1 | Agent Core | 2 | C | 1 |
| 2.2a | Coding Agent Tools | 2 | D | 2 |
| 2.2b | Coding Agent Session/Config | 2 | D | 2 |
| 2.2c | Coding Agent Logic | 2 | D | 2 |
| 2.2d | Coding Agent Extensions/SDK | 2 | D | 1 |
| 2.2e | Coding Agent CLI/Utils | 2 | D | 2 |
| 2.2f | Coding Agent Modes | 2 | D | 2 |
| 3.1 | Web UI | 3 | E | 3 |
| 3.2 | Mom (Slack Bot) | 3 | E | 2 |
| 3.3 | Pods | 3 | E | 1 |

**Critical path** (sequential minimum): Phase 0 (1) + Phase 1 longest (2) + Phase 2 longest (2) + Phase 3 longest (3) = **~8 sessions**

**With full parallelism**: Each phase completes as fast as its longest task.
