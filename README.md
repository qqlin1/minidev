# MiniDev —— AI 应用开发岗学习项目（主投）

MiniDev 是一个面向 **2027 届 AI 应用开发 / 大模型应用开发** 的学习项目。

**主投岗位：AI 应用开发**（企业知识库 / 垂直 RAG / 智能客服类）。

**Agent 开发：次要线**——只保留共用底座与概念级 Loop，不作为简历主项目深挖。

项目不用“堆框架”代替能力证明；主交付是一条可验收的 AI 应用纵切，**语料以企业文档为主，不以代码仓库为主**：

1. **MiniDev Knowledge Base（第一纵切 / RAG 核心）**：面向本地知识库场景——企业制度、产品手册、FAQ、政策文档等。完成文档摄取、结构化切块、检索、引用、拒答与分层评测。
2. **MiniDev SupportOps（目标作品）**：复用 Knowledge Base 的摄取、检索和评测底座，加入实时业务工具、多租户权限、工单与人工交接，形成企业技术客服与内部知识支持系统。
3. **MiniDev Safe Coding Agent（次要 / 冻结深挖）**：已有 Tool Calling Loop 只作为共用底座与安全实验；完整改码闭环、Checkpoint、多 Agent 暂不加码。

**语料与策略边界（2026-09-13 决议）：**

- 主线语料是**文档**（Markdown / 约定结构的文本 / 后续 PDF），不是源代码。
- 切分策略跟语料结构走：文档用标题/段落切分；固定行数作基线与降级；**Python AST 仅在语料含代码时作为可选插件**，不作为项目主线叙事。
- 已有 `repo_qa/chunking/` 四层可插拔架构与代码 AST 实现保留为可复用底座与策略插件示例；后续主战场是文档切分策略与知识库评测。

共用底座（Python、模型客户端、结构化输出、评测、可观测）两线共享。训练、微调、复杂多 Agent 不属于当前 P0。

## 当前真实状态

| 能力 | 状态 | 证据 / 缺口 |
|---|---|---|
| DeepSeek / OpenAI 兼容 API 调用 | `IMPLEMENTED / NOT_LIVE_VERIFIED` | `apps/hello_api.py` 是独立流式 smoke，展示 Token 用量；2026-09-13 未消耗额度复测 |
| 单 Agent Tool Calling 循环 | `UNIT_TESTED / INTEGRATION_FAILED` | Runtime 分支有离线测试，但真实 `LLMClient.chat()` 返回 Message，Runtime 仍按完整 Response 访问 `.choices`；组合 smoke 必现 `AttributeError` |
| LLM 客户端重试封装 | `UNIT_TESTED / NOT_INTEGRATED` | 429、超时、断连和耗尽转换已有组件测试；还需统一 Client/Runtime 返回契约，并消除 SDK 与应用层重试叠乘 |
| 工作区沙箱与敏感文件保护 | `DEFERRED` | 对 AI 应用岗非 P0；当前读取工具仍无路径边界，不可对不可信任务开放 |
| RAG / 知识库切块底座 | `PARTIAL` | 可插拔四层（Schema/Strategy/Config/Pipeline）已就绪；现有评测偏代码场景（fixed-lines `4/8`、code-AST `7/8`），**文档语料评测尚未建立** |
| 文档切分策略（标题/段落） | `NOT_STARTED` | 知识库主线的对口策略；AST 仅作可选插件 |
| FastAPI / SSE、会话交付 | `NOT_STARTED` | 完整服务交付所需；本批样本中流式/异步/并发明确出现 4/15 |
| 文档摄取、索引更新、多租户与客服工作流 | `NOT_STARTED` | Knowledge Base → SupportOps 的真实项目主线 |
| MCP、Checkpoint、多 Agent / Safe Coding 闭环 | `DEFERRED` | 次要线冻结；仅由目标 JD 或同集评测结果触发 |

状态不等于“写过代码”：是否已实现、离线测试、接入主链路、真实模型验证、提交和可面试口述分别记录。

**当前方向（2026-09-13）：** 主线转向本地知识库 / 客服场景。优先补齐文档语料的切分策略与评测，而不是继续深化代码 AST。共用底座中的 Client/Runtime 跨组件契约缺陷仍记录在案，可并行修复，不阻塞文档 RAG 知识线。

## 学习地图

