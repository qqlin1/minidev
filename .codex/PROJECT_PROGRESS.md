# MiniDev SupportOps 项目进度

> 最后更新：2026-09-17（目标收敛：2 周做出可投递版本 v1）
>
> **作品**：MiniDev SupportOps —— 一个能对话的企业技术客服 Agent。完整定义见 `README.md` 第 1—2 节。
> **投递目标**：2027 届 AI 应用开发 / 大模型应用开发校招；尚未投递，**2 周内需要拿出手**，每天高强度投入。
> 岗位与真实场景证据见 `AI_APP_MARKET_AND_REAL_SCENARIOS_2026-09-13.md`；完整知识边界见 `AI_APP_AGENT_LEARNING_ROADMAP_2026.md`。

## 0. v1 收敛决议（2026-09-17）

原 S0—S8 完整阶段合计 42—63 个学习日，**远超投递窗口**。学习者决议：每天高强度学习，**2 周内拿出可投递版本**。

因此把 S0—S5 压缩进 14 天，S6—S8 顺延：

| 阶段 | 收敛自 | 14 天内必须做完 |
|---|---|---|
| 第 1 周 · 知识底座与检索 | S1 + S2 + S3 精简 | 摄取、结构切块、质量过滤、幂等导入、BM25、Dense、混合检索、带引用回答 |
| 第 2 周 · 客服编排与交付 | S4 + S5 + S7 精简 | 意图与风险路由、实时工具、证据门与拒答、人工交接、FastAPI + SSE、评测报告 |

**明确顺延到 v1.5 / v2**：多租户 ACL（S6）、PDF/OCR/表格、Rerank、删除传播、Prompt Injection 负例、
幂等键、Docker、Langfuse、多 Agent。顺延不是遗忘——触发条件是「目标 JD 明写」或「评测结果证明需要」。

逐日排期与砍单顺序见 `README.md` 第 2 节。

## 0.1 优先级决议（2026-09-10，2026-09-13 复核并调整语料方向）

| 线 | 占比 | 状态 | 说明 |
|---|---|---|---|
| **AI 应用纵切：Knowledge Base → SupportOps** | **~70%** | 主线 | **文档**生命周期 → 切块 → 检索 → 引用/拒答 → 实时工具 → 人工交接 → 服务化 |
| 共用底座（Client/重试/结构化/Eval 方法） | ~20% | 存在 P0 契约故障 | Client/Runtime 跨组件假绿可并行修复；不阻塞文档 RAG 知识线 |
| Agent 纵切：Safe Coding Agent | **~10% 或冻结** | **次要 / 暂停深挖** | 保留 `runtime/v0` + 重试契约证据；沙箱、Checkpoint、多 Agent **DEFERRED** |

**2026-09-13 语料方向决议（学习者确认）：**

1. 热点场景是**本地知识库 RAG / 企业客服**，不是「代码仓库问答」。
2. 主线语料是文档（Markdown、制度、手册、FAQ；后续 PDF），**不以源代码为项目叙事中心**。
3. 切分策略跟语料结构走：文档用标题/段落策略；固定行数作基线与降级；**Python AST 仅作语料含代码时的可选插件**。
4. 已有 `repo_qa/chunking/` 可插拔架构与 code_ast 实现保留为底座与插件示例，不删除；后续学习优先级让位于文档切分与文档评测。
5. 包名 `repo_qa` 暂不重命名（避免无收益重构）；文档与口述中统一称为 Knowledge Base 纵切。

2026-09-13 的关键词筛选便利样本覆盖 15 家公司：软件/系统工程 `15/15`、RAG/知识库 `14/15`、项目证据 `14/15`、具名框架 `12/15`、Python `12/15`、Tool/FC/MCP `10/15`、Eval/可观测 `10/15`。这些只是本批样本内部计数，不是市场比例；投递状态和完整链接见调研文档。

## 1. 项目职责

MiniDev 用一个共享工程底座证明岗位能力；**主交付只有一条，分两步纵切，语料以企业文档为主**：

- **第一纵切：MiniDev Knowledge Base（RAG 核心）**

  面向本地知识库：企业制度、产品手册、FAQ、政策文档等。完成版本化摄取、结构化切块（标题/段落优先）、检索、引用、拒答和分层评测；它是最终项目的知识底座，不是独立终局。代码 AST 只作为可选策略插件保留。

- **最终作品：MiniDev SupportOps（主线）**

  面向企业开发者平台的多租户技术客服与内部知识支持系统。静态文档/政策走 RAG；实时工单和服务状态走业务 API；高风险动作走确定性规则、权限和人工确认；证据不足时澄清、拒答或转人工。

- **Agent 纵切：MiniDev Safe Coding Agent（次要 / 冻结深挖）**

  已有：单 Agent Loop、Tool 回填、模型重试终态的组件级实现和测试。
  当前缺陷：真实 `LLMClient` 返回 message，Runtime 却按 response 再访问 `.choices`，因此尚未跨组件集成。

  **有意不做**：完整改码闭环、工作区沙箱、Checkpoint、多 Agent——在 AI 应用岗形成可投简历证据前，不占用主线时间。

MiniDev 负责 Python/LLM/RAG 工程学习；Java 后端主线留在独立 Java 项目。两边共享的数据库、缓存、MQ、鉴权、并发和部署知识可以复用，但不在两个仓库重复造相同业务模块。

