"""Repo QA 对照评测 — ④ 的另一半：让策略好坏有分母。

场景从产品问题反推，不是随机凑 case。
"""

from .cases import ALL_SCENARIOS, ScenarioCase
from .runner import StrategyReport, evaluate_strategy, compare_strategies

__all__ = [
    "ALL_SCENARIOS",
    "ScenarioCase",
    "StrategyReport",
    "evaluate_strategy",
    "compare_strategies",
]
