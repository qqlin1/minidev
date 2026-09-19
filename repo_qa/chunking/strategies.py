"""Chunking 可插拔策略 (②).

职责：决定「在哪里切」。所有策略遵守同一契约：
  split(path, text, config) -> list[Chunk]

当前策略：
- fixed_lines：固定行数基线（永远可复现，作为对照组）
- code_ast：Python 按顶层 def/class 符号切；失败时退回 fixed_lines
- markdown_heading：Markdown 按标题切；失败时退回 fixed_lines

明确不负责：不读磁盘、不扫仓库、不做检索。

关于「降级」这条统一约定
------------------------
三种策略都有一个共同形状：**先判断「这份输入适不适合我用」，
不适合就走 fixed_lines，而不是抛异常。**

为什么不是抛异常：切块器是摄取流水线上的一个环节，每天要处理几千份文件。
一份文件长得不像预期，正确的反应是「用保底方式处理掉，记一笔」，
而不是让整条流水线停在这一份文件上。
"""

from __future__ import annotations

import ast
from typing import Protocol

from .headings import (
    compute_block_bounds,
    find_headings,
    is_markdown_path,
    split_oversized_block,
)
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


class MarkdownHeadingStrategy:
    """Markdown：每个块 = 一个标题 + 它下面的正文。

    核心规则：**每个标题行之前，断开。**

    为什么需要它
    ------------
    ``fixed_lines`` 按行窗口切，切出来的单位是「第 25 行到第 32 行」，
    它不认识文档自己的结构。后果是**标题和它的正文被切到不同的块里**：

    用户问「迟到超过 15 分钟怎么处理」，答案在第 13-14 行，
    而告诉模型「这段在讲迟到」的标题在第 11 行。
    按 ``max_lines=6`` 切，第 11 行落在 7-12 块、第 13-14 行落在 13-18 块——
    **关键词和答案不在同一块里，两块都答不了这个问题。**

    本策略按标题切，保证「标题 + 它的正文」永远在同一块。

    层级不参与切分决策
    ------------------
    不管 ``#`` 还是 ``######``，只要出现标题就切一刀，**平铺不嵌套**。
    层级只用来记录父子关系（拼标题路径、判断空壳块）。

    如果按层级嵌套着切，子节内容会在父块里重复出现一遍——
    同一段文字被 embedding 两次，白花钱，还会让检索结果出现重复。

    降级规则（三条）
    ----------------
    1. ``path`` 不是 Markdown → 退回 ``fixed_lines``
    2. 文档一个标题都没有 → 退回 ``fixed_lines``
    3. 空文本 → 返回空列表

    第 1 条为什么同时认 ``.md`` 和 ``.markdown``：摄取层两个都收，
    如果策略只认 ``.md``，那 ``.markdown`` 文件会被静默降级成按行数切——
    用户看不出任何异常，只是质量悄悄变差了。这种「静默降级」最难查。
    """

    name = "markdown_heading"

    def split(self, *, path: str, text: str, max_lines: int) -> list[Chunk]:
        # 降级 1：不是 Markdown，这套规则用不上
        if not is_markdown_path(path):
            return FixedLinesStrategy().split(path=path, text=text, max_lines=max_lines)

        # 降级 2：空文本（含全空白）
        if not text.strip():
            return []

        headings = find_headings(text)

        # 降级 3：没有标题 = 没有结构可用
        if not headings:
            return FixedLinesStrategy().split(path=path, text=text, max_lines=max_lines)

        lines = text.splitlines()
        bounds = compute_block_bounds(headings, len(lines))

        chunks: list[Chunk] = []

        for bound in bounds:
            # 取出这个块覆盖的原文行
            block_lines = lines[bound.start_line - 1 : bound.end_line]

            # 超长块再切一刀（题 4）。不超长时，这里原样返回一个区间。
            for sub_start, sub_end in split_oversized_block(
                block_lines, bound.start_line, max_lines
            ):
                # 用原文行拼 content，保证「一个字不改」。
                # 用行号从 lines 里取，而不是用 block_lines 的切片——
                # 因为二级切分返回的是**原文行号**，必须换算回原文取，
                # 否则会取到别的行（这是最容易犯的错，且 citation 会一起错）。
                content = "\n".join(lines[sub_start - 1 : sub_end])

                # 整块都是空白的不生成 Chunk（Chunk 的 __post_init__ 也会拒绝空内容，
                # 但在这里挡掉更清楚：这不是错误，是正常的空块）
                if not content.strip():
                    continue

                chunks.append(
                    Chunk(
                        path=path,
                        start_line=sub_start,
                        end_line=sub_end,
                        content=content,
                        # 二级切出来的所有子块共用同一个标题路径。
                        #
                        # 为什么第二个子块也要带上：它的正文里**没有标题**，
                        # 标题留在了第一个子块里。所以对第二个子块来说，
                        # 标题路径是它唯一能知道「我属于哪一节」的地方——
                        # 这里比第一个子块更需要它。
                        heading_path=bound.heading_path,
                    )
                )

        # 兜底：如果上面一个块都没生成（理论上不会，因为 headings 非空），
        # 退回固定行数，保证「有文本就有块」这个不变量
        return chunks or FixedLinesStrategy().split(
            path=path, text=text, max_lines=max_lines
        )


STRATEGIES: dict[str, ChunkStrategy] = {
    "fixed_lines": FixedLinesStrategy(),
    "code_ast": CodeASTStrategy(),
    "markdown_heading": MarkdownHeadingStrategy(),
}


def get_strategy(name: str) -> ChunkStrategy:
    try:
        return STRATEGIES[name]
    except KeyError as exc:
        raise ValueError(f"unknown strategy: {name!r}") from exc