## 2. 完成状态定义

| 状态 | 含义 |
|---|---|
| `NOT_STARTED` | 尚未开始；README 或文档提到不算实现 |
| `LEARNING` | 正在学习、设计或手写 |
| `IMPLEMENTED` | 有代码，但不代表测试、集成或线上验证通过 |
| `TESTED` | 离线自动化测试通过，命令与结果已记录 |
| `INTEGRATED` | 已接入 MiniDev 主调用链，不是孤立 Demo |
| `INTEGRATION_FAILED` | 真实组件组合可复现失败；单元测试通过也不能算集成 |
| `LIVE_VERIFIED` | 在注明 provider/model/date 的真实模型 smoke 中通过 |
| `EVIDENCED` | 有固定评测集、失败实验、Trace/报告和可复现结果 |
| `INTERVIEW_READY` | 能脱稿讲清流程、取舍、失败、指标，并接两层追问 |
| `DEFERRED` | 当前有意暂缓，不是遗忘 |

一项能力可以同时处于不同证据层。例如“重试代码已测试但未接入主 Loop”不能写成“Agent 已具备稳定重试”。

## 3. 当前仓库事实基线

### 3.1 Git 与工作区

- 分支：`main`，比 `origin/main` **领先 1 个提交**。
- HEAD：`7159378 feat: establish agent and repository QA foundations`。
- 当前共有 3 个提交。
- 学习者现有未提交工作必须保留：

```text
M  README.md
M  prompt-log.md
?? .codex/
?? .idea/
```

后续任务只能在这些改动上增量收口，不得用重建目录、覆盖文件或 Git 回退“整理”工作区。

### 3.2 已实现到哪里

| 能力 | 当前状态 | 事实 |
|---|---|---|
| API 连通脚本 | `IMPLEMENTED` / `NOT_LIVE_VERIFIED` | `apps/hello_api.py` 当前只保留流式 smoke 与 Token Usage；本轮未调用真实模型 |
| Agent Loop | `TESTED`（组件）/ `INTEGRATED` | `agent/runtime/v0.py` 的 `msg = resp` 契约已与真实 `LLMClient` 对齐；`tests/agent/test_client_runtime_contract.py` 用真实 Client + 真实 Runtime 离线跑通直接回答与 Tool Round Trip |
| Tool 错误回填 | `TESTED`（组件） | 非法 JSON、未知工具和工具异常会回填对应 `tool_call_id`；尚无统一结构化 ToolError 模型 |
| LLM Client | `TESTED`（组件）/ `INTEGRATED` | 实现应用层 429/超时/断连重试和 stream；`chat()` 返回 message；**SDK 内部重试已显式关闭（`max_retries=0`）**，应用层是唯一重试责任人，`max_retries` 即真实总尝试次数 |
| 离线测试入口 | `TESTED`（组件 + 跨组件） | `uv run pytest -q` 自动发现并通过 **55 项**；新增跨边界契约测试后，Client/Runtime 组合已纳入回归，同类假绿不再依赖人工探针 |
| Prompt 实验日志 | `LEARNING` | `prompt-log.md` 有模板，但第一条“结果对比/结论”仍为空 |
| Bad Case | `TESTED` | `badcases.md` 有 2 个已修复案例；跨组件假绿案例 2026-09-17 由 `DISCOVERED / UNFIXED` 关闭为 `FIXED`，回归测试常驻 |
| 工作区沙箱 | `NOT_STARTED` | 工具可读取任意路径及 `.env`；当前最大安全缺口 |
| RAG / Knowledge Base 切块底座 | `PARTIAL` | `repo_qa/chunking/` 可插拔四层已就绪；现有 eval 偏代码场景：固定行 `4/8`、AST `7/8`；**文档语料切分与评测未建** |
| Chunk 质量过滤（入库前） | `TESTED`（组件）/ `NOT_INTEGRATED` | `filters.py` 四条规则（无文字 / 页码页脚 / 过短 / 重复）+ 丢弃报告；过滤开与关在 8 条场景上命中数完全一致；**未接真实摄取链路，无真实文档语料** |
| 文档切分策略（标题/段落） | `LEARNING` | `markdown_heading` 任务包已下发（8 道题，代码由学习者实现）；对应 v1 第 1 周 Day 2 |
| 文档摄取（扫描 / doc_id / 统计） | `NOT_STARTED` | v1 第 1 周 Day 2—3 任务 B；尚无 `docs/` 语料与 `repo_qa/ingest/` |
| SupportOps | `NOT_STARTED` | 业务边界和路线已定义；尚无路由、实时 Tool、多租户、人工交接或服务 API |
| MCP / Checkpoint / Trace 平台 | `NOT_STARTED` | 尚未实现 |
| 多 Agent | `DEFERRED` | 当前只有单 Agent；消融实验前不实施 |

### 3.3 本次验证

