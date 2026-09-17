"""MiniDev Repo QA — AI 应用纵切。

职责：为仓库代码与文档提供可引用、可拒答、可评测的 RAG 能力。

当前已落地子能力：
- `ingest/`：磁盘文件 → 可切块的文档（扫描 + 准入 + 读取 + 内容指纹）
- `chunking/`：文本 → 可引用 Chunk（Schema + 策略 + 配置 + 过滤 + 编排）
- `eval/`：固定场景集 + 策略对照（④ 的评测半边）

数据流与依赖方向（单向，不循环）：

    ingest ──> [调用方] ──> chunking ──> eval
      ↑                        ↑
      └── 互不依赖 ────────────┘

`ingest` 不知道 `Chunk` 长什么样，`chunking` 不知道文件在磁盘哪里。
调用方同时依赖两者，把 `doc.text` 交给 `chunk_text(path=doc.path, ...)` 完成交接。

后续规划子包（有场景再建，不空占）：
- `indexing/`、`retrieval/`、`qa/`
"""

from .chunking import Chunk, ChunkConfig, chunk_text, split_text_into_chunks
from .ingest import AdmissionConfig, IngestReport, IngestedDoc, ingest

__all__ = [
    "AdmissionConfig",
    "Chunk",
    "ChunkConfig",
    "IngestReport",
    "IngestedDoc",
    "chunk_text",
    "ingest",
    "split_text_into_chunks",
]
