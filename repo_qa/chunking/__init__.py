"""Chunking 子包 — Knowledge Base 的切块能力边界 (①②③④).

对外 API：

- `Chunk`：可引用块 Schema
- `ChunkConfig` / `FilterConfig`：策略名、数值参数、过滤阈值
- `split_text_into_chunks`：固定行数基线（兼容旧学习入口，不过滤）
- `chunk_text`：按 config 选策略切块并过滤，返回可入库的块
- `chunk_text_result`：同上，但连被丢弃的块和原因一起返回
- `filter_chunks` / `FilterResult`：单独调用质量过滤，查看丢弃报告

调用方只应 import 本包公开符号。
"""

from .config import ChunkConfig, FilterConfig
from .filters import DroppedChunk, FilterResult, filter_chunks
from .models import Chunk
from .pipeline import chunk_text, chunk_text_result, split_text_into_chunks

__all__ = [
    "Chunk",
    "ChunkConfig",
    "DroppedChunk",
    "FilterConfig",
    "FilterResult",
    "chunk_text",
    "chunk_text_result",
    "filter_chunks",
    "split_text_into_chunks",
]
