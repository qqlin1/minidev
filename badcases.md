# Bad Case 日志

> **职责：失败证据层。** 记录 Agent/模型链路中的真实故障、分层根因、修复和回归，
> 为评测回归与面试追问提供证据；不承担运行时代码，也不把成功 Demo 当成质量证明。
>
> 面试第五层拷打（"最严重的一次失败是什么、怎么定位修复的"）的弹药库。
> 每次 agent 行为不符合预期就记一条，五要素写全。修完的坑必须在 W6 转化为评测回归用例。

## 记录模板

### [日期] 一句话现象
- **输入**：当时给 agent 的任务原话
- **现象**：预期 vs 实际（影响范围：必现/偶发）
- **根因**：分层排查后确认的原因（哪一层：上下文/检索/模型/工具/编排）
- **修复**：改了哪一层、为什么不能只改 prompt
- **回归**：怎么证明修好了且没引入新问题（对应哪个测试/case）

## 记录

### 2026-09-09 模型重试耗尽后，SDK 原始异常会泄漏到 CLI
- **输入**：故障注入任务：让注入到 `run_turn("请求模型", fake)` 的 Fake LLMClient 模拟“Client 已完成 3 次超时重试仍失败”。
- **现象**：预期是 Agent 以确定终态停止，并输出用户可读提示；实际是 `APITimeoutError` 直接从 Runtime 冒泡，CLI 没有 `Stop Reason`，调用方只能依赖 SDK 异常类型。影响范围为必现：只要 `LLMClient` 的可重试错误耗尽，旧实现都会走该路径。
- **根因**：模型适配层把最后一个 Provider SDK 异常原样抛出；Agent Runtime 只处理正常模型回复和最大步数，缺少“模型请求预算耗尽”的应用级错误契约与终态映射。这是**模型适配层 + 编排层**的边界缺失，不是 Prompt、工具或检索问题。
- **修复**：新增 `agent/llm/errors.py` 的 `ModelRetryExhaustedError(last_error, attempts)`；`LLMClient` 在 429、超时或连接错误耗尽后抛出它，并保留原始技术原因；`agent/runtime/v0.py` 捕获该稳定异常，返回 `AgentRunResult(stop_reason=MODEL_RETRY_EXHAUSTED)`，只向 CLI 输出“模型服务暂时不可用，已在 N 次尝试后停止。请稍后重试。”。不能只改 Prompt，因为模型请求尚未得到回复，Prompt 根本没有机会影响网络/Provider 故障。
- **回归**：`tests/agent/test_llm_client.py::test_timeout_retry_exhausts_and_raises` 断言 Client 保留 `APITimeoutError` 与 3 次尝试；`tests/agent/test_runtime_v0.py::test_run_turn_converts_model_retry_exhaustion_to_stop_reason` 断言 Runtime 返回 `MODEL_RETRY_EXHAUSTED`、不泄漏 `APITimeoutError`。2026-09-09 当时执行 `uv run pytest -q` 为 15 passed；这是历史组件测试数量，不证明 Client/Runtime 已集成。

> 限制：当前仅把“可重试错误已耗尽”转换为终态；400/401 等不可重试 Provider 错误尚未定义统一的 Agent 级错误协议，后续 Provider 契约阶段处理。

### 2026-09-13 27 项测试全绿，但真实 Client 与 Runtime 组合必崩

- **状态**：`DISCOVERED / UNFIXED`。本文只记录证据与修复方向；业务源码尚未修改，不能填写“回归通过”。
- **输入**：离线组合探针：Fake SDK 返回与 OpenAI Chat Completions 相同形状的 response，把它注入真实 `LLMClient`，再将真实 Client 注入 `run_turn("直接回答", llm_client)`。
- **现象**：预期 Runtime 获得 assistant message 并返回 `FINAL_ANSWER`；实际在 `agent/runtime/v0.py:140` 抛出 `AttributeError: 'ChatCompletionMessage' object has no attribute 'choices'`。与此同时，`uv run pytest -q` 的 27 项测试全部通过。
- **根因**：`agent/llm/client.py` 的 `chat()` 已执行 `response.choices[0].message` 并返回 message；Runtime 又执行一次 `resp.choices[0].message`。Client 单测认可“返回 message”，Runtime Fake 却返回“带 choices 的 response wrapper”，两个 Fake 契约不一致，且缺少穿过真实 Client/Runtime 边界的集成测试。这是**适配器返回契约 + 测试替身真实性**问题，不是 Prompt 或模型质量问题。
- **拟修复**：先新增一条会失败的跨组件测试，覆盖直接回答与 Tool Round Trip；再确定项目内部唯一的 AssistantMessage/DTO 或 Protocol，让 Provider Adapter 只归一化一次，Runtime 不依赖 SDK wrapper。同时核对 SDK 默认重试，避免 SDK 和应用重试次数相乘。
- **待回归**：修复后必须记录新增测试名、先红后绿证据、27 项既有测试无退化、实际总尝试次数，以及更新后的总测试数。在这些证据出现前，状态保持 `UNFIXED`。
