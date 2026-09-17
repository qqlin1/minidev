# Agent 项目分层调研与 MiniDev 对照

> 用途：记录本项目参考成熟 Agent 项目的分层方式，并把“文件名 → 职责 → 边界”固定下来。
> 结论不是照搬某个框架，而是提取多个成熟项目反复出现的边界。

## 1. 查询范围

本次查询了三个维护中的 Python Agent 项目官方仓库。GitHub 的 `main` 会持续变化，下面同时记录查询到的树 SHA，方便回看当时的文件结构：

1. [OpenAI Agents SDK](https://github.com/openai/openai-agents-python/tree/544b8b03b8cf95e62c7f5ebb89adfc4bd66c9d1f)
2. [LangGraph](https://github.com/langchain-ai/langgraph/tree/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1)
3. [Pydantic AI](https://github.com/pydantic/pydantic-ai/tree/62f1e8302a356d09962c55117f41a282cf1eb243)

它们不是唯一的“标准答案”，但都是有清晰运行时、工具、模型和测试边界的代表性实现。

## 2. OpenAI Agents SDK：配置、Runner、模型和工具分开

核心目录：[src/agents](https://github.com/openai/openai-agents-python/tree/544b8b03b8cf95e62c7f5ebb89adfc4bd66c9d1f/src/agents)

| 文件/目录 | 主要职责 | 不负责什么 |
|---|---|---|
| `agent.py` | 定义 Agent 的身份、指令、工具、guardrail、handoff 等运行配置 | 不直接承担完整的底层 HTTP 重试实现 |
| `run.py` | 对外提供运行入口，管理一次 Agent Run 的生命周期 | 不把 Provider 的请求细节散落到业务工具中 |
| `models/interface.py` | 定义模型抽象接口，规定如何获得普通/流式响应 | 不决定具体 Agent 业务流程 |
| `models/openai_*.py` | OpenAI Responses/Chat Completions 适配 | 不定义工具的业务权限 |
| `model_settings.py` | 集中管理 temperature、tool choice、reasoning 等模型参数 | 不保证所有 Provider 都支持所有字段 |
| `run_internal/run_loop.py` | 内部编排模型回合、工具执行、审批、guardrail 和终止 | 不作为用户直接调用的公共 API |
| `run_internal/model_retry.py` | 归一化模型错误，依据网络/超时/Provider 建议决定重试 | 不重放已经产生副作用的任意工具 |
| `tool.py` | 工具定义、Schema、参数解析、调用包装、工具错误和工具 guardrail | 不让模型直接获得本地执行权限 |
| `run_state.py` | 序列化运行状态、恢复中断任务、保存工具调用身份 | 不等同于长期用户记忆 |
| `memory/session.py` | 会话历史的存取接口和实现 | 不负责模型推理 |
| `tracing/` | Trace、Span、模型/工具调用观测 | 不改变 Agent 的业务结果 |
| `sandbox/` | 工作区、文件、Shell、快照和沙箱运行时 | 不把任意本机能力默认暴露给模型 |
| `testing/model.py` | 可编排的 Fake/Testing Model，支持确定性测试 | 不作为生产模型适配器 |

最值得 MiniDev 学习的关系是：

```text
Agent 配置
  -> Runner / Run Loop
      -> Model 抽象 -> Provider Adapter
      -> Tool 定义 -> Tool Executor
      -> RunState / Session
      -> Trace / Result
```

## 3. LangGraph：图定义、运行时、状态和持久化分层

核心目录：[libs/langgraph/langgraph](https://github.com/langchain-ai/langgraph/tree/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/langgraph/langgraph)

| 文件/目录 | 主要职责 |
|---|---|
| `graph/state.py` | 定义 StateGraph、节点、边、Reducer，并编译成可执行图 |
| `pregel/main.py` | 对外的 Pregel/图运行入口，协调输入、输出、流式和执行上下文 |
| `pregel/_loop.py` | 执行 superstep、准备任务、处理中断、恢复和终止 |
| `channels/` | 节点之间传递和合并状态的 Channel 抽象 |
| `pregel/_checkpoint.py` | 创建、更新和恢复 checkpoint |
| `types.py` | RetryPolicy、TimeoutPolicy、CachePolicy、Interrupt、Command 等运行契约 |
| `prebuilt/chat_agent_executor.py` | 用 StateGraph 组合出常见 ReAct Agent |
| `prebuilt/tool_node.py` | 独立执行工具，负责并行、参数校验、错误回填和状态注入 |
| `_internal/` | 序列化、队列、重试、超时等内部基础设施 |

LangGraph 的关键思想不是“Agent 必须写成图”，而是把以下内容显式化：

```text
State Schema + Reducer
  -> Graph Definition
      -> Compiled Runtime
          -> Node / Tool
          -> Checkpoint
          -> Interrupt / Resume
          -> Stream / Debug
```

这说明 `messages` 不应永远只是一个局部 list；当任务需要恢复、并发或人工审批时，状态必须成为独立的结构化对象。

## 4. Pydantic AI：类型约束、ToolManager 和 Capability 中间件

核心目录：[pydantic_ai_slim/pydantic_ai](https://github.com/pydantic/pydantic-ai/tree/62f1e8302a356d09962c55117f41a282cf1eb243/pydantic_ai_slim/pydantic_ai)

| 文件/目录 | 主要职责 |
|---|---|
| `agent/abstract.py` | 对外 Agent 抽象和运行方法，定义依赖、指令、输出、重试等入口契约 |
| `_agent_graph.py` | 用户输入节点、模型请求节点、工具调用节点和下一轮决策 |
| `models/_abstract.py` | 所有模型共有的身份和能力边界 |
| `models/*.py`、`providers/*.py` | 各 Provider 的请求/响应适配 |
| `settings.py` | 通用模型设置，包括 thinking/reasoning 等，并声明 Provider 支持差异 |
| `tool_manager.py` | 工具发现、参数校验、验证结果和执行前控制 |
| `_tool_execution.py` | 工具执行、并行、延期、审批和工具结果转换 |
| `capabilities/` | 以可组合中间件扩展 Prompt、工具、模型、历史和事件处理 |
| `messages.py` | 统一模型消息、Tool Call、Tool Return 和流事件的数据结构 |
| `result.py`、`output.py` | 最终结果、结构化输出、流式结果和输出校验 |
| `retries.py` | 工具/输出重试和预算配置 |
| `durable_exec/` | 把运行和工具操作接入可持久化任务系统 |
| `models/test.py` | 测试模型和脚本化模型行为 |

Pydantic AI 对 MiniDev 最有价值的启发是：

- 模型配置可以统一，但必须承认 Provider 能力不一致；不能把 `reasoning_effort` 无条件发给所有模型。
- 工具参数校验和工具执行是两个阶段；参数合法不等于业务允许执行。
- Agent 的扩展能力适合放在 capability/middleware，而不是继续把所有逻辑塞进一个大循环。
- 测试模型是正式架构的一部分，不是临时 Mock。

## 5. 三个项目的共同分层

三个项目虽然 API 不同，但边界高度一致：

```text
入口层（CLI / API / SDK）
  -> Agent 配置层（instructions / tools / model settings）
  -> Runtime / Runner（循环、状态转移、预算、停止）
  -> Model Port（统一模型接口）
      -> Provider Adapter（OpenAI、DeepSeek、Anthropic 等）
  -> Tool Port（Schema、Registry、校验）
      -> Tool Executor（权限、超时、执行、副作用）
  -> State / Session / Checkpoint
  -> Result / Stream / Trace / Eval
  -> Testing Fakes
```

### 5.1 重试边界

- 模型 HTTP 重试属于模型适配或 Runner 的可靠性策略。
- 工具失败回填属于 Tool Executor 与 Runtime 的协作。
- 有副作用的工具不能因为模型请求失败就自动重放。
- `max_retries` 和 `max_steps/max_turns` 是不同预算，成熟项目会分开表达。

### 5.2 推理强度边界

“思考/推理强度”属于模型设置，但发送前要经过 Provider/Model capability 适配。它不应让 Agent Loop 直接拼接 Provider 私有字段。

MiniDev 当前只保留 `model`、`temperature`、重试配置；推理参数等到有真实模型和能力契约后再加入。

## 6. MiniDev 当前结构的判断

当前 `agent/runtime/v0.py` 把入口、工具、Schema 和 Loop 放在一个文件，这是学习版，优点是能看完整调用流；它还不是长期结构。

当前已经完成的第一步分层：

```text
agent/runtime/v0.py
  -> Agent Loop / CLI / 当前工具组合根 + AgentRunResult / StopReason
agent/llm/client.py
  -> Model Port + DeepSeek/OpenAI-compatible Adapter + 请求可靠性
agent/llm/errors.py
  -> 模型重试耗尽的应用级错误契约；不直接生成用户文案
tests/agent/test_runtime_v0.py
  -> Runtime 的 Fake Client 测试
tests/agent/test_llm_client.py
  -> Provider Adapter 的故障注入测试
```

2026-09-13 复核发现：Client 测试把 `chat()` 契约定义为返回 message，Runtime Fake 却返回 SDK response wrapper，真实组合会在 Runtime 再次访问 `.choices` 时失败。因此上述两组只能算组件级分层，不能作为已集成证据；S0 必须补一条跨真实组件的契约测试。

后续按学习路线逐步拆分，而不是现在一次搬空：

```text
agent/
  runtime/          # 当前已有：状态、循环、停止和预算的 v0
  llm/              # 当前已有：模型配置、Provider 适配、重试、流式
  tools/            # 后续按业务需要：Registry、Schema、权限和工具执行
  state/            # 后续按业务需要：RunState、Checkpoint、Resume
  observability/    # SupportOps 服务化阶段：RunEvent、Trace、成本和延迟
  eval/             # Agent 支线需要时：固定数据集、轨迹和安全评测
apps/               # 当前 Provider smoke；后续 FastAPI/CLI 入口
repo_qa/            # 当前主线：Chunk 已有，摄取/检索/引用/拒答待实现
```

现在不应为了模仿框架而提前创建所有目录；每拆一层都要绑定一个真实场景、测试和失败证据。

## 7. 对本项目文件注释的约定

以后打开文件，顶部应该能回答三件事：

1. 这个文件属于哪一层？
2. 它负责什么？
3. 它明确不负责什么？

本轮已按此约定给当前非依赖源码和测试文件补充模块说明。`uv.lock`、`.venv`、`.idea`、`__pycache__` 等生成/依赖/IDE 文件不加入业务职责注释。
