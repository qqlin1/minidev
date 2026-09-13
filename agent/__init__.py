"""MiniDev Agent 核心包 — Safe Coding Agent 纵切。

职责：作为 Agent 领域代码的包边界。

当前子包：
- `llm/`：模型适配、Provider 重试、错误契约
- `runtime/`：Agent Loop（W1 版 `v0`）

后续规划（有场景再建）：
- `tools/`、`state/`、`observability/`、`eval/`

本文件目前只提供包说明，不创建客户端、不读取 API Key，也不产生运行时副作用。
"""
