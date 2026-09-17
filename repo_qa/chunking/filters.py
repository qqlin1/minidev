"""Chunking 质量过滤 — ④ Quality Gate 的「过滤」半边。

职责：在**切块之后、向量化之前**，决定「哪些块不该进向量库」。

为什么切块之后还要过滤
----------------------
切块算法只看结构，不看内容。它只知道「从第 1 行切到第 3 行」，
不知道这三行是正文，还是一行分隔线加两个空行。
所以切完的块里必然混着没有信息量的东西：

- 只有三五个字符的碎块（章节号、表格残渣、孤立的小标题）
- 纯符号（``---``、``=====``、``| --- |``）
- 每页重复出现的页码、页眉、页脚
- 同一份文件里被切出来两次的完全相同的内容

这些块如果进了向量库，会变成「永远召得回、但答不了任何问题」的噪声：
用户问 A，检索却把一条 ``---`` 排到前面；而且每个块做 embedding 都要花钱。

明确不负责
----------
本模块只做**可以机械判定**的形式判断，不做语义判断。
「这个块讲得全不全、有没有用」属于评测指标的职责，不在这里拍脑袋。

规则契约
--------
每条规则实现 ``reject_reason(chunk) -> str | None``：

- 返回 ``None``：这个块没问题，交给下一条规则继续看
- 返回字符串：这个块该丢，字符串就是丢掉它的原因（会写进报告给人看）

规则按固定顺序执行，**第一个说不的规则说了算**，后面的不再看。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from .config import FilterConfig
from .models import Chunk


class ChunkFilter(Protocol):
    """一条过滤规则的契约。规则只读一个块，不读别的块，也不改任何东西。"""

    name: str

    def reject_reason(self, chunk: Chunk) -> str | None:
        ...


class NoTextFilter:
    """整块里一个字母、一个数字、一个汉字都没有 —— 纯符号或纯装饰。"""

    name = "no_text"

    def reject_reason(self, chunk: Chunk) -> str | None:
        if any(ch.isalnum() for ch in chunk.content):
            return None
        return "整块没有任何文字字符（字母/数字/汉字），只有符号"


# 页码、页眉、页脚在一份文档里反复出现，形状高度固定，适合用正则一次说清。
_PAGE_FURNITURE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 第 3 页 / 第 3 页 共 10 页 / 第3页/共10页
    re.compile(r"第\s*\d+\s*页(?:\s*[/／|]\s*共?\s*\d+\s*页)?"),
    # Page 3 / page 3 of 10
    re.compile(r"page\s+\d+(?:\s*(?:/|of)\s*\d+)?", re.IGNORECASE),
    # 单独一行的 - 3 - / 3 / 12
    re.compile(r"-{0,2}\s*\d{1,3}\s*-{0,2}"),
)


class PageFurnitureFilter:
    """整块都是页码或页眉页脚 —— 每一页都长一样，不是正文。"""

    name = "page_furniture"

    def reject_reason(self, chunk: Chunk) -> str | None:
        lines = [line.strip() for line in chunk.content.splitlines() if line.strip()]
        if not lines:
            return None
        if all(
            any(pattern.fullmatch(line) for pattern in _PAGE_FURNITURE_PATTERNS)
            for line in lines
        ):
            return "整块都是页码或页眉页脚，每一页都重复出现"
        return None


class TooShortFilter:
    """有效字符太少 —— 连一个完整的词组都装不下，谈不上承载信息。"""

    name = "too_short"

    def __init__(self, *, min_chars: int) -> None:
        self.min_chars = min_chars

    def reject_reason(self, chunk: Chunk) -> str | None:
        length = len(chunk.content.strip())
        if length >= self.min_chars:
            return None
        return f"去掉首尾空白后只有 {length} 个字符，少于阈值 {self.min_chars}"


class DuplicateFilter:
    """同一份文件里，前面已经出现过一模一样的内容（页眉最常见）。

    注意：这条规则**有状态**（记住前面见过的内容），
    所以每次过滤都要新建一个实例，不能全局复用一个。
    ``filter_chunks`` 每次调用都会重新构造规则，正是为了这一点。
    """

    name = "duplicate"

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()

    def reject_reason(self, chunk: Chunk) -> str | None:
        key = (chunk.path, _dedup_key(chunk.content))
        if key in self._seen:
            return "同一文件内重复出现，只保留第一次出现的位置"
        self._seen.add(key)
        return None


def _dedup_key(content: str) -> str:
    """去重用的归一化键：忽略所有空白字符和大小写差异。"""
    return "".join(content.split()).casefold()


@dataclass(frozen=True, slots=True)
class DroppedChunk:
    """一个被丢掉的块，以及是谁丢的、为什么丢。"""

    chunk: Chunk
    rule: str
    reason: str


@dataclass(frozen=True, slots=True)
class FilterResult:
    """过滤的完整结果：保留了什么、丢了什么、为什么丢。

    只返回「保留了什么」是看不见问题的。生产里必须能回答
    「这次摄取丢掉了多少块、主要因为哪条规则」，
    否则阈值调大调小全靠感觉，出了坏结果也查不出原因。
    """

    kept: tuple[Chunk, ...]
    dropped: tuple[DroppedChunk, ...]

    @property
    def total(self) -> int:
        return len(self.kept) + len(self.dropped)

    def dropped_by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.dropped:
            counts[item.rule] = counts.get(item.rule, 0) + 1
        return counts

    def summary(self) -> str:
        if not self.dropped:
            return f"过滤：{self.total} 块，全部保留"
        by_rule = "，".join(
            f"{rule} {count} 块" for rule, count in sorted(self.dropped_by_rule().items())
        )
        return (
            f"过滤：{self.total} 块 -> 保留 {len(self.kept)}，"
            f"丢弃 {len(self.dropped)}（{by_rule}）"
        )


def _build_rules(config: FilterConfig) -> list[ChunkFilter]:
    """按配置构造本次过滤要用的规则，顺序就是判定顺序。"""
    rules: list[ChunkFilter] = [NoTextFilter(), PageFurnitureFilter()]
    if config.min_chars > 0:
        rules.append(TooShortFilter(min_chars=config.min_chars))
    if config.drop_duplicates:
        rules.append(DuplicateFilter())
    return rules


def filter_chunks(
    chunks: Iterable[Chunk],
    config: FilterConfig | None = None,
) -> FilterResult:
    """按规则丢弃没有信息量的块，返回保留项和丢弃原因。

    规则顺序固定为：no_text -> page_furniture -> too_short -> duplicate。
    靠前的规则更「绝对」（这块根本没有文字），靠后的更「相对」
    （这块有文字，只是太短；或这块和前面重复）。
    先判绝对的，报出来的原因才准确。
    """
    if config is None:
        config = FilterConfig()

    if not config.enabled:
        kept = tuple(chunks)
        return FilterResult(kept=kept, dropped=())

    rules = _build_rules(config)
    kept_list: list[Chunk] = []
    dropped_list: list[DroppedChunk] = []

    for chunk in chunks:
        rejection: tuple[str, str] | None = None
        for rule in rules:
            reason = rule.reject_reason(chunk)
            if reason is not None:
                rejection = (rule.name, reason)
                break

        if rejection is None:
            kept_list.append(chunk)
        else:
            dropped_list.append(
                DroppedChunk(chunk=chunk, rule=rejection[0], reason=rejection[1])
            )

    return FilterResult(kept=tuple(kept_list), dropped=tuple(dropped_list))
