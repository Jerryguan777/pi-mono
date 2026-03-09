# Pi-Mono TypeScript → Python 重写计划

## 概述

将 pi-mono TypeScript 单体仓库（7 个包，约 80,000 行）重写为 Python，保留原有架构、接口和逻辑，同时采用 Pythonic 最佳实践。所有 Python 代码位于 `py/` 目录下。工作分为 5 个阶段（0–4），同一阶段内的任务在独立 worktree 中并行执行。

**分支**: `python-rewrite`
**预估总量**: 约 36,800 行 Python 代码

---

## 依赖关系图

```
ai (基础层, 无依赖)              tui (独立, 无 pi-mono 内部依赖)
    ↓                                 ↓
  agent (依赖 ai)                     │
    ↓                                 ↓
  coding-agent (依赖 ai, agent, tui)
    ↓               ↓
  mom (依赖 coding-agent)          web-ui (跳过)
  pods (依赖 agent)
```

---

## Phase 0: 基础设施（1 个任务，串行）

| 任务 | 分支 | 预估行数 | 描述 |
|------|------|---------|------|
| 0-1 | `py/infra` | 800 | 项目脚手架 + CI |

**范围**: 创建 `py/` 目录结构（pyproject.toml, ruff.toml, mypy.ini, conftest.py），各包的 stub，脚本（`extract_public_api.py`、`check_parity.py`），将 `_CLAUDE.md` 移为 `py/PYTHON_REWRITE_GUIDE.md`，创建 `py/CLAUDE.md`，修复 CI 工作流，创建测试目录。

**验收**: `cd py && uv sync` 成功；`ruff check .` 通过；`mypy --strict .` 通过。

---

## Phase 1: 基础层（4 个并行任务）

这些包没有 pi-mono 内部跨包依赖，可完全并行。

| 任务 | 分支 | 预估行数 | 描述 |
|------|------|---------|------|
| 1-1 | `py/ai-core` | 1,500 | pi_ai 核心类型 + 工具函数 |
| 1-2 | `py/ai-providers-a` | 2,500 | Provider: Anthropic + OpenAI 系列 |
| 1-3 | `py/ai-providers-b` | 3,500 | Provider: Google + Bedrock + OAuth |
| 1-4 | `py/tui` | 4,000 | pi_tui 终端 UI |

### 任务 1-1: pi_ai 核心类型 + 工具函数
**TS 源文件**: `types.ts` (308), `stream.ts` (60), `api-registry.ts` (98), `models.ts` (77), `env-api-keys.ts` (115), `utils/event-stream.ts` (87), `utils/overflow.ts` (121), `utils/validation.ts` (84), `utils/sanitize-unicode.ts` (25), `utils/json-parse.ts` (28), `utils/http-proxy.ts` (13), `providers/simple-options.ts` (46), `providers/transform-messages.ts` (167), `providers/register-builtins.ts` (73)

**Python 输出**: `py/pi_ai/types.py`, `stream.py`, `api_registry.py`, `models.py`, `env_api_keys.py`, `utils/*.py`, `providers/simple_options.py`, `providers/transform_messages.py`, `providers/register_builtins.py`

### 任务 1-2: pi_ai Providers A（Anthropic + OpenAI）
**TS 源文件**: `anthropic.ts` (851), `openai-completions.ts` (828), `openai-responses.ts` (259), `openai-responses-shared.ts` (480), `azure-openai-responses.ts` (256), `openai-codex-responses.ts` (863), `github-copilot-headers.ts` (37)

**Python 输出**: `py/pi_ai/providers/anthropic.py`, `openai_completions.py`, `openai_responses.py`, `openai_responses_shared.py`, `azure_openai_responses.py`, `openai_codex_responses.py`, `github_copilot_headers.py`

**注意**: 这些文件会 import `pi_ai.types` 等，可使用 `TYPE_CHECKING` import + stub。运行时集成在 Phase 2 完成。

