"""Chunking 子包 — Knowledge Base 的切块能力边界 (①②③④).

对外 API：

- `Chunk`：可引用块 Schema
- `ChunkConfig` / `FilterConfig`：策略名、数值参数、过滤阈值
- `split_text_into_chunks`：固定行数基线（兼容旧学习入口，不过滤）
- `chunk_text`：按 config 选策略切块并过滤，返回可入库的块
- `chunk_text_result`：同上，但连被丢弃的块和原因一起返回
- `filter_chunks` / `FilterResult`：单独调用质量过滤，查看丢弃报告
- `find_headings` / `compute_block_bounds` / `BlockBound`：Markdown 结构解析
- `build_heading_paths`：算每个标题的祖先路径（标题路径 / breadcrumb）
- `split_oversized_block`：超长块的二级切分

三种策略：

| 策略名 | 按什么切 | 语料 |
|---|---|---|
| `fixed_lines` | 固定行数 | 任何文本（基线，永远可用） |
| `code_ast` | 顶层 def / class | Python 代码 |
| `markdown_heading` | 标题行 | Markdown 文档 |

调用方只应 import 本包公开符号。
"""

from .config import ChunkConfig, FilterConfig
from .filters import DroppedChunk, FilterResult, filter_chunks
from .headings import (
    BlockBound,
    build_heading_paths,
    compute_block_bounds,
    find_headings,
    is_markdown_path,
    split_oversized_block,
)
from .models import Chunk
from .pipeline import chunk_text, chunk_text_result, split_text_into_chunks

__all__ = [
    "BlockBound",
    "Chunk",
    "ChunkConfig",
    "DroppedChunk",
    "FilterConfig",
    "FilterResult",
    "build_heading_paths",
    "chunk_text",
    "chunk_text_result",
    "compute_block_bounds",
    "filter_chunks",
    "find_headings",
    "is_markdown_path",
    "split_oversized_block",
    "split_text_into_chunks",
]
