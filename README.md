# MiniDev —— 多智能体终端编程助手

理解任务 → 规划步骤 → 调用工具改代码 → 自我检查结果 → 知识库随查随用。
对标 Claude Code 的核心循环的简化实现，用于系统性学习 Python 多智能体构建。

**技术栈**：Python 3.13 · uv · OpenAI 兼容 API（DeepSeek） · pydantic · Chroma · bge-m3 · MCP · Langfuse · rich

## 里程碑

- [ ] W1 手写 Agent Loop（能调用工具）
- [ ] W2 工具系统 + ReAct 完整跑通
- [ ] W3 多智能体编排（Planner / Coder / Reviewer）
- [ ] W4 记忆 + 沙箱执行 + 流式 CLI
- [ ] W5 RAG 知识库工具 + MCP 接入
- [ ] W6 评测集 + Langfuse 观测 + 失败处理
- [ ] W7 压测修复 + 面试叙事打磨
- [ ] W8-9 OA 接入 Spring AI Alibaba（另仓库）
- [ ] W10 开源贡献 + 复盘

## 快速开始

```bash
uv sync
copy .env.example .env   # 填入 LLM_API_KEY
uv run hello_api.py      # W0 验收脚本
```

## 架构（W3 后补图）

```
minidev/
├── agent/      # core(循环/状态机/上下文) agents(三角色) tools memory llm
├── mcp/        # host + server
├── eval/       # cases/ run_eval.py report.md
├── ui/         # cli.py
└── tests/
```

## 评测报告（W6 填写）

| 指标 | 数值 |
|---|---|
| 解决率 | - / 20 |
| 平均步数 | - |
| 平均 token 成本 | - |
| p95 延迟 | - |

## 失败模式与处理（W6 填写）

- [ ] 工具报错 → 指数退避重试
- [ ] 死循环 → 最大步数熔断
- [ ] 上下文超限 → 历史压缩降级
- [ ] 模型超时 → 备用模型切换
