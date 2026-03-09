# Pi-Mono Python 重写 — 逐步操作指南

本文档包含每个任务的详细操作步骤和完整的 GitHub Issue 内容，可直接用 `gh issue create` 创建或复制粘贴。

---

## 一次性准备工作

```bash
# 1. 确保在 python-rewrite 分支
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git checkout python-rewrite

# 2. 创建 GitHub 标签
gh label create python-rewrite --color 0E8A16
gh label create phase-0 --color FBCA04
gh label create phase-1 --color FBCA04
gh label create phase-2 --color FBCA04
gh label create phase-3 --color FBCA04
gh label create phase-4 --color FBCA04
gh label create "pkg:ai" --color C5DEF5 2>/dev/null || true
gh label create "pkg:agent" --color C5DEF5 2>/dev/null || true
gh label create "pkg:tui" --color C5DEF5 2>/dev/null || true
gh label create "pkg:coding-agent" --color C5DEF5 2>/dev/null || true
gh label create "pkg:pods" --color C5DEF5 2>/dev/null || true
gh label create "pkg:mom" --color C5DEF5 2>/dev/null || true

# 3.（可选）创建 GitHub Project 看板
#    名称: "Pi-Mono Python Rewrite"
#    列: Backlog | In Progress | Review | Done
```

---

## Phase 0: 基础设施

### 创建 Issue