```text
uv run pytest -q
结果：55 passed，exit 0（2026-09-17 收盘）
      其中 6 项是新增的 tests/agent/test_client_runtime_contract.py 跨组件契约测试；
      原 49 项零退化。这是组件级 + 跨边界双绿灯。

uv run python -m compileall -q agent apps repo_qa tests
结果：exit 0

uv lock --check
结果：exit 0

git diff --check
结果：exit 0；仅有 Git 的 LF/CRLF 转换提示

跨组件契约 smoke（现已转为常驻测试，不再是人工脚本）
结果：真实 LLMClient + 假 SDK + 真实 run_turn 直接回答走通
     AgentRunResult(stop_reason=FINAL_ANSWER, agent_steps=1, final_output='你好，我是模型')
修复前：AttributeError: 'ChatCompletionMessage' object has no attribute 'choices'
       位置：agent/runtime/v0.py:140

OpenAI SDK 默认重试探测
结果：OpenAI().max_retries == 2（共 3 次尝试）；应用层 max_retries=3
     → 未干预时最坏 9 次真实请求；已在 client.py 显式传 max_retries=0
```

结论：跨组件契约已由常驻回归测试持有（`tests/agent/test_client_runtime_contract.py`），
Client/Runtime 组合可标 `INTEGRATED`；但这仍不是真实模型调用，不能写 `LIVE_VERIFIED`。
重试责任已收敛到应用层单一来源，最坏尝试次数等于 `LLMClient.max_retries`，不再与 SDK 相乘。

## 4. 学习执行规则

1. 每个单元先完整讲授：**知识全貌 → 项目作用 → 数据/调用流 → 方案比较 → 代码任务 → 失败实验 → 验收 → 面试追问**。
2. 不按 LangChain、LangGraph、MCP、Langfuse 的 API 目录推进；框架只能服务于已定义的场景和指标。
3. 每个知识点至少绑定代码/配置、正反测试、Trace/报告和口述中的三类证据。
4. 固定评测从第一阶段开始，不等项目完成；新增策略先与基线比较。
5. AI 可以生成样板，但安全、数据、状态、重试、幂等和评测标准必须由学习者决策。
6. 不读取框架源码来替代项目主线；除非真实故障必须定位到框架内部。
7. 不编造 QPS、准确率、节省比例或用户量；所有数字有分母、配置、日期和原始报告。
8. 每投一个岗位重新读 JD；P2 技能若被简历或 JD 明写，临时升级为该岗位 P0。
9. Python/后端基础和算法每天单独保留时间；Agent 项目不能成为逃避基础的理由。
10. 源码默认由学习者手打；本文只安排任务和给出验收，除非学习者明确要求助手代改代码。

## 5. 学习者与 AI 的分工

| 标记 | 含义 |
|---|---|
| `G` | AI 可生成初稿；学习者审查、运行并对结果负责 |
| `D` | 学习者必须亲自作出设计决定并实现关键路径；AI 可讲解和评审 |
| `R` | 不要求源码级手写，但必须能画流程并解释机制、取舍和失败边界 |

| 内容 | 分工 |
|---|---|
| FastAPI 路由、DTO、CLI、Dockerfile、测试 fixture 骨架 | `G + R` |
| SDK 适配和序列化样板 | `G + R` |
| Provider 能力表、错误分类、重试/取消/重放边界 | `D + R` |
| Prompt 初稿和非金标测试问题扩充 | `G` |
| Chunk、Embedding、Hybrid、Rerank 选择 | `D + R` |
| 评测集目标、金标、分母和判分规则 | `D` |
| Agent 状态机、终止语义、Checkpoint/Resume | `D + R` |
| Tool Schema、权限、路径沙箱、审批和幂等 | `D + R` |
| MCP/框架接入样板 | `G + R` |
| 是否采用多 Agent | `D`，必须由消融数据决定 |

## 6. 双岗位知识进度

### 6.1 共用底座

| 知识 | 优先级 | 当前状态 | 升级到完成所需证据 |
|---|---|---|---|
| Python 包、类型、依赖注入、异常、测试 | P0 | `LEARNING` | 主组件可注入；无 Key/网络也能跑离线测试 |
| HTTP/REST、SSE、asyncio、取消 | P0 | `NOT_STARTED` | FastAPI 流式接口、断连和取消测试 |
| LLM 应用原理、messages/token/context/model 参数 | P0 | `LEARNING` | 能比较 RAG/微调/长上下文；画普通调用与 Tool 回填；契约测试 |
| Structured Output / JSON Schema | P0 | `NOT_STARTED` | 坏 JSON、缺字段、错类型、业务非法值测试 |
| Provider 能力与模型选型 | P0 | `NOT_STARTED` | 能力表、离线契约和带日期 live smoke |
| timeout/retry/backoff/rate limit/circuit breaker | P0 | `LEARNING` | Client 接入主链；副作用重放边界明确 |
| Prompt 与 Context Engineering | P0 | `LEARNING` | 版本、回归、压缩/裁剪对照实验 |
| RAG 基础与分段评测 | P0 | `PARTIAL` | 当前只有 Chunk 区间命中；下一步同集比较关键词/向量/混检并分离检索与生成归因 |
| Tool/FC、MCP、Skill、Harness、Workflow/Agent 边界 | P0 概念 | `LEARNING` | 不依赖框架名，能画完整组件与消息流 |
| Eval、Bad Case、Trace、成本/延迟 | P0 | `PARTIAL` | 有 Chunk 小样本和 Bad Case；仍需检索/生成分层数据集、Trace 与成本报告 |
| Prompt Injection、隐私、最小权限 | P0 | `NOT_STARTED` | 安全负例零越权 |
| 数据库/Redis/MQ/并发/Linux/Docker | P0/P1 | `NOT_STARTED` | 只在真实用例中引入并有故障实验 |
| 算法与数据结构 | P0 | `ONGOING_OUTSIDE_REPO` | 持续手写；不由 MiniDev 里程碑替代 |

