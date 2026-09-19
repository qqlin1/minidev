# MiniDev SupportOps

> **一个能对话的企业技术客服 Agent。**
> 用户提问 → 意图与风险路由 → 静态知识查文档、实时状态查工单、高风险动作走人工确认 →
> 回答带引用，证据不足就拒答，用户要求就转人工。

面向 **2027 届校招 · AI 应用开发 / 大模型应用开发**方向的可投递作品。

本文是项目的唯一入口：**作品定义 → 可投递版本 → 当前状态 → 怎么跑**。
学习过程记录在 `.codex/`，不放在这里抢主线。

---

## 1. 这个作品是什么

市面上「上传 PDF → 向量化 → 调模型回答」只到演示级。真实客服场景里，一个问题可能有四种归属，
把它们混进一个向量库就会答错：

| 用户问什么 | 权威数据源 | 系统必须做什么 |
|---|---|---|
| 「错误码 `MODEL_RETRY_EXHAUSTED` 是什么意思？」 | 技术文档 RAG | 检索并引用；证据不足时拒答 |
| 「我的工单处理到哪了？」 | 实时工单 API | 校验身份后查询，**不能从向量库猜** |
| 「按文档看这个故障符合退款条件吗？」 | 政策 RAG + 实时状态 + 规则代码 | 收集证据，资格由确定性规则判断 |
| 「直接替我执行退款」 | 有副作用的业务工具 | 展示真实参数，经权限与人工确认后执行 |
| 「资料里没写」 | 无可靠来源 | 澄清、拒答或转人工 |
| 「我要人工客服」 | 工单与会话系统 | 建立交接记录，**之后机器人零回复** |

**三条能讲的线**（面试追问基本都落在这三条上）：

1. **RAG 链路** —— 摄取、版本、结构切块、检索、引用、更新与删除。
2. **Agent 编排** —— 意图与风险路由、工具调用、会话状态机、步数与预算终态。
3. **生产边界** —— 拒答与证据门、人工交接、幂等、分层评测与成本延迟。

---

## 2. 可投递版本 v1（2 周）

**时间点：2026-09-17 决议。目标是在 14 天内拿出一个能完整演示、能对着面试官讲 30 分钟、每个数字都有分母的版本。** 前提是每天高强度投入。

范围是刻意砍过的：**先做一条完整闭环，再谈深度**。砍掉的东西在 2.3 明确列出，不是遗忘。

### 2.1 第 1 周：让「问文档」跑通

| 天 | 做什么 | 当天产出 |
|---|---|---|
| 1 | 修 Client/Runtime 跨组件契约（半天）+ 摄取骨架 | 真实 Client 驱动 Runtime 的离线回归转绿 |
| 2 | `markdown_heading` 结构切块 + 接上已有质量过滤 | 一份 Markdown 切出干净块，citation 指向真实行号 |
| 3 | 建索引与幂等导入 | 一条命令把 `docs/` 索引进库；重复导入两次块数不变 |
| 4 | BM25 检索 + 固定评测集 | ≥ 40 条带源位置的检索题；Recall@5 / MRR@10 有分母 |
| 5 | Dense 向量检索（走 API embedding） | 同一题集上的向量基线数字 |
| 6 | 混合检索 + 同集对照 | BM25 / Dense / Hybrid 三条链的对照表 |
| 7 | 带引用的回答生成 | 回答带 `path:start-end`，能落回原文行号 |

### 2.2 第 2 周：让「客服」跑通

| 天 | 做什么 | 当天产出 |
|---|---|---|
| 8 | 意图与风险路由 | 静态知识 / 实时事实 / 高风险动作三条责任链 |
| 9 | 实时工具：查工单状态（本地 mock 数据） | 实时问题必须走工具，不走向量库 |
| 10 | 证据门与拒答 | 证据不足时安全拒答，不许编 |
| 11 | 人工交接状态机 | 转人工后机器人零回复，有测试钉住 |
| 12 | FastAPI + SSE 流式端点 | 一条 curl 命令能演示完整对话 |
| 13 | 评测报告与 Bad Case | 一份带分母、版本、失败记录的报告 |
| 14 | README 作品化 + 口述练习 | 架构图、指标表、90 秒主干回答 |

### 2.3 这一版有意不做

多租户 ACL、PDF/OCR/表格解析、Rerank、删除传播、Prompt Injection 负例、幂等键、Docker/K8s、Langfuse、多 Agent。
这些在 `.codex/AI_APP_AGENT_LEARNING_ROADMAP_2026.md` 的 S6—S8 里，顺延到 v1.5 / v2，**由目标 JD 或评测结果触发，不提前做**。

### 2.4 如果时间不够，按这个顺序砍

