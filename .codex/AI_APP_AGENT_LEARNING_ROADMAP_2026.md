# 2026 AI 应用开发岗学习路线（主投）与 Agent 开发对照

> 初次调研：2026-09-08；**最新岗位与场景复核：2026-09-13**
>
> 适用对象：2027 届、本科、已有一段非头部公司实习；**主投 AI 应用开发 / 大模型应用开发**。
> 本文负责“岗位证据、知识边界和课程设计”；动态完成状态只记录在 `PROJECT_PROGRESS.md`。

## 0. 投递优先级（2026-09-10 决议）

| 优先级 | 岗位类型 | MiniDev 主证据 | 时间占比 |
|---|---|---|---|
| **P0 主投** | AI 应用开发 / 大模型应用开发 / RAG 工程师 | **Repo QA → SupportOps**：摄取、检索、引用/拒答、实时工具、客服交接、Eval、FastAPI/SSE | **~70%** |
| **P1 共用底座** | 两岗都要 | LLM Client 重试、结构化输出、Prompt/Context、评测方法论 | **~20%** |
| **P2 次要 / 冻结深挖** | Agent 开发 / Agent 后端（可顺投） | 已有 `runtime/v0` Tool Loop + StopReason；**不把主项目做成 Coding Agent** | **~10% 或暂缓** |
| 按 JD 选择性 | Agent 算法 / 模型训练 | 不在当前 P0 | 0 |

2026-09-13 的 15 家公司便利样本中，软件/系统工程 `15/15`、RAG/知识库 `14/15`、项目证据 `14/15`、具名框架 `12/15`、Python `12/15`、Tool/FC/MCP `10/15`、Eval/可观测 `10/15`。这些是关键词筛选样本的内部计数，不是市场百分比；完整来源、状态和编码边界见 `AI_APP_MARKET_AND_REAL_SCENARIOS_2026-09-13.md`。

投递前仍以当周 JD 职责动词为准：“接入、封装、编排、服务化、评测、上线”优先投；“训练、对齐、分布式推理”属于另一条算法/模型工程路线；“多 Agent、复杂 MCP、GraphRAG”不因热门就进入当前 P0。

## 1. 先说结论

1. **AI 应用开发和 Agent 开发不是两个完全分离的技术栈。** 二者共用 Java/Python 中至少一门、后端工程、模型 API、Prompt 与 Context、结构化输出、RAG、评测、可观测性、安全和部署；MiniDev 选择 Python 落地。**2026-09-10 起主投 AI 应用**；Agent 岗在此基础上更强调多步运行时、工具治理、状态、恢复和行动安全——那是顺投能力，不是主项目方向。
2. **AI 应用开发岗的交付物是可用的 AI 产品或服务。** 本批样本支持重点准备：业务问题是否适合 LLM、数据怎样进入上下文、RAG 效果怎么测、接口如何流式交付、失败如何降级、成本和权限怎样治理，而不只是“会调 Chat API”。第一纵切是 **Repo QA**，最终作品是复用该底座的 **MiniDev SupportOps**。
3. **Agent 开发岗的交付物是可控的任务执行系统。** 本批样本中的追问会沿 Tool Calling 深入参数校验、权限、超时、幂等、循环终止、上下文膨胀、中断恢复、Trace 和轨迹评测。当前仅保留概念级 Loop 与重试契约，**不在主投阶段深挖 Safe Coding Agent 闭环**。
4. **Agent 不等于多 Agent，RAG 不等于接一个向量库。** Repo QA 必须先有固定评测集与关键词基线，再谈向量/混检；多 Agent 仅在 Agent 顺投需要时再评估。
5. **训练/微调岗是第三条路线。** PyTorch、Transformer 数学、SFT、DPO/RLHF、CUDA、vLLM 深层优化在部分“Agent 算法岗”会成为核心，但不是当前应用工程主线的 P0；投递前按具体 JD 决定是否补。
6. **MiniDev 不再按框架名排周次。** 课程按“真实场景 → 知识 → 方案取舍 → 核心实现 → 失败实验 → 指标/Trace → 面试口述”执行。

## 2. 调研口径与可信边界

本路线先在 2026-09-08 调查早期岗位和面经，2026-09-13 又复核了 15 家公司岗位、GitHub issue、客服产品文档、检索/评测文档和 OWASP RAG 安全资料。详细原始链接集中记录在 `AI_APP_MARKET_AND_REAL_SCENARIOS_2026-09-13.md`。

采用规则：

- JD 只提取职责、任职要求或加分项中明确写出的能力，不从岗位标题猜技术栈；“训练是职责/硬要求”另行排除纯加分项。
- 面经优先保留公司、岗位、轮次、日期或具体题目中至少两项明确的帖子。
- 同一篇来源中，一个主题无论追问多少次最多算一次，避免长帖放大频率。
- 便利样本只能说明这些主题在本批帖子中反复出现，不能推出全市场百分比或“必考率”。
- 面经属于候选人自述，无法独立核验其完整性；本文把它作为真实交流平台上的追问线索，不把它当公司官方考纲。
- 培训题库、卖课引流、无原始轮次的二次汇总和没有分母的“命中率”不作为定优先级的主证据。

### 2.1 2026-09-13 岗位样本

本次定向样本为 **15 家不同公司的 15 个岗位**，每家公司只计一岗。它是按 AI 应用、RAG、知识库、Agent 等关键词筛选的便利样本，不是随机抽样，也不是市场占比调查。

