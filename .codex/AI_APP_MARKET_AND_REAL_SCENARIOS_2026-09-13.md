# 2026 校招 AI 应用岗位与真实开发场景调研

> 调研日期：2026-09-13
>
> 目标：为 2027 届 AI 应用开发 / 大模型应用开发方向确定项目边界、学习顺序和验收证据。
>
> 本文记录岗位与外部场景证据；课程边界见 `AI_APP_AGENT_LEARNING_ROADMAP_2026.md`，动态完成状态见 `PROJECT_PROGRESS.md`。

## 1. 结论

本地知识库和客服可以作为校招项目入口，但“上传 PDF → 向量化 → 调模型回答”只达到演示级。岗位和真实工程问题共同要求继续补齐：

1. Python 与后端工程：API、数据库、异步/流式、异常、测试和部署。
2. 完整 RAG：摄取、解析、版本、Chunk、关键词/向量检索、混检、重排、引用和拒答。
3. 评测与观测：固定数据集、分层指标、Trace、延迟、Token/成本和 Bad Case。
4. 业务边界：静态知识走 RAG，实时事实走业务 API，高风险写操作走确定性权限和人工确认。
5. 生产边界：增量更新与删除、多租户 ACL、Prompt Injection、幂等、转人工和恢复。

因此 MiniDev 的推荐终局是：

> **MiniDev SupportOps：面向企业开发者平台的多租户技术客服与内部知识支持系统。**

Repo QA 继续作为第一个 RAG 纵切；SupportOps 复用其摄取、检索、引用和评测底座，再加入实时工具、权限和人工交接。已有 Safe Coding Agent 只保留 Tool Loop 与安全实验，不与主作品争夺范围。

## 2. 调查方法与可信边界

### 2.1 岗位样本

- 抓取日期：2026-09-13。
- 样本：15 家不同公司，每家公司只计 1 个岗位，避免同公司重复放大。
- 检索范围：明确涉及 AI 应用、LLM 应用、RAG、知识库、Agent 或智能体的校招/实习岗位。
- 这是关键词筛选后的便利样本，不是随机抽样，不能代表整个招聘市场，也不能把 `14/15` 解读为“市场上 93% 的岗位都要求 RAG”。
- 职责、任职要求或加分项明确出现才计数；加分项被计为“出现”不等于硬门槛。
- 已结束岗位只用于分析企业曾明确提出的能力，不能表述为仍在招聘。
- 招聘平台的投递时间、高校就业网发布时间和实习平台刷新时间不是同一口径；投递前必须回公司官网复核。

### 2.2 来源分级

- **Job-A：公司招聘官网具体岗位。** 一手来源，优先确认岗位内容和投递状态。
- **Job-B：高校就业网具体岗位。** 通常包含企业信息、官方投递地址和发布时间，属于较强二手来源。
- **Job-C：牛客、实习僧等招聘平台具体岗位。** 可分析能力要求，但可能转载、过期或状态异常。
- **Forum：论坛、面经和个人自述。** 只用于发现追问和工程问题，不纳入岗位频次，也不作为市场统计。

GitHub issue 证明某个具体版本或程序中有人报告过该故障，不代表所有项目或当前版本仍存在同一问题。

## 3. 15 家公司岗位样本

### 3.1 能力频次

