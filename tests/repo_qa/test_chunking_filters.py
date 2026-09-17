"""质量过滤测试 — 四条规则的正反例、开关、边界，以及「不误杀」的回归。

这里最重要的两组断言是：

1. 每条规则都要有**它该丢的块被丢掉**（正例）和**正常块没被连累**（反例）。
   只有正例的测试，把 min_chars 调到 10000 也能全绿。
2. 打开过滤后，现有 8 条场景评测的命中数不能下降。
   过滤是「减操作」，减错东西就是直接伤害检索。
"""

import pytest

from repo_qa.chunking import (
    Chunk,
    ChunkConfig,
    FilterConfig,
    chunk_text,
    chunk_text_result,
    filter_chunks,
)
from repo_qa.eval import compare_strategies


def _chunk(content: str, *, start_line: int = 1, path: str = "doc.md") -> Chunk:
    """按内容长度自动算行数，省得每处手写 end_line。"""
    lines = content.splitlines() or [""]
    return Chunk(
        path=path,
        start_line=start_line,
        end_line=start_line + len(lines) - 1,
        content=content,
    )


# ---------------------------------------------------------------------------
# 规则一：no_text —— 整块没有文字字符
# ---------------------------------------------------------------------------


def test_symbol_only_chunk_is_dropped():
    result = filter_chunks([_chunk("----------------")])

    assert result.kept == ()
    assert len(result.dropped) == 1
    assert result.dropped[0].rule == "no_text"


def test_table_separator_row_is_dropped():
    result = filter_chunks([_chunk("| --- | --- | --- |")])

    assert result.dropped[0].rule == "no_text"


def test_chunk_with_one_chinese_char_survives():
    # 只要有一个汉字就还算是文字，不能被 no_text 判定为纯符号
    result = filter_chunks([_chunk("## 概述：系统架构总览与部署拓扑说明")])

    assert result.kept != ()
    assert result.dropped == ()


# ---------------------------------------------------------------------------
# 规则二：page_furniture —— 整块都是页码/页眉页脚
# ---------------------------------------------------------------------------


def test_page_number_chunk_is_dropped():
    result = filter_chunks([_chunk("第 3 页 / 共 10 页")])

    assert result.kept == ()
    assert result.dropped[0].rule == "page_furniture"


def test_english_page_number_chunk_is_dropped():
    result = filter_chunks([_chunk("Page 7 of 12")])

    assert result.dropped[0].rule == "page_furniture"


def test_chunk_mentioning_page_number_in_a_sentence_survives():
    # 正文里出现「第 3 页」不代表整块都是页码，正则必须整行匹配才不会误杀
    result = filter_chunks(
        [_chunk("详见第 3 页的配置表，那里列出了全部环境变量。")]
    )

    assert result.dropped == ()


# ---------------------------------------------------------------------------
# 规则三：too_short —— 有效字符太少
# ---------------------------------------------------------------------------


def test_short_chunk_is_dropped_with_readable_reason():
    result = filter_chunks([_chunk("3.2")])

    assert result.kept == ()
    assert result.dropped[0].rule == "too_short"
    assert "3 个字符" in result.dropped[0].reason


def test_chunk_exactly_at_min_chars_survives():
    # 边界：刚好等于阈值要保留（判定用的是 < 而不是 <=）
    content = "class App:"  # 正好 10 个字符
    assert len(content) == 10

    result = filter_chunks([_chunk(content)])

    assert result.kept == (_chunk(content),)
    assert result.dropped == ()


def test_disabling_min_chars_keeps_short_chunks():
    result = filter_chunks([_chunk("3.2")], FilterConfig(min_chars=0))

    assert result.dropped == ()


# ---------------------------------------------------------------------------
# 规则四：duplicate —— 同一文件内重复
# ---------------------------------------------------------------------------


def test_repeated_header_is_kept_once():
    header = "某某公司内部资料 严禁外传"  # 12 个字符，不会被 too_short 拦下
    chunks = [
        _chunk(header, start_line=1),
        _chunk("正文第一段，讲的是系统的基本组成和职责边界。", start_line=3),
        _chunk(header, start_line=5),
    ]

    result = filter_chunks(chunks)

    assert len(result.kept) == 2
    assert result.kept[0].start_line == 1  # 保留第一次出现的位置
    assert len(result.dropped) == 1
    assert result.dropped[0].rule == "duplicate"
    assert result.dropped[0].chunk.start_line == 5


def test_same_content_in_different_files_is_not_a_duplicate():
    header = "某某公司内部资料 严禁外传"
    chunks = [
        _chunk(header, path="a.md"),
        _chunk(header, path="b.md"),
    ]

    result = filter_chunks(chunks)

    assert len(result.kept) == 2


def test_disabling_dedup_keeps_both_copies():
    header = "某某公司内部资料 严禁外传"
    chunks = [_chunk(header, start_line=1), _chunk(header, start_line=5)]

    result = filter_chunks(chunks, FilterConfig(drop_duplicates=False))

    assert len(result.kept) == 2
    assert result.dropped == ()


def test_dedup_ignores_whitespace_and_case_differences():
    chunks = [
        _chunk("Configuration Reference Manual", start_line=1),
        _chunk("configuration   reference\nmanual", start_line=9),
    ]

    result = filter_chunks(chunks)

    assert len(result.kept) == 1
    assert result.dropped[0].rule == "duplicate"