### 任务 1-3: pi_ai Providers B（Google + Bedrock）+ OAuth
**TS 源文件**: `google.ts` (452), `google-shared.ts` (317), `google-gemini-cli.ts` (940), `google-vertex.ts` (482), `amazon-bedrock.ts` (731), `utils/oauth/`（8 个文件，约 2,641 行）

**Python 输出**: `py/pi_ai/providers/google*.py`, `amazon_bedrock.py`, `py/pi_ai/oauth/*.py`

### 任务 1-4: pi_tui
**TS 源文件**: `packages/tui/src/`（25 个文件，9,858 行）

**Python 输出**: `py/pi_tui/` — `terminal.py`, `tui.py`, `keys.py`, `keybindings.py`, `stdin_buffer.py`, `autocomplete.py`, `fuzzy.py`, `utils.py`, `terminal_image.py`, `components/*.py`

**设计决策**: 自研差异渲染引擎（与 TS 版本一致），直接操作终端转义序列，不依赖 textual/prompt-toolkit。保持相同的 Component/Container/Focusable 组件模型。

---

## Phase 2: 中间层（2 个并行任务）

需要 Phase 1 全部合并后才能开始。

| 任务 | 分支 | 预估行数 | 描述 |
|------|------|---------|------|
| 2-1 | `py/agent` | 1,500 | pi_agent |
| 2-2 | `py/ai-integration` | 500 | pi_ai 集成 + 最终导出 |

### 任务 2-1: pi_agent
**TS 源文件**: `agent-loop.ts` (417), `agent.ts` (559), `proxy.ts` (340), `types.ts` (194)

**Python 输出**: `py/pi_agent/types.py`, `agent_loop.py`, `agent.py`, `proxy.py`

**设计决策**: Agent loop 用 async generator 输出事件流；Tool 接口用 ABC/Protocol；Proxy 用 httpx。

### 任务 2-2: pi_ai 集成
**范围**: 整合 Task 1-1/1-2/1-3 的成果 — 编写最终的 `__init__.py`（完整 `__all__`）、provider 注册、`register_builtins()`、生成 `models_generated.py`、`stream()` 分发路径的集成测试。

---

## Phase 3: 上层（8 个并行任务）

需要 Phase 2 全部合并后才能开始。coding-agent 拆分为 6 个独立任务。web-ui 跳过。

| 任务 | 分支 | 预估行数 | 描述 |
|------|------|---------|------|
| 3-1 | `py/ca-session` | 3,000 | coding-agent 核心会话 |
| 3-2 | `py/ca-tools` | 2,500 | coding-agent 工具 |
| 3-3 | `py/ca-extensions` | 4,000 | 扩展 + 压缩 + 模型管理 |
| 3-4a | `py/ca-interactive-core` | 3,000 | 交互模式核心 + CLI |
| 3-4b | `py/ca-interactive-components` | 2,500 | 交互模式组件 |
| 3-4c | `py/ca-rpc-utils` | 1,500 | RPC + 工具函数 |
| 3-5 | `py/pods` | 1,500 | pi_pods |
| 3-6 | `py/mom` | 2,500 | pi_mom |

### 任务 3-1: 核心会话
**TS 源文件**: `agent-session.ts` (2,865), `session-manager.ts` (1,401), `package-manager.ts` (1,729), `event-bus.ts`, `messages.ts`, `system-prompt.ts`, `bash-executor.ts`, `exec.ts`

### 任务 3-2: 工具
**TS 源文件**: `packages/coding-agent/src/core/tools/*.ts` (2,483)
**设计决策**: 使用类继承 `class BashTool(AgentTool)` 替代工厂函数。

### 任务 3-3: 扩展 + 压缩 + 模型管理
**TS 源文件**: `extensions/` (2,967), `compaction/` (1,322), `model-registry.ts` (665), `model-resolver.ts` (527), `auth-storage.ts` (464), `settings-manager.ts` (888), `skills.ts` (459), `resource-loader.ts` (871), `prompt-templates.ts` (299)

