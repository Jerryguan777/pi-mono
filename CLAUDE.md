# Pi-Mono Python 重写指南

## 项目结构

这是一个 TypeScript -> Python 的重写项目。所有 Python 代码统一放在 `py/` 目录下。

```
py/
├── pyproject.toml          # uv workspace 根配置
├── uv.lock
├── ruff.toml
├── mypy.ini
├── scripts/
│   ├── extract_public_api.py   # 解析 TS 导出，生成 Python 需实现的 API 清单
│   └── check_parity.py         # 对比 TS 导出 vs Python 公共 API，报告差异
├── pi_types/               # 共享类型定义/协议（最先实现）
├── pi_ai/                  # AI/LLM 抽象层（对应 packages/ai/）
├── pi_tui/                 # 终端 UI 库（对应 packages/tui/）
├── pi_agent/               # Agent 核心（对应 packages/agent/）
├── pi_coding_agent/        # 编码 Agent（对应 packages/coding-agent/）
├── pi_web_ui/              # Web UI（对应 packages/web-ui/）
├── pi_mom/                 # Slack 机器人（对应 packages/mom/）
├── pi_pods/                # Pod 管理（对应 packages/pods/）
└── tests/
    ├── unit/               # 单元测试（按包分子目录）
    ├── integration/        # 跨模块集成测试
    ├── e2e/                # 端到端测试
    └── comparison/         # TS vs Python 行为对比测试
```

TS 源码在 `packages/` 目录下，作为改写参考。改写时先读取对应的 TS 源文件理解接口和行为。

## 改写原则

### 接口对等
- 每个 TS 包的所有 public export 都必须有对应的 Python 实现
- 函数名：camelCase -> snake_case（如 `streamAnthropic` -> `stream_anthropic`）
- 类名：保持 PascalCase
- TS `type` / `interface` -> Pydantic `BaseModel` 或 `dataclass` 或 `TypedDict`
- TS `enum` -> Python `enum.Enum` 或 `StrEnum`
- TS `namespace` -> Python module
- 不要遗漏任何 public class、function、type、constant

### Python 最佳实践
- 异步代码使用 `asyncio` + `async`/`await`，不使用线程
- 流式处理使用 `async generator`（`async def stream() -> AsyncIterator[...]`）
- 错误处理使用异常，不使用返回错误码
- 类型标注使用 Python 3.12+ 语法（`list[str]` 而非 `List[str]`，`X | None` 而非 `Optional[X]`）
- 文件路径使用 `pathlib.Path`
- 日志使用 `logging` 模块
- 配置使用 `pydantic-settings` 或环境变量
- 字符串使用 f-string

### 不要做的事
- 不要逐行翻译 TS 代码，要写出 Pythonic 的实现
- 不要保留 TS 风格的回调/Promise 链，改用 async/await
- 不要用裸 dict 代替应该定义为类的结构化数据
- 不要把 TS 的 null/undefined 双值逻辑带入 Python（Python 只有 None）
- 不要添加 TS 中不存在的功能
- 不要省略 TS 中存在的 public API

## 每个模块必须产出

1. **实现代码** — 带完整类型标注，放在 `py/<包名>/` 下
2. **MAPPING.md** — 放在 `py/<包名>/MAPPING.md`，格式：
   ```markdown
   | TS 函数/类 | Python 等价物 | 状态 | 备注 |
   |-----------|-------------|------|------|
   | streamAnthropic() | stream_anthropic() | Done | 使用 anthropic SDK |
   ```
3. **单元测试** — 放在 `py/tests/unit/<包名>/`，覆盖率 >= 80%
4. **通过 mypy --strict**（在 `py/` 目录下运行）
5. **通过 ruff check && ruff format**（在 `py/` 目录下运行）

## 质量工具（全部在 py/ 目录下运行）

```bash
cd py/
uv sync                         # 安装依赖
ruff check .                    # lint
ruff format .                   # 格式化
mypy --strict .                 # 类型检查
pytest --cov --cov-fail-under=80  # 测试 + 覆盖率
python scripts/check_parity.py  # TS vs Python API 对等检查
```

## 技术栈

| 用途 | Python 库 |
|------|----------|
| 包管理 | uv workspace |
| 类型检查 | mypy (strict) |
| Lint + 格式化 | ruff |
| 测试 | pytest + pytest-asyncio + pytest-cov |
| 数据模型/验证 | pydantic |
| CLI | typer 或 click |
| HTTP 客户端 | httpx |
| OpenAI | openai |
| Anthropic | anthropic |
| Google AI | google-genai |
| AWS Bedrock | boto3 |
| Slack | slack-bolt |
| SSH | asyncssh 或 paramiko |
| 终端 UI | textual 或 prompt-toolkit |
| Git | gitpython 或 subprocess |

## scripts/ 说明

### extract_public_api.py
- **输入**：TS 源文件或目录路径
- **行为**：解析所有 `export` 的 function、class、type、interface、const
- **输出**：markdown 格式的 checklist，列出每个导出项的名称、类型、签名
- **用法**：`python scripts/extract_public_api.py ../../packages/ai/src/types.ts`
- **示例输出**：
  ```
  - [ ] type Message -> class/TypedDict
  - [ ] function createStream() -> async def create_stream()
  - [ ] const DEFAULT_MODEL -> DEFAULT_MODEL
  ```

### check_parity.py
- **输入**：TS 包路径 + 对应的 Python 包路径
- **行为**：对比 TS 导出列表 vs Python `__all__` / 公共 API
- **输出**：报告缺失的、多余的、名称不匹配的项
- **用法**：`python scripts/check_parity.py ../../packages/ai/src pi_ai`

## 工作流

1. 读取 GitHub Issue 中的任务范围和验收标准
2. 读取对应的 TS 源文件，理解接口和行为
3. 运行 `python scripts/extract_public_api.py` 生成 API 清单
4. 先定义 Python 接口（Protocol / ABC），再实现
5. 每个函数/类实现后立即写测试
6. 填写 MAPPING.md
7. 运行全部质量检查（ruff、mypy、pytest）
8. 提交并推送到当前分支