- [AI 应用开发岗与 Agent 开发岗学习路线](.codex/AI_APP_AGENT_LEARNING_ROADMAP_2026.md)：岗位边界、真实 JD / 面经证据、P0/P1/P2 知识点、场景追问和项目任务。
- [2026 校招岗位与真实开发场景调研](.codex/AI_APP_MARKET_AND_REAL_SCENARIOS_2026-09-13.md)：15 家公司便利样本、来源分级、真实 issue/论坛场景、SupportOps 终局和建议验收线。
- [项目学习进度](.codex/PROJECT_PROGRESS.md)：当前事实、分阶段任务、验收标准、学习者与 AI 的分工、唯一下一步。
- [Agent 项目分层调研](.codex/AGENT_ARCHITECTURE_RESEARCH.md)：OpenAI Agents SDK、LangGraph、Pydantic AI 的分层分析及 MiniDev 对照。
- [S0 Runtime 证据](.codex/S0_RUNTIME_EVIDENCE.md)：当前跨组件断点、目标 Tool Calling 图、重试责任和真实口述草稿。

## 文件职责速查

```text
apps/hello_api.py             Provider Smoke Test，只验证模型环境，不参与 Agent 编排
agent/runtime/v0.py           当前学习版 CLI + 单 Agent Loop + 临时工具组合根
agent/llm/client.py           模型适配与可靠性：配置、请求、流式、重试
agent/llm/errors.py           模型重试耗尽的应用级错误契约，不生成用户文案
agent/                        Agent 领域包边界，不初始化客户端
agent/runtime/                Agent Loop / 运行时子包
agent/llm/                    模型适配子包边界

repo_qa/chunking/models.py    ① Chunk Schema：可引用块契约（文档/代码通用）
repo_qa/chunking/strategies.py ② 可插拔策略：fixed-lines 基线；code_ast 代码插件；后续加文档标题/段落策略
repo_qa/chunking/config.py    ③ 策略配置
repo_qa/chunking/pipeline.py  ④ 策略路由 + Quality Gate
repo_qa/eval/                 Chunk 区间覆盖对照（当前偏代码场景）；不等于完整 RAG Eval
repo_qa/                      Knowledge Base 纵切包（历史包名）；后续 indexing/retrieval/eval 同级生长

tests/agent/                  Agent 纵切测试（镜像 agent/）
tests/repo_qa/                Knowledge Base / 切块测试（镜像 repo_qa/）

prompt-log.md                 Prompt 版本和实验记录
badcases.md                   失败证据、根因、修复和回归记录
.codex/STRUCTURE.md           目录改造的前后对照
.codex/                       学习路线、架构调研和项目进度，不是运行时代码
```

组织方式：**package-by-feature**（一个能力一个包）。顶层是产品纵切（`agent/`、`repo_qa/`）和入口层（`apps/`）；Schema/Config/策略是包内文件，不是全局 `models/`、`config/` 目录。当前 `agent/runtime/v0.py` 为了学习完整调用流暂时合并多个职责；后续只有在真实场景和测试需要时再拆成 `tools/`、`state/` 等。

执行顺序固定为：

```text
真实场景
  -> 必要知识
  -> 方案比较
  -> 核心实现
  -> 失败实验
  -> 指标与 Trace
  -> 面试口述
```

## 当前依赖

- Python 3.13
- uv
- `openai>=3.7.0`
- `python-dotenv>=1.2.3`
- OpenAI 兼容 API（当前配置为 DeepSeek）

`pydantic`、RAG 框架、向量数据库、MCP、Langfuse 等只有在对应阶段真正实现并验收后，才会进入当前技术栈。

## 快速开始

```powershell
uv sync
Copy-Item .env.example .env
# 在 .env 中填写 LLM_API_KEY 后再执行；会访问真实模型并可能产生费用
uv run -m apps.hello_api
# Agent 交互 CLI（同样需要 API Key；当前有已知 Client/Runtime 契约缺陷，修复前不作为验收入口）
uv run -m agent.runtime.v0
```

当前离线测试：

```powershell
uv run pytest -q
```

该命令自动发现 `tests/` 下所有 `test_*.py` 中的 `test_*` 函数；测试使用 Fake Client，
不需要 API Key、不访问真实模型，也不会因 Windows GBK 控制台输出而产生假失败。

2026-09-13 的当前结果是 `27 passed`。单元测试通过不等于组件已经集成；当前 Client/Runtime 契约缺陷需要新增跨组件测试后才可关闭。

## 安全提示

当前 `agent/runtime/v0.py` 还没有工作区边界、敏感路径拒绝、写操作审批或命令沙箱。不要让它处理不可信提示词，也不要把本机目录、密钥或真实业务数据暴露给模型。安全边界完成前只做受控、本地、只读实验。