```bash
gh issue create --title "[Phase 0] Python 重写项目脚手架 + CI" --label "python-rewrite,phase-0" --body "$(cat <<'ISSUE_EOF'
## [Phase 0] 项目脚手架 + CI

### 范围
搭建 `py/` 目录结构和 CI 流水线。

### 任务清单
1. 创建 `py/` 目录，包含:
   - `pyproject.toml` — uv workspace 根配置（Python >=3.12，声明所有包为 workspace 成员）
   - `ruff.toml` — 代码检查/格式化配置（行宽 120，目标 py312）
   - `mypy.ini` — strict 模式配置
   - `conftest.py` — 共享 pytest fixture
2. 为每个包创建 stub `pyproject.toml` 和 `__init__.py`:
   - `py/pi_ai/`, `py/pi_agent/`, `py/pi_tui/`, `py/pi_coding_agent/`, `py/pi_mom/`, `py/pi_pods/`
3. 创建 `py/scripts/extract_public_api.py`:
   - 输入: TS 源文件或目录路径
   - 解析所有 `export` 声明（函数、类、类型、接口、常量）
   - 输出: 包含名称、种类和签名的 Markdown 检查清单
4. 创建 `py/scripts/check_parity.py`:
   - 输入: TS 包路径 + Python 包路径
   - 比对 TS 导出列表 vs Python `__all__` / 公共 API
   - 输出: 缺失、多余和名称不匹配的项目
5. 将 `_CLAUDE.md` 移为 `py/PYTHON_REWRITE_GUIDE.md`
6. 创建 `py/CLAUDE.md`，内容: `Read PYTHON_REWRITE_GUIDE.md in this directory for all rewrite conventions and rules. Only use English for code comments.`
7. 修复 `.github/workflows/python-quality.yml`:
   - 中文标签改为英文
   - 添加 `working-directory: py` 默认设置
   - 所有命令加 `uv run` 前缀
   - 添加分支过滤: `branches: ['python-rewrite', 'py/**']`
   - 移除 paths 中的 `tests/**`（测试在 `py/` 内部）
8. 创建测试目录结构:
   - `py/tests/unit/`（每个包一个子目录）
   - `py/tests/integration/`
   - `py/tests/e2e/`
   - `py/tests/comparison/`
   - `py/tests/fixtures/`（每个包一个子目录）

### 操作指引
1. 直接在 `python-rewrite` 分支上工作（无需单独的功能分支）
2. 先阅读 `_CLAUDE.md` 了解重写指南内容
3. 实现以上所有项目
4. 运行: `cd py && uv sync && uv run ruff check . && uv run mypy --strict .`

### 验收标准
- [ ] `cd py && uv sync` 成功
- [ ] `uv run ruff check .` 通过
- [ ] `uv run ruff format --check .` 通过
- [ ] `uv run mypy --strict .` 通过
- [ ] `py/scripts/extract_public_api.py` 对示例 TS 文件运行无报错
- [ ] `py/scripts/check_parity.py` 运行无报错（报告全部缺失属正常）
- [ ] `.github/workflows/python-quality.yml` 使用英文标签且设置了 working-directory
- [ ] `py/PYTHON_REWRITE_GUIDE.md` 存在且包含完整指南
- [ ] `py/CLAUDE.md` 存在
ISSUE_EOF
)"
```

### 执行 Phase 0

```bash
# 运行 Claude Code（无需 worktree，直接在 python-rewrite 分支上工作）
cd /home/jerry/ai/pi-mono-worktree/pi-mono
claude "Read issue #<ISSUE_NUM> from github (gh issue view <ISSUE_NUM> --json title,body,comments,labels,state). Follow the instructions in the issue to implement the task. Read _CLAUDE.md first."

# 完成后审核并提交
git add py/ .github/workflows/python-quality.yml
git commit -m "feat: Python rewrite infrastructure setup"
git push origin python-rewrite
```

---

## Phase 1: 基础层（4 个并行任务）

### 创建 Issues

#### Issue: 任务 1-1 — pi_ai 核心类型 + 工具函数

```bash
gh issue create --title "[Phase 1] 重写 pi_ai 核心类型和工具函数为 Python" --label "python-rewrite,phase-1,pkg:ai" --body "$(cat <<'ISSUE_EOF'
## [Phase 1] 重写 pi_ai 核心类型 + 工具函数

### 范围
重写 `ai` 包的核心类型、流式处理、注册表和工具模块。

**TS 源文件**（均位于 `packages/ai/src/`）:
- `types.ts` (308 行) — Message, Event, StreamOptions 等核心类型
- `stream.ts` (60) — stream 分发
- `api-registry.ts` (98) — provider 注册表
- `models.ts` (77) — Model 类型, 目录辅助函数
- `env-api-keys.ts` (115) — 环境变量 API key 检测
- `utils/event-stream.ts` (87) — 用 AsyncIterator 替代
- `utils/overflow.ts` (121)
- `utils/validation.ts` (84)
- `utils/sanitize-unicode.ts` (25)
- `utils/json-parse.ts` (28)
- `utils/http-proxy.ts` (13)
- `providers/simple-options.ts` (46)
- `providers/transform-messages.ts` (167)
- `providers/register-builtins.ts` (73)

### Python 输出文件
```
py/pi_ai/
├── __init__.py
├── types.py
├── stream.py
├── api_registry.py
├── models.py
├── env_api_keys.py
├── utils/
│   ├── __init__.py
│   ├── overflow.py
│   ├── validation.py
│   ├── sanitize_unicode.py
│   ├── json_parse.py
│   └── http_proxy.py
├── providers/
│   ├── __init__.py
│   ├── simple_options.py
│   ├── transform_messages.py
│   └── register_builtins.py
└── MAPPING.md
```

### 依赖关系
- 依赖: Phase 0 基础设施（#<phase0-issue>）
- 被依赖: 任务 1-2, 任务 1-3, 任务 2-1, 任务 2-2

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md` 了解映射规则
2. 阅读上面列出的每个 TS 源文件
3. 运行 `cd py && uv run python scripts/extract_public_api.py ../../packages/ai/src/types.ts`（以及其他文件）
4. 按指南实现 Python 模块:
   - `types.py`: 接口用 `@dataclass`，判别联合用 `Literal`，枚举用 `StrEnum`
   - `stream.py`: 用 `AsyncIterator` 替代 `EventStream`
   - `api_registry.py`: 基于 dict 的简单注册表
   - 为 dataclass 编写显式的 `serialize`/`deserialize` 函数
5. 在 `py/tests/unit/pi_ai/` 编写单元测试
6. 创建 `py/pi_ai/MAPPING.md`
7. 运行: `cd py && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest tests/unit/pi_ai/ --cov=pi_ai --cov-fail-under=80 -v`

### 关键设计决策
- `EventStream<T, R>` 替换为原生 `AsyncIterator[T]`（async generator + yield）
- 所有消息/事件类型用 `@dataclass`，不用 TypedDict
- 判别联合用 `Literal["type_value"]` + `isinstance()` 检查
- 不做泛型体操 — 直接具体化
- `AbortController` → `asyncio.Event`

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 完整
- [ ] 无未标注的 `Any` 类型（除非有注释说明理由）
ISSUE_EOF
)"
```

#### Issue: 任务 1-2 — pi_ai Providers A（Anthropic + OpenAI）

```bash
gh issue create --title "[Phase 1] 重写 pi_ai providers: Anthropic + OpenAI 为 Python" --label "python-rewrite,phase-1,pkg:ai" --body "$(cat <<'ISSUE_EOF'
## [Phase 1] 重写 pi_ai Providers A（Anthropic + OpenAI）

### 范围
重写 Anthropic 和 OpenAI 系列的 provider 实现。

**TS 源文件**（均位于 `packages/ai/src/providers/`）:
- `anthropic.ts` (851 行)
- `openai-completions.ts` (828)
- `openai-responses.ts` (259)
- `openai-responses-shared.ts` (480)
- `azure-openai-responses.ts` (256)
- `openai-codex-responses.ts` (863)
- `github-copilot-headers.ts` (37)

### Python 输出文件
```
py/pi_ai/providers/
├── anthropic.py
├── openai_completions.py
├── openai_responses.py
├── openai_responses_shared.py
├── azure_openai_responses.py
├── openai_codex_responses.py
└── github_copilot_headers.py
py/tests/unit/pi_ai/
├── test_anthropic.py
├── test_openai_completions.py
├── test_openai_responses.py
└── ...
py/tests/fixtures/pi_ai/
├── anthropic_basic_response.json
├── anthropic_tool_call_response.json
├── openai_completion_response.json
└── ...
```

### Shared Interface Contract

本任务与任务 1-1（核心类型）并行开发。**必须**严格使用以下名称和签名，不得自行变体：

#### 从 `pi_ai.types` import（由任务 1-1 定义）
```python
# 类型名称（注意大小写）
StopReason = Literal["stop", "length", "toolUse", "error", "aborted"]

class DoneEvent:
    reason: StopReason  # 不是 Literal["stop", "length", "toolUse"]

class ErrorEvent:
    reason: StopReason

class ToolCallStartEvent:   # 大写 C，不是 ToolcallStartEvent
class ToolCallDeltaEvent:   # 大写 C
class ToolCallEndEvent:     # 大写 C

class UsageCost:            # 不是 CostBreakdown

# 类型别名
AssistantMessageEventStream = AsyncIterator[AssistantMessageEvent]
StreamFunction = Callable[..., AssistantMessageEventStream]
```

#### 从 `pi_ai.providers.transform_messages` import（由任务 1-1 定义）
```python
def transform_messages(
    messages: list[Message],
    model: Model,
    normalize_tool_call_id: Callable[[str, Model, AssistantMessage], str] | None = None,
    #                                 ^^^ 三个参数，不是一个
) -> list[Message]: ...

# 如果你的 normalize 函数只接受 str，用 lambda 包装：
transform_messages(msgs, model, lambda tc_id, _m, _a: your_function(tc_id))
```

#### `# type: ignore` 使用规则
- **允许**: `# type: ignore[call-overload]` 用于 OpenAI SDK 的 `create(**kwargs)` 调用
- **禁止**: `# type: ignore[arg-type]` 用于 pi_ai 内部模块间的类型不匹配 — 必须修正类型

### 依赖关系
- 依赖: Phase 0（#<phase0-issue>）
- 使用任务 1-1 的类型 — 用 `TYPE_CHECKING` import，运行时类型可能尚不存在，需要 stub
- 被依赖: 任务 2-2（AI 集成）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md` 了解映射规则
2. **阅读上方"Shared Interface Contract"，确认使用的类型名称和签名**
3. 阅读上面列出的每个 TS 源文件
4. 阅读 `packages/ai/src/types.ts` 了解这些 provider 使用的核心类型
5. 运行 `cd py && uv run python scripts/extract_public_api.py ../../packages/ai/src/providers/anthropic.ts`（以及其他文件）
6. 实现每个 provider 模块:
   - Anthropic provider 使用 `anthropic` SDK
   - OpenAI 系列 provider 使用 `openai` SDK
   - 每个 provider 函数应为 async generator，yield 事件
   - 对 `pi_ai.types` 的 import 使用 `TYPE_CHECKING` 守卫（任务 1-1 可能尚未合并）
7. 使用 mock SDK 响应编写单元测试（`unittest.mock.AsyncMock`）
8. 在 `py/tests/fixtures/pi_ai/` 中录制 fixture JSON 文件
9. 运行质量检查

### 关键设计决策
- 每个 `streamXxx()` TS 函数 → `async def stream_xxx()` Python async generator
- 测试中 mock 外部 SDK 调用 — 绝不发送真实 API 请求
- 使用 fixture JSON 文件确保测试可重现
- 跨任务类型依赖使用 `TYPE_CHECKING` import

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 中包含所有 provider 的条目
- [ ] 测试中无真实 API 调用
- [ ] 无未标注的 `Any` 类型
- [ ] **类型名称与 Shared Interface Contract 完全一致**
ISSUE_EOF
)"
```

#### Issue: 任务 1-3 — pi_ai Providers B（Google + Bedrock）+ OAuth

```bash
gh issue create --title "[Phase 1] 重写 pi_ai providers: Google + Bedrock + OAuth 为 Python" --label "python-rewrite,phase-1,pkg:ai" --body "$(cat <<'ISSUE_EOF'
## [Phase 1] 重写 pi_ai Providers B（Google + Bedrock）+ OAuth

### 范围
重写 Google、Vertex、Bedrock provider 和 OAuth 工具模块。

**TS 源文件**:
- `packages/ai/src/providers/google.ts` (452 行)
- `packages/ai/src/providers/google-shared.ts` (317)
- `packages/ai/src/providers/google-gemini-cli.ts` (940)
- `packages/ai/src/providers/google-vertex.ts` (482)
- `packages/ai/src/providers/amazon-bedrock.ts` (731)
- `packages/ai/src/utils/oauth/` — 全部 8 个文件（约 2,641 行）:
  - `types.ts`, `storage.ts`, `pkce.ts`, `server.ts`, `client.ts`, `google-oauth.ts`, `github-oauth.ts`, `index.ts`

### Python 输出文件
```
py/pi_ai/
├── providers/
│   ├── google.py
│   ├── google_shared.py
│   ├── google_gemini_cli.py
│   ├── google_vertex.py
│   └── amazon_bedrock.py
├── oauth/
│   ├── __init__.py
│   ├── types.py
│   ├── storage.py
│   ├── pkce.py
│   ├── server.py
│   ├── client.py
│   ├── google_oauth.py
│   └── github_oauth.py
py/tests/unit/pi_ai/
├── test_google.py
├── test_amazon_bedrock.py
├── test_oauth.py
└── ...
```

### Shared Interface Contract

本任务与任务 1-1（核心类型）并行开发。**必须**严格使用以下名称和签名，不得自行变体：

（与任务 1-2 完全相同的契约，此处复制以确保每个 Claude Code 实例都能看到）

#### 从 `pi_ai.types` import（由任务 1-1 定义）
```python
StopReason = Literal["stop", "length", "toolUse", "error", "aborted"]

class DoneEvent:
    reason: StopReason  # 不是 Literal["stop", "length", "toolUse"]

class ErrorEvent:
    reason: StopReason

class ToolCallStartEvent:   # 大写 C，不是 ToolcallStartEvent
class ToolCallDeltaEvent:   # 大写 C
class ToolCallEndEvent:     # 大写 C

class UsageCost:            # 不是 CostBreakdown

AssistantMessageEventStream = AsyncIterator[AssistantMessageEvent]
StreamFunction = Callable[..., AssistantMessageEventStream]
```

#### 从 `pi_ai.providers.transform_messages` import（由任务 1-1 定义）
```python
def transform_messages(
    messages: list[Message],
    model: Model,
    normalize_tool_call_id: Callable[[str, Model, AssistantMessage], str] | None = None,
) -> list[Message]: ...

# 如果你的 normalize 函数只接受 str，用 lambda 包装：
transform_messages(msgs, model, lambda tc_id, _m, _a: your_function(tc_id))
```

#### `# type: ignore` 使用规则
- **允许**: `# type: ignore[call-overload]` 用于第三方 SDK 的动态调用
- **禁止**: `# type: ignore[arg-type]` 用于 pi_ai 内部模块间的类型不匹配

### 依赖关系
- 依赖: Phase 0（#<phase0-issue>）
- 使用任务 1-1 的类型 — 用 `TYPE_CHECKING` import
- 被依赖: 任务 2-2（AI 集成）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md` 了解映射规则
2. **阅读上方"Shared Interface Contract"，确认使用的类型名称和签名**
3. 阅读上面列出的每个 TS 源文件
4. 运行 `cd py && uv run python scripts/extract_public_api.py ../../packages/ai/src/providers/google.ts`（等）
5. 实现 provider:
   - Google/Gemini provider 使用 `google-genai` SDK
   - Amazon Bedrock provider 使用 `boto3`
   - OAuth: HTTP 请求用 `httpx`，异步服务器用 `asyncio`
6. 使用 mock SDK 响应编写单元测试
7. 运行质量检查

### 关键设计决策
- Google provider: 使用 `google-genai` SDK（非 `google-generativeai`）
- Bedrock: `boto3` + 异步包装 或 `aioboto3`
- OAuth PKCE 流程: `secrets` 模块生成 code，`httpx` 换取 token
- OAuth 本地服务器: `aiohttp` 或简单 `asyncio` HTTP 服务器处理回调

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 中包含所有模块的条目
- [ ] 测试中无真实 API 调用
- [ ] 无未标注的 `Any` 类型
- [ ] **类型名称与 Shared Interface Contract 完全一致**
ISSUE_EOF
)"
```

#### Issue: 任务 1-4 — pi_tui

```bash
gh issue create --title "[Phase 1] 重写 pi_tui 终端 UI 为 Python" --label "python-rewrite,phase-1,pkg:tui" --body "$(cat <<'ISSUE_EOF'
## [Phase 1] 重写 pi_tui 终端 UI

### 范围
重写整个 TUI 包 — 自研差异渲染引擎、终端控制、组件。

**TS 源文件**: `packages/tui/src/` — 全部 25 个文件（共 9,858 行）

关键文件:
- `terminal.ts` — 终端抽象（转义序列、光标、颜色）
- `tui.ts` — 主 TUI 类，渲染循环，差异渲染
- `keys.ts`, `keybindings.ts` — 按键解析和绑定系统
- `stdin-buffer.ts` — 原始 stdin 处理
- `autocomplete.ts`, `fuzzy.ts` — 补全和模糊匹配
- `utils.ts` — 字符串宽度、换行等
- `terminal-image.ts` — 内联图片渲染（kitty/sixel）
- `components/` — 约 12 个组件文件（TextInput, TextArea, Scrollable, Menu, Dialog 等）

### Python 输出文件
```
py/pi_tui/
├── __init__.py
├── terminal.py
├── tui.py
├── keys.py
├── keybindings.py
├── stdin_buffer.py
├── autocomplete.py
├── fuzzy.py
├── utils.py
├── terminal_image.py
├── components/
│   ├── __init__.py
│   ├── text_input.py
│   ├── text_area.py
│   ├── scrollable.py
│   ├── menu.py
│   ├── dialog.py
│   └── ...（每个组件一个文件）
├── MAPPING.md
py/tests/unit/pi_tui/
├── test_terminal.py
├── test_keys.py
├── test_fuzzy.py
├── test_utils.py
└── ...
```

### 依赖关系
- 依赖: Phase 0（#<phase0-issue>）
- 无 pi-mono 跨包依赖（完全独立）
- 被依赖: 任务 3-4a（coding-agent 交互模式）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md` 了解映射规则
2. 阅读 `packages/tui/src/` 下的所有 TS 源文件
3. 运行 `cd py && uv run python scripts/extract_public_api.py ../../packages/tui/src/`
4. 实现 TUI 引擎:
   - 自研差异渲染 — 不使用 textual 或 prompt-toolkit
   - 直接操作终端转义序列（ANSI/VT100）
   - 保持与 TS 版本相同的 Component/Container/Focusable 模型
   - 原始 stdin 处理: `sys.stdin` raw 模式
   - Unicode 字符宽度: `wcwidth`
5. 编写单元测试（重点: 按键解析、模糊匹配、文本换行、组件渲染）
6. 创建 `py/pi_tui/MAPPING.md`
7. 运行质量检查

### 关键设计决策
- **自研渲染引擎**，与 TS 版本一致 — 不依赖第三方 TUI 框架
- 直接操作 ANSI 转义序列
- 组件模型: 基类 `Component`，`Container` 用于布局，`Focusable` 协议
- 字符宽度计算使用 `wcwidth` 库
- Raw 模式 stdin: `tty.setraw()` + `termios`
- 图片支持: kitty graphics protocol + sixel 回退

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 完整
- [ ] 不依赖 textual/prompt-toolkit/curses
- [ ] 无未标注的 `Any` 类型
ISSUE_EOF
)"
```

### 执行 Phase 1

```bash
# 创建 worktree 并同时创建分支
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git worktree add -b py/ai-core ../py-ai-core python-rewrite
git worktree add -b py/ai-providers-a ../py-ai-providers-a python-rewrite
git worktree add -b py/ai-providers-b ../py-ai-providers-b python-rewrite
git worktree add -b py/tui ../py-tui python-rewrite

# 在独立终端中启动 Claude Code（用实际 issue 编号替换 XX）
# 终端 1:
cd /home/jerry/ai/pi-mono-worktree/py-ai-core
claude "Read issue #XX from github (gh issue view XX --json title,body,comments,labels,state). Follow the instructions in the issue to implement the task. Read py/PYTHON_REWRITE_GUIDE.md first."

# 终端 2:
cd /home/jerry/ai/pi-mono-worktree/py-ai-providers-a
claude "Read issue #XX from github (gh issue view XX --json title,body,comments,labels,state). Follow the instructions in the issue to implement the task. Read py/PYTHON_REWRITE_GUIDE.md first."

# 终端 3:
cd /home/jerry/ai/pi-mono-worktree/py-ai-providers-b
claude "Read issue #XX from github (gh issue view XX --json title,body,comments,labels,state). Follow the instructions in the issue to implement the task. Read py/PYTHON_REWRITE_GUIDE.md first."

# 终端 4:
cd /home/jerry/ai/pi-mono-worktree/py-tui
claude "Read issue #XX from github (gh issue view XX --json title,body,comments,labels,state). Follow the instructions in the issue to implement the task. Read py/PYTHON_REWRITE_GUIDE.md first."

# 监控进度
cd /home/jerry/ai/pi-mono-worktree/pi-mono
for d in py-ai-core py-ai-providers-a py-ai-providers-b py-tui; do
  echo "=== $d ===" && cd ../$d && git log --oneline python-rewrite..HEAD 2>/dev/null | head -5 && cd ../pi-mono
done

# 审核通过后合并
git checkout python-rewrite
git merge --no-ff py/ai-core -m "merge: [Phase 1] AI 核心类型和工具函数"
git merge --no-ff py/ai-providers-a -m "merge: [Phase 1] AI providers (Anthropic + OpenAI)"
git merge --no-ff py/ai-providers-b -m "merge: [Phase 1] AI providers (Google + Bedrock) + OAuth"
git merge --no-ff py/tui -m "merge: [Phase 1] TUI 包"

# 验证
cd py && uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest --cov --cov-fail-under=80 -v

# 清理
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git worktree remove ../py-ai-core
git worktree remove ../py-ai-providers-a
git worktree remove ../py-ai-providers-b
git worktree remove ../py-tui
git push origin python-rewrite
```

---

## Phase 2: 中间层（2 个并行任务）

### 创建 Issues

#### Issue: 任务 2-1 — pi_agent

```bash
gh issue create --title "[Phase 2] 重写 pi_agent 为 Python" --label "python-rewrite,phase-2,pkg:agent" --body "$(cat <<'ISSUE_EOF'
## [Phase 2] 重写 pi_agent

### 范围
重写 agent 运行时包。

**TS 源文件**（均位于 `packages/agent/src/`）:
- `agent-loop.ts` (417 行) — 主 agent 循环
- `agent.ts` (559) — Agent 类
- `proxy.ts` (340) — 传输代理
- `types.ts` (194) — agent 类型

### Python 输出文件
```
py/pi_agent/
├── __init__.py
├── types.py
├── agent_loop.py
├── agent.py
├── proxy.py
└── MAPPING.md
py/tests/unit/pi_agent/
├── test_types.py
├── test_agent_loop.py
├── test_agent.py
└── test_proxy.py
```

### Shared Interface Contract

本任务定义的类型将被 Phase 3 的多个任务 import。**必须**严格使用以下名称和签名。

#### 本任务定义的类型（Phase 3 任务会 import）
```python
# pi_agent.types

ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]

AgentMessage = Message  # 或 Message | CustomAgentMessage 联合类型

@dataclass
class AgentToolResult:
    content: list[TextContent | ImageContent]
    details: Any

AgentToolUpdateCallback = Callable[[AgentToolResult], None]

class AgentTool(ABC):
    """工具基类 — Phase 3 的所有工具类继承此类"""
    name: str
    label: str
    description: str
    parameters: dict[str, Any]  # JSON Schema

    @abstractmethod
    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.Event | None = None,
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult: ...

@dataclass
class AgentState:
    system_prompt: str
    model: Model
    thinking_level: ThinkingLevel
    tools: list[AgentTool]
    messages: list[AgentMessage]
    is_streaming: bool
    stream_message: AgentMessage | None
    pending_tool_calls: set[str]
    error: str | None = None

@dataclass
class AgentContext:
    system_prompt: str
    messages: list[AgentMessage]
    tools: list[AgentTool] | None = None

@dataclass
class AgentLoopConfig:
    model: Model
    convert_to_llm: Callable[[list[AgentMessage]], list[Message]] | None = None
    transform_context: Callable[..., Any] | None = None
    get_api_key: Callable[[str], str | None] | None = None
    # ... 其他可选字段

# AgentEvent 判别联合
AgentEvent = (AgentStartEvent | AgentEndEvent | TurnStartEvent | TurnEndEvent
              | MessageStartEvent | MessageUpdateEvent | MessageEndEvent
              | ToolExecutionStartEvent | ToolExecutionUpdateEvent | ToolExecutionEndEvent)

# pi_agent.agent
class Agent:
    def subscribe(self, fn: Callable[[AgentEvent], None]) -> Callable[[], None]: ...
    @property
    def state(self) -> AgentState: ...
    def set_system_prompt(self, v: str) -> None: ...
    def set_model(self, m: Model) -> None: ...
    def set_tools(self, t: list[AgentTool]) -> None: ...
    async def prompt(self, message: AgentMessage | str, ...) -> None: ...
    def abort(self) -> None: ...
    async def wait_for_idle(self) -> None: ...
    # ...

# pi_agent.agent_loop
async def agent_loop(
    prompts: list[AgentMessage],
    context: AgentContext,
    config: AgentLoopConfig,
    signal: asyncio.Event | None = None,
) -> AsyncIterator[AgentEvent]: ...
```

### 依赖关系
- 依赖: Phase 1 完成（特别是任务 1-1 pi_ai 核心类型）
- 被依赖: 任务 3-1（coding-agent 会话）, 任务 3-2（工具）, 任务 3-5（pods）, 任务 3-6（mom）, 任务 4-1（集成测试）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md` 了解映射规则
2. **阅读上方"Shared Interface Contract"，确认导出的类型名称和签名**
3. 阅读上面列出的每个 TS 源文件
4. 阅读 `py/pi_ai/types.py` 了解可用类型（Phase 1 已合并）
5. 运行 `cd py && uv run python scripts/extract_public_api.py ../../packages/agent/src/`
6. 实现:
   - `types.py`: Agent 类型用 `@dataclass`，Tool 接口用 `ABC`/`Protocol`
   - `agent_loop.py`: async generator yield 事件，替代 EventStream 模式
   - `agent.py`: Agent 类使用 pi_ai stream 函数
   - `proxy.py`: HTTP 代理使用 `httpx`
7. 使用 mock LLM 响应编写单元测试
8. 创建 `py/pi_agent/MAPPING.md`
9. 运行: `cd py && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest tests/unit/pi_agent/ --cov=pi_agent --cov-fail-under=80 -v`

### 关键设计决策
- Agent loop: async generator yield 事件（`async for event in agent.run():`）
- Tool 接口: `class AgentTool(ABC)` + `async def execute()` 方法
- Proxy: `httpx.AsyncClient` 用于 HTTP 传输
- 不引入 `EventStream` 类 — 使用原生 `AsyncIterator`

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 完整
- [ ] 无未标注的 `Any` 类型
- [ ] **导出的类型名称与 Shared Interface Contract 完全一致**
ISSUE_EOF
)"
```

#### Issue: 任务 2-2 — pi_ai 集成

```bash
gh issue create --title "[Phase 2] pi_ai 集成: 最终导出和 provider 注册" --label "python-rewrite,phase-2,pkg:ai" --body "$(cat <<'ISSUE_EOF'
## [Phase 2] pi_ai 集成

### 范围
将分别开发的 pi_ai 模块（核心 + providers A + providers B）整合为一个完整的包。

### 任务清单
1. 编写最终的 `py/pi_ai/__init__.py`，包含完整的 `__all__` 列出所有公共导出
2. 编写 `py/pi_ai/providers/__init__.py`，包含 provider 注册
3. 确保 `register_builtins()` 注册所有 provider（Anthropic, OpenAI 变体, Google 变体, Bedrock）
4. 生成 `py/pi_ai/models_generated.py`（模型目录）— 方式:
   - 从 `packages/ai/src/models.generated.ts` 移植，或
   - 编写生成脚本 `py/scripts/generate_models.py`
5. 编写集成测试验证 `stream()` 分发路径（mock SDK）
6. 完善并最终确定 `py/pi_ai/MAPPING.md`
7. 验证所有跨模块 import 在运行时正常工作（不仅限于 TYPE_CHECKING 下）

### Python 输出文件
```
py/pi_ai/
├── __init__.py          （更新 — 完整 __all__）
├── providers/
│   └── __init__.py      （更新 — 注册所有 provider）
├── models_generated.py  （新增）
├── MAPPING.md           （最终版）
py/tests/integration/
└── test_ai_stream_dispatch.py
```

### 依赖关系
- 依赖: 任务 1-1, 任务 1-2, 任务 1-3（Phase 1 所有 AI 任务已合并）
- 被依赖: Phase 3 所有任务

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md`
2. 阅读 `packages/ai/src/index.ts` 查看完整公共 API
3. 阅读 `packages/ai/src/models.generated.ts` 获取模型目录数据
4. 验证所有 `TYPE_CHECKING` 守卫的 import 已转为运行时 import
5. 编写集成测试: 创建 mock provider，注册，调用 `stream()`，验证事件
6. 运行全量质量检查

### 验收标准
- [ ] `from pi_ai import *` 导出所有公共 API 项
- [ ] `register_builtins()` 注册所有 7+ 个 provider
- [ ] `models_generated.py` 包含模型目录数据
- [ ] 集成测试通过（使用 mock provider）
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] MAPPING.md 完整准确
ISSUE_EOF
)"
```

### 执行 Phase 2

```bash
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git worktree add -b py/agent ../py-agent python-rewrite
git worktree add -b py/ai-integration ../py-ai-integration python-rewrite

# 终端 1:
cd /home/jerry/ai/pi-mono-worktree/py-agent
claude "Read issue #XX from github (gh issue view XX --json title,body,comments,labels,state). Follow the instructions in the issue to implement the task. Read py/PYTHON_REWRITE_GUIDE.md first."

# 终端 2:
cd /home/jerry/ai/pi-mono-worktree/py-ai-integration
claude "Read issue #XX from github (gh issue view XX --json title,body,comments,labels,state). Follow the instructions in the issue to implement the task. Read py/PYTHON_REWRITE_GUIDE.md first."

# 合并
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git checkout python-rewrite
git merge --no-ff py/agent -m "merge: [Phase 2] Agent 包"
git merge --no-ff py/ai-integration -m "merge: [Phase 2] AI 集成"

# 验证
cd py && uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest --cov --cov-fail-under=80 -v

# 清理
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git worktree remove ../py-agent
git worktree remove ../py-ai-integration
git push origin python-rewrite
```

---

## Phase 3: 上层（8 个并行任务）

### 创建 Issues

#### Issue: 任务 3-1 — coding-agent 核心会话

```bash
gh issue create --title "[Phase 3] 重写 pi_coding_agent 核心会话为 Python" --label "python-rewrite,phase-3,pkg:coding-agent" --body "$(cat <<'ISSUE_EOF'
## [Phase 3] 重写 pi_coding_agent 核心会话

### 范围
重写 coding agent 的核心会话管理。

**TS 源文件**（位于 `packages/coding-agent/src/core/`）:
- `agent-session.ts` (2,865 行)
- `session-manager.ts` (1,401)
- `package-manager.ts` (1,729)
- `event-bus.ts`
- `messages.ts`
- `system-prompt.ts`
- `bash-executor.ts`
- `exec.ts`

### Python 输出文件
```
py/pi_coding_agent/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── agent_session.py
│   ├── session_manager.py
│   ├── package_manager.py
│   ├── event_bus.py
│   ├── messages.py
│   ├── system_prompt.py
│   ├── bash_executor.py
│   └── exec.py
├── MAPPING.md
py/tests/unit/pi_coding_agent/
├── test_agent_session.py
├── test_session_manager.py
└── ...
```

### Shared Interface Contract

Phase 3 的 8 个任务并行开发，都在 `pi_coding_agent` 包内。以下契约确保合并时类型兼容。

#### 本任务定义的类型（其他任务会 import）

```python
# pi_coding_agent.core.event_bus
class EventBus(Protocol):
    def emit(self, channel: str, data: Any) -> None: ...
    def on(self, channel: str, handler: Callable[[Any], None]) -> Callable[[], None]: ...
    def clear(self) -> None: ...

def create_event_bus() -> EventBus: ...

# pi_coding_agent.core.messages
@dataclass
class BashExecutionMessage:
    role: Literal["bash_execution"]
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    # ... 其他字段

@dataclass
class CustomMessage:
    role: Literal["custom"]
    # ...

@dataclass
class BranchSummaryMessage:
    role: Literal["branch_summary"]
    summary: str
    # ...

@dataclass
class CompactionSummaryMessage:
    role: Literal["compaction_summary"]
    summary: str
    # ...

def convert_to_llm(messages: list[AgentMessage]) -> list[Message]: ...

# pi_coding_agent.core.session_manager
@dataclass
class SessionEntry:
    # 判别联合，type 字段区分
    ...

@dataclass
class SessionContext:
    messages: list[AgentMessage]
    # ...

class SessionManager:
    def append_message(self, ...) -> None: ...
    def append_compaction_entry(self, ...) -> None: ...
    # ...

# pi_coding_agent.core.agent_session
class AgentSession:
    # 公共属性
    @property
    def state(self) -> AgentState: ...
    @property
    def model(self) -> Model | None: ...
    @property
    def messages(self) -> list[AgentMessage]: ...
    @property
    def session_id(self) -> str: ...
    @property
    def is_streaming(self) -> bool: ...

    # 公共方法
    def subscribe(self, listener: Callable[[AgentSessionEvent], None]) -> Callable[[], None]: ...
    async def prompt(self, text: str, **kwargs: Any) -> None: ...
    async def abort(self) -> None: ...
    async def compact(self, custom_instructions: str | None = None) -> CompactionResult: ...
    async def new_session(self, **kwargs: Any) -> None: ...
    async def set_model(self, model: Model) -> None: ...
    # ... 完整方法列表见 TS 源码
```

#### 从其他并行任务 import 的类型

```python
# 从任务 3-2（工具）import — 使用 TYPE_CHECKING 守卫
from pi_coding_agent.core.tools import (
    BashTool,       # 不是 create_bash_tool
    EditTool,       # 不是 create_edit_tool
    ReadTool,
    WriteTool,
    GrepTool,
    FindTool,
    LsTool,
    create_coding_tools,    # (cwd: str, **kwargs) -> list[AgentTool]
    create_all_tools,       # (cwd: str, **kwargs) -> dict[str, AgentTool]
)

# 从任务 3-3（扩展+压缩）import — 使用 TYPE_CHECKING 守卫
from pi_coding_agent.core.extensions import (
    ExtensionRunner,        # Protocol / ABC
    ToolInfo,               # @dataclass: name, active, label, description
    # 事件类型
    SessionStartEvent,
    SessionShutdownEvent,
    AgentStartEvent,
    AgentEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionEndEvent,
)
from pi_coding_agent.core.compaction import (
    CompactionResult,       # @dataclass: summary, tokens_before, tokens_after, cost
    CompactionSettings,     # @dataclass: threshold, window_size, token_limits
    compact,                # async def compact(agent, ...) -> CompactionResult
    should_compact,         # (context_tokens: int, context_window: int, settings) -> bool
)
```

### 依赖关系
- 依赖: Phase 2（pi_agent, pi_ai 集成）
- 被依赖: 任务 4-1（集成测试）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md` 了解映射规则
2. **阅读上方"Shared Interface Contract"，确认导出和导入的类型名称**
3. 阅读每个 TS 源文件
4. 阅读 `py/pi_agent/types.py` 和 `py/pi_ai/types.py` 了解可用类型
5. 用 Pythonic 模式实现:
   - 会话管理用 `pathlib.Path` 进行文件操作
   - 事件总线用简单发布/订阅模式（`asyncio.Queue` 或回调列表）
   - Bash 执行用 `asyncio.create_subprocess_exec`
6. 编写单元测试
7. 运行质量检查

### 关键设计决策
- 会话持久化: JSON 文件 + `pathlib.Path`
- 包管理器: `subprocess.run` 调用 npm/pip/uv 命令
- 事件总线: 基于回调的发布/订阅（非 asyncio.Queue）
- 系统提示词: 模板字符串 + f-string 格式化

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 完整
- [ ] **导出的类型名称与 Shared Interface Contract 完全一致**
ISSUE_EOF
)"
```

#### Issue: 任务 3-2 — coding-agent 工具

```bash
gh issue create --title "[Phase 3] 重写 pi_coding_agent 工具为 Python" --label "python-rewrite,phase-3,pkg:coding-agent" --body "$(cat <<'ISSUE_EOF'
## [Phase 3] 重写 pi_coding_agent 工具

### 范围
重写所有 coding agent 工具。

**TS 源文件**: `packages/coding-agent/src/core/tools/*.ts`（共 2,483 行）
- `bash.ts`, `edit.ts`, `edit-diff.ts`, `read.ts`, `write.ts`, `grep.ts`, `find.ts`, `ls.ts`, `agent.ts`, `ask-user.ts`, `web-search.ts`, `web-fetch.ts` 等

### Python 输出文件
```
py/pi_coding_agent/core/tools/
├── __init__.py
├── bash.py
├── edit.py
├── edit_diff.py
├── read.py
├── write.py
├── grep.py
├── find.py
├── ls.py
├── agent.py
├── ask_user.py
├── web_search.py
├── web_fetch.py
└── ...
py/tests/unit/pi_coding_agent/
└── test_tools.py（或每个工具单独的测试文件）
```

### Shared Interface Contract

#### 本任务定义的类型（任务 3-1 会 import）

```python
# pi_coding_agent.core.tools.__init__

# 工具类命名规则: XxxTool（PascalCase），不是 create_xxx_tool 工厂函数
class BashTool(AgentTool):
    async def execute(self, tool_call_id: str, params: dict[str, Any],
                      signal: asyncio.Event | None = None,
                      on_update: AgentToolUpdateCallback | None = None) -> AgentToolResult: ...

class EditTool(AgentTool): ...
class ReadTool(AgentTool): ...
class WriteTool(AgentTool): ...
class GrepTool(AgentTool): ...
class FindTool(AgentTool): ...
class LsTool(AgentTool): ...

# 工具集合工厂函数
def create_coding_tools(cwd: str, **kwargs: Any) -> list[AgentTool]: ...
def create_read_only_tools(cwd: str, **kwargs: Any) -> list[AgentTool]: ...
def create_all_tools(cwd: str, **kwargs: Any) -> dict[str, AgentTool]: ...

# 工具名类型
ToolName = Literal["read", "bash", "edit", "write", "grep", "find", "ls"]
```

#### 从 `pi_agent` import（Phase 2 已合并）
```python
from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
```

### 依赖关系
- 依赖: Phase 2（pi_agent 提供 AgentTool 基类）
- 被依赖: 任务 3-1（会话注册工具），任务 4-1（集成测试）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md`
2. **阅读上方"Shared Interface Contract"，确认工具类命名和工厂函数签名**
3. 阅读所有工具 TS 源文件
4. 阅读 `py/pi_agent/types.py` 了解 `AgentTool` 基类/协议
5. 将每个工具实现为类: `class BashTool(AgentTool)`, `class EditTool(AgentTool)` 等
6. 文件操作用 `pathlib`，bash 用 `subprocess`，网络用 `httpx`
7. 在临时目录中编写单元测试（`tmp_path` fixture）
8. 运行质量检查

### 关键设计决策
- 工厂函数 → 类继承: `class BashTool(AgentTool)`
- 文件工具: 全程使用 `pathlib.Path`
- Bash 工具: `asyncio.create_subprocess_exec` + 超时
- Grep 工具: 优先 `subprocess` 调用 `rg`（ripgrep），回退到 Python `re`

### 验收标准
- [ ] 所有 TS 工具导出都有 Python 类对应
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 中包含所有工具的条目
- [ ] **工具类名和工厂函数签名与 Shared Interface Contract 完全一致**
ISSUE_EOF
)"
```

#### Issue: 任务 3-3 — coding-agent 扩展 + 压缩 + 模型管理

```bash
gh issue create --title "[Phase 3] 重写 pi_coding_agent 扩展、压缩、模型管理为 Python" --label "python-rewrite,phase-3,pkg:coding-agent" --body "$(cat <<'ISSUE_EOF'
## [Phase 3] 重写 pi_coding_agent 扩展 + 压缩 + 模型管理

### 范围
重写扩展系统、上下文压缩和模型/设置管理。

**TS 源文件**（位于 `packages/coding-agent/src/core/`）:
- `extensions/` — 全部文件 (2,967 行)
- `compaction/` — 全部文件 (1,322 行)
- `model-registry.ts` (665)
- `model-resolver.ts` (527)
- `auth-storage.ts` (464)
- `settings-manager.ts` (888)
- `skills.ts` (459)
- `resource-loader.ts` (871)
- `prompt-templates.ts` (299)

### Python 输出文件
```
py/pi_coding_agent/core/
├── extensions/
│   ├── __init__.py
│   ├── extension.py
│   ├── loader.py
│   └── ...
├── compaction/
│   ├── __init__.py
│   ├── compactor.py
│   └── ...
├── model_registry.py
├── model_resolver.py
├── auth_storage.py
├── settings_manager.py
├── skills.py
├── resource_loader.py
└── prompt_templates.py
py/tests/unit/pi_coding_agent/
├── test_extensions.py
├── test_compaction.py
├── test_model_registry.py
├── test_settings_manager.py
└── ...
```

### Shared Interface Contract

#### 本任务定义的类型（任务 3-1 和 3-4a 会 import）

```python
# pi_coding_agent.core.extensions

class ExtensionRunner(ABC):
    """Extension lifecycle manager."""
    async def run_session_start(self, event: SessionStartEvent) -> None: ...
    async def run_session_shutdown(self, event: SessionShutdownEvent) -> None: ...
    async def run_agent_start(self, event: AgentStartEvent) -> None: ...
    async def run_tool_execution_start(self, event: ToolExecutionStartEvent) -> None: ...
    async def run_tool_execution_end(self, event: ToolExecutionEndEvent) -> None: ...
    # ...

@dataclass
class ToolInfo:
    name: str
    active: bool
    label: str
    description: str

# 扩展事件类型 — 全部用 @dataclass + Literal type 字段
@dataclass
class SessionStartEvent:
    type: Literal["session_start"] = "session_start"
@dataclass
class SessionShutdownEvent:
    type: Literal["session_shutdown"] = "session_shutdown"
@dataclass
class AgentStartEvent:
    type: Literal["agent_start"] = "agent_start"
@dataclass
class AgentEndEvent:
    type: Literal["agent_end"] = "agent_end"
@dataclass
class ToolExecutionStartEvent:
    type: Literal["tool_execution_start"] = "tool_execution_start"
    tool_call_id: str
    tool_name: str
@dataclass
class ToolExecutionEndEvent:
    type: Literal["tool_execution_end"] = "tool_execution_end"
    tool_call_id: str
    tool_name: str
    is_error: bool
# ... 其他事件类型

# pi_coding_agent.core.compaction

@dataclass
class CompactionResult:
    summary: str
    tokens_before: int
    tokens_after: int
    cost: UsageCost | None = None

@dataclass
class CompactionSettings:
    threshold: float        # 0.0-1.0, context usage ratio to trigger
    # ...

def should_compact(context_tokens: int, context_window: int, settings: CompactionSettings) -> bool: ...
async def compact(agent: Agent, ...) -> CompactionResult: ...

# pi_coding_agent.core.settings_manager
class SettingsManager:
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    # ...
```

### 依赖关系
- 依赖: Phase 2（pi_ai, pi_agent）
- 被依赖: 任务 3-1（会话使用扩展和压缩），任务 3-4a（交互模式使用设置/扩展）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md`
2. **阅读上方"Shared Interface Contract"，确认导出的类型名称和签名**
3. 阅读上面列出的所有 TS 源文件
4. 实现:
   - 扩展: 使用 importlib 的插件加载系统
   - 压缩: 消息历史截断/摘要
   - 模型注册表: 模型查找和配置
   - 设置: 基于 JSON 的设置 + `pathlib.Path` 存储
   - 技能: 技能文件发现和加载
5. 编写单元测试
6. 运行质量检查

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 中包含所有模块的条目
- [ ] **导出的类型名称与 Shared Interface Contract 完全一致**
ISSUE_EOF
)"
```

#### Issue: 任务 3-4a — coding-agent 交互模式核心 + CLI

```bash
gh issue create --title "[Phase 3] 重写 pi_coding_agent 交互模式核心 + CLI 为 Python" --label "python-rewrite,phase-3,pkg:coding-agent" --body "$(cat <<'ISSUE_EOF'
## [Phase 3] 重写 pi_coding_agent 交互模式核心 + CLI

### 范围
重写交互模式主循环、主题系统、打印模式、CLI 入口和 CLI 工具。

**TS 源文件**:
- `packages/coding-agent/src/modes/interactive/interactive-mode.ts` (4,391 行)
- `packages/coding-agent/src/modes/interactive/theme/theme.ts` (1,100) + `dark.json`, `light.json`, `theme-schema.json`
- `packages/coding-agent/src/modes/print-mode.ts` (124)
- `packages/coding-agent/src/main.ts` (770)
- `packages/coding-agent/src/config.ts` (241)
- `packages/coding-agent/src/migrations.ts` (295)
- `packages/coding-agent/src/cli/args.ts` (310)
- `packages/coding-agent/src/cli/config-selector.ts`
- `packages/coding-agent/src/cli/list-models.ts` (104)
- `packages/coding-agent/src/cli/file-processor.ts` (96)
- `packages/coding-agent/src/cli/session-picker.ts`

### Python 输出文件
```
py/pi_coding_agent/
├── main.py
├── config.py
├── migrations.py
├── modes/
│   ├── __init__.py
│   ├── print_mode.py
│   └── interactive/
│       ├── __init__.py
│       ├── interactive_mode.py
│       └── theme.py
├── cli/
│   ├── __init__.py
│   ├── args.py
│   ├── config_selector.py
│   ├── list_models.py
│   ├── file_processor.py
│   └── session_picker.py
├── data/
│   ├── dark.json
│   ├── light.json
│   └── theme-schema.json
py/tests/unit/pi_coding_agent/
├── test_interactive_mode.py
├── test_cli_args.py
└── ...
```

### Shared Interface Contract

本任务是 Phase 3 并行任务中的"消费者"，需要 import 其他并行任务定义的类型。

#### 从任务 3-1（核心会话）import — 使用 TYPE_CHECKING 守卫
```python
from pi_coding_agent.core.agent_session import AgentSession
from pi_coding_agent.core.event_bus import EventBus, create_event_bus
from pi_coding_agent.core.messages import (
    BashExecutionMessage,
    convert_to_llm,
)
from pi_coding_agent.core.session_manager import SessionManager, SessionContext
```

#### 从任务 3-2（工具）import — 使用 TYPE_CHECKING 守卫
```python
from pi_coding_agent.core.tools import create_all_tools, ToolName
```

#### 从任务 3-3（扩展+压缩+设置）import — 使用 TYPE_CHECKING 守卫
```python
from pi_coding_agent.core.extensions import ExtensionRunner, ToolInfo
from pi_coding_agent.core.compaction import CompactionResult, CompactionSettings
from pi_coding_agent.core.settings_manager import SettingsManager
```

### 依赖关系
- 依赖: Phase 2（pi_ai, pi_agent），任务 1-4（pi_tui）
- 使用: 任务 3-1, 3-2, 3-3 — 如尚未合并可使用 stub/TYPE_CHECKING
- 被依赖: 任务 4-1（E2E 测试）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md`
2. **阅读上方"Shared Interface Contract"，确认 import 路径和类型名称**
3. 阅读上面列出的所有 TS 源文件
4. 阅读 `py/pi_tui/` 了解可用的 TUI 组件
5. 实现:
   - CLI: 使用 `click` 或 `typer` 解析参数
   - 交互模式: 使用 pi_tui 的主渲染循环
   - 主题: JSON 主题加载，深色/浅色变体
   - 配置/迁移: JSON 配置 + 版本迁移
6. 编写单元测试
7. 运行质量检查

### 关键设计决策
- CLI 框架: `click`（或 `typer`）
- 入口: 通过 pyproject.toml `[project.scripts]` 配置 `python -m pi_coding_agent`
- 主题: 加载 JSON 文件，按 schema 验证
- 交互模式: 集成 pi_tui 渲染循环

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] `python -m pi_coding_agent --help` 正常工作
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 中包含所有模块的条目
- [ ] **import 路径和类型名称与 Shared Interface Contract 完全一致**
ISSUE_EOF
)"
```

#### Issue: 任务 3-4b — coding-agent 交互组件

```bash
gh issue create --title "[Phase 3] 重写 pi_coding_agent 交互组件为 Python" --label "python-rewrite,phase-3,pkg:coding-agent" --body "$(cat <<'ISSUE_EOF'
## [Phase 3] 重写 pi_coding_agent 交互组件

### 范围
重写全部 30 个交互模式 UI 组件。

**TS 源文件**: `packages/coding-agent/src/modes/interactive/components/`（7,536 行，约 30 个文件）

主要组件包括: MessageList, ToolCallView, InputArea, StatusBar, Sidebar, PermissionDialog, ModelSelector, HelpOverlay, DiffView 等。

### Python 输出文件
```
py/pi_coding_agent/modes/interactive/components/
├── __init__.py
├── message_list.py
├── tool_call_view.py
├── input_area.py
├── status_bar.py
├── sidebar.py
├── permission_dialog.py
├── model_selector.py
├── help_overlay.py
├── diff_view.py
└── ...（每个组件一个文件）
py/tests/unit/pi_coding_agent/
└── test_interactive_components.py
```

### Shared Interface Contract

#### 从任务 3-1（核心会话）import — 使用 TYPE_CHECKING 守卫
```python
from pi_coding_agent.core.agent_session import AgentSession
from pi_coding_agent.core.messages import BashExecutionMessage
```

#### 从任务 3-3（扩展）import — 使用 TYPE_CHECKING 守卫
```python
from pi_coding_agent.core.extensions import ToolInfo
```

#### 从 pi_tui import（Phase 1 已合并）
```python
from pi_tui.tui import Component, Container  # 基类
from pi_tui.components.text import Text
from pi_tui.components.input import Input
# ... 其他 pi_tui 组件
```

### 依赖关系
- 依赖: Phase 2，任务 1-4（pi_tui 组件）
- 配合: 任务 3-4a（交互模式核心），3-1（会话），3-3（扩展）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md`
2. **阅读上方"Shared Interface Contract"，确认 import 路径和类型名称**
3. 阅读所有组件 TS 源文件
4. 阅读 `py/pi_tui/components/` 了解可用的基础组件
5. 将每个组件实现为继承 pi_tui 组件的 Python 类
6. 编写组件渲染逻辑的单元测试
7. 运行质量检查

### 验收标准
- [ ] 全部 30 个 TS 组件都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 中包含所有组件的条目
- [ ] **import 路径和类型名称与 Shared Interface Contract 完全一致**
ISSUE_EOF
)"
```

#### Issue: 任务 3-4c — coding-agent RPC + 工具函数

```bash
gh issue create --title "[Phase 3] 重写 pi_coding_agent RPC + 工具函数为 Python" --label "python-rewrite,phase-3,pkg:coding-agent" --body "$(cat <<'ISSUE_EOF'
## [Phase 3] 重写 pi_coding_agent RPC + 工具函数

### 范围
重写 RPC 模式、工具模块和 HTML 导出。

**TS 源文件**:
- `packages/coding-agent/src/modes/rpc/rpc-types.ts` (263)
- `packages/coding-agent/src/modes/rpc/rpc-client.ts` (510)
- `packages/coding-agent/src/modes/rpc/rpc-mode.ts` (639)
- `packages/coding-agent/src/utils/shell.ts` (202)
- `packages/coding-agent/src/utils/git.ts` (192)
- `packages/coding-agent/src/utils/clipboard*.ts`
- `packages/coding-agent/src/utils/image-*.ts`
- `packages/coding-agent/src/utils/tools-manager.ts` (237)
- 其他工具（共约 1,515 行）
- `packages/coding-agent/src/core/export-html/` (652)

### Python 输出文件
```
py/pi_coding_agent/
├── modes/rpc/
│   ├── __init__.py
│   ├── rpc_types.py
│   ├── rpc_client.py
│   └── rpc_mode.py
├── utils/
│   ├── __init__.py
│   ├── shell.py
│   ├── git.py
│   ├── clipboard.py
│   ├── image.py
│   └── tools_manager.py
├── core/export_html/
│   ├── __init__.py
│   └── exporter.py
py/tests/unit/pi_coding_agent/
├── test_rpc.py
├── test_utils.py
└── test_export_html.py
```

### Shared Interface Contract

#### 从任务 3-1（核心会话）import — 使用 TYPE_CHECKING 守卫
```python
from pi_coding_agent.core.agent_session import AgentSession
from pi_coding_agent.core.messages import convert_to_llm
```

### 依赖关系
- 依赖: Phase 2（pi_ai, pi_agent），任务 3-1（会话）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md`
2. **阅读上方"Shared Interface Contract"，确认 import 路径**
3. 阅读所有 TS 源文件
4. 实现:
   - RPC: 基于 stdio/websocket 的 JSON-RPC，使用 `httpx` 或 `websockets`
   - Shell 工具: `subprocess` 封装
   - Git 工具: `subprocess.run(["git", ...])`（不用 gitpython）
   - 剪贴板: 平台相关 subprocess 调用（xclip/pbcopy 等）
   - HTML 导出: Jinja2 模板或字符串格式化
5. 编写单元测试
6. 运行质量检查

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 中包含所有模块的条目
- [ ] **import 路径与 Shared Interface Contract 完全一致**
ISSUE_EOF
)"
```

#### Issue: 任务 3-5 — pi_pods

```bash
gh issue create --title "[Phase 3] 重写 pi_pods 为 Python" --label "python-rewrite,phase-3,pkg:pods" --body "$(cat <<'ISSUE_EOF'
## [Phase 3] 重写 pi_pods

### 范围
重写 pod 管理 CLI 工具。

**TS 源文件**: `packages/pods/src/`（共 1,773 行）

### Python 输出文件
```
py/pi_pods/
├── __init__.py
├── cli.py
├── config.py
├── ssh.py
├── types.py
├── commands/
│   ├── __init__.py
│   ├── create.py
│   ├── destroy.py
│   ├── list.py
│   ├── ssh.py
│   └── ...
├── MAPPING.md
py/tests/unit/pi_pods/
├── test_cli.py
├── test_config.py
├── test_ssh.py
└── ...
```

### 依赖关系
- 依赖: Phase 2（pi_agent）

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md`
2. 阅读 `packages/pods/src/` 下的所有 TS 源文件
3. 实现:
   - CLI: `click` 或 `typer`
   - SSH: `asyncssh` 或 `subprocess` 调用 ssh 命令
   - 配置: JSON/YAML 配置文件 + `pathlib.Path`
4. 编写单元测试（mock SSH 连接）
5. 运行质量检查

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 完整
ISSUE_EOF
)"
```

#### Issue: 任务 3-6 — pi_mom

```bash
gh issue create --title "[Phase 3] 重写 pi_mom Slack 机器人为 Python" --label "python-rewrite,phase-3,pkg:mom" --body "$(cat <<'ISSUE_EOF'
## [Phase 3] 重写 pi_mom Slack 机器人

### 范围
重写委托给 pi agent 的 Slack 机器人。

**TS 源文件**: `packages/mom/src/`（共 4,120 行）

### Python 输出文件
```
py/pi_mom/
├── __init__.py
├── agent.py
├── slack.py
├── context.py
├── events.py
├── tools/
│   ├── __init__.py
│   └── ...
├── MAPPING.md
py/tests/unit/pi_mom/
├── test_agent.py
├── test_slack.py
├── test_events.py
└── ...
```

### Shared Interface Contract

#### 从任务 3-1（核心会话）import — 使用 TYPE_CHECKING 守卫
```python
from pi_coding_agent.core.agent_session import AgentSession
from pi_coding_agent.core.messages import convert_to_llm
```

#### 从 pi_agent import（Phase 2 已合并）
```python
from pi_agent.types import Agent, AgentEvent, AgentTool, AgentMessage
```

### 依赖关系
- 依赖: Phase 2（pi_agent），Phase 3 任务 3-1（coding-agent 会话）
- 注意: 可使用 stub 先行开发 coding-agent 依赖部分

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md`
2. **阅读上方"Shared Interface Contract"，确认 import 路径和类型名称**
3. 阅读 `packages/mom/src/` 下的所有 TS 源文件
4. 实现:
   - Slack 集成: 使用 `slack-bolt` 库
   - Agent 委托: 使用 pi_agent 和 pi_coding_agent
   - 事件处理: Slack 事件的异步事件循环
5. 编写单元测试（mock Slack API）
6. 运行质量检查

### 验收标准
- [ ] 所有 TS 公共导出都有 Python 对应实现
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] MAPPING.md 完整
- [ ] **import 路径和类型名称与 Shared Interface Contract 完全一致**
ISSUE_EOF
)"
```

### 执行 Phase 3

```bash
# 创建 worktree 并同时创建分支（8 路并行）
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git worktree add -b py/ca-session ../py-ca-session python-rewrite
git worktree add -b py/ca-tools ../py-ca-tools python-rewrite
git worktree add -b py/ca-extensions ../py-ca-extensions python-rewrite
git worktree add -b py/ca-interactive-core ../py-ca-interactive-core python-rewrite
git worktree add -b py/ca-interactive-components ../py-ca-interactive-components python-rewrite
git worktree add -b py/ca-rpc-utils ../py-ca-rpc-utils python-rewrite
git worktree add -b py/pods ../py-pods python-rewrite
git worktree add -b py/mom ../py-mom python-rewrite

# 在 8 个终端中启动 Claude Code（用实际 issue 编号替换 XX）
cd /home/jerry/ai/pi-mono-worktree/py-ca-session
claude "Read issue #XX from github (gh issue view XX --json title,body,comments,labels,state). Follow the instructions in the issue to implement the task. Read py/PYTHON_REWRITE_GUIDE.md first."

# ... 对每个 worktree 重复 ...

# 全部完成并审核后合并
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git checkout python-rewrite
git merge --no-ff py/ca-session -m "merge: [Phase 3] Coding-agent core session"
git merge --no-ff py/ca-tools -m "merge: [Phase 3] Coding-agent tools"
git merge --no-ff py/ca-extensions -m "merge: [Phase 3] Coding-agent extension"
git merge --no-ff py/ca-interactive-core -m "merge: [Phase 3] Coding-agent interactive core + CLI"
git merge --no-ff py/ca-interactive-components -m "merge: [Phase 3] Coding-agent interactive component"
git merge --no-ff py/ca-rpc-utils -m "merge: [Phase 3] Coding-agent RPC + util functions"
git merge --no-ff py/pods -m "merge: [Phase 3] Pods package"
git merge --no-ff py/mom -m "merge: [Phase 3] Mom package"

# 验证
cd py && uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest --cov --cov-fail-under=80 -v

# 清理
cd /home/jerry/ai/pi-mono-worktree/pi-mono
for d in py-ca-session py-ca-tools py-ca-extensions py-ca-interactive-core py-ca-interactive-components py-ca-rpc-utils py-pods py-mom; do
  git worktree remove ../$d
done
git push origin python-rewrite
```

---

## Phase 4: 集成与收尾（2 个并行任务）

### 创建 Issues

#### Issue: 任务 4-1 — 跨包集成测试 + E2E 测试

```bash
gh issue create --title "[Phase 4] 跨包集成测试和 E2E 测试" --label "python-rewrite,phase-4" --body "$(cat <<'ISSUE_EOF'
## [Phase 4] 跨包集成测试 + E2E 测试

### 范围
编写全面的集成测试和端到端测试。

### 原则
- **不设覆盖率目标** — 覆盖率已由单元测试保证，集成/E2E 测试的目的是验证跨组件边界的真实交互
- **不重复单元测试** — 如果 mock 掉了所有依赖只测单个函数，那是单元测试，不属于本 issue 范围
- **每个测试必须跨越至少两个真实组件的边界**
- **每个测试必须能回答："这个测试能防止什么真实故障？"**

### 集成测试（`py/tests/integration/`）

#### 1. `test_agent_loop_with_tools.py` — Agent loop × 真实工具执行
不 mock 工具。在真实 temp 目录里跑 agent loop + ReadTool/WriteTool/EditTool，使用确定性 fake LLM（按脚本返回固定响应序列，不是 mock 掉整个接口）。

验证链路：
- fake LLM 返回"写文件"tool call → WriteTool 执行 → 文件真实存在于磁盘
- fake LLM 返回"读文件"tool call → ReadTool 执行 → 返回内容与写入一致
- fake LLM 返回"编辑文件"tool call → EditTool 执行 → 文件内容确实被修改
- 整个过程中 event stream 事件顺序正确（ToolExecutionStart → ToolExecutionEnd → MessageEnd）

#### 2. `test_session_persistence.py` — Session 持久化 × 跨实例恢复
不 mock SessionManager 内部。真实走完：

- 实例 A：创建 session → 跑一轮 agent loop（用 fake LLM）→ 消息写入磁盘
- 实例 B：从同一个 session file 加载 → 验证对话历史完整 → 继续跑一轮 → 验证新消息追加到同一文件
- 验证 JSONL 文件可被第三方 JSON parser 正确逐行解析（防止序列化格式回归）

#### 3. `test_mom_event_to_agent.py` — Mom event → agent 调用链路
用 fake Slack client（实现真实接口，in-memory 收发消息）+ fake LLM：

- 写一个 immediate event JSON 文件到 events 目录
- EventsWatcher 拾取 → 触发 agent 调用 → agent 产出响应 → 响应到达 fake Slack outbox
- 验证端到端：输入的 event text 与最终发送到 channel 的消息之间有因果关系

### E2E 测试（`py/tests/e2e/`）

#### 4. `test_cli_process.py` — CLI 真实进程启动
用 `subprocess.run` 启动真实 Python 入口点（需先确保有 `__main__.py`）：

- `python -m pi_coding_agent --version` → stdout 包含版本号，exit code 0
- `python -m pi_coding_agent --help` → stdout 包含 Usage，exit code 0
- `python -m pi_coding_agent --invalid-flag` → stderr 包含错误信息，exit code != 0
- `python -m pi_coding_agent -p "hello"` → 需配合 fake LLM 或 `--provider mock` 参数

#### 5. `test_pods_ssh_commands.py` — Pods SSH 命令拼装 × mock server
验证 `ssh_exec` 拼装出的完整命令行正确：

- 使用 subprocess 录制/回放模式，捕获实际传给 `create_subprocess_exec` 的完整参数列表
- 验证各种 SSH 选项组合（port、keepalive、StrictHostKeyChecking）生成的命令字符串
- 验证 `scp_file` 的源/目标路径正确传递

### 不写什么
- ~~CLI 参数解析的各种 flag 组合~~ → `tests/unit/pi_coding_agent/test_cli_args.py` 已覆盖
- ~~类型序列化 roundtrip~~ → 各包单元测试已覆盖
- ~~event 解析的各种 error case~~ → `tests/unit/pi_mom/test_events.py` 已覆盖
- ~~`assert isinstance(x, SomeClass)` 式断言~~ → 没有信息量

### 依赖关系
- 依赖: Phase 3 所有任务已合并

### 操作指引
1. 阅读 `py/PYTHON_REWRITE_GUIDE.md`
2. 先阅读 `tests/unit/` 下已有的单元测试，明确哪些路径已被覆盖，避免重复
3. 实现 fake LLM：一个实现真实 LLM 接口但按脚本返回固定响应序列的类，供多个集成测试复用
4. 编写跨组件边界的集成测试（真实工具 + fake LLM，不 mock 工具）
5. 编写 CLI 入口的 E2E 测试（真实 subprocess，不直接调用内部函数）
6. 所有测试不依赖网络、不依赖 API key
7. 运行: `cd py && uv run pytest tests/ -v`

### 验收标准
- [ ] 所有集成测试通过
- [ ] 所有 E2E 测试通过
- [ ] 每个测试跨越至少两个真实组件的边界（不允许 mock 掉所有依赖）
- [ ] 测试中无真实 API/网络调用
- [ ] 不与 `tests/unit/` 中已有测试重复覆盖相同路径
ISSUE_EOF
)"
```

#### Issue: 任务 4-2 — 对等验证 + 最终打磨

```bash
gh issue create --title "[Phase 4] 对等验证和最终打磨" --label "python-rewrite,phase-4" --body "$(cat <<'ISSUE_EOF'
## [Phase 4] 对等验证 + 最终打磨

### 范围
验证所有包的 API 对等性，修复遗漏。

### 任务清单
1. 对每个包运行 `check_parity.py`:
   ```bash
   cd py
   uv run python scripts/check_parity.py ../../packages/ai/src pi_ai
   uv run python scripts/check_parity.py ../../packages/agent/src pi_agent
   uv run python scripts/check_parity.py ../../packages/tui/src pi_tui
   uv run python scripts/check_parity.py ../../packages/coding-agent/src pi_coding_agent
   uv run python scripts/check_parity.py ../../packages/pods/src pi_pods
   uv run python scripts/check_parity.py ../../packages/mom/src pi_mom
   ```
2. 修复对等检查发现的所有缺失实现
3. 确保所有 `MAPPING.md` 文件完整准确
4. 最终质量检查全部通过:
   ```bash
   cd py && uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest --cov --cov-fail-under=80
   ```
5. 更新 CI 工作流: 移除对等检查步骤的 `continue-on-error`

### 依赖关系
- 依赖: Phase 3 所有任务 + 任务 4-1 已合并

### 验收标准
- [ ] `check_parity.py` 对所有包报告 0 个缺口
- [ ] 所有 MAPPING.md 文件完整
- [ ] mypy --strict 通过
- [ ] ruff check + format 通过
- [ ] 测试覆盖率 >= 80%
- [ ] CI 工作流对等检查已设为必须（非 continue-on-error）
ISSUE_EOF
)"
```

### 执行 Phase 4

```bash
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git worktree add -b py/integration ../py-integration python-rewrite
git worktree add -b py/parity ../py-parity python-rewrite

# 在 2 个终端中启动 Claude Code
cd /home/jerry/ai/pi-mono-worktree/py-integration
claude "Read issue #XX from github (gh issue view XX --json title,body,comments,labels,state). Follow the instructions in the issue to implement the task. Read py/PYTHON_REWRITE_GUIDE.md first."

cd /home/jerry/ai/pi-mono-worktree/py-parity
claude "Read issue #XX from github (gh issue view XX --json title,body,comments,labels,state). Follow the instructions in the issue to implement the task. Read py/PYTHON_REWRITE_GUIDE.md first."

# 合并
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git checkout python-rewrite
git merge --no-ff py/integration -m "merge: [Phase 4] integration test和 E2E test"
git merge --no-ff py/parity -m "merge: [Phase 4] quivenlent test"

# 最终验证
cd py && uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest --cov --cov-fail-under=80 && uv run python scripts/check_parity.py

# 清理
cd /home/jerry/ai/pi-mono-worktree/pi-mono
git worktree remove ../py-integration
git worktree remove ../py-parity
git push origin python-rewrite
```

---

## 审核检查清单（每个分支合并前）

- [ ] `MAPPING.md` 存在且完整
- [ ] `__init__.py` 导出齐全
- [ ] 无硬编码密钥或测试用 API key
- [ ] 代码风格 Pythonic（非逐行翻译）
- [ ] 测试有意义（非空壳测试）
- [ ] `uv run ruff check .` 通过
- [ ] `uv run ruff format --check .` 通过
- [ ] `uv run mypy --strict .` 通过
- [ ] `uv run pytest --cov --cov-fail-under=80` 通过

---

## 最终验收（Phase 4 完成后）

```bash
cd /home/jerry/ai/pi-mono-worktree/pi-mono/py
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict .
uv run pytest --cov --cov-fail-under=80
uv run python scripts/check_parity.py  # 应报告 0 个缺口
```

---

## Phase 5: 手动集成测试

### 5.1 接线验证

`sdk.py` 的 `create_agent_session()` 和 `main.py` 的模式分发已从 stub 替换为真实实现。

### 5.2 静态检查

```bash
cd /home/jerry/ai/pi-mono-worktree/pi-mono/py
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict .
```

### 5.3 自动化测试

```bash
uv run pytest --cov --cov-fail-under=80
```

### 5.4 CLI 冒烟测试

```bash
# Help and version
uv run python -m pi_coding_agent --help
uv run python -m pi_coding_agent --version

# List models
uv run python -m pi_coding_agent --list-models

# Print mode (requires API key)
echo "Say hello" | uv run python -m pi_coding_agent -p --provider openai --model gpt-4o-mini

# JSON mode
echo "Say hello" | uv run python -m pi_coding_agent --mode json --provider openai --model gpt-4o-mini
```

### 5.5 Pods 冒烟测试

```bash
cd /home/jerry/ai/pi-mono-worktree/pi-mono/py

# Help / 子命令列表
uv run python -m pi_pods.cli --help

# list（无运行中的 pod 时应正常返回空列表）
uv run python -m pi_pods.cli list

# start --help（确认参数解析正常）
uv run python -m pi_pods.cli start --help

# shell --help
uv run python -m pi_pods.cli shell --help

# ssh --help
uv run python -m pi_pods.cli ssh --help
```

> **注意**: `start` / `stop` / `ssh` / `shell` 等子命令需要 RunPod API key
> (`RUNPOD_API_KEY`) 和实际 GPU 资源，仅在有环境时手动验证。

### 5.6 Mom (Slack Bot) 冒烟测试

```bash
cd /home/jerry/ai/pi-mono-worktree/pi-mono/py

# 无参数应打印 usage 并退出
uv run python -m pi_mom.main 2>&1; echo "exit: $?"
# 预期: Usage: mom [--sandbox=...] <working-directory> / exit: 1

# --help（如果 argparse 支持）
uv run python -m pi_mom.main --help 2>&1 || true

# 模块导入检查（验证所有依赖链正常）
uv run python -c "
from pi_mom.slack import SlackBot
from pi_mom.agent import AgentRunner
from pi_mom.events import EventsWatcher
print('All mom modules imported OK')
"
```

> **注意**: 完整运行 mom bot 需要 Slack tokens (`MOM_SLACK_APP_TOKEN`,
> `MOM_SLACK_BOT_TOKEN`) 和 API key，仅在有 Slack workspace 时手动验证：
> ```bash
> export MOM_SLACK_APP_TOKEN=xapp-...
> export MOM_SLACK_BOT_TOKEN=xoxb-...
> export OPENAI_API_KEY=sk-...
> uv run python -m pi_mom.main /tmp/mom-workdir
> ```