### 6.2 AI 应用开发纵切（主线）

> **时间主战场。** 完成定义：能对着面试官讲完整链路，并有分母指标。

| 知识 | 优先级 | 当前状态 | 完成证据 |
|---|---|---|---|
| 业务问题与 LLM/RAG/API/Workflow 选择 | P0 | `LEARNING` | SupportOps 的静态知识、实时事实和高风险动作路由题集 |
| 数据摄取、元数据、版本与删除 | P0 | `NOT_STARTED` | Markdown/文档 幂等导入、增量更新和删除传播测试 |
| 文本/PDF/OCR/表格解析与 Chunk | P0 | `PARTIAL` | 可插拔切块架构已就绪；现有小样本偏代码（固定行 vs AST）。**主线需文档 fixture**：标题/段落切分对照 + 真实文档解析指标；AST 仅作含代码语料的可选插件 |
| Embedding / BM25 / Hybrid / Rerank | P0 | `NOT_STARTED` | Recall@k/MRR、延迟和成本基线 |
| Grounding、引用、No-answer | P0 | `NOT_STARTED` | 引用与拒答单独评分 |
| RAG Eval 与数据泄漏 | P0 | `PARTIAL` | 至少 30 可答 + 20 无答案/歧义 held-out 集，分层指标 |
| 业务 Tool、规则与人工交接 | P0 | `NOT_STARTED` | 实时事实只走 API；高风险动作确认；接管后 Bot 零回复 |
| 多租户/ACL/Prompt Injection/幂等 | P0 | `NOT_STARTED` | 跨租户零泄漏；恶意文档不触发写工具；重放不重复副作用 |
| FastAPI/SSE、会话、鉴权/配额 | P0 | `NOT_STARTED` | API 自动化、断连、越权、并发和恢复测试 |
| Prompt/模型版本、路由、缓存、灰度 | P1 | `NOT_STARTED` | 版本对比、回滚和成本报告 |
| 多模态与高级 RAG | P2 | `DEFERRED` | 目标 JD 或 Bad Case 明确需要 |

### 6.3 Agent 开发纵切（次要线 / 冻结深挖）

> 2026-09-10：主投 AI 应用后，本表仅作“顺投面试时能讲”的检查清单。
>
> **在 SupportOps 达到可投递前，不启动 Safe Coding Agent 深挖。** 当前 Loop 与 Client 只有组件级证据，跨组件集成尚未通过。

| 知识 | 优先级 | 当前状态 | 完成证据 |
|---|---|---|---|
| Chatbot / Workflow / Agent 边界 | P0 概念 | `LEARNING` | 能口头区分即可，不写第二套系统 |
| Agent Loop / 显式状态机 / Stop Reason | P0 概念 | `TESTED`（组件）/ `INTEGRATED` | 真实 Client + Runtime 契约回归已常驻（6 项），见 `tests/agent/test_client_runtime_contract.py` |
| Tool Registry、Schema、执行器和错误 | P0 概念 | `TESTED`（v0） | 参数/权限/超时/异常负例（基础已有） |
| 工作区沙箱、密钥保护、HITL | P0（仅 Agent 岗深挖） | `DEFERRED` | 路径逃逸与未批准副作用全部被拒绝 |
| 时间/步数/Token/费用预算 | P0/P1 | `LEARNING`（仅 MAX_STEPS） | 任一预算耗尽有确定终态 |
| Context、State、Checkpoint、Memory | P0/P1 | `DEFERRED` | 长上下文和中断恢复测试 |
| 幂等、重试、补偿、并发工具 | P0/P1 | `DEFERRED` | 故障恢复不重复副作用 |
| Agent 结果/轨迹/安全 Eval | P0 | `DEFERRED` | 10—20 个 fixture repo 任务 |
| MCP client/server | P0 概念 / P1 实现 | `DEFERRED` | 一个真实只读用例和协议/安全测试 |
| 多 Agent / A2A | P2 | `DEFERRED` | 相同任务和预算下优于单 Agent |

## 7. 阶段看板

| 阶段 | 目标 | 状态 | v1 归属 | 关键验收 |
|---|---|---|---|---|
| **S0** | **修复 Client/Runtime 契约假绿** | `INTEGRATED` | **第 1 周 Day 1 ✅ 已完成** | 真实组件组合离线回归 ✅；重试总次数符合预算 ✅ |
| S1 | 文档生命周期与 BM25 基线 | `NOT_STARTED` | **第 1 周 Day 3—4** | 幂等导入、增量更新、删除传播、Recall/MRR |
| S2 | 真实解析与结构切块 | `PARTIAL` | **第 1 周 Day 2**（仅 Markdown） | Markdown 结构切块 fixture；PDF/OCR 顺延 |
| S3 | Dense/Hybrid/Rerank | `NOT_STARTED` | **第 1 周 Day 5—6**（Rerank 顺延） | 同集消融；质量、延迟和成本有分母 |
| S4 | 引用、证据门与拒答 | `NOT_STARTED` | **第 1 周 Day 7 + 第 2 周 Day 10** | 可答/无答案/歧义分开评分 |
| S5 | SupportOps 路由、Tool 与人工交接 | `NOT_STARTED` | **第 2 周 Day 8—11** | 实时事实不靠 RAG 猜；接管后 Bot 零回复 |
| S6 | Tenant/ACL、安全与幂等 | `NOT_STARTED` | 顺延 v1.5 | 跨租户零泄漏；写动作确认；重放只执行一次 |
| S7 | FastAPI/SSE、Trace、部署与恢复 | `NOT_STARTED` | **第 2 周 Day 12—13**（部署顺延） | 断连/并发/脱敏/恢复测试与 Docker |
| S8 | 作品化与面试证据 | `NOT_STARTED` | **第 2 周 Day 14 + 持续** | README、ADR、报告、Trace、Bad Case、口述一致 |