| 能力项 | 出现数 / 15 | 样本内含义 |
|---|---:|---|
| 实际软件或系统工程开发 | 15/15 | AI 应用岗不是只写 Prompt 或调用模型 API |
| RAG、知识库或检索 | 14/15 | 是本批应用型岗位的基础能力 |
| 项目、实习、课程项目或开源证据 | 14/15 | 可演示、可追问的实践明显比“了解原理”重要 |
| 具名 Agent/LLM 应用框架 | 12/15 | 包括 LangChain、LangGraph、LlamaIndex、Dify、AutoGen、CrewAI 等 |
| 明确点名 Python | 12/15 | Python 最通用，但也存在 Go、Java、TypeScript 入口 |
| Prompt Engineering | 11/15 | 属于基础能力，不能单独构成项目亮点 |
| Tool Calling、Function Calling 或 MCP | 10/15 | 是普通问答与 Agent 应用的重要分界 |
| 评测、可观测或实验闭环 | 10/15 | 需要证明效果、成本、延迟和稳定性 |
| 明确要求硕士及以上 | 8/15 | 样本偏技术岗，不能据此推断本科没有入口 |
| SQL、关系数据库或向量数据库 | 5/15 | JD 可能省略，但完整 RAG 项目仍需掌握 |
| 微调或 Post-training | 5/15 | 多为算法岗或加分项，不是应用开发入门第一优先级 |
| 流式、异步或并发 | 4/15 | 是区分课程 Demo 与工程项目的能力 |
| 权限、沙箱、输出过滤等安全机制 | 2/15 | JD 中低频，但生产风险高，适合作为差异化证据 |

### 3.2 完整样本

