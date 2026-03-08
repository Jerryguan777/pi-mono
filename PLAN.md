# Pi-Mono Python Rewrite — 完整执行计划

## 项目概况

| 包 | TS 文件数 | TS 行数 | 依赖 |
|---|---------|--------|------|
| ai | 38 | 23,022 | 无内部依赖 |
| agent | 5 | 1,518 | ai |
| tui | 25 | 9,858 | 无内部依赖 |
| coding-agent | 112 | 37,666 | ai, agent, tui |
| web-ui | 71 | 14,539 | ai, agent, tui |
| mom | 16 | 4,120 | ai, agent, coding-agent |
| pods | 9 | 1,773 | agent |

## 依赖关系图（决定了开发阶段）

```
Layer 0 (无依赖):  tui, ai-types
Layer 1 (基础):    ai-core, ai-providers, ai-utils
Layer 2 (中间):    agent, coding-agent-tools
Layer 3 (上层):    coding-agent-core, coding-agent-session
Layer 4 (应用):    coding-agent-cli, coding-agent-modes, web-ui, mom, pods
```

---

## 阶段 0：项目脚手架（人工 + 1 个 Claude）

### 任务 0.1：项目脚手架和基础设施

**范围**: 创建 `py/` 目录结构，配置工具链，搭建 CI

**这个任务由你（人工）和 1 个 Claude 协作完成。**

---

## 阶段 1：无依赖的基础层（2 个 worktree 并行）

这一层的两个包互不依赖，可以完全并行开发。

### 任务 1.1：pi_tui — TUI 库

- **TS 源码**: `packages/tui/src/` (25 files, ~9,858 lines)
- **分为 2 个子任务**:
  - **1.1a TUI 核心** (~5,000 lines): terminal.ts, keys.ts, keybindings.ts, editor-component.ts, kill-ring.ts, undo-stack.ts, stdin-buffer.ts, tui.ts, utils.ts, fuzzy.ts, autocomplete.ts
  - **1.1b TUI 组件** (~5,000 lines): components/ 目录全部文件, terminal-image.ts
- **这两个子任务有顺序依赖**（1.1b 依赖 1.1a 的基础组件接口），建议在同一个 worktree 中串行完成

### 任务 1.2：pi_ai — AI 抽象层

- **TS 源码**: `packages/ai/src/` (38 files, ~23,022 lines)
- **分为 4 个子任务，建议 2 个 worktree**:

| 子任务 | 范围 | 行数 | Worktree |
|-------|------|------|----------|
| 1.2a 核心类型和流 | types.ts, stream.ts, models.ts, models.generated.ts, api-registry.ts, env-api-keys.ts, index.ts, cli.ts | ~5,000 | worktree-ai-core |
| 1.2b OpenAI 提供商 | providers/openai-*.ts, azure-*.ts, github-copilot-*.ts, transform-messages.ts, simple-options.ts, register-builtins.ts | ~8,000 | worktree-ai-providers |
| 1.2c 非 OpenAI 提供商 | providers/anthropic.ts, google*.ts, amazon-bedrock.ts | ~5,000 | worktree-ai-providers |
| 1.2d 工具函数 | utils/ 全部 (event-stream, http-proxy, json-parse, oauth/, overflow, sanitize-unicode, validation, typebox-helpers) | ~5,000 | worktree-ai-core |

- **依赖关系**: 1.2b/1.2c 依赖 1.2a 的类型定义；1.2d 相对独立
- **建议**: 1.2a + 1.2d 在一个 worktree 串行，1.2b + 1.2c 在另一个 worktree 串行（合并后跑集成测试）

**阶段 1 并行度: 3 个 worktree (tui / ai-core / ai-providers)**

---

## 阶段 2：中间层（阶段 1 完成后启动，最多 4 个 worktree 并行）

### 任务 2.1：pi_agent — Agent 核心