完整阶段知识和时长建议见学习路线第 8 节。这里负责记录真实状态，不复制第二份路线。

## 8. S0 详细任务

### S0-01：先保护现有学习成果

- [x] Agent、Repo QA 和测试基础已进入 HEAD `7159378`。
- [x] 本次只更新文档，没有改业务源码；`README.md`、`prompt-log.md` 和 `.idea/` 的既有工作继续保留。
- [ ] 整个 `.codex/` 仍是未跟踪目录；学习者确认内容后再决定是否提交。

验收：`git status` 中每个文件都能解释来源；没有覆盖或丢失现有改动。

### S0-02A：模型客户端可注入（组件级已完成）

**先学：** 依赖注入、模块 import 副作用、调用方/适配器责任、异常传播。

**亲自决策：** 哪层决定重试；哪些异常可重试；重试耗尽怎样成为 Agent Stop Reason；stream 断开是否可重放。

**已实现：** `agent/runtime/v0.py` 使用可注入 Client；导入模块不要求真实 API Key；Client 和 Runtime 各自有 Fake 测试。

**证据限制：** Runtime Fake 返回 SDK response wrapper，而真实 `LLMClient.chat()` 返回 message；两组单测使用了不一致的返回契约，所以“可注入”不能升级为“已集成”。

### S0-02B：跨组件契约恢复（2026-09-17 完成）

**先写失败测试：** ✅ `tests/agent/test_client_runtime_contract.py` —— 用假 SDK 驱动真实 `LLMClient`，再把它注入真实 `run_turn`，覆盖一次直接回答和一次 Tool Round Trip。

**当时复现：** Runtime 在 `agent/runtime/v0.py:140` 对 `ChatCompletionMessage` 访问 `.choices`，抛出 `AttributeError`。复现细节与逐步讲解存于 `.codex/S0_RUNTIME_EVIDENCE.md`；一次性探针 `_repro_contract_bug.py` 已删除（事实已转正常驻测试）。

**亲自决策（已定）：**

- Client 对 Runtime **返回 message**，Runtime 不接触 Provider SDK wrapper。判据是依赖方向：SDK 形状是 Client 的实现细节，适配器只翻译一次。
- 重试预算**只由应用层承担**：`client.py` 显式传 `max_retries=0` 关掉 SDK 内部重试，应用层 `max_retries` 即真实总尝试次数。

**完成验收：** ✅ 新增 6 项跨组件测试由红转绿；既有 49 项零退化（现 55 passed）；无 Key、无网络；`client.py` 模块 docstring 与 `chat()` 类型标注与唯一返回契约一致。

### S0-03：统一测试入口与依赖

- [x] 在 `pyproject.toml` 声明 pytest 与测试直接使用的 `httpx2`；不依赖 SDK 的传递依赖碰巧存在。
- [x] 把脚本式断言改为 pytest 自动发现的 `test_*` 函数；移除手工入口和控制台编码依赖。
- [x] 默认离线；真实模型验证仍只有显式运行的 `apps/hello_api.py`，会读取 Key 且可能产生费用。
- [x] 固定命令 `uv run pytest -q`，写入 README 和本文件。

验收：`uv run pytest -q` 当前通过 55 项离线测试；`uv lock --check` 通过。跨组件回归已补齐（见 S0-02B），S0 可关闭。

### S0-04：Agent Loop 分支测试

- [x] 模型直接回答。
- [x] 一次 Tool Call。
- [x] 同一轮多个 Tool Call；当前明确为按模型返回顺序的**串行**执行与回填。
- [x] Tool 参数非法 JSON。
- [x] 未知 Tool。
- [x] Tool 抛异常。
- [x] 模型超时/重试耗尽：LLMClient 转换为 `ModelRetryExhaustedError`，Runtime 转换为 `MODEL_RETRY_EXHAUSTED`。
- [x] 达到最大步数。
- [x] Tool Result 正确绑定 `tool_call_id` 并回填。

验收状态：相关组件分支通过；Client 层覆盖 429、超时、断连的恢复/耗尽边界，Runtime 有 `FINAL_ANSWER`、`MODEL_RETRY_EXHAUSTED` 和 `MAX_STEPS_EXCEEDED` 三种终态。2026-09-17 补齐跨组件契约测试后，Client 与 Runtime 的组合可复现走通，本项由组件级 `TESTED` 升级为 `INTEGRATED`。

### S0-05：第一份真实证据