### 任务 3-4a: 交互模式核心 + CLI
**TS 源文件**: `interactive-mode.ts` (4,391), `theme.ts` (1,100) + 主题 JSON 文件, `print-mode.ts` (124), `main.ts` (770), `config.ts` (241), `migrations.ts` (295), `cli/args.ts` (310) 等

### 任务 3-4b: 交互模式组件
**TS 源文件**: `modes/interactive/components/`（7,536 行，30 个组件）

### 任务 3-4c: RPC + 工具函数
**TS 源文件**: `rpc-types.ts` (263), `rpc-client.ts` (510), `rpc-mode.ts` (639), `utils/shell.ts` (202), `utils/git.ts` (192), clipboard/image 工具 (1,515), `export-html/` (652)

### 任务 3-5: pi_pods
**TS 源文件**: `packages/pods/src/` (1,773)

### 任务 3-6: pi_mom
**TS 源文件**: `packages/mom/src/` (4,120)

---

## Phase 4: 集成与收尾（2 个并行任务）

| 任务 | 分支 | 预估行数 | 描述 |
|------|------|---------|------|
| 4-1 | `py/integration` | 1,500 | 跨包集成测试 + E2E 测试 |
| 4-2 | `py/parity` | 500 | 对等验证 + 最终打磨 |

---

## 质量保证策略

### 每个任务提交前的检查

```bash
cd py
uv run ruff check .                    # 代码检查
uv run ruff format --check .           # 格式检查
uv run mypy --strict .                 # 类型检查
uv run pytest tests/unit/<pkg>/ --cov=<pkg> --cov-fail-under=80 -v  # 单元测试
uv run python scripts/check_parity.py ../../packages/<pkg>/src py/<package>  # 对等检查
```

### 单元测试规范

- **位置**: `py/tests/unit/<package>/test_<module>.py`
- **框架**: pytest + pytest-asyncio（auto 模式）
- **Mock 策略**: 对外部 SDK（anthropic, openai, google-genai, boto3）使用 `unittest.mock.AsyncMock`
- **覆盖率**: 每个公共函数/类至少 1 个正向测试 + 1 个边界/异常测试
- **Fixture 目录**: `py/tests/fixtures/<package>/` 存放录制的 JSON 响应数据
- **命名规范**: `test_<函数名>_<场景>` (例: `test_stream_anthropic_basic`)

### Phase 合并后的验证

```bash
cd py && uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest --cov --cov-fail-under=80 -v
```

---

## CI/CD

修复后的 `.github/workflows/python-quality.yml`:

```yaml
name: Python Quality
on:
  push:
    paths: ['py/**']
    branches: ['python-rewrite', 'py/**']
  pull_request:
    paths: ['py/**']

jobs:
  quality:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: py
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          version: "latest"
      - name: Install dependencies
        run: uv sync
      - name: Lint
        run: uv run ruff check .
      - name: Format check
        run: uv run ruff format --check .
      - name: Type check
        run: uv run mypy --strict .
      - name: Tests
        run: uv run pytest --cov --cov-fail-under=80 -x
      - name: Parity check
        run: uv run python scripts/check_parity.py
        continue-on-error: true
```

---

## 合并策略

1. Phase 0 首先合并到 `python-rewrite` 分支
2. 同一 Phase 内的任务互不冲突（各自写不同的 `py/<package>/` 文件），可任意顺序合并
3. 跨 Phase 必须上一 Phase 全部合并后才开始下一 Phase
4. 合并命令: `git merge --no-ff py/<branch> -m "merge: [Phase X] <描述>"`
5. 合并后: 运行全量质量检查

### 冲突预防
- 每个任务只写自己包目录下的文件
- `py/pyproject.toml`（workspace 根）仅在 Phase 0 修改
- 各包的 `pyproject.toml` 各自独立
- 如需添加 workspace 级依赖，记录在 issue 中由合并协调人统一添加

---

## 跳过的包

- **pi_web_ui**: 浏览器端组件（Lit + Tailwind），不适用于 Python。未来需要时再单独处理。