| 能力主题 | 出现数 / 15 | 对学习顺序的意义 |
|---|---:|---|
| 软件或系统工程开发 | 15/15 | 先具备 API、异常、测试、数据和部署能力 |
| RAG、知识库或检索 | 14/15 | 作为作品主链，而不是只做模型聊天 |
| 项目、实习、课程或开源证据 | 14/15 | 每个能力都要留下可运行、可测量证据 |
| 具名 Agent/LLM 应用框架 | 12/15 | 会用框架，但必须先懂责任边界和调用流 |
| Python | 12/15 | MiniDev 继续用 Python；后端基础不可跳过 |
| Tool/Function Calling/MCP | 10/15 | 在 RAG 稳定后加入真实业务工具和治理 |
| Eval 或可观测 | 10/15 | 固定数据集、Trace、成本和延迟从早期建立 |
| 微调或 Post-training | 5/15 | 当前不是应用开发入门 P0 |

完整岗位、页面日期、抓取状态、来源分级和编码限制见 `AI_APP_MARKET_AND_REAL_SCENARIOS_2026-09-13.md`。过期岗位只作为历史技能证据；实际投递必须回公司官网复核。

### 2.2 真实开发场景证据

论坛和开源 issue 反复出现的不是“框架 API 不会背”，而是以下工程边界：

1. PDF、扫描件和表格解析错误会污染后续切块与检索，失败摄取不能留下半成品索引。
2. 文档重复、更新和删除必须能传播到关键词索引、向量索引、缓存和引用。
3. 错误码等精确词适合 BM25，语义改写适合 Dense；Hybrid/Rerank 必须用同一数据集做消融后再保留。
4. 相似度分数不是答案可信概率；必须单独设计可答性、引用、澄清和拒答。
5. 静态知识走 RAG，实时工单/订单/服务状态走业务 API，不能把可能过期的事实塞进向量库猜。
6. 写操作需要权限、参数确认、幂等和 HITL；转人工后要切换会话所有权，机器人不能继续回复。
7. 多租户过滤、间接 Prompt Injection、长会话污染、重试与恢复都要有负例和 Trace。

这些场景的官方文档、GitHub issue、论坛线索和 MiniDev 建议验收线统一放在 `AI_APP_MARKET_AND_REAL_SCENARIOS_2026-09-13.md`，不把单一 issue 或个人面经夸大成行业普遍结论。

### 2.3 第一人称面经样本（2026-09-08 历史快照，未独立核验）

面经样本为 10 篇第一人称原帖，AI 应用与 Agent 各 5 篇。