- **TS 源码**: `packages/agent/src/` (5 files, ~1,518 lines)
- **范围**: agent.ts, agent-loop.ts, proxy.ts, types.ts, index.ts
- **体量小，1 个 worktree 即可**
- **依赖**: pi_ai

### 任务 2.2：pi_coding_agent — 分为 6 个子任务

- **TS 源码**: `packages/coding-agent/src/` (112 files, ~37,666 lines)
- **这是最大的包，必须细分**:

| 子任务 | 范围 | 文件数 | 估计行数 | 依赖 | Worktree |
|-------|------|-------|---------|------|----------|
| 2.2a 工具 | core/tools/ (bash, edit, edit-diff, find, grep, ls, read, write, truncate, path-utils) | 11 | ~4,000 | pi_ai, pi_agent | wt-ca-tools |
| 2.2b 会话和配置 | core/agent-session, session-manager, settings-manager, auth-storage, config, migrations, defaults, resolve-config-value | 10 | ~5,000 | pi_ai, pi_agent | wt-ca-session |
| 2.2c Agent 逻辑 | core/model-resolver, model-registry, system-prompt, prompt-templates, messages, compaction/, skills, slash-commands, event-bus, diagnostics, timings, keybindings, footer-data-provider, package-manager | 18 | ~6,000 | pi_ai, pi_agent | wt-ca-logic |
| 2.2d 扩展和 SDK | core/extensions/ (index, loader, runner, types, wrapper), core/sdk, core/exec, core/bash-executor, core/resource-loader, core/export-html/ | 12 | ~3,000 | pi_ai, pi_agent | wt-ca-ext |
| 2.2e 工具函数和 CLI | utils/ (git, clipboard*, image*, shell, sleep, mime, frontmatter, changelog, photon, tools-manager), cli/ (args, session-picker, config-selector, file-processor, list-models), cli.ts, main.ts | 18 | ~4,000 | 2.2a-d | wt-ca-cli |
| 2.2f 交互和 RPC 模式 | modes/interactive/ (全部组件), modes/rpc/, modes/print-mode.ts | 40 | ~15,000 | pi_tui, 2.2a-d | wt-ca-modes |

- **依赖关系**:
  - 2.2a/2.2b/2.2c/2.2d 可以在 pi_agent 完成后并行启动（4 个 worktree）
  - 2.2e 需要 2.2a-d 完成后才能开始
  - 2.2f 需要 pi_tui + 2.2a-d 完成后才能开始
  - 2.2e 和 2.2f 可以并行

**阶段 2 并行度**: 先 1 (agent) + 4 (ca-tools/session/logic/ext)，然后 2 (ca-cli/ca-modes)

---

## 阶段 3：应用层（阶段 2 完成后启动，3 个 worktree 并行）

### 任务 3.1：pi_web_ui

- **TS 源码**: `packages/web-ui/src/` (71 files, ~14,539 lines)
- **注意**: web-ui 大量是前端 Web Components（Lit）。Python 改写只涉及后端逻辑部分（storage, tools 后端, prompts, agent 接口），前端保持 TS/JS
- **分为 2 个子任务**:
  - 3.1a 后端（storage, tools 后端逻辑, prompts, AgentInterface 后端部分）
  - 3.1b 前端适配（前端保持 JS，适配调用 Python 后端 API）

### 任务 3.2：pi_mom — Slack 机器人

- **TS 源码**: `packages/mom/src/` (16 files, ~4,120 lines)
- **范围**: agent.ts, slack.ts, sandbox.ts, store.ts, events.ts, context.ts, tools/, download.ts, main.ts
- **1 个 worktree 即可**

### 任务 3.3：pi_pods — Pod 管理

- **TS 源码**: `packages/pods/src/` (9 files, ~1,773 lines)
- **范围**: ssh.ts, commands/, cli.ts, config.ts, model-configs.ts, types.ts
- **1 个 worktree 即可**
- **可以在阶段 2.1 (pi_agent) 完成后就开始**，不需要等 coding-agent

