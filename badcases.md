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

### 2026-09-13 记录 / 2026-09-17 修复：49 项测试全绿，但真实 Client 与 Runtime 组合必崩

- **状态**：`FIXED`（2026-09-17）。修复与回归证据见下；本案例从 `DISCOVERED / UNFIXED` 关闭。
- **输入**：离线组合探针：Fake SDK 返回与 OpenAI Chat Completions 相同形状的 response，把它注入真实 `LLMClient`，再将真实 Client 注入 `run_turn("你好", llm_client)`。
- **现象**：预期 Runtime 获得 assistant message 并返回 `FINAL_ANSWER`；实际在 `agent/runtime/v0.py:140` 抛出 `AttributeError: 'ChatCompletionMessage' object has no attribute 'choices'`。与此同时，`uv run pytest -q` 的 27 项测试全部通过（2026-09-17 补齐过滤后为 49 项，仍然全部通过）。**这是本次故障最值得记的一点：绿灯数量和真实可运行性无关。**
- **根因**：`agent/llm/client.py` 的 `chat()` 已执行 `response.choices[0].message` 并返回 message；Runtime 又执行一次 `resp.choices[0].message`。**同一次「去皮」被做了两遍**——Client 已经把 SDK 的壳剥掉交出去了，Runtime 却对着已经剥好的东西再剥一次，第一个 `.choices` 就落空。两个 Fake 契约不一致（Client 单测认可"返回 message"，Runtime 的 Fake 却返回"带 choices 的 wrapper"），且缺少穿过真实 Client/Runtime 边界的集成测试。这是**适配器返回契约 + 测试替身真实性**问题，不是 Prompt 或模型质量问题。
- **修复**：分两处，缺一不可。
  1. **Runtime 去掉第二次去皮**（本次修 bug 的正解）。`agent/runtime/v0.py:140` 由 `msg = resp.choices[0].message` 改为 `msg = resp`。选这一侧的判据是**依赖方向**：Provider SDK wrapper 是 Client 的实现细节，Runtime 不该知道它长什么样；Client 作为适配器，职责就是把 SDK 形状翻译成项目内部形状，只翻译一次。
  2. **测试替身对齐真货**（本次修假绿的镜像）。`tests/agent/test_runtime_v0.py:45` 由 `return SimpleNamespace(choices=[SimpleNamespace(message=response)])` 改为 `return response`。只改第一处的话，Runtime 改成吃 message 了、Fake 还在交 wrapper，7 项测试会从"假绿"翻成"真红"——**同一个 bug 的镜像**。这印证了那条规则：Fake 的返回形状必须抄真货，一个字段都不能多不能少。
- **附带修复**：查到 `OpenAI(...)` 未显式传 `max_retries`，SDK 默认 `2`（共 3 次尝试），而应用层 `LLMClient.max_retries=3`，两者相乘最坏 **9 次**真实请求。已在 `client.py` 显式传 `max_retries=0`，让应用层成为唯一重试责任人；实测 `OpenAI().max_retries` 为 `2`，改动后在测试中断言为 `0`。
- **回归**（2026-09-17 执行）：
  - 新增 `tests/agent/test_client_runtime_contract.py`（6 项），用假 SDK 驱动真实 `LLMClient`、再注入真实 `run_turn`，覆盖：Client 返回契约（有 content/tool_calls、无 choices）、SDK 内部重试为 0、直接回答、Tool Round Trip、Runtime 不再二次去皮、以及把当年崩溃形状固定下来供对照。
  - `tests/agent/test_runtime_v0.py` 7 项由红转绿（同类契约变更的镜像修复）。
  - 全量：`uv run pytest -q` → **55 passed，exit 0**（修复前 49 passed；新增 6 项）。原 49 项零退化。
  - 修复前必崩、修复后走通的证据已由 `test_real_client_drives_real_runtime_for_direct_answer` 常驻持有，不再依赖一次性脚本 `_repro_contract_bug.py`（已删除）。
- **面试可讲点**：这个案例的价值不在"修了一个 AttributeError"，而在**"49 个测试全绿不代表能跑"**。两组组件测试各自使用了对自己有利的假货，凑在一起条件成立、分开看全对——**假绿是两边一起错、错得对称**。定位手段是造一个穿过真实边界的探针，而不是继续加组件测试。详见 `.codex/S0_RUNTIME_EVIDENCE.md`。

> 已知残留：`test_runtime_v0.py` 的 7 项测试此前的"绿"属于假绿已修正，但**同类风险仍在**——任何新增的 Fake 若未对齐真货形状，都会复现同一个坑。防御手段是保持 `test_client_runtime_contract.py` 这类跨边界测试，新增适配器时同步补一条。

