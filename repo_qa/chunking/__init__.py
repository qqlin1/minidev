"""Chunking 子包 — Repo QA 的切块能力边界 (①②③④).

对外 API：
- `Chunk`：可引用块 Schema
- `ChunkConfig`：策略名 + 数值参数
- `split_text_into_chunks`：固定行数基线（兼容旧学习入口）
- `chunk_text`：按 config 选策略的统一入口

调用方只应 import 本包公开符号。
"""

from .config import ChunkConfig
from .models import Chunk
from .pipeline import chunk_text, split_text_into_chunks

__all__ = [
    "Chunk",
    "ChunkConfig",
    "chunk_text",
    "split_text_into_chunks",
]