**阶段 3 并行度**: 3 个 worktree (web-ui / mom / pods)

---

## 阶段 4：集成测试和端到端验证

在所有模块合并到主分支后：

1. **跨模块集成测试**: 测试模块间的真实交互（如 agent 调用 ai 进行流式对话）
2. **端到端测试**: 完整的用户场景测试
3. **TS vs Python 行为对比测试**: 用相同输入跑 TS 和 Python 版本，对比输出
4. **性能基准测试**: 确保 Python 版本性能在可接受范围

---

## 完整时间线总览

```
阶段 0 ─────── 脚手架 (1 worktree)
                │
阶段 1 ─────── tui (1 wt) ──────────────────────┐
           ├── ai-core+utils (1 wt) ─────────┐   │
           └── ai-providers (1 wt) ──────────┤   │
                                              │   │
阶段 2 ─────── agent (1 wt) ─────────────────┤   │
           ├── ca-tools (1 wt) ──────────┐   │   │
           ├── ca-session (1 wt) ────────┤   │   │
           ├── ca-logic (1 wt) ──────────┤   │   │
           └── ca-ext (1 wt) ───────────┤   │   │
                                         │   │   │
           ├── ca-cli (1 wt) ───────────┤   │   │
           └── ca-modes (1 wt) ─────────┘   │   │
                                              │   │
阶段 3 ─────── pods (1 wt) ←── 可在 agent 完成后提前开始
           ├── web-ui (1 wt)
           ├── mom (1 wt)
           └── pods (1 wt)
                │
阶段 4 ─────── 集成测试 + E2E 测试
```

---

## 质量保证机制

### 每个模块开发中的质量保证

1. **API 全量覆盖检查**:
   - 开发前: 运行 `extract_public_api.py` 生成 TS 公共 API 清单
   - 开发后: 运行 `check_parity.py` 对比，确保零遗漏
   - MAPPING.md 记录每个 TS 导出的 Python 对应物

2. **代码质量门禁** (每次 commit 自动执行):
   ```
   ruff check . && ruff format --check .   # lint + format
   mypy --strict .                          # 类型检查
   pytest --cov --cov-fail-under=80         # 测试 + 覆盖率
   ```

3. **人工 Review 检查点**:
   - 每个子任务完成后，人工 review PR
   - 重点检查: 接口是否一致、是否遗漏功能、是否符合 Python 最佳实践

### 模块合并后的质量保证

1. **集成测试** (`py/tests/integration/`):
   - 测试跨模块调用链（如 coding-agent -> agent -> ai -> provider）
   - 测试配置传递、错误传播

2. **行为对比测试** (`py/tests/comparison/`):
   - 用相同的 mock 输入运行 TS 和 Python 版本
   - 对比输出结构和内容

3. **E2E 测试** (`py/tests/e2e/`):
   - 完整的用户场景: 启动 CLI -> 发送消息 -> 接收流式响应 -> 使用工具

---

## CI/CD 自动化

### GitHub Actions 工作流

1. **`ci-python.yml`** — 每次 PR 自动运行:
   ```yaml
   jobs:
     lint:
       - ruff check .
       - ruff format --check .
     typecheck:
       - mypy --strict .
     test:
       - pytest --cov --cov-fail-under=80
     parity:
       - python scripts/check_parity.py (对变更的包)
   ```

2. **`ci-merge-integration.yml`** — 合并到 main 时运行:
   ```yaml
   jobs:
     integration-tests:
       - pytest py/tests/integration/
     comparison-tests:
       - pytest py/tests/comparison/
   ```

3. **Pre-commit hooks** (本地):
   ```yaml
   # .pre-commit-config.yaml
   - repo: local
     hooks:
       - id: ruff-check
       - id: ruff-format
       - id: mypy-strict
   ```

---

## GitHub Projects 任务管理

### Project Board 设置

创建一个 GitHub Project (Board 视图)，列如下：