| # | 公司与岗位 | 层级 | 页面时间及抓取时状态 | 代表性要求 |
|---:|---|:---:|---|---|
| 1 | [百度：2027AIDU-Agent 应用全栈工程师](https://talent.baidu.com/jobs/detail/GRADUATE/6f9c3a86-6557-409d-8fa7-e6f4c68d6765) | Job-A | 2026-07-21；官网具体岗位 | Planning/Acting/Reflection、Tool/API、Memory、RAG、Eval、成本和延迟 |
| 2 | [拼多多：27 届提前批 AI Agent 研发工程师](https://career.nankai.edu.cn/correcruit/content/id/116275.html) | Job-B | 2026-07-13；是否仍开放需回官网 | 规划、记忆、工具、RAG、缓存、MQ、异步、安全、沙箱、可观测 |
| 3 | [神州信息：AI Agent 开发工程师](https://career.nankai.edu.cn/correcruit/content/id/117965.html) | Job-B | 2026-09-07；投递状态需官网确认 | 金融客服/风控/运营助手、Python、向量库、RAG、Prompt、评测 |
| 4 | [北方华创：Agent 开发工程师](https://www.career.zju.edu.cn/jyxt/sczp/zpztgl/ckZpgwXq.zf?zpxxbh=57D1C5700C9202A7E0653A68DD0E9B18) | Job-B | 页面时间 2026-08-04，页面标注截止 2027-05-31 | 经营分析、研发效能、Workflow、多模型路由、Tool、Skill、知识库 |
| 5 | [广联达：27 届 AI Agent 开发工程师](https://www.nowcoder.com/jobs/detail/466398) | Job-C | 2026-09-01 起；结束时间异常 | FastAPI、数据库/向量库、RAG、AgentOps、评测 |
| 6 | [字节跳动：抖音 Agent 开发实习生](https://www.shixiseng.com/intern/inn_pceqm0fghwlg?pcm=pc_SearchList) | Job-C | 2026-08-14 刷新，页面截止 2026-09-14 | TypeScript、React/Vue、SSE、WebSocket、Agent 状态和工具链可视化 |
| 7 | [彩讯科技：AI Agent 应用开发工程师实习](https://www.nowcoder.com/jobs/detail/438217?urlSource=sitemap) | Job-C | 页面投递截至 2026-06-30；已过期 | EVAL、GraphRAG、混检、Milvus、Kubernetes、OpenTelemetry |
| 8 | [美的：大模型应用研发实习生](https://www.shixiseng.com/intern/inn_ei0l6vsctofy) | Job-C | 2026-08-03 刷新；已下线 | Dify、Python、FastAPI、异步、系统集成、日志和文档 |
| 9 | [携程：2027 届 Agent 开发工程师实习](https://www.nowcoder.com/jobs/detail/434803) | Job-C | 页面投递截至 2026-06-30；已结束 | Agent 框架、记忆一致性、评测观测、注册、发现和部署 |
| 10 | [千里科技：AI 开发实习生](https://www.nowcoder.com/jobs/detail/30300000146406?channel=npJobTab&deliverSource=1&pageSource=5001) | Job-C | 页面日期 2026-08-18；抓取时提供投递 | 数据/运营 Agent、私有知识库、切片、向量化、API 联调和部署 |
| 11 | [阿里云：2027 届大模型应用开发实习](https://www.nowcoder.com/jobs/detail/440351?urlSource=sitemap) | Job-C | 页面投递截至 2026-06-30；已结束 | RAG 切片/召回/重排、LLMOps、标注、Memory、Tool、MCP |
| 12 | [普渡科技：Agent 开发工程师](https://www.nowcoder.com/jobs/detail/460226) | Job-C | 2026-08-17 至 2026-12-31；抓取时可申请 | AI 服务架构、RAG、MCP、Function Call、记忆、延迟和并发 |
| 13 | [快手：大模型应用算法工程师](https://www.nowcoder.com/jobs/detail/458197?urlSource=sitemap) | Job-C | 2026-08-06 至 2026-10-31；抓取时可申请 | 对话、代码、电商、多模态、Agent、RAG、Function Call、微调 |
| 14 | [中国电子云：2027 Agent 开发工程师](https://www.nowcoder.com/jobs/detail/463592) | Job-C | 2026-08-26 至 2026-12-01；抓取时可申请 | Go、Eino、LangGraph、Workflow、端到端性能优化 |
| 15 | [新石器无人车：Agent 开发工程师](https://www.nowcoder.com/jobs/detail/452237?urlSource=sitemap) | Job-C | 2026-07-03 起；异常结束时间需官网复核 | 记忆、规划、反思、第三方 API、企业系统、权限、CS 基础 |

## 4. MiniDev SupportOps 业务边界

```text
文档 / 代码 / 扫描件 / 表格
  -> 解析校验 -> 版本化 -> Chunk -> BM25 + Vector Index
  -> Tenant/ACL Filter -> Hybrid/Rerank -> Citation

用户消息
  -> 身份与意图/风险路由
      -> 静态知识：RAG
      -> 实时事实：订单/服务状态/工单 API
      -> 高风险动作：确定性规则 + 权限 + HITL
  -> Evidence Gate
      -> 回答并引用 / 澄清 / 拒答 / 转人工
  -> Eval + Trace + Cost/Latency + Audit
```

| 请求示例 | 权威数据源 | 系统责任 |
|---|---|---|
| “错误码 `MODEL_RETRY_EXHAUSTED` 是什么意思？” | 代码与技术文档 RAG | 检索并引用；证据不足时拒答 |
| “我的工单处理到哪了？” | 实时工单 API | 校验身份后查询；不能从向量库猜 |
| “按文档看这个故障是否符合退款/补偿条件？” | 政策 RAG + 实时服务状态 + 规则代码 | 收集证据，资格由确定性规则判断 |
| “直接替我执行退款/重跑任务” | 有副作用的业务工具 | 展示真实参数，经权限和人工确认后执行 |
| “资料里没有说明” | 无可靠来源 | 澄清、拒答或转人工 |
| “我要人工客服” | 工单与会话系统 | 建立一次交接记录，并停止机器人继续回复 |

## 5. 真实故障场景课程

下表数字是 **MiniDev 建议验收线，不是行业统一 SLA**。每份报告必须同时记录数据集版本、分母、模型、代码版本、语料规模、硬件和日期。

| # | 真实问题 | 要学的责任边界 | MiniDev 案例与建议验收 |
|---:|---|---|---|
| 1 | PDF 能打开，但阅读顺序、中文词或表格行列抽错 `[TB1][TB2]` | Parser adapter、OCR 路由、表格结构、页码/bbox、失败隔离 | 五类 fixture；40 个关键字段至少正确 38 个；失败文件不能留下半成品索引 |
| 2 | 固定切块分开标题、主体、表格或定义 `[TA1]` | 结构切块、标题继承、父子 Chunk、overlap、按数据集选型 | ≥40 条带源位置检索题；同时报告 Recall@5、MRR@10、Context Token 和 p95 |
| 3 | 重复上传产生重复向量；更新/删除后旧内容仍可召回 `[TA2][TB3][TA3]` | 稳定 doc ID、hash、版本、幂等 upsert、删除传播、回滚 | 重复导入数量不变；只重算变更文档；删除后所有索引/缓存/引用均不可命中 |
| 4 | 漏一次 tenant filter 就可能串库 `[TA4][TB4]` | 服务端身份、强制 ACL、fail closed、权限同步 | 请求体 tenant ID 不作授权依据；跨租户负例零泄漏；Trace 保存实际 tenant/ACL version |
| 5 | 静态政策与实时业务状态混进 RAG 后产生过期答案 `[TA5]` | Intent/router、RAG/API 分流、结构化工具、降级 | 60 条路由题；实时问题必须查工具，API 失败明确无法核实，不能编造 |
| 6 | 纯向量漏错误码/SKU，纯 BM25 不理解改写 `[TA6]` | Dense、BM25、RRF、候选集、Rerank | 对比四条链的 Recall/MRR/p50/p95；只有同集改善才增加复杂度 |
| 7 | 无关问题也可能有较高相似度，“score > 0.7”不是概率 `[TB5][TA7]` | 阈值校准、证据充分性、OOD、澄清、拒答、逐项引用 | 30 可答 + 20 无答案/歧义；无依据安全拒答，引用可定位真实页/章节/chunk |
| 8 | 对话和 Tool Result 持续回灌导致 Context 膨胀、旧错误复活 `[TA8]` | Context、结构化 State、短期历史、摘要、Memory 的区别 | 50 轮不超设定预算；纠正后的旧值不复活；tenant/user/thread 零串线 |
| 9 | Tool 参数错、超时、重复调用和 checkpoint 重放造成死循环/重复副作用 `[TA9][TB6]` | Schema、错误分类、有限重试、幂等键、读写分级、HITL | 覆盖非法 JSON/400/429/500/timeout；相同幂等键重放只执行一次；有确定步数终态 |
| 10 | 已转人工但 Bot 继续回复；Webhook 重放创建多张工单 `[TB7][TA5]` | 会话所有权状态机、交接包、事件幂等 | 每次只建一张工单；交接含 transcript/动作/结果/引用/失败原因；人工接管后 Bot 零回复 |
| 11 | 只看最终答案，无法定位解析、召回、重排还是生成失败 `[TA10]` | 黄金集、检索/生成分层 Eval、Trace、版本、成本 | 初期 60—100 条人工核验题；每次请求可按 run ID 归因和回放；回归阈值由基线后确定 |
| 12 | 恶意知识文档诱导写工具；本地部署没有认证、备份或恢复 `[TA11][TA12]` | 间接 Prompt Injection、最小权限、代码级 Action Gate、恢复 | 恶意输入不能泄密或触发写工具；Qdrant 不裸露公网；重启/快照恢复后回归通过 |

## 6. 强来源索引

### 6.1 Tech-A：官方文档与源码

- `[TA1]` [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)：切块局部语境、BM25、Embedding 与 Rerank 的组合取舍。
- `[TA2]` [LlamaIndex BaseIndex 源码](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/indices/base.py)：文档 hash 与更新/删除行为。
- `[TA3]` [Elastic Content Syncs](https://www.elastic.co/docs/reference/search-connectors/content-syncs)：full/incremental sync 与源端删除同步。
- `[TA4]` [Qdrant Multitenancy](https://qdrant.tech/documentation/manage-data/multitenancy/) 与 [Elastic DLS](https://www.elastic.co/docs/reference/search-connectors/es-dls-overview)：租户分区和文档级权限。
- `[TA5]` [Chatwoot AgentBot](https://www.chatwoot.com/hc/user-guide/articles/1677497472-how-to-use-agent-bots)：知识回答、业务 API、身份筛选与人工转接。
- `[TA6]` [Qdrant Hybrid Queries](https://qdrant.tech/documentation/search/hybrid-queries/)：Dense/Sparse、RRF、多阶段查询和重排。
- `[TA7]` [LlamaIndex Citation Workflow](https://developers.llamaindex.ai/python/examples/workflow/citation_query_engine/)：来源不足时拒答并保留 source nodes。
- `[TA8]` [LangGraph Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)：长会话 trim、delete、summarize 与 checkpoint。
- `[TA9]` [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents) 与 [Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)：工具错误、状态与高风险动作审批。
- `[TA10]` [LangSmith RAG Evaluation](https://docs.langchain.com/langsmith/evaluate-rag-tutorial)：correctness、relevance、groundedness 与 retrieval relevance 分层评测。
- `[TA11]` [OWASP RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)：知识投毒、间接注入、权限和删除风险。
- `[TA12]` [Qdrant Production Checklist](https://qdrant.tech/documentation/production-checklist/) 与 [Snapshots](https://qdrant.tech/documentation/snapshots/)：认证、TLS、持久化、容量与恢复。

### 6.2 Tech-B：具体 GitHub issue

- `[TB1]` [Docling #1678](https://github.com/docling-project/docling/issues/1678)：表格列错位导致下游 LLM 错答。
- `[TB2]` [Docling #539](https://github.com/docling-project/docling/issues/539)：中文表格换行破坏检索。
- `[TB3]` [LlamaIndex #8832](https://github.com/run-llama/llama_index/issues/8832)：特定 PGVectorStore 刷新流程产生重复文档。
- `[TB4]` [Qdrant #8015](https://github.com/qdrant/qdrant/issues/8015)：认证身份到强制 tenant filter 的绑定仍依赖应用层。
- `[TB5]` [LlamaIndex #13913](https://github.com/run-llama/llama_index/issues/13913)：无关/乱码查询仍可能得到较高相似度。
- `[TB6]` [LangGraph #7417](https://github.com/langchain-ai/langgraph/issues/7417)：长工具从 checkpoint 被重复执行。
- `[TB7]` [Chatwoot #12](https://github.com/chatwoot/rasa-agent-bot-demo/issues/12)：会话切到 OPEN 后 Bot 仍继续回复。

### 6.3 Forum：论坛和面经，只作需求信号

- [Reddit：What does Production RAG look like?](https://www.reddit.com/r/Rag/comments/1usojml/what_does_production_rag_looks_like/)：讨论检索评测、权限、删除、索引新鲜度和审计。
- [牛客：腾讯大模型岗面经汇总](https://www.nowcoder.com/discuss/924823622970003456?sourceSSR=dynamic)：涉及解析、切块、向量库、上线性能、评测、成本、并发与 SSE；属于个人整理，不能当公司考纲。
- [牛客：阿里淘天 AI Agent 二面自述](https://www.nowcoder.com/feed/main/detail/a8cce58f881d4304b2b994b704069724?sourceSSR=dynamic)：追问错召、漏召、检索优化和指标；属于个人自述。

## 7. 对学习顺序的影响

1. 先修复当前 Client/Runtime 契约假绿，并统一重试责任层。
2. 做纯文本/代码摄取、稳定元数据和关键词检索基线。
3. 做 Markdown/PDF/OCR/表格与结构切块。
4. 在固定数据集上增加向量、Hybrid 和 Rerank；无净收益不保留。
5. 做可引用回答、证据门、澄清和拒答。
6. 加实时只读工具、业务规则、工单和人工交接。
7. 加 tenant/ACL、增量更新、删除、Prompt Injection 和幂等负例。
8. 最后完成 FastAPI/SSE、Trace、成本、Docker 和恢复演练。
9. Multi-Agent、GraphRAG、微调、复杂 MCP、vLLM 和 Kubernetes 只由目标 JD 或评测结果触发。

## 8. 最终作品必须留下的证据

- 一个解析失败及修复前后对比。
- 一次 BM25/dense/hybrid/rerank 的同数据集消融。
- 一个有引用回答、一个安全拒答、一个人工转接。
- 一次跨租户负例和一次 Prompt Injection 负例。
- 一次重复 Tool Call 幂等测试。
- 一次索引删除传播或快照恢复演练。
- 一份标明分母、版本、硬件、p95、Token/成本和 Bad Case 的报告。
- 一段能说明“数据从哪里来、如何流动、哪里失败、怎样证明”的项目口述。
