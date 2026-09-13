"""模型适配子包。

职责：集中放置模型配置、Provider 适配、请求可靠性、流式响应和模型调用契约。

边界：这里不决定 Agent 的规划、工具选择、权限和任务终止；这些属于 Agent Runtime
及 Tool Executor。当前具体实现见 `client.py`。
"""