- [x] 在 `badcases.md` 记录故障注入的“模型重试耗尽后 SDK 异常泄漏”已修复案例。
- [x] 记录跨组件假绿案例；**2026-09-17 已由 `DISCOVERED / UNFIXED` 关闭为 `FIXED`**，补全了发现过程、根因、两处修复 diff、回归测试名与前后测试数（49 → 55）。
- [ ] 补完 `prompt-log.md` 第一条的 A/B 输出、结论和限制；当前没有可复现真实输出，不能编造。
- [x] 在 `.codex/S0_RUNTIME_EVIDENCE.md` 画出目标调用图、当前断点和重试耗尽转换图。
- [x] 在 `.codex/S0_RUNTIME_EVIDENCE.md` 写出 90 秒口述草稿和两层追问；学习者尚需脱稿练习，不能标记 `INTERVIEW_READY`。

## 8.1 S0 完成记录（2026-09-17）

**S0 从 `INTEGRATION_FAILED` 关闭为 `INTEGRATED`。** 剩余未完成项只有 `prompt-log.md` 第一条（不阻塞）。

```text
修复前：49 passed，但真实 Client + 真实 Runtime 必崩
        AttributeError: 'ChatCompletionMessage' object has no attribute 'choices'
        agent/runtime/v0.py:140

修复后：55 passed，跨边界组合可复现走通
```

改动清单：

| 文件 | 改动 |
|---|---|
| `agent/runtime/v0.py:140` | `msg = resp.choices[0].message` → `msg = resp`（去掉第二次去皮） |
| `tests/agent/test_runtime_v0.py:45` | Fake Client 由返回 wrapper 改为返回 message（假货对齐真货） |
| `agent/llm/client.py` | `OpenAI(...)` 显式传 `max_retries=0`；模块 docstring 写明重试只在应用层 |
| `tests/agent/test_client_runtime_contract.py` | 新增文件，6 项跨组件契约测试 |
| `badcases.md` | 跨组件假绿案例由 `UNFIXED` 关闭为 `FIXED` |
| `_repro_contract_bug.py` | 删除；一次性探针的事实已转正常驻测试 |

**这段是面试素材**：49 个测试全绿却跑不起来，说明**绿灯数量和真实可运行性无关**。
定位手段不是继续加组件测试，而是造一个穿过真实边界的探针。
详见 `badcases.md` 该条与 `.codex/S0_RUNTIME_EVIDENCE.md`。

## 9. 当前唯一任务

**主任务：v1 第 1 周 —— 知识底座与检索。**

这一步决定整个 v1 能不能立起来：没有稳定的摄取和索引，后面的检索、路由、引用全部无从谈起。
逐日排期见 `README.md` 第 2 节。

### Day 1（半天到一天）：修 Client/Runtime 跨组件契约假绿

现有 49 项测试全绿，但真实 `LLMClient` 返回 `ChatCompletionMessage`，Runtime 的 Fake 却返回带 `.choices` 的 wrapper，
真实组件组合处必崩。**Day 7 要生成带引用的回答，届时一定会撞上它**，不能拖。

1. 先写真实 Client + Fake SDK + 真实 Runtime 的离线失败测试，固定崩溃证据。
2. 选择唯一返回契约，修改最小实现，让直接回答和 Tool Round Trip 都通过。
3. 检查 SDK 默认重试设置，画出最坏尝试次数；避免 SDK 和应用层重试相乘。

### Day 2—3：摄取与结构切块

1. Markdown 文档 → 稳定 `doc_id`（按内容 hash）→ 块入库；重复导入不产生重复块。
2. `markdown_heading` 策略（任务包已下发，代码由学习者实现）。
3. 复用已有 `filters.py`，把质量过滤接进摄取链路。

### Day 4—7：检索与引用

1. BM25 基线 + 固定评测集（≥ 40 条带源位置的检索题，Recall@5 / MRR@10 有分母）。
2. Dense 向量检索（走 API embedding，不在本地跑模型）。
3. 混合检索与同集对照；带引用的回答生成，引用格式 `path:start-end`。

**本阶段不做**：多租户、PDF/OCR、Rerank、删除传播、Docker、Langfuse、多 Agent。

## 10. 每个单元的固定产物

```text
1. 一张调用/数据流图
2. 一个方案对比或 ADR
3. 核心实现
4. 正常 + 异常 + 边界测试
5. 至少一个真实或故障注入 Bad Case
6. 一份可复现命令与结果
7. 90 秒主干回答 + 两层追问
```

没有失败证据和机器可判断结果，不标记 `EVIDENCED`；只看完教程或让 AI 生成代码，不标记 `IMPLEMENTED`。

## 11. 面试叙事检查表

### AI 应用开发

- [ ] 为什么本地知识库需要或不需要 RAG？基线是什么？
- [ ] Chunk、Embedding、Hybrid、Rerank 分别解决哪个失败？
- [ ] 检索命中和最终回答正确为什么要分开测？
- [ ] 无答案、过期数据、权限过滤和 Prompt Injection 怎么处理？
- [ ] SSE 断开、模型超时、并发打满和成本超限怎么办？
- [ ] 一个指标如何计算，数据集从哪里来，是否泄漏？

### Agent 开发

- [ ] 模型为什么不能直接执行函数？
- [ ] Agent 状态、消息历史、Checkpoint 和 Memory 有何区别？
- [ ] Tool 如何注册、校验、授权、超时、重试和审计？
- [ ] 如何阻止路径逃逸、读 `.env`、命令注入和未批准写入？
- [ ] 任务中断如何恢复且不重复副作用？
- [ ] 如何同时评估最终结果、执行轨迹和安全违规？
- [ ] MCP 和 Function Calling、Tool Registry、Agent 编排分别解决什么问题？
- [ ] 为什么当前先做单 Agent？多 Agent 的保留门槛是什么？

