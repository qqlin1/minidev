"""Chunking 可插拔策略 (②).

职责：决定「在哪里切」。所有策略遵守同一契约：
  split(path, text, config) -> list[Chunk]

当前策略：
- fixed_lines：固定行数基线（永远可复现，作为对照组）
- code_ast：Python 按顶层 def/class 符号切；失败时退回 fixed_lines

明确不负责：不读磁盘、不扫仓库、不做检索。
"""

from __future__ import annotations

import ast
from typing import Protocol

from .models import Chunk


class ChunkStrategy(Protocol):
    name: str

    def split(self, *, path: str, text: str, max_lines: int) -> list[Chunk]:
        ...


class FixedLinesStrategy:
    """基线：按 max_lines 切。简单、无语言依赖，永远先有它。"""

    name = "fixed_lines"

    def split(self, *, path: str, text: str, max_lines: int) -> list[Chunk]:
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


class CodeASTStrategy:
    """Python：每个顶层 def/class 尽量整块保留；解析失败退回固定行数。"""

    name = "code_ast"

    def split(self, *, path: str, text: str, max_lines: int) -> list[Chunk]:
        if not path.endswith(".py"):
            return FixedLinesStrategy().split(path=path, text=text, max_lines=max_lines)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return FixedLinesStrategy().split(path=path, text=text, max_lines=max_lines)

        lines = text.splitlines()
        if not lines:
            return []

        chunks: list[Chunk] = []
        covered_end = 0

        for node in tree.body:
            start = node.lineno
            end = getattr(node, "end_lineno", None) or start
            # 模块级残余（import、赋值）若在符号前，先单独成块
            if start - 1 > covered_end:
                head = "\n".join(lines[covered_end : start - 1])
                if head.strip():
                    chunks.append(
                        Chunk(
                            path=path,
                            start_line=covered_end + 1,
                            end_line=start - 1,
                            content=head,
                        )
                    )
            body = "\n".join(lines[start - 1 : end])
            if body.strip():
                chunks.append(
                    Chunk(
                        path=path,
                        start_line=start,
                        end_line=end,
                        content=body,
                    )
                )
            covered_end = end

        if covered_end < len(lines):
            tail = "\n".join(lines[covered_end:])
            if tail.strip():
                chunks.append(
                    Chunk(
                        path=path,
                        start_line=covered_end + 1,
                        end_line=len(lines),
                        content=tail,
                    )
                )

        return chunks or FixedLinesStrategy().split(
            path=path, text=text, max_lines=max_lines
        )


STRATEGIES: dict[str, ChunkStrategy] = {
    "fixed_lines": FixedLinesStrategy(),
    "code_ast": CodeASTStrategy(),
}


def get_strategy(name: str) -> ChunkStrategy:
    try:
        return STRATEGIES[name]
    except KeyError as exc:
        raise ValueError(f"unknown strategy: {name!r}") from exc
