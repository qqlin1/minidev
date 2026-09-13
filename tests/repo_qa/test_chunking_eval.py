"""对照评测测试：固定行数基线 vs code_ast。

这些断言就是「有分母的证据」——数字变了说明夹具或策略变了，必须重新口述原因。
"""

from repo_qa.chunking import ChunkConfig
from repo_qa.eval import ALL_SCENARIOS, compare_strategies


def test_scenario_catalog_has_stable_size_and_families():
    assert len(ALL_SCENARIOS) == 8
    families = {s.family for s in ALL_SCENARIOS}
    assert families == {"code_symbol", "code_config", "doc_section"}


def test_fixed_lines_baseline_is_recorded_with_denominator():
    (baseline,) = compare_strategies(
        configs=[ChunkConfig(strategy="fixed_lines", max_lines=3)]
    )

    assert baseline.total_cases == 8
    assert baseline.strategy == "fixed_lines"
    # 基线必须能在「恰好对齐行窗口」的配置类 case 上命中，否则夹具写坏了
    assert baseline.hits_by_family["code_config"] == baseline.totals_by_family["code_config"]
    # 固定行数在符号族上不应全中——这是引入 AST 的动机证据
    assert baseline.hits_by_family["code_symbol"] < baseline.totals_by_family["code_symbol"]
    assert baseline.misses, "基线应留下可解释的 miss，而不是空评测"


def test_code_ast_beats_fixed_lines_on_symbol_family():
    reports = compare_strategies(
        configs=[
            ChunkConfig(strategy="fixed_lines", max_lines=3),
            ChunkConfig(strategy="code_ast", max_lines=3),
        ]
    )
    baseline, ast = reports

    assert ast.strategy == "code_ast"
    assert (
        ast.hits_by_family["code_symbol"]
        >= baseline.hits_by_family["code_symbol"]
    )
    # 代码符号族上 AST 应接近打满；文档族 AST 不负责，允许持平或略差
    assert ast.hits_by_family["code_symbol"] == ast.totals_by_family["code_symbol"]
    assert ast.hit_rate > baseline.hit_rate


def test_misses_are_actionable_case_ids():
    (baseline,) = compare_strategies(
        configs=[ChunkConfig(strategy="fixed_lines", max_lines=3)]
    )
    miss_ids = {m.case_id for m in baseline.misses}

    # 至少钉住「函数被切开」这一条经典失败模式
    assert "code_load_config_symbol" in miss_ids or "code_connect_db_symbol" in miss_ids