## 12. 更新记录

### 2026-09-17：S0 关闭 —— 跨组件契约假绿修复 + 重试预算收敛

**改动清单**

| 文件 | 改动 |
|---|---|
| `agent/runtime/v0.py:140` | `msg = resp.choices[0].message` → `msg = resp`（去掉第二次去皮；由学习者亲手完成） |
| `tests/agent/test_runtime_v0.py:45` | Fake Client 由返回 wrapper 改为返回 message（假货对齐真货，修复镜像报错） |
| `agent/llm/client.py` | `OpenAI(...)` 显式传 `max_retries=0`；模块 docstring 写明「重试只在本层」 |
| `tests/agent/test_client_runtime_contract.py` | 新增 6 项跨组件契约测试 |
| `badcases.md` | 跨组件假绿案例由 `DISCOVERED / UNFIXED` 关闭为 `FIXED` |
| `_repro_contract_bug.py` | 删除；一次性探针的事已转正常驻测试 |
| `PROJECT_PROGRESS.md` / `README.md` | 状态口径同步：S0 `INTEGRATION_FAILED` → `INTEGRATED`；测试数 49 → 55 |

**验证**：`uv run pytest -q` → 55 passed，exit 0；原 49 项零退化；`compileall` exit 0。

**实测证据**：`OpenAI().max_retries == 2`（共 3 次尝试）× 应用层 `max_retries=3` = 最坏 9 次真实请求；改动后 SDK 侧为 0，总尝试次数等于应用层配置。

**这次最值得记的一句话**：**49 个测试全绿，和「跑得起来」是两回事。** 两组组件测试各自用了对自己有利的假货，凑在一起才暴露。定位靠的是穿过真实边界的探针，不是继续加组件测试。

### 2026-09-17：目标收敛为 2 周可投递版本 v1

**背景**：原 S0—S8 完整阶段合计 42—63 个学习日，按每周 5 天算要 8—13 周，远超投递窗口。
学习者决议：每天高强度学习，**2 周内拿出可投递版本**。

**这次改了什么**

- `README.md` 重写：作品定义（MiniDev SupportOps 客服 Agent）提到最前面；第 2 节改成 14 天逐日排期；
  第 3.1 节改成按两周排期看进度；学习过程文档退到第 8 节。
- 本文件顶部新增「v1 收敛决议」；第 7 节阶段看板增加「v1 归属」列，标出每个 S 阶段落在第几天；
  第 9 节从「修 Client/Runtime 契约」改成「v1 第 1 周」，把工程债降为 Day 1 的前置动作。
- 状态口径同步：S0 曾为 `INTEGRATION_FAILED`，是 Day 1 必须先清的障碍；**2026-09-17 已关闭为 `INTEGRATED`**（见第 8.1 节）。

**范围决策**

- 14 天做：摄取、结构切块、质量过滤、幂等导入、BM25、Dense、混合检索、引用回答、
  意图与风险路由、实时工具、证据门、人工交接、FastAPI + SSE、评测报告。
- 顺延 v1.5 / v2：多租户 ACL、PDF/OCR/表格、Rerank、删除传播、注入负例、幂等键、Docker、Langfuse、多 Agent。
- 砍单顺序（时间不够时）：先砍混合检索，再砍 SSE；**人工交接和评测报告不砍**。

**本次只改文档**，没有修改 `agent/`、`apps/`、`repo_qa/` 或 `tests/` 源码。

### 2026-09-17：补齐 Chunk 质量过滤（入库前 Quality Gate）

- 新增 `repo_qa/chunking/filters.py`：规则契约 `reject_reason(chunk) -> str | None`，四条规则按 `no_text -> page_furniture -> too_short -> duplicate` 顺序执行，第一个说不的规则决定丢弃原因。
- `config.py` 新增 `FilterConfig(enabled / min_chars / drop_duplicates)` 并嵌入 `ChunkConfig.filter`；`pipeline.py` 的 `chunk_text` 接上过滤，新增 `chunk_text_result` 返回 `FilterResult`（保留块 + 丢弃块 + 原因 + 按规则计数）。
- 新增 22 项测试（`tests/repo_qa/test_chunking_filters.py`），`uv run pytest -q` 为 `49 passed`。
- 对照证据：过滤开与关，8 条场景命中数完全一致（`fixed_lines 4/8`、`code_ast 7/8`，且分族命中数相同）——证明过滤没有误杀评测期望覆盖的块。
- **发现一条已知边界**：页码跟在正文后面时，固定行数会把它们切进同一块，`page_furniture` 规则此时必须放手（丢整块等于连正文一起丢）。已写成测试 `test_page_number_glued_to_body_is_a_known_limit`。这条边界指向的下一步不是加规则，而是换按段落/标题切的策略，或在解析阶段就摘掉页眉页脚。
- 本次只动 `repo_qa/chunking/` 与 `tests/repo_qa/`，未动 `agent/`、`apps/`。**S0-02B（Client/Runtime 跨组件契约）仍未修复**，本节记录的是 RAG 线的并行推进，不代表 S0 关闭。

### 2026-09-13（方向决议）：主线改为本地知识库 / 客服，语料以文档为主

