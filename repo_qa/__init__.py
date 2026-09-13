"""MiniDev Repo QA — AI 应用纵切。

职责：为仓库代码与文档提供可引用、可拒答、可评测的 RAG 能力。

当前已落地子能力：
- `chunking/`：文本 → 可引用 Chunk（Schema + 策略 + Quality Gate）
- `eval/`：固定场景集 + 策略对照（④ 的评测半边）

后续规划子包（有场景再建，不空占）：
- `indexing/`、`retrieval/`、`qa/`
"""

from .chunking import Chunk, ChunkConfig, chunk_text, split_text_into_chunks

__all__ = ["Chunk", "ChunkConfig", "chunk_text", "split_text_into_chunks"]
