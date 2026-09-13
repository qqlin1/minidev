"""Chunking 配置 (③)。

职责：把「切多大、用哪个策略」从算法里抽出来，方便 A/B。
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChunkConfig:
    strategy: str = "fixed_lines"
    max_lines: int = 50

    def __post_init__(self) -> None:
        if self.max_lines < 1:
            raise ValueError("max_lines must be at least 1")