1. 先砍第 6 天的混合检索——保留 BM25 和 Dense 两条独立结果，不做融合。
2. 再砍第 12 天的 SSE——改成同步 JSON 响应，演示差一点但功能完整。
3. **第 11 天的人工交接不能砍。** 那是这个作品区别于「又一个 RAG 玩具」的地方。
4. **第 13 天的评测报告也不能砍。** 没有分母，前面 12 天做的东西在面试里全是形容词。

---

## 3. 当前真实状态

### 3.1 按两周排期看

| 阶段 | 状态 | 事实 |
|---|---|---|
| 第 1 周 · 知识底座与检索 | **进行中** | 摄取 + 准入 + 结构切块 + 质量过滤 + 标题路径 + 幂等导入已完成，**`212 passed`**；**BM25、向量、引用回答未开始** |
| 第 2 周 · 客服编排与交付 | **未开始** | 无路由、无实时工具、无证据门、无人工交接、无服务化、无评测报告 |

Day 1—3 是唯一「进行中」的区间，Day 4 之后每一格都还是空的。

### 3.2 按技术能力看（明细）

| 能力 | 状态 | 证据 / 缺口 |
|---|---|---|
| DeepSeek / OpenAI 兼容 API 调用 | `IMPLEMENTED / NOT_LIVE_VERIFIED` | `apps/hello_api.py` 是独立流式 smoke，展示 Token 用量；2026-09-13 未消耗额度复测 |
| 单 Agent Tool Calling 循环 | `UNIT_TESTED / INTEGRATED` | Runtime 分支有离线测试；真实 `LLMClient` + 真实 `run_turn` 的跨组件契约测试已常驻（`tests/agent/test_client_runtime_contract.py`），直接回答与 Tool Round Trip 均可离线走通 |
| LLM 客户端重试封装 | `UNIT_TESTED / INTEGRATED` | 429、超时、断连和耗尽转换已有组件测试；重试责任已收敛到应用层——`client.py` 显式关闭 SDK 内部重试（`max_retries=0`），消除 SDK×应用层叠乘（原最坏 9 次真实请求） |
| RAG / 知识库切块底座 | `PARTIAL` | 可插拔四层已就绪；现有评测偏代码场景（fixed-lines `4/8`、code-AST `7/8`），**文档语料评测尚未建立** |
| Chunk 质量过滤（入库前） | `TESTED / INTEGRATED` | 四条规则（无文字 / 页码页脚 / 过短 / 重复）+ 丢弃报告；已接进摄取链路；已知边界：空壳块是否存活取决于字符数，正解是 `heading_path`（已实现） |
| 文档切分策略（标题/段落） | `TESTED` | `markdown_heading` 已实现并注册；11 条场景上 `fixed_lines 5/11` vs `markdown_heading 8/11`，文档族 `2/5 -> 5/5` |
| 标题路径（breadcrumb） | `TESTED` | `Chunk.heading_path` + 祖先栈算法；空壳块被过滤后结构信息不丢，有回归测试 |
| 文档摄取 + 准入 | `TESTED` | 扫描 + 密钥/空文件/超大拦截 + UTF-8 读取 + 换行规范化 + 内容指纹 |
| 幂等导入（账本比对） | `TESTED / NOT_INTEGRATED` | **文档状态机**（PROCESSING/READY/FAILED）+ 七种动作 + 僵尸接管 + 失败重试 + 删除安全阀 + JSON 账本原子写；**未接向量库** |
| 真实 embedding、BM25、检索 | `NOT_STARTED` | 模块 2、3 的核心缺口 |
| 检索（BM25 / Dense / Hybrid）、引用与拒答 | `NOT_STARTED` | 模块 2、3 的核心缺口 |
| 实时工具、路由、人工交接 | `NOT_STARTED` | 模块 3 的核心缺口 |
| FastAPI / SSE、评测报告 | `NOT_STARTED` | 模块 4 的核心缺口 |
| 工作区沙箱与敏感文件保护 | `DEFERRED` | 对 AI 应用岗非 P0；当前读取工具仍无路径边界，不可对不可信任务开放 |
| MCP、Checkpoint、多 Agent | `DEFERRED` | 仅由目标 JD 或评测结果触发 |

状态不等于「写过代码」：是否已实现、离线测试、接入主链路、真实模型验证、提交和可面试口述分别记录。

---

## 4. 快速开始

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

2026-09-17 的当前结果是 `49 passed`。单元测试通过不等于组件已经集成；当前 Client/Runtime 契约缺陷需要新增跨组件测试后才可关闭。

---

## 5. 技术栈与依赖

- Python 3.13
- uv
- `openai>=3.7.0`
- `python-dotenv>=1.2.3`
- OpenAI 兼容 API（当前配置为 DeepSeek）

