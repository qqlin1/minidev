"""Chunking pipeline — 策略路由 + 质量门 (④ 运行时部分).

对外两套入口：
1. 学习基线兼容：split_text_into_chunks(...) — 固定行数
2. 可插拔入口：chunk_text(path, text, config) — 按 config.strategy 选实现
"""

from .config import ChunkConfig
from .models import Chunk
from .strategies import get_strategy


def split_text_into_chunks(
    *,
    path: str,
    text: str,
    max_lines: int,
) -> list[Chunk]:
    """Split one text value into fixed-size, line-based chunks."""
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


def chunk_text(*, path: str, text: str, config: ChunkConfig) -> list[Chunk]:
    """按配置选择策略切块；空块跳过由策略与 Quality Gate 共同保证。"""
    strategy = get_strategy(config.strategy)
    chunks = strategy.split(path=path, text=text, max_lines=config.max_lines)
    return [c for c in chunks if c.content.strip()]
