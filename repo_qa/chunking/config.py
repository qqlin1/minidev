"""Chunking 配置 (③)。

职责：把「切多大、用哪个策略、丢哪些块」从算法里抽出来，方便 A/B。
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FilterConfig:
    """入库前过滤的开关与阈值 (④ Quality Gate 的配置半边)。

    三个字段对应三件事：

    - ``enabled``：总开关。关掉后所有块原样放行，用来做「过滤 vs 不过滤」的对照实验。
    - ``min_chars``：一个块去掉首尾空白后至少要有多少个字符。设成 0 等于关掉这条规则。
    - ``drop_duplicates``：是否丢弃同一文件内重复出现的块（页眉页脚最常见）。
    """

    enabled: bool = True
    min_chars: int = 10
    drop_duplicates: bool = True

    def __post_init__(self) -> None:
        if self.min_chars < 0:
            raise ValueError("min_chars must not be negative")


@dataclass(frozen=True, slots=True)
class ChunkConfig:
    strategy: str = "fixed_lines"
    max_lines: int = 50
    filter: FilterConfig = FilterConfig()

    def __post_init__(self) -> None:
        if self.max_lines < 1:
            raise ValueError("max_lines must be at least 1")
