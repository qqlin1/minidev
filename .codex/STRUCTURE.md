# MiniDev 目标结构（改造前 → 改造后）

> 原则：package-by-feature（一个能力一个包）；层是包内文件，不是顶层目录；
> 入口与领域代码分离；tests 镜像包结构；不提前建空目录。

## Before（扁平 / 混层）

```text
minidev/
  agent_v0.py          # CLI + Loop + 工具 混在根目录
  hello_api.py         # Provider smoke 也在根目录
  agent/
    __init__.py
    llm/
      client.py
      errors.py
  repo_qa/
    __init__.py
    models.py          # ① Schema 与 ② 策略同层
    chunking.py        # ②③④ 挤在一个函数文件
  tests/
    test_agent_v0.py
    test_llm_client.py
    test_repo_qa_chunking.py
    test_repo_qa_models.py
  README.md
  pyproject.toml
  ...
```

问题：
1. Agent 运行时入口散落在仓库根，和工程配置混在一起。
2. `repo_qa` 扁平两文件，chunking 四层无法按子包演进（策略/配置/评测接不上）。
3. tests 扁平，加 retrieval 后命名会失控。
4. 调用方依赖 `sys.path.insert`，不是可安装包形态。

## After（package-by-feature + 入口层）

```text
minidev/
  # ---------- 产品纵切 1：Repo QA ----------
  repo_qa/
    __init__.py
    chunking/              # ② 切块能力收拢为一个子包
      __init__.py          # 对外只导出 Chunk / split_text_into_chunks
      models.py            # ① Schema
      pipeline.py          # 固定行数策略 + Quality Gate（④ 运行时）

  # ---------- 产品纵切 2：Safe Coding Agent ----------
  agent/
    __init__.py
    llm/                   # 已有：模型适配
      __init__.py
      client.py
      errors.py
    runtime/               # Agent Loop / 运行时（W1 仍合并在 v0 单文件）
      __init__.py
      v0.py                # 原 agent_v0.py；uv run -m agent.runtime.v0

  # ---------- 入口层（只放可执行脚本，不含业务逻辑） ----------
  apps/
    __init__.py
    hello_api.py           # Provider smoke：uv run -m apps.hello_api

  # ---------- 测试：镜像包结构 ----------
  tests/
    repo_qa/
      test_chunking_models.py
      test_chunking_pipeline.py
    agent/
      test_runtime_v0.py
      test_llm_client.py

  # ---------- 工程配置 / 文档（留在根） ----------
  README.md
  pyproject.toml           # + pythonpath = ["."]，测试不再 sys.path hack
  prompt-log.md
  badcases.md
  .env.example
  .gitignore
```

## 命令变化

| 场景 | Before | After |
|---|---|---|
| Agent CLI | `uv run agent_v0.py` | `uv run -m agent.runtime.v0` |
| Provider smoke | `uv run hello_api.py` | `uv run -m apps.hello_api` |
| 离线测试 | `uv run pytest -q` | 不变 |

## 刻意不做

- 不拆 `v0.py` 内部 runtime/tools（W1 学习叙事保留；下一步再拆）。
- 不建空的 `indexing/`、`retrieval/`。`repo_qa/eval/` 已随 Chunk 场景建立，但当前只评估答案区间是否被 Chunk 包含，不代表检索或问答质量。
- 不改 `Chunk` / `LLMClient` 语义，只动目录与 import。