`pydantic`、RAG 框架、向量数据库、MCP、Langfuse 等只有在对应阶段真正实现并验收后，才会进入当前技术栈。
**不为简历关键字提前引入依赖**——引入即意味着要能解释它的取舍。

---

## 6. 语料与策略边界（2026-09-13 决议）

- 主线语料是**文档**（Markdown / 约定结构的文本 / 后续 PDF），不是源代码。
- 切分策略跟语料结构走：文档用标题/段落切分；固定行数作基线与降级；**Python AST 仅在语料含代码时作为可选插件**。
- 已有 `repo_qa/chunking/` 四层可插拔架构与代码 AST 实现保留为可复用底座与策略插件示例。

---

## 7. 文件职责速查

```text
apps/hello_api.py             Provider Smoke Test，只验证模型环境，不参与 Agent 编排
agent/runtime/v0.py           当前学习版 CLI + 单 Agent Loop + 临时工具组合根
agent/llm/client.py           模型适配与可靠性：配置、请求、流式、重试
agent/llm/errors.py           模型重试耗尽的应用级错误契约，不生成用户文案
agent/                        Agent 领域包边界，不初始化客户端
agent/runtime/                Agent Loop / 运行时子包
agent/llm/                    模型适配子包边界

repo_qa/chunking/models.py    ① Chunk Schema：可引用块契约（文档/代码通用）
repo_qa/chunking/strategies.py ② 可插拔策略：fixed-lines 基线；code_ast 代码插件；markdown_heading 文档策略
repo_qa/chunking/config.py    ③ 策略配置 + 过滤配置（开关、最小字符数、是否去重）
repo_qa/chunking/filters.py   ④ 质量过滤：四条规则 + 丢弃报告
repo_qa/chunking/pipeline.py  ④ 策略路由 + 过滤编排
repo_qa/eval/                 Chunk 区间覆盖对照（当前偏代码场景）；不等于完整 RAG Eval
repo_qa/                      SupportOps 的知识底座包（历史包名）；后续 indexing/retrieval/qa 同级生长

tests/agent/                  Agent 纵切测试（镜像 agent/）
tests/repo_qa/                知识底座测试（镜像 repo_qa/）

prompt-log.md                 Prompt 版本和实验记录
badcases.md                   失败证据、根因、修复和回归记录
.codex/STRUCTURE.md           目录改造的前后对照
.codex/                       学习路线、架构调研和项目进度，不是运行时代码
```

组织方式：**package-by-feature**（一个能力一个包）。顶层是产品纵切（`agent/`、`repo_qa/`）和入口层（`apps/`）；Schema/Config/策略是包内文件，不是全局 `models/`、`config/` 目录。当前 `agent/runtime/v0.py` 为了学习完整调用流暂时合并多个职责；后续只有在真实场景和测试需要时再拆成 `tools/`、`state/` 等。

---

## 8. 学习地图（过程文档）

作品定义在上面。下面这些是**怎么学**的记录，遇到具体问题再翻：

- [AI 应用开发岗与 Agent 开发岗学习路线](.codex/AI_APP_AGENT_LEARNING_ROADMAP_2026.md)：岗位边界、真实 JD / 面经证据、P0/P1/P2 知识点、场景追问和阶段任务 S0—S8。
- [2026 校招岗位与真实开发场景调研](.codex/AI_APP_MARKET_AND_REAL_SCENARIOS_2026-09-13.md)：15 家公司便利样本、来源分级、12 个真实故障场景、建议验收线。
- [项目学习进度](.codex/PROJECT_PROGRESS.md)：当前事实、分阶段任务、验收标准、学习者与 AI 的分工、当前唯一任务。
- [Agent 项目分层调研](.codex/AGENT_ARCHITECTURE_RESEARCH.md)：OpenAI Agents SDK、LangGraph、Pydantic AI 的分层分析及 MiniDev 对照。
- [S0 Runtime 证据](.codex/S0_RUNTIME_EVIDENCE.md)：跨组件断点、目标 Tool Calling 图、重试责任和口述草稿。

每个学习单元的固定执行顺序：

```text
真实场景
  -> 必要知识
  -> 方案比较
  -> 核心实现
  -> 失败实验
  -> 指标与 Trace
  -> 面试口述
```

**每个单元都要能回答：它长成上面四个模块中的哪一块。** 答不上来的，就是范围跑偏了。

---

## 9. 安全提示

当前 `agent/runtime/v0.py` 还没有工作区边界、敏感路径拒绝、写操作审批或命令沙箱。不要让它处理不可信提示词，也不要把本机目录、密钥或真实业务数据暴露给模型。安全边界完成前只做受控、本地、只读实验。
