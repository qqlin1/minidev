"""策略对照评测 runner — 同一场景集，只换 ChunkConfig。

输出必须带分母（total_cases）与可复现配置摘要；禁止无分母的「感觉更好」。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..chunking import ChunkConfig, Chunk, chunk_text
from .cases import ALL_SCENARIOS, ScenarioCase


@dataclass(frozen=True, slots=True)
class ScenarioOutcome:
    case_id: str
    family: str
    hit: bool
    matched_citation: str | None


@dataclass(frozen=True, slots=True)
class StrategyReport:
    strategy: str
    max_lines: int
    total_cases: int
    hits: int
    hit_rate: float
    hits_by_family: dict[str, int]
    totals_by_family: dict[str, int]
    num_chunks_by_source: dict[str, int]
    misses: tuple[ScenarioOutcome, ...]

    def summary(self) -> str:
        fam = ", ".join(
            f"{k}:{self.hits_by_family.get(k, 0)}/{self.totals_by_family[k]}"
            for k in sorted(self.totals_by_family)
        )
        return (
            f"{self.strategy}(max_lines={self.max_lines}) "
            f"hit_rate={self.hits}/{self.total_cases}={self.hit_rate:.2f} [{fam}]"
        )


def _covered(chunks: list[Chunk], case: ScenarioCase) -> str | None:
    for c in chunks:
        if (
            c.path == case.path
            and c.start_line <= case.expect_start_line
            and c.end_line >= case.expect_end_line
        ):
            return c.citation
    return None


def evaluate_strategy(
    *,
    cases: tuple[ScenarioCase, ...] | list[ScenarioCase] = ALL_SCENARIOS,
    config: ChunkConfig,
) -> StrategyReport:
    """在固定场景集上评测一种配置。"""
    hits = 0
    outcomes: list[ScenarioOutcome] = []
    hits_by_family: Counter[str] = Counter()
    totals_by_family: Counter[str] = Counter()
    num_chunks_by_source: dict[str, int] = {}

    # 同一 source_text 只切一次，避免重复计数 chunk 数
    source_cache: dict[tuple[str, str], list[Chunk]] = {}

    for case in cases:
        key = (case.path, case.source_text)
        if key not in source_cache:
            source_cache[key] = chunk_text(
                path=case.path,
                text=case.source_text,
                config=config,
            )
        chunks = source_cache[key]
        citation = _covered(chunks, case)
        hit = citation is not None
        hits += int(hit)
        totals_by_family[case.family] += 1
        if hit:
            hits_by_family[case.family] += 1
        outcomes.append(
            ScenarioOutcome(
                case_id=case.id,
                family=case.family,
                hit=hit,
                matched_citation=citation,
            )
        )

    for (path, _text), chunks in source_cache.items():
        num_chunks_by_source[path] = len(chunks)

    total = len(cases)
    # 某族 0 命中时也要保留 key，避免调用方 KeyError
    hits_map = {fam: hits_by_family.get(fam, 0) for fam in totals_by_family}
    return StrategyReport(
        strategy=config.strategy,
        max_lines=config.max_lines,
        total_cases=total,
        hits=hits,
        hit_rate=hits / total if total else 0.0,
        hits_by_family=hits_map,
        totals_by_family=dict(totals_by_family),
        num_chunks_by_source=dict(num_chunks_by_source),
        misses=tuple(o for o in outcomes if not o.hit),
    )


def compare_strategies(
    *,
    cases: tuple[ScenarioCase, ...] | list[ScenarioCase] = ALL_SCENARIOS,
    configs: list[ChunkConfig],
) -> list[StrategyReport]:
    """同一数据、同一 cases，只换 config —— 对照实验的最小形态。"""
    return [evaluate_strategy(cases=cases, config=c) for c in configs]
