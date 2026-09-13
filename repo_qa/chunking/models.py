"""RAG domain models — Chunk schema (①).

职责：定义「一块可引用的仓库文本」长什么样：路径、行号区间、内容、稳定 citation。

明确不负责：文件扫描、切分算法、embedding、检索或入库。
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chunk:
    """A citeable piece of text from one file in the indexed repository."""

    path: str
    start_line: int
    end_line: int
    content: str

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("path must not be empty")
        if self.start_line < 1:
            raise ValueError("start_line must be at least 1")
        if self.end_line < self.start_line:
            raise ValueError("end_line must not be before start_line")
        if not self.content.strip():
            raise ValueError("content must not be empty")

    @property
    def citation(self) -> str:
        """The stable source location shown beside a future RAG answer."""
        return f"{self.path}:{self.start_line}-{self.end_line}"
