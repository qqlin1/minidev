"""Chunking pipeline — 策略路由 + 质量过滤 (④ 运行时部分).

对外三套入口：

1. 学习基线兼容：split_text_into_chunks(...) — 固定行数，不做质量过滤
2. 可插拔入口：chunk_text(path, text, config) — 按 config.strategy 选实现，返回可入库的块
3. 可观测入口：chunk_text_result(path, text, config) — 同上，但连被丢弃的块和原因一起返回
"""

from .config import ChunkConfig
from .filters import FilterResult, filter_chunks
from .models import Chunk
from .strategies import get_strategy


def split_text_into_chunks(
    *,
    path: str,
    text: str,
    max_lines: int,
) -> list[Chunk]:
    """按固定行数切块。

    这是最早的学习基线，只跳过纯空白块，**不做质量过滤**——
    保留它原样，是为了让「过滤到底改变了什么」有一个能对照的起点。
    需要过滤时走 chunk_text / chunk_text_result。
    """
    if max_lines < 1:
        raise ValueError("max_lines must be at least 1")

    lines = text.splitlines()
    chunks: list[Chunk] = []

    for start_index in range(0, len(lines), max_lines):
        end_index = min(start_index + max_lines, len(lines))
        content = "\n".join(lines[start_index:end_index])

        if content.strip():
            chunks.append(
                Chunk(
                    path=path,
                    start_line=start_index + 1,
                    end_line=end_index,
                    content=content,
                )
            )

    return chunks


def chunk_text_result(*, path: str, text: str, config: ChunkConfig) -> FilterResult:
    """切块 + 过滤的完整结果：保留的块、丢弃的块、丢弃原因。

    想看「过滤到底丢了什么」，用这个入口；只想要能入库的块，用 chunk_text。
    """
    strategy = get_strategy(config.strategy)
    chunks = strategy.split(path=path, text=text, max_lines=config.max_lines)
    return filter_chunks(chunks, config.filter)


def chunk_text(*, path: str, text: str, config: ChunkConfig) -> list[Chunk]:
    """按配置选策略切块并过滤，返回可以进向量库的块。"""
    return list(chunk_text_result(path=path, text=text, config=config).kept)