| 编号 | 岗位 / 时间 | 作者记录的追问信号 | 来源 |
|---|---|---|---|
| A1 | 联想 AI 应用一面，原帖 2026-04-02 | RAG Chunk/Context/幻觉/向量库/相似度，Agent 框架/Tool/Skill，Python 闭包与 Java 内存泄漏 | [牛客原帖](https://www.nowcoder.com/discuss/869169098146537472) |
| A2 | 阿里国际 AI 应用实习一面，2026-04-02 | 隐私与端到端链路、Java/JVM/HashMap、HTTPS、慢 SQL/TopK、Prompt、RAG vs 微调、Agent、幻觉/Eval/NL2SQL | [牛客原帖](https://www.nowcoder.com/discuss/872069472310288384) |
| A3 | 新大陆大模型应用线下一面，2026-06-15 | Agent 项目实现、向量库与用户都无信息时怎么办、百余企业文档调研和解析失败 | [牛客原帖](https://www.nowcoder.com/feed/main/detail/1a85477771e0493086facc1e97cc3a48) |
| A4 | 安软 AI 应用实习，2026-07-25 | 项目真实性、模型成本、Context/幻觉、自研框架/模型适配/Tool 权限/Memory、RAG 评测泄漏、Redis/IO/数据库 | [牛客原帖](https://www.nowcoder.com/feed/main/detail/40920533fad14136bff01c3928c7e953) |
| A5 | 要务科技 AI 应用实习，2026-09-07 | 意图 fallback、数据一致性/重试、Webhook 签名幂等、Prompt Injection/Tool 权限、脏 Context、异构文档、SSE/WS、Redis/JWT | [牛客原帖](https://www.nowcoder.com/discuss/926539013991796736) |
| G1 | 有赞 Agent 开发实习一面，原帖 2026-01-23 | Token/Context、向量库、MCP vs FC 与安全、Tool 注册/版本、Memory 生命周期、RAG 切分 | [牛客原帖](https://www.nowcoder.com/discuss/844326240679886848) |
| G2 | 蚂蚁 Agent 开发一面，原帖 2026-04-24 | 项目架构、单/多 Agent 角色/通信/并发、混合 RAG、Tool/FC/MCP、Schema 不匹配、Context、上线质量 | [牛客原帖](https://www.nowcoder.com/feed/main/detail/7a0ddb8e077041d4b72ba9e5290ad36a) |
| G3 | 成都某中厂 Agent 产品开发实习，2026-06-15 | Prompt/Context/Harness/Loop、FC 流程、RAG/LoRA 数据、Dify/Coze Workflow vs Coding Agent、Skill/渐进披露 | [牛客原帖](https://www.nowcoder.com/feed/main/detail/d770696f3495465d9e3d40c3d631d54c) |
| G4 | 虾皮 Agent 开发一面，2026-08-20 | 项目 ownership、Single/Multi/Workflow、ReAct/ToolMessage、Memory/Context、父子索引/混检/Rerank/更新、后端与算法 | [牛客原帖](https://www.nowcoder.com/feed/main/detail/79fe3fc8f8cb4c4d9beca478f4279e3a) |
| G5 | 美团 Agent 开发日常一面，原帖 2026-08-25 | 项目全链路/选型、RAG vs Long Context vs grep、检索全链、幻觉、Plan-and-Execute vs ReAct、Harness/Context、协程线程和算法 | [牛客原帖](https://www.nowcoder.com/feed/main/detail/58159306df52463ab75d72daa80d66df) |

面经方向性编码：

| 主题 | AI 应用组 `n=5` | Agent 组 `n=5` |
|---|---:|---:|
| RAG | 5/5 | 5/5 |
| Agent 架构 / Context / Workflow | 5/5 | 5/5 |
| Tool / FC / MCP | 3/5 | 5/5 |
| Eval / 幻觉 / Fallback / 质量 | 5/5 | 3/5 |
| 项目 / 交付深挖 | 4/5 | 4/5 |
| 后端 / CS 基础 | 4/5 | 3/5 |
| 安全 / 隐私 / 权限 | 3/5 | 1/5 |
| 训练 / 微调 | 1/5 | 2/5 |
| 现场算法 | 0/5 | 2/5 |

在这批便利样本内反复出现的结构是：**项目真实性与取舍 → AI 链路细节 → 失败与指标 → 后端/算法基础**。因此只背 LangChain 类名或只做“能回答”的 Demo 都不够。

## 3. 三类岗位先分清

| 岗位类型 | 主要交付 | 面试主线 | 当前策略 |
|---|---|---|---|
| **AI 应用开发 / 大模型应用开发** | 把 LLM、RAG、结构化生成、对话或多模态能力集成到业务产品 | 场景是否适合 LLM、数据链路、效果评测、服务稳定性、成本、权限、部署 | **主投、主学（~70%）** |
| Agent 开发 / Agent 平台 / Agent 后端 | 构建能多步决策并安全行动的运行时、工具平台或垂直 Agent | Loop/State、Tool、Context/Memory、权限沙箱、恢复、Trace、Eval、MCP | **次要 / 顺投；保留底座，冻结深挖（~10% 或暂缓）** |
| Agent 算法 / 大模型算法 / 后训练 | 改善模型规划、工具学习、推理或领域能力 | Transformer、训练数据、SFT/LoRA、偏好优化、RL、PyTorch、论文与实验 | **按 JD 选择性投递** |

投递前看职责中的动词：

- “接入、封装、编排、服务化、上线、治理、评测”通常偏应用工程。
- “运行时、状态、工具平台、沙箱、恢复、Trace”通常偏 Agent 工程。
- “训练、微调、对齐、奖励、推理优化”通常偏算法或模型工程。

## 4. 两个岗位共用的 P0 底座

### 4.1 知识地图

| 模块 | 必须掌握到什么程度 | MiniDev 中的证据 |
|---|---|---|
| Python 工程化 | 类型标注、包与依赖、Protocol/ABC、依赖注入、异常边界、配置、日志、pytest/fake、asyncio 基础 | 模型、工具、存储可替换；无 API Key 也能跑离线测试 |
| 计算机与后端基础 | 数据结构/算法，HTTP/REST，SSE 与 WebSocket 区别，进程/线程/协程，数据库、Redis、Linux、Git、Docker | FastAPI/SSE 服务、持久化和缓存各有真实用途；能做算法题 |
| LLM 应用原理 | 概念级理解 Tokenization、Attention/Transformer、自回归生成、预训练/指令微调/偏好对齐；掌握 Temperature/Top-p、Context、幻觉，以及 Embedding 与生成模型差异，不要求数学推导 | 能解释 RAG、微调、长上下文各改变了什么；用小实验比较采样参数和模型行为 |
| 模型消息协议 | System/User/Assistant/Tool 消息、Tool Call ID、Finish Reason 和上下文累计 | 能画出一次普通调用和一次工具回填的完整消息流 |
| 模型 API | 同步、流式、取消、结构化输出、Tool Calling、Finish Reason、Usage | 正常、流式、非法 JSON、无工具、单/多工具都有契约测试 |
| Provider 适配 | 不同模型请求/响应、能力和错误码不完全一致；能力探测不能只靠“OpenAI 兼容”四个字 | Provider capability profile + 契约测试；不支持能力时明确失败或降级 |
| 客户端可靠性 | 连接/读超时、429、5xx、指数退避、`Retry-After`、熔断、取消、重放安全 | Fake Client 故障注入；重试耗尽返回结构化 stop reason |
| Prompt Engineering | 指令、示例、输出约束、Prompt 版本、变量边界；知道 Prompt 不能替代权限和业务校验 | 每版 Prompt 有 ID、输入、差异、评测结果，不凭感觉覆盖 |
| Context Engineering | 选择什么信息进入上下文、何时检索、裁剪、摘要、渐进披露；理解“更多上下文不一定更好” | 大文件/长会话不超预算；关键事实丢失有检测或恢复方案 |
| RAG 基础 | 数据摄取、Chunk/Metadata、Embedding、Sparse/Dense/Hybrid、Rerank、引用、拒答和检索/生成分段评测 | Repo QA 用同一数据集比较关键词、向量和混检；所有结论有引用或拒答 |
| Agent 术语边界 | 能区分 Tool/Function Calling、MCP、平台相关 Skill、Harness、Workflow 和 Agent；知道 Skill 没有跨平台唯一语义 | 不用框架名代替调用流；能画出模型、Harness、MCP Client/Server 与本地 Tool 的位置 |
| 数据契约 | Pydantic / JSON Schema、输入输出校验、结构化错误、版本兼容 | 缺字段、错类型、额外字段和幻觉参数都由应用拒绝 |
| 测试与 Eval | 单元/集成/契约测试；确定性断言与 LLM Judge 的边界；数据集防泄漏 | 固定回归集、Bad Case、基线与变更对比，不让模型自证正确 |
| 可观测性 | Run/Trace/Span、模型/Prompt 版本、Token、成本、TTFT、总延迟、工具耗时、错误类型 | 任一失败可按 `run_id` 回放链路并定位归因 |
| 安全与隐私 | Prompt Injection、敏感信息、越权、最小权限、输入/输出校验、依赖与日志泄漏 | `.env`、工作区外路径和恶意文档不可被读取或驱动高风险操作 |
| 工程交付 | 配置隔离、健康检查、超时、限流、Docker、最小 CI、README 与复现实验 | 新环境按文档可启动；一条命令生成测试/评测报告 |

### 4.2 共用底座的典型场景题

1. 模型请求 30 秒后超时，是否应该重试？已经产生副作用时还能否重试？
2. API 声称兼容 OpenAI，但某个参数被忽略，怎样在上线前发现？
3. 流式输出到一半客户端断开，服务端模型调用、计费和任务状态怎么处理？
4. JSON 能解析但字段语义错误，应该由模型、Schema 还是业务代码兜底？
5. Prompt 改了一句话，如何证明效果变好而不是只对三个演示问题过拟合？
6. 同一问题用大模型和小模型的成功率、TTFT、总延迟和成本如何比较？
7. 为什么日志不能原样记录 Prompt、文档和 Tool Result？如何既可排障又不泄密？

## 5. AI 应用开发岗知识地图

### 5.1 AI-P0：必须实现、测量并能解释

#### A. 场景与方案选择

- 区分规则系统、搜索、传统 ML、单次 LLM、固定 Workflow、RAG 和 Agent。
- 先定义用户、输入、输出、错误成本和成功指标，再选模型或框架。
- 知道哪些结果必须由确定性代码校验，哪些可以接受概率性输出。
- 能比较 RAG、长上下文和微调：外部知识可更新不等于要改模型权重，领域行为变化也不等于只加检索。

MiniDev 任务：为 SupportOps 建立路由题集，明确哪些请求走 Repo QA/RAG、哪些走实时业务 API、哪些必须确定性规则 + HITL、哪些应澄清/拒答/转人工。

验收：能解释“为什么不是把整个仓库直接塞进长上下文”“为什么实时工单状态不能用 RAG 猜”“为什么高风险写操作不能只靠 Prompt 约束”。

#### B. 模型调用、结构化生成与 Prompt 生命周期

- Chat/Responses 类消息协议、流式事件、Usage、Finish Reason。
- JSON Schema/Pydantic、结构化输出失败、模型能力差异。
- Prompt 模板、变量隔离、版本、回归、灰度和回滚。
- 模型选择：质量、上下文、工具能力、延迟、稳定性、价格和数据政策。

MiniDev 任务：统一模型接口；同一任务支持文本、流式和结构化结果；记录 provider/model/prompt_version/usage/latency。

验收：Fake Provider 覆盖坏 JSON、截断、429、5xx、超时和不支持能力；真实模型 smoke test 与离线测试分开。

#### C. RAG 全链路

必须能从数据变化讲到最终引用：

```text
数据源
  -> 解析与清洗
  -> Chunk + Metadata
  -> Embedding / 关键词索引
  -> 候选召回
  -> 过滤 / 混合 / Rerank
  -> Context 组装
  -> 生成 / 拒答 / 引用
  -> 反馈、更新与删除
```

必须理解：

- 固定长度、段落/标题、函数/类/AST、语义切块及 overlap 的代价。
- Dense、Sparse/BM25、Hybrid、Metadata Filter、Rerank 各解决什么问题。
- Embedding 选型不能只看维度；要用领域数据比较召回、速度、成本和中英文/代码能力。
- 文档 ID、版本、权限、增量更新、删除、去重和索引一致性；失败摄取不留下半成品。
- Markdown、文本 PDF、扫描 PDF、OCR 和表格的解析质量必须先于下游问答评测。
- 证据不足时拒答；答案引用必须能定位到真实文件与行号。

MiniDev 任务：对 Python/Markdown 和代表性 PDF fixture 建 Repo QA 索引，先验证幂等导入、更新和删除，再比较 BM25、Dense、Hybrid 与 Rerank；高级组件只有在基线失败类型明确后加入。

验收：至少 30 个可回答 + 20 个无答案/歧义问题；分别记录解析质量、Recall@k、MRR、引用正确率、Groundedness、拒答正确率、端到端成功率、P95 和 Token 成本。

#### D. AI API 与交互交付

- FastAPI、Pydantic、asyncio、SSE、连接断开与背压。
- 会话与消息持久化、任务状态、取消、重试、错误协议。
- 鉴权、租户隔离、速率限制、配额和审计。
- 业务 API/数据库/缓存/MQ 的集成边界；静态知识走 RAG，实时事实走 API。
- 会话所有权、人工交接包和事件幂等；人工接管后 Bot 必须停止回复。

MiniDev 任务：提供问答、流式、Run 状态和人工交接接口；让工单/服务状态只通过结构化 Tool 查询；高风险动作只生成待确认计划。

验收：正常、超时、模型错误、客户端断开、并发限额、跨租户、Tool 重放和人工接管都有自动化测试与日志证据。

#### E. AI 效果评测与运营

- 离线集：来源、标注、难例、不可回答、版本和泄漏风险。
- 分段评测：检索、上下文、生成、引用分开测，不能只看最终回答。
- 确定性规则、人工评分、LLM-as-a-Judge 的适用边界和偏差。
- 线上指标：任务成功、采纳/转化、用户反馈、延迟、错误率、Token/成本。
- Bad Case 归因：数据、检索、Prompt、模型、工具、权限、系统故障。

MiniDev 任务：一条命令运行离线集并生成版本对比；真实线上样本只能脱敏后进入候选回归集。

验收：任何“准确率提升”都有数据集版本、分母、基线、配置和可复现实验，不能写“接近 100%”而无解释。

### 5.2 AI-P1：做一个真实样例并会比较

- Query Rewrite、HyDE、Multi-query、Contextual Compression 等增强策略；按 Bad Case 选择，不全开。
- 模型路由、缓存、批处理、并发控制、降级与成本预算。
- 用户反馈闭环、Prompt A/B、灰度、回滚和数据看板。
- 图片、音频等超出当前文档/OCR 范围的多模态理解。
- 异步长任务、队列与状态查询。
- 一个主框架深入使用并看懂抽象边界；其余框架只做比较。

### 5.3 AI-P2：由目标 JD 触发

- LoRA/SFT、DPO/RLHF、训练数据工程和模型评测。
- vLLM、量化、KV Cache、GPU 性能与推理集群。
- GraphRAG、知识图谱、大规模分布式向量数据库。
- 复杂语音/视觉实时链路和模型算法复现。

## 6. Agent 开发岗知识地图

### 6.1 AG-P0：必须实现、故障注入并能解释

#### A. Chatbot、Workflow 与 Agent 的边界

- Chatbot 主要生成回答；Workflow 的路径由代码预先定义；Agent 由模型根据环境反馈动态选择步骤和工具。
- 自主性会增加延迟、成本和复合错误。可预测流程优先用确定性代码或 Workflow。
- ReAct、Plan-and-Execute 是模式，不是框架名称；重点是状态、终止和反馈闭环。

MiniDev 任务：同一个“定位代码问题”任务分别实现固定 Workflow 和单 Agent，记录成功率、步骤、成本和失败类型。

验收：能用数据回答为什么当前功能需要或不需要 Agent。

#### B. 可验证的 Agent Loop / 状态机

核心状态至少包括：

```text
READY -> MODEL_CALL -> TOOL_REQUESTED -> TOOL_RUNNING
      -> OBSERVATION -> MODEL_CALL -> FINAL
      -> WAITING_APPROVAL / CANCELLED / FAILED / BUDGET_EXCEEDED
```

必须掌握：消息回填、多个 Tool Call、最大步数、时间/Token/费用预算、重复调用检测、取消、明确 Stop Reason。

MiniDev 任务：把散落在 `for` 循环中的控制逻辑收口为可测试状态；模型、工具和时钟均可注入。

验收：直接回答、单工具、多工具、坏参数、工具异常、重复调用、模型超时、预算耗尽和取消均有离线轨迹测试。

#### C. Tool Contract 与执行器

- Tool Registry、名称/描述、JSON Schema、输入输出类型和版本。
- 应用负责执行；模型只提出调用意图。
- 参数、业务状态和权限三层校验；错误结果结构化。
- 超时、并发、输出截断、幂等键、重试与补偿。
- 工具描述本身是 Agent-Computer Interface，需要像 API 一样测试。
- MCP 是 Host/Client/Server 之间的互操作层，不替 Agent 做规划、状态或授权；Skill 的具体含义依平台而异，不能笼统说成“新协议”或“取代 Tool”。

MiniDev 任务：统一 `ToolSpec / ToolCall / ToolResult / ToolError`；实现只读 `search/read/list`，随后才加入 patch 和测试命令。

验收：未知工具、缺字段、错类型、额外字段、路径越界、超时、输出过大和异常都不会炸掉 Loop，且 Trace 可定位。

#### D. 权限、沙箱和 Human-in-the-loop

- Prompt Injection 可能来自用户、网页、仓库文档、工具结果和记忆。
- 模型输出不是授权；应用必须使用真实用户身份、最小权限和白名单。
- 路径 canonicalization、`..`、绝对路径、符号链接逃逸、敏感文件拒绝。
- 读、写、命令、网络按风险分级；高风险动作展示真实参数和影响后再审批。
- Shell 需要工作目录、命令/参数策略、超时、输出上限、环境变量隔离和可恢复操作。

MiniDev 任务：所有文件工具绑定 workspace root；默认拒绝 `.env`、凭据和工作区外路径；写文件使用 patch + diff；执行测试使用 allowlist；写/执行必须批准。

验收：路径逃逸、恶意 README、命令注入、未批准写入、敏感信息进日志等用例全部被确定性代码阻断。

#### E. Context、State、Checkpoint 与 Memory

必须分清：

- **Context**：本轮模型真正看到的有限输入。
- **State**：任务运行的权威结构化状态，不应只藏在对话文本中。
- **Checkpoint**：可恢复的运行快照，保证中断后继续。
- **Long-term Memory**：跨任务保留的经确认事实、偏好或经验，不等于把全部聊天写进向量库。
- **RAG**：按查询检索外部知识；它与记忆有重叠，但不是同一个概念。

MiniDev 任务：工具大输出渐进披露；旧 Observation 可裁剪/摘要；关键决策进入结构化 State；每个副作用前后建立 checkpoint。

验收：大文件不会撑爆上下文；压缩后关键约束不丢；中断恢复不重复写入或命令副作用。

#### F. Agent 可靠性与恢复

- 失败分类：模型、协议、工具、业务、权限、资源、用户取消。
- 重试必须考虑副作用与幂等；不是所有异常都可以重放。
- 长任务需要 timeout、heartbeat/checkpoint、取消和恢复策略。
- 多工具并行只用于相互独立的读操作；存在依赖或副作用时必须排序。

MiniDev 任务：对模型断连、Tool timeout、进程中断、磁盘错误、重复 Tool Call 做故障注入。

验收：每种失败都有确定终态；恢复后不重复副作用；无法恢复时给出可操作错误而非无限循环。

#### G. Agent Eval 与 Trace

- 最终结果：任务是否完成、测试是否通过、diff 是否符合要求。
- 轨迹：工具选择、参数、顺序、无效步骤、重复步骤、违规动作。
- 系统：成功率、P95、Token/成本、工具错误率、人工介入率、恢复率。
- Eval 需要固定环境、初始仓库版本、判分器和结果快照。

MiniDev 任务：建立 10—20 个小型仓库任务；同时保存 final result、trajectory 和 safety violation。

验收：修改 Prompt、模型、工具描述或编排后能与基线对比；测试失败不能被模型的“已经完成”覆盖。

#### H. Agent 中的检索与环境 Grounding

- 会比较全量 Context、确定性 `grep/rg`、结构化索引和语义 RAG；精确符号、路径、错误码通常先用词法或结构化搜索。
- 检索器可以是 Tool，但返回内容仍是不可信 Observation；必须带来源、版本、权限并受输出预算限制。
- Agent 项目的 RAG 价值不是“有向量库”，而是让模型以更少 Context 找到完成当前动作所需的可靠证据。

MiniDev 任务：让 `search_repo` 与 Repo QA Retriever 在同一批精确符号和自然语言问题上对照，Agent 根据任务类型使用更合适的检索方式。

验收：报告检索命中、步骤、Context Token、延迟和错误引用；不能用语义检索替代所有精确代码搜索。

### 6.2 AG-P1：Agent 岗应有一个真实实现

- MCP client/server：Tools、Resources、Prompts、transport、错误、超时、授权和能力协商；能解释 MCP 与 Tool Calling/本地 Registry 的边界。
- 持久运行：任务 API、SSE 事件、状态查询、取消、checkpoint 和 resume。
- Context 策略：摘要、工具结果清理、按需读取、长期记忆写入准入和冲突处理。
- 规划/反思/Reviewer：在明确判分标准下做一次对照实验。
- Tool/Skill 的发现与渐进加载；大量工具时控制 schema token 与误选率。
- 选择一个框架（如 LangGraph 或 Agents SDK）重写一个纵切，并与手写 Loop 比较可控性、调试性和恢复能力。

### 6.3 AG-P2：按 JD 或评测结果再做

- Planner/Coder/Reviewer 等复杂多 Agent；Agent-to-Agent 协议。
- 自适应长期记忆、自我改进、复杂反思树和开放式自治。
- Browser/Computer Use、任意 Shell、跨机器执行和大型沙箱平台。
- 大规模 MCP Registry、复杂 Skill 市场和多租户 Agent 平台。
- Agent 框架源码级研究。

## 7. 样本中反复出现的面试追问链

### 7.1 AI 应用开发岗

```text
介绍 RAG
  -> 文档为什么这样切
  -> Embedding 为什么这样选
  -> 只做向量召回有什么问题
  -> 如何混检和重排
  -> 怎么证明召回真的改善
  -> 接近 100% 是否数据泄漏或过拟合
  -> 更新/删除/多租户权限怎么办
  -> SSE 断开、模型超时、线上故障怎么办
```

```text
为什么选这个模型
  -> 质量、延迟、价格怎么测
  -> 长上下文是否就不需要 RAG
  -> Provider 不稳定怎么降级
  -> Prompt/模型升级怎么回归和回滚
```

### 7.2 Agent 开发岗

```text
Function Calling 怎么工作
  -> 模型还是应用执行函数
  -> 参数不合法怎么办
  -> 工具超时能否重试
  -> 有副作用如何避免重复执行
  -> 一直重复调用如何终止
  -> 怎样从 Trace 定位卡点
```

```text
为什么自研 Agent
  -> Loop 和状态怎样设计
  -> 新增 Provider / Tool 改哪些地方
  -> 上下文过长怎样处理
  -> 任务中断怎样恢复
  -> Memory 存什么、何时淘汰
  -> MCP 解决什么问题
  -> 为什么要或不要多 Agent
```

```text
Agent 可以改代码
  -> 如何限制工作区
  -> 如何阻止读密钥和间接 Prompt Injection
  -> 写文件/执行命令谁授权
  -> 如何展示真实 diff 和命令参数
  -> 测试通过是否足以证明修改正确
```

每条链都要准备：90 秒主干回答、两层追问、一个失败案例、一次可复现实验。

## 8. MiniDev 场景任务重排

### S0：修复跨组件契约假绿（2—4 个学习日）

**知识：** Python 依赖注入、调用方/适配器契约、Fake fidelity、异常归一化、SDK 与应用重试责任。

**任务：** 先增加“真实 `LLMClient` + Fake SDK + 真实 Runtime”的离线集成测试，复现当前 `ChatCompletionMessage` 被再次访问 `.choices` 的崩溃；再选择并统一 Client/Runtime 返回契约，同时明确只能由哪一层执行重试。

**失败实验：** 返回类型错配、429/超时/断连、SDK 内部重试叠加应用重试、坏 JSON、未知工具、最大步数。

**验收：** 组件测试和跨组件测试都通过；无 `.env`、无网络；失败尝试次数符合明确预算。修复前不得写“已集成”。

### S1：文档生命周期与关键词基线（4—6 个学习日）

**知识：** 文档 ID、内容 hash、版本、元数据、幂等 upsert、增量同步、删除传播、倒排索引/BM25。

**任务：** 摄取 Python/Markdown 文档，建立稳定 ID 和版本清单；先完成 BM25 检索基线，不接向量库。

**失败实验：** 重复上传、只改一份文件、删除后旧 Chunk/缓存仍可命中、失败摄取留下半成品。

**验收：** 重复导入数量不变；只重算变更内容；删除后所有索引和引用不可命中；固定题集报告 Recall@5/MRR@10。

### S2：真实解析与结构切块（5—8 个学习日）

**知识：** Parser adapter、Markdown 标题、代码 AST、PDF 阅读顺序、OCR 路由、表格结构、父子 Chunk 和 overlap。

**任务：** 保留现有固定行/AST 对照，加入 Markdown、文本 PDF、扫描 PDF、表格和失败文件 fixture；元数据保留文件、页码、标题、行号或 bbox。

**失败实验：** 标题与正文分离、函数签名与主体分离、表格列错位、中文断词、OCR 失败。

**验收：** 解析正确率和检索指标分开报告；坏文件被隔离；Chunk 选择必须由同一数据集的效果、Token 和 p95 决定。

### S3：Dense、Hybrid 与 Rerank（6—9 个学习日）

**知识：** Embedding、向量距离、Metadata Filter、Dense/Sparse、RRF、候选集与 Cross-encoder Rerank。

**任务：** 在 S1 同一数据集依次比较 BM25、Dense、Hybrid、Hybrid+Rerank，不另挑有利样本。

**失败实验：** 错误码/SKU 精确词漏召、同义改写漏召、同名符号错召、跨版本召回旧文档。

**验收：** 同时报告 Recall@5、MRR@10、p50/p95、候选数和成本；无可重复净收益的组件不保留。

### S4：可引用回答与证据门（5—7 个学习日）

**知识：** Context 组装、Grounding、Claim-Citation 对齐、Answerability/OOD、阈值校准、澄清和拒答。

**任务：** 每个事实性结论绑定可定位来源；证据门只允许“回答并引用 / 澄清 / 拒答”三类安全结果。

**失败实验：** 无答案也高相似、引用与结论不一致、来源过期、冲突文档、恶意文档指令。

**验收：** 至少 30 条可答和 20 条无答案/歧义题；检索、引用、Groundedness、拒答分开评分，不用单个总分掩盖失败。

### S5：SupportOps 客服业务闭环（7—10 个学习日）

**知识：** 意图/风险路由、静态知识与实时事实边界、结构化 Tool、会话所有权状态机、人工交接。

**任务：** 让错误码/文档问题走 RAG，让工单/服务状态走只读 API；高风险动作只生成待确认计划；实现一次可审计的人工转接包。

**失败实验：** 实时问题误走 RAG、API 不可用时编造、Tool 参数错误、已转人工 Bot 仍回复、Webhook 重放重复建单。

**验收：** 路由题集可复现；实时数据只能来自工具；人工接管后 Bot 零回复；交接包含 transcript、工具结果、引用和失败原因。

### S6：多租户、安全与副作用治理（6—9 个学习日）

**知识：** 服务端身份、tenant/ACL、fail closed、Prompt Injection、最小权限、幂等键、HITL、Checkpoint/Resume。

**任务：** 认证身份强制绑定检索过滤；读/写工具分级；写操作经权限和确认；恢复时复用幂等键。

**失败实验：** 请求伪造 tenant ID、权限撤销后旧索引可见、恶意知识文档诱导写工具、重复调用与断点重放。

**验收：** 跨租户负例零泄漏；恶意文档不能泄密或触发写工具；同一幂等键重放只执行一次。

### S7：服务化、评测、观测与恢复（7—10 个学习日）

**知识：** FastAPI、asyncio、SSE、取消、鉴权/配额、Run/Trace/Span、回归、Docker、备份与恢复。

**任务：** 提供流式问答、状态和人工交接 API；记录版本、耗时、TTFT、Token/成本和失败分类；完成一次索引快照恢复。

**失败实验：** 客户端断开、模型超时、并发打满、日志泄密、容器重启、索引损坏。

**验收：** API 自动化和小规模并发测试通过；任一失败可按 `run_id` 回放；新环境可启动并从快照恢复后跑回归。

### S8：作品与面试证据（持续）

- 每个核心模块保留架构图、ADR、关键代码、故障实验、指标报告和 Bad Case。
- 至少形成四段可复现故事：契约假绿、RAG 失败归因、业务路由/拒答、权限或人工交接。
- 简历只写已实现且有分母的数据；本地 Demo 不包装成生产流量。
- Multi-Agent、GraphRAG、复杂 MCP、微调、vLLM 和 Kubernetes 只有在目标 JD 或既有评测明确需要时再开支线。
- 继续准备 Python、后端基础和算法，不能被 AI 项目挤掉。

## 9. AI 生成、亲自决策与理解边界

标记：

- `G`：可以让 AI 生成初稿，但必须审查、运行和记录来源。
- `D`：学习者必须亲自做方案决策和核心实现；AI 可评审，不能替你拍板。
- `R`：不必源码级手写，但必须能画流程、解释机制、取舍和失败边界。

| 内容 | 标记 | 执行要求 |
|---|---|---|
| FastAPI 路由、Pydantic DTO、CLI、Dockerfile、测试夹具骨架 | `G + R` | AI 可生成；你决定接口语义、错误协议和验收 |
| Provider SDK 适配样板、序列化代码 | `G + R` | 必须核对官方文档并做契约测试 |
| 重试、超时、取消、熔断和重放边界 | `D + R` | 必须根据错误类型和副作用亲自决策 |
| Prompt 初稿和测试问题扩充 | `G` | 不能让同一模型生成题、答案并宣布自己通过 |
| Chunk、Embedding、检索、Rerank 方案 | `D + R` | 用同一评测集比较后选择 |
| 评测集目标、分母、标注和判分规则 | `D` | AI 可辅助扩样，金标与泄漏风险由你负责 |
| Agent Loop、Stop Reason、状态与恢复语义 | `D + R` | 必须亲手画状态机并实现关键路径 |
| Tool Schema、权限、路径沙箱、HITL | `D + R` | 安全边界不能外包给 Prompt |
| MCP/框架接入样板 | `G + R` | 必须解释抽象下的真实消息、失败和权限边界 |
| 多 Agent 是否采用 | `D` | 只依据消融结果，不依据流行度 |
| Transformer/训练/推理框架源码 | `R` 或按 JD 升级 | 当前只建概念地图，不占用应用工程 P0 时间 |

## 10. 两条岗位线的毕业标准

### 10.1 AI 应用开发岗可投递基准

- 能从业务问题判断不用 LLM、单次 LLM、RAG、Workflow 或 Agent。
- 能独立实现 Python/FastAPI 的模型服务，处理流式、超时、错误、鉴权、限流和部署。
- 能完整解释并实现 RAG 摄取、版本、检索、生成、引用、更新、删除与权限链路。
- 能把静态知识路由到 RAG、实时事实路由到业务 API，并在工具失败时停止猜测。
- 能实现高风险动作确认与可审计的人工交接；人工接管后机器人不继续回复。
- 有固定评测集，能分别定位检索失败和生成失败。
- 能用数据比较 Prompt、模型和检索方案的质量、延迟与成本。
- 有跨租户、删除传播、Prompt Injection、重复副作用等负例，并有至少一个真实 Bad Case 的修复前后证据。
- Python/算法/数据库/网络/操作系统等基础不因岗位带 AI 而缺失。

### 10.2 Agent 开发岗可投递基准

- 不依赖框架术语，能手画 Model ↔ Runtime ↔ Tool ↔ Environment 循环。
- 能实现可测试的单 Agent 状态机、Tool Registry、结构化错误和终止预算。
- 能解释并验证权限沙箱、审批、幂等、超时、取消、恢复和日志脱敏。
- 能区分 Context、State、Checkpoint、Memory、RAG、Skill 和 MCP。
- 有结果评测、轨迹评测和安全负例；可从 Trace 定位一次失败。
- 能用同一评测集解释为什么选择 Workflow/单 Agent/多 Agent。
- 能完成算法题，并具备真正的后端服务与工程交付能力。

## 11. 当前明确暂缓

- 同时学习 LangChain、LangGraph、LlamaIndex、AutoGen、CrewAI、Dify 的所有 API。
- 一开始就搭 Planner/Coder/Reviewer，多 Agent 先降为 P2。
- 没有检索基线和评测就上 Chroma + bge-m3 + Rerank 全家桶。
- 没有统一 RunEvent/Trace 数据模型就先搭 Langfuse。
- 为了简历关键字写多个无实际用途的 MCP Server。
- 开放任意 Shell、任意网络、自动覆盖文件或自动提交代码。
- Transformer 数学、后训练、CUDA 和推理集群的深挖；目标 JD 明确要求时再升级。
- 把 Prompt Engineering 学成“万能提示词模板”，或把框架源码考古当开发能力。

## 12. 一手技术依据

完整岗位列表、页面状态、GitHub issue、论坛线索和来源分级见 `AI_APP_MARKET_AND_REAL_SCENARIOS_2026-09-13.md`；本节只保留课程长期依赖的核心资料。

- [DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)：模型提出工具调用，实际函数由应用侧提供和执行；strict schema 也不替代业务与权限校验。
- [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)：优先简单、可组合方案；Workflow 与 Agent 的边界；复杂度必须由评测收益证明。
- [Anthropic Context Windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)：System、消息、工具描述和 Tool Result 都消耗 Context；长上下文仍需主动管理。
- [OpenAI Agents SDK — Tools](https://openai.github.io/openai-agents-python/tools/)：工具 Schema、超时、错误、审批和本地执行边界的参考实现。
- [OpenAI Agents SDK — Guardrails](https://openai.github.io/openai-agents-python/guardrails/)：输入、输出和 Tool Guardrail 的执行位置及边界。
- [OpenAI Agents SDK — Tracing](https://openai.github.io/openai-agents-python/tracing/)：Run、模型、工具、Guardrail 和 Handoff 的 Trace 结构。
- [LangChain Agent Evals](https://docs.langchain.com/oss/python/langchain/test/evals)：最终响应之外，还要评估 Tool Call 与完整轨迹。
- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)：持久执行、Streaming、Human-in-the-loop 与 Checkpoint 的运行时参考。
- [MCP Tools specification 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)：当前 Tools 协议、Schema、调用结果和安全要求。
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)：目标劫持、工具滥用、身份/权限、供应链、记忆和失控自治等风险清单。

## 13. 维护规则

1. 本文只在岗位样本、技术边界或课程结构发生变化时更新；完成状态写入 `PROJECT_PROGRESS.md`。
2. 新增技能前必须回答：哪个目标岗位或 Bad Case 需要它？不用它的基线是什么？验收指标是什么？
3. 简历写入某项技术后，该项自动升级为“简历 P0”，必须能接至少两层追问。
4. 所有指标注明数据集版本、分母、运行配置和日期；无证据不写百分比。
5. 每完成一个模块，至少留下代码/配置、正反测试、Trace/报告和 2—8 分钟口述提纲中的三类证据。
