"""Agent Runtime 子包 — Agent Loop / 状态机运行时。

职责：承载工具调用循环、停止条件、步骤预算与终态映射。

当前：
- `v0.py`：W1 学习版（CLI + Loop + 临时工具合并在一个文件）

后续规划（有场景再拆）：
- `tools/`：工具注册与执行器
- `state/`：RunState / Checkpoint
"""