| 列 | 含义 |
|---|------|
| Backlog | 待开始的任务 |
| Ready | 依赖已满足，可以开始 |
| In Progress | Claude 正在开发 |
| In Review | 人工 Review 中 |
| Done | 完成并合并 |

### Issue 命名规范

```
[Py Rewrite] {阶段}.{子任务} {包名}: {描述}
```

例如: `[Py Rewrite] 1.2a pi_ai: 核心类型和流`

### Issue 内容模板（每个 Issue 需要包含）

```markdown
## 范围
- 列出具体的 TS 源文件
- 对应的 Python 目标文件

## TS 公共 API 清单
(由 extract_public_api.py 生成，粘贴到这里)

## 关键设计决策
- TS 中的 X 模式在 Python 中用 Y 替代
- 需要注意的差异点

## 验收标准
- [ ] 所有公共 API 有 Python 等价物 (check_parity.py 通过)
- [ ] MAPPING.md 完成
- [ ] 单元测试覆盖率 >= 80%
- [ ] mypy --strict 通过
- [ ] ruff check/format 通过

## 依赖
- 被阻塞于: #XX (issue 编号)

## 元数据
- 阶段: X
- 包: xxx
- Worktree 分支: python/phaseX-xxx
```

---

## 人工执行步骤（按顺序）

### 步骤 1：安装工具（一次性）

```bash
# 安装 gh CLI（如果还没安装）
# macOS
brew install gh
# Linux
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list
sudo apt update && sudo apt install gh

# 登录
gh auth login

# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 pre-commit
pip install pre-commit
```

### 步骤 2：创建 GitHub Project

```bash
# 创建 Project
gh project create --title "Pi-Mono Python Rewrite" --owner <your-org-or-username>

# 记下 Project Number (后续要用)
gh project list --owner <your-org-or-username>
```

### 步骤 3：创建所有 GitHub Issues

以下脚本会创建所有 Issue。**Issue 内容需要是详细的**——每个 Issue 在创建前，需要先对相应的 TS 源文件运行 `extract_public_api.py`，将 API 清单嵌入 Issue body。

**但 `extract_public_api.py` 还不存在**，所以步骤是：

1. 先执行阶段 0（创建脚手架 + 脚本）
2. 然后用脚本为每个包生成 API 清单
3. 最后创建带详细内容的 Issues

### 步骤 4：执行阶段 0 — 项目脚手架

```bash
cd ~/pi-mono

# 启动 1 个 Claude 执行阶段 0
# Claude 将会：
# - 创建 py/ 目录结构
# - 配置 pyproject.toml (uv workspace)
# - 配置 ruff.toml, mypy.ini
# - 创建 pytest 配置
# - 实现 scripts/extract_public_api.py
# - 实现 scripts/check_parity.py
# - 创建 .github/workflows/ci-python.yml
# - 创建 .pre-commit-config.yaml
# - 定义 pi_types/ 中的共享类型

claude --worktree "请完成阶段 0 的脚手架任务，详见 CLAUDE.md"
```

**人工检查点**: Review 阶段 0 的 PR，确认工具链可正常工作：
```bash
cd py/
uv sync
ruff check .
mypy --strict .
pytest
python scripts/extract_public_api.py ../../packages/ai/src/types.ts  # 测试脚本
```

### 步骤 5：生成 API 清单并创建详细 Issues

```bash
cd ~/pi-mono/py

# 为每个包生成 API 清单
python scripts/extract_public_api.py ../packages/ai/src/ > /tmp/ai-api.md
python scripts/extract_public_api.py ../packages/tui/src/ > /tmp/tui-api.md
python scripts/extract_public_api.py ../packages/agent/src/ > /tmp/agent-api.md
python scripts/extract_public_api.py ../packages/coding-agent/src/ > /tmp/ca-api.md
python scripts/extract_public_api.py ../packages/web-ui/src/ > /tmp/webui-api.md
python scripts/extract_public_api.py ../packages/mom/src/ > /tmp/mom-api.md
python scripts/extract_public_api.py ../packages/pods/src/ > /tmp/pods-api.md

# 然后启动 1 个 Claude，让它读取这些 API 清单，生成详细的 Issue 内容并通过 gh 创建
claude "请读取 /tmp/*-api.md 文件和 PLAN.md 中的任务划分，为每个任务创建详细的 GitHub Issue。每个 Issue 需要包含：具体的 TS 文件列表、对应 Python 文件、API 清单、关键设计决策、验收标准。使用 gh issue create 创建，并加到 GitHub Project 中。"
```