# ---------------------------------------------------------------------------
# 总开关与报告
# ---------------------------------------------------------------------------


def test_disabling_filtering_keeps_everything():
    chunks = [_chunk("---"), _chunk("3.2"), _chunk("正常的一段正文内容，长度足够。")]

    result = filter_chunks(chunks, FilterConfig(enabled=False))

    assert result.kept == tuple(chunks)
    assert result.dropped == ()


def test_report_counts_drops_by_rule():
    chunks = [
        _chunk("-----------", start_line=1),
        _chunk("3.2", start_line=3),
        _chunk("第 1 页 / 共 5 页", start_line=5),
        _chunk("正常的一段正文内容，长度足够。", start_line=7),
    ]

    result = filter_chunks(chunks)

    assert result.total == 4
    assert len(result.kept) == 1
    assert result.dropped_by_rule() == {"no_text": 1, "too_short": 1, "page_furniture": 1}
    assert "保留 1" in result.summary()
    assert "丢弃 3" in result.summary()


def test_report_says_all_kept_when_nothing_is_dropped():
    result = filter_chunks([_chunk("正常的一段正文内容，长度足够。")])

    assert result.summary() == "过滤：1 块，全部保留"


def test_negative_min_chars_is_rejected():
    with pytest.raises(ValueError, match="min_chars"):
        FilterConfig(min_chars=-1)


# ---------------------------------------------------------------------------
# 端到端：pipeline 入口
# ---------------------------------------------------------------------------

REALISTIC_DOC = """\
某某公司 内部资料
# 员工报销制度

## 适用范围

本制度适用于公司全体正式员工，试用期员工参照执行。

---

某某公司 内部资料
## 报销额度

单次差旅报销上限为 5000 元，超出部分需部门负责人审批。

第 2 页 / 共 3 页
"""


def test_pipeline_returns_only_clean_chunks():
    config = ChunkConfig(strategy="fixed_lines", max_lines=3)

    chunks = chunk_text(path="expense.md", text=REALISTIC_DOC, config=config)

    contents = [c.content for c in chunks]
    # 这一块是「空行 + --- + 空行」，整块没有文字，必须被丢掉
    assert "\n---\n" not in contents
    # 正文块一块都不能少
    assert any("本制度适用于公司全体正式员工" in c for c in contents)
    assert any("单次差旅报销上限为 5000 元" in c for c in contents)


def test_pipeline_report_explains_what_was_dropped():
    config = ChunkConfig(strategy="fixed_lines", max_lines=3)

    result = chunk_text_result(path="expense.md", text=REALISTIC_DOC, config=config)

    # 15 行按 3 行一组 = 5 块，其中 1 块是分隔线
    assert result.total == 5
    assert len(result.kept) == 4
    assert result.dropped_by_rule() == {"no_text": 1}
    assert result.dropped[0].chunk.citation == "expense.md:7-9"
    assert "保留 4" in result.summary()
    # 引用行号仍然指向原始文件，过滤不会让 citation 失真
    assert all(c.citation.startswith("expense.md:") for c in result.kept)


def test_page_number_glued_to_body_is_a_known_limit():
    """已知边界（失败实验）：页码跟在正文后面时，固定行数会把它和正文切进同一块。

    这份文档是 15 行，第 13-15 行是「正文 / 空行 / 第 2 页」。按 3 行一组切，
    它们落在同一个窗口里，所以这个块是「正文 + 页码」，不是「纯页码」。

    过滤层此时**必须放手**：整块不是页码，丢它就把正文一起丢了。
    这不是过滤规则的缺陷，而是「按固定行数切」这个策略的局限——
    它切出来的单位是行窗口，不是语义单元，认不出哪一行是页脚。

    要真正解决，只有两条路：换按段落/标题切的策略，或者在解析阶段
    （文本还没进切块器之前）就把页眉页脚摘掉。这条测试存在的意义，
    就是把「什么时候该换策略」这个判断钉在证据上，而不是凭感觉。
    """
    config = ChunkConfig(strategy="fixed_lines", max_lines=3)

    result = chunk_text_result(path="expense.md", text=REALISTIC_DOC, config=config)

    glued = [c for c in result.kept if "第 2 页 / 共 3 页" in c.content]
    assert len(glued) == 1, "固定行数把页脚粘进了正文块，这是当前已知局限"
    assert "单次差旅报销上限" in glued[0].content


# ---------------------------------------------------------------------------
# 回归：过滤不能伤害已有评测
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("strategy", "max_lines"),
    [("fixed_lines", 3), ("code_ast", 3)],
)
def test_filtering_never_lowers_existing_hit_rate(strategy: str, max_lines: int):
    """过滤是减操作；如果它减掉了评测期望覆盖的块，命中数必然下降。"""
    (without,) = compare_strategies(
        configs=[
            ChunkConfig(
                strategy=strategy,
                max_lines=max_lines,
                filter=FilterConfig(enabled=False),
            )
        ]
    )
    (with_filter,) = compare_strategies(
        configs=[ChunkConfig(strategy=strategy, max_lines=max_lines)]
    )

    assert with_filter.total_cases == without.total_cases == 8
    assert with_filter.hits >= without.hits
    assert with_filter.hits_by_family == without.hits_by_family
