"""对照评测测试：固定行数基线 vs code_ast vs markdown_heading。

这些断言就是「有分母的证据」——数字变了说明夹具或策略变了，必须重新口述原因。

2026-09-17：场景数从 8 变成 11。新增的三条是员工手册上的文档场景
（迟到处理 / 差旅报销上限 / 年假天数），用来给 markdown_heading 一个靶子。
数字变了不是 bug，是提醒——它逼你重新说一遍「为什么多了这几条」。
"""

from pathlib import Path

from repo_qa.chunking import ChunkConfig
from repo_qa.eval import ALL_SCENARIOS, compare_strategies
from repo_qa.eval.cases import EMPLOYEE_HANDBOOK

# 场景总数。改这个数字之前，先能说清「多了哪几条、为什么加」。
EXPECTED_SCENARIO_COUNT = 11


def test_scenario_catalog_has_stable_size_and_families():
    assert len(ALL_SCENARIOS) == EXPECTED_SCENARIO_COUNT
    families = {s.family for s in ALL_SCENARIOS}
    assert families == {"code_symbol", "code_config", "doc_section"}


def test_handbook_fixture_matches_source_file():
    """内嵌的语料必须和项目根目录的源文件逐字节一致。

    为什么要有这条：评测集内嵌语料是为了自包含，但内嵌有抄错的风险。
    抄错一个数字，期望行号就全错了，而测试仍然是绿的（因为它拿错的数据
    去比对错的实现）。这条断言把「抄写」这个环节也纳入检查。
    """
    source = Path("_unit3_employee_handbook.md").read_text(encoding="utf-8")
    assert EMPLOYEE_HANDBOOK == source, "内嵌语料和源文件不一致，说明有一边被改过"


def test_fixed_lines_baseline_is_recorded_with_denominator():
    (baseline,) = compare_strategies(
        configs=[ChunkConfig(strategy="fixed_lines", max_lines=3)]
    )

    assert baseline.total_cases == EXPECTED_SCENARIO_COUNT
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


def test_markdown_heading_wins_on_doc_section_family():
    """markdown_heading 必须在文档族上全面胜出——这是它存在的唯一理由。

    数字变了（比如从 5/5 掉到 4/5）说明策略或夹具坏了，
    不允许「改断言让它变绿」，要回去查根因。
    """
    baseline, heading = compare_strategies(
        configs=[
            ChunkConfig(strategy="fixed_lines", max_lines=6),
            ChunkConfig(strategy="markdown_heading", max_lines=6),
        ]
    )

    assert heading.strategy == "markdown_heading"
    # 文档族：按标题切应打满，按行数切应全 miss
    assert heading.hits_by_family["doc_section"] == heading.totals_by_family["doc_section"]
    assert baseline.hits_by_family["doc_section"] < baseline.totals_by_family["doc_section"]
    assert heading.hit_rate > baseline.hit_rate


def test_markdown_heading_falls_back_on_non_markdown():
    """非 Markdown 路径上，markdown_heading 的行为必须等同 fixed_lines。

    这是「降级」的证据：代码族上两者命中数应完全一致，
    因为 markdown_heading 在 .py 上直接退回了固定行数。
    """
    baseline, heading = compare_strategies(
        configs=[
            ChunkConfig(strategy="fixed_lines", max_lines=6),
            ChunkConfig(strategy="markdown_heading", max_lines=6),
        ]
    )

    assert heading.hits_by_family["code_symbol"] == baseline.hits_by_family["code_symbol"]
    assert heading.hits_by_family["code_config"] == baseline.hits_by_family["code_config"]


def test_misses_are_actionable_case_ids():
    (baseline,) = compare_strategies(
        configs=[ChunkConfig(strategy="fixed_lines", max_lines=3)]
    )
    miss_ids = {m.case_id for m in baseline.misses}

    # 至少钉住「函数被切开」这一条经典失败模式
    assert "code_load_config_symbol" in miss_ids or "code_connect_db_symbol" in miss_ids