### 步骤 6：执行阶段 1 — 基础层（3 个 worktree 并行）

```bash
cd ~/pi-mono

# Worktree 1: TUI
git worktree add ../pi-mono-tui python/phase1-tui
cd ../pi-mono-tui
claude "请完成 GitHub Issue #<tui-issue-number>。从 gh issue view 中读取详细要求。"

# Worktree 2: AI 核心 + 工具函数
git worktree add ../pi-mono-ai-core python/phase1-ai-core
cd ../pi-mono-ai-core
claude "请完成 GitHub Issue #<ai-core-issue-number> 和 #<ai-utils-issue-number>。从 gh issue view 中读取详细要求。"

# Worktree 3: AI 提供商
git worktree add ../pi-mono-ai-providers python/phase1-ai-providers
cd ../pi-mono-ai-providers
claude "请完成 GitHub Issue #<ai-openai-issue-number> 和 #<ai-non-openai-issue-number>。从 gh issue view 中读取详细要求。"
```

**人工检查点**: 每个 worktree 完成后：
1. Review PR (重点检查 MAPPING.md 和 check_parity.py 结果)
2. 确认测试通过
3. 合并到 main

### 步骤 7：阶段 1 合并后集成测试

```bash
# 合并所有阶段 1 的 PR 到 main
# 然后在 main 上运行集成测试

cd ~/pi-mono/py
uv sync
pytest tests/integration/  # 测试 ai 模块各子模块协作
python scripts/check_parity.py ../packages/ai/src pi_ai
python scripts/check_parity.py ../packages/tui/src pi_tui
```

### 步骤 8：执行阶段 2（最多 5 个 worktree 并行）

```bash
# 先启动 agent（体量小，很快完成）
git worktree add ../pi-mono-agent python/phase2-agent
cd ../pi-mono-agent && claude "请完成 GitHub Issue #<agent-issue>。"

# agent 完成并合并后，启动 4 个 coding-agent worktree
git worktree add ../pi-mono-ca-tools python/phase2-ca-tools
git worktree add ../pi-mono-ca-session python/phase2-ca-session
git worktree add ../pi-mono-ca-logic python/phase2-ca-logic
git worktree add ../pi-mono-ca-ext python/phase2-ca-ext

# 在每个 worktree 中启动 Claude（4 个终端窗口）
cd ../pi-mono-ca-tools && claude "请完成 GitHub Issue #<ca-tools-issue>。"
cd ../pi-mono-ca-session && claude "请完成 GitHub Issue #<ca-session-issue>。"
cd ../pi-mono-ca-logic && claude "请完成 GitHub Issue #<ca-logic-issue>。"
cd ../pi-mono-ca-ext && claude "请完成 GitHub Issue #<ca-ext-issue>。"

# 上面 4 个合并后，再启动
git worktree add ../pi-mono-ca-cli python/phase2-ca-cli
git worktree add ../pi-mono-ca-modes python/phase2-ca-modes
cd ../pi-mono-ca-cli && claude "请完成 GitHub Issue #<ca-cli-issue>。"
cd ../pi-mono-ca-modes && claude "请完成 GitHub Issue #<ca-modes-issue>。"
```

**人工检查点**: 每个 PR 合并前 Review

### 步骤 9：阶段 2 合并后集成测试