- 学习者确认：热点与可做性优先——本地知识库 RAG / 企业客服；**不以「代码仓库清洗/问答」为项目主叙事**。
- README 与本文件同步：第一纵切更名为 **MiniDev Knowledge Base**；SupportOps 仍为终局作品。
- 语料边界：文档为主；切分策略跟结构走（标题/段落优先）；**Python AST 降为可选插件**，保留已有实现与 8 条代码向评测作为底座证据，不删除代码。
- 包名 `repo_qa` 暂不重命名；文档与口述统一称 Knowledge Base 纵切。
- 本次只修改学习与项目文档，没有修改 `agent/`、`apps/`、`repo_qa/` 或 `tests/` 源码。

### 2026-09-13：岗位、真实场景与仓库事实复核

- 新增 `AI_APP_MARKET_AND_REAL_SCENARIOS_2026-09-13.md`：15 家公司便利样本、12 类真实故障、来源强弱、SupportOps 业务边界和建议验收线。
- 将最终作品确定为 `MiniDev SupportOps`，Repo QA 作为其第一个 RAG 纵切；静态知识、实时事实、高风险动作和人工交接使用不同责任链。
- 仓库复核发现 27 项组件测试全绿仍掩盖 Client/Runtime 返回类型失配；撤销旧 `INTEGRATED` 结论，S0 重新打开为 `INTEGRATION_FAILED`。
- 更新阶段为 S0—S8；Multi-Agent、GraphRAG、复杂 MCP、微调等仍由目标 JD 或评测触发，不抢占 P0。
- 本次只修改学习与项目文档，没有修改 `agent/`、`apps/`、`repo_qa/` 或 `tests/` 源码。

### 2026-09-08：推进 S0-05 第一份证据（历史记录）

- 在 `badcases.md` 记录“模型重试耗尽导致 SDK 异常泄漏到 CLI”的故障注入、根因、修复和两个回归测试。
- 新增 `.codex/S0_RUNTIME_EVIDENCE.md`，保存正常 Tool Calling / 模型重试耗尽调用图、当前 Stop Reason、90 秒口述草稿和追问。
- Prompt A/B 真实输出和学习者脱稿练习仍未完成，不夸大为 `EVIDENCED` 或 `INTERVIEW_READY`。

### 2026-09-08：完成 S0-04 Agent Loop 分支测试与模型终态（历史记录）

- 为多 Tool Call 顺序、坏 JSON、未知工具、工具异常、最大步数、模型超时/重试耗尽补充离线测试。
- `LLMClient` 在可重试错误耗尽时抛出 `ModelRetryExhaustedError`，保存最后技术原因和尝试次数；最后一次失败后不再无意义等待。
- 当时的 `agent_v0.py`（现为 `agent/runtime/v0.py`）新增 `AgentRunResult` 和 `StopReason`，将最终回答、模型重试耗尽、最大步数熔断转换为确定终态；CLI 只展示安全的用户文案。
- 当时 `uv run pytest -q` 收集并通过 15 项离线测试；这是历史组件测试数量，2026-09-13 已更新为 27 项，且集成假绿问题尚未修复。未进行真实模型调用。

### 2026-09-08：完成 S0-03 统一测试入口与直接依赖（历史记录）

- 在 dev dependency group 中显式声明 `pytest` 和测试直接使用的 `httpx2`，并同步 `uv.lock`。
- 配置 pytest 只从 `tests/` 目录发现测试；删除测试文件的 `__main__` 手工入口。
- README 的唯一离线测试命令更新为 `uv run pytest -q`，不再依赖 `PYTHONUTF8` 或终端 emoji 输出。
- 验证 5 项 pytest 测试、compileall、lock 一致性与 diff 格式检查均通过；没有真实模型调用。

### 2026-09-08：完成 S0-02 模型客户端可注入（历史记录，非集成完成）

- 当时的 `agent_v0.py`（现为 `agent/runtime/v0.py`）改为通过 `run_turn(..., llm_client)` 注入模型客户端。
- 真实 `LLMClient` 只在 CLI 启动时创建；导入模块不再初始化 OpenAI 客户端或要求 API Key。
- 删除 `agent/llm/client.py` 的模块级默认实例，保留模型、重试和流式配置在客户端层。
- 当时新增的测试现位于 `tests/agent/test_runtime_v0.py`，验证 Fake Client 驱动直接回答和工具回填；该 Fake 的返回形状与真实 Client 不一致。
- 初步验证 compileall、LLMClient 重试测试和 Agent Loop 注入测试；随后在 S0-03 统一为 pytest。此记录只证明可注入，2026-09-13 已确认不证明跨组件集成。
- 查询 OpenAI Agents SDK、LangGraph、Pydantic AI 的官方仓库并新增 `.codex/AGENT_ARCHITECTURE_RESEARCH.md`；为当前源码、测试和记录文件补充模块职责与边界说明。

### 2026-09-08：按真实 AI 应用 / Agent 岗重排

- 完成当前仓库只读审计，区分已提交、工作区实现、离线测试、未集成和纯规划能力。
- 基于 10 条早期职业 JD、10 篇第一人称面经及一手技术资料，新增双岗位学习路线。
- README 从“多智能体技术栈清单”改为两条可验收纵切，并明确当前安全缺口。
- 多 Agent 从原 W3 下调到 P2；RAG、MCP、Trace、评测按依赖与失败证据重排。
- 本轮只修改学习文档，未修改 `agent_v0.py`、`agent/`、`tests/` 或其他源码。