```bash
cd ~/pi-mono/py
uv sync
pytest tests/integration/
python scripts/check_parity.py ../packages/agent/src pi_agent
python scripts/check_parity.py ../packages/coding-agent/src pi_coding_agent
```

### 步骤 10：执行阶段 3（3 个 worktree 并行）

```bash
# pods 可以在 agent 完成后提前开始（不需要等 coding-agent）
git worktree add ../pi-mono-pods python/phase3-pods
git worktree add ../pi-mono-mom python/phase3-mom
git worktree add ../pi-mono-webui python/phase3-webui

cd ../pi-mono-pods && claude "请完成 GitHub Issue #<pods-issue>。"
cd ../pi-mono-mom && claude "请完成 GitHub Issue #<mom-issue>。"
cd ../pi-mono-webui && claude "请完成 GitHub Issue #<webui-issue>。"
```

### 步骤 11：最终集成和 E2E 测试

```bash
cd ~/pi-mono/py
uv sync

# 全量 parity 检查
for pkg in ai tui agent coding-agent mom pods; do
  python scripts/check_parity.py ../packages/$pkg/src pi_$(echo $pkg | tr '-' '_')
done

# 全量测试
pytest --cov --cov-fail-under=80
pytest tests/integration/
pytest tests/e2e/

# 类型检查
mypy --strict .
```

---

## 合并策略

### 分支命名

```
main (或 master)
├── python/phase0-foundation
├── python/phase1-tui
├── python/phase1-ai-core
├── python/phase1-ai-providers
├── python/phase2-agent
├── python/phase2-ca-tools
├── python/phase2-ca-session
├── python/phase2-ca-logic
├── python/phase2-ca-ext
├── python/phase2-ca-cli
├── python/phase2-ca-modes
├── python/phase3-webui
├── python/phase3-mom
└── python/phase3-pods
```

### 合并规则

1. **同阶段的并行分支**: 各自独立开发在 `py/<package>/` 下，文件路径不冲突，合并应该是 fast-forward 或无冲突
2. **合并顺序**: 按依赖关系从底层到上层合并
3. **合并后必须**: 运行全量测试 + parity check + mypy
4. **如果合并有冲突**: 通常是因为共享类型 (pi_types) 变更，需要人工 resolve

### 为什么文件冲突风险低

- 每个包的代码都在独立的目录下 (`py/pi_ai/`, `py/pi_tui/`, etc.)
- 测试也在独立的子目录 (`py/tests/unit/pi_ai/`, etc.)
- 唯一可能冲突的是 `py/pi_types/` 和 `py/pyproject.toml`
- 建议: 每个分支只修改自己包相关的 pyproject.toml 中的依赖声明，主 workspace 配置在阶段 0 固定

---

## Claude 与 GitHub Projects 集成

### Claude 读取任务的方式

每个 Claude 实例启动时，可以通过 `gh` CLI 读取分配给它的 Issue：

```bash
# Claude 在 worktree 中执行
gh issue view <issue-number>                    # 读取任务详情
gh issue comment <issue-number> -b "开始开发"    # 更新状态
gh issue comment <issue-number> -b "完成，PR: #XX"  # 完成通知
```

### 人工在 Project Board 上的操作

1. 将 Issue 从 "Ready" 拖到 "In Progress" 表示 Claude 开始工作
2. Claude 完成后将 Issue 移到 "In Review"
3. 人工 Review 通过后移到 "Done"

---

## 风险和应对

| 风险 | 应对 |
|-----|------|
| pi_types 共享类型在多个分支中不一致 | 阶段 0 中充分定义，后续分支只读不改 |
| 单个模块太大，Claude 上下文不够 | 已按 ~5,000 行划分子任务 |
| Python 版本性能不如 TS | 关键路径用 async，I/O 密集场景性能差异不大 |
| 合并后集成测试发现接口不匹配 | 每个模块独立运行 check_parity.py，接口在 pi_types 中预定义 |
| web-ui 前端改写范围不明确 | 后端用 Python，前端保持 JS/TS，通过 API 通信 |
