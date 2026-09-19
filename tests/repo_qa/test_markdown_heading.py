"""markdown_heading 策略测试 —— 标题解析、边界计算、降级、超长章节。

这个文件覆盖四层，每层单独测，出错时能立刻定位是哪一层：

1. ``find_headings``：找出标题行
2. ``compute_block_bounds``：算出块的行号区间
3. ``MarkdownHeadingStrategy.split``：拼成策略 + 三条降级
4. ``split_oversized_block``：超长块的二级切分

为什么分层测而不是只测最终的 Chunk 列表：
只测最终结果的话，「切出来的块不对」可能来自标题识别错、边界算错、
二级切分错三个地方，你得一个个排除。分层之后，哪层的测试红了就是哪层的问题。

全部离线：不访问网络、不读项目根目录的临时文件（语料从 eval 夹具取）。
"""

from __future__ import annotations

import pytest

from repo_qa.chunking import Chunk, ChunkConfig, chunk_text_result
from repo_qa.chunking.headings import (
    BlockBound,
    build_heading_paths,
    compute_block_bounds,
    find_headings,
    is_markdown_path,
    split_oversized_block,
)
from repo_qa.chunking.strategies import STRATEGIES, FixedLinesStrategy
from repo_qa.eval.cases import EMPLOYEE_HANDBOOK

HANDBOOK_LINES = EMPLOYEE_HANDBOOK.splitlines()
HANDBOOK_TOTAL = len(HANDBOOK_LINES)
STRATEGY = STRATEGIES["markdown_heading"]

# 地面真值：脚本从文档里数出来的
EXPECTED_HEADING_LINES = [1, 3, 5, 11, 16, 18, 27, 32, 34, 39]
EXPECTED_RANGES = [
    (1, 2), (3, 4), (5, 10), (11, 15), (16, 17),
    (18, 26), (27, 31), (32, 33), (34, 38), (39, 42),
]


# ===========================================================================
# 第一层：find_headings
# ===========================================================================


def test_finds_exactly_ten_headings_in_handbook():
    headings = find_headings(EMPLOYEE_HANDBOOK)
    assert [h[0] for h in headings] == EXPECTED_HEADING_LINES


def test_heading_carries_line_number_level_and_title():
    headings = find_headings(EMPLOYEE_HANDBOOK)
    assert headings[0] == (1, 1, "员工手册")
    assert headings[2] == (5, 3, "1.1 上班时间")
    assert headings[5] == (18, 3, "2.1 差旅报销")


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
def test_recognizes_all_six_levels(level: int):
    text = f"{'#' * level} 标题文字"
    assert find_headings(text) == [(1, level, "标题文字")]


def test_seven_hashes_is_not_a_heading():
    """7 个 # 超过 Markdown 定义的 6 级上限，不算标题。

    这条钉住的是 ``str.lstrip("#")`` 那个坑：lstrip 会把所有 # 都削掉，
    于是 ####### 也会被当成标题，而且拿不到「到底是几个」。
    """
    assert find_headings("####### 七个井号") == []


def test_multiple_spaces_after_hashes_still_count():
    assert find_headings("#  员工手册") == [(1, 1, "员工手册")]
    assert find_headings("#\t制表符") == [(1, 1, "制表符")]


def test_hash_without_space_is_rejected():
    """# 后面没有空格 → 不认。

    理由不是「标准这么规定」，而是误判的代价不可逆：
    真实技术文档里 #!/usr/bin/env python、#include <stdio.h>、#TODO:、#region
    这类行大量存在且都不是标题。认了它们，切块会在这些行切一刀，
    把完整代码块从中间切开，而且修不回来。
    """
    assert find_headings("#员工手册") == []
    assert find_headings("#!/usr/bin/env python") == []
    assert find_headings("#include <stdio.h>") == []
    assert find_headings("#TODO: 补充说明") == []


def test_empty_heading_is_skipped():
    """只有 # 没有文字 → 不认。空标题不携带信息，只会制造必然被过滤的空块。"""
    assert find_headings("###") == []
    assert find_headings("##   ") == []


def test_body_and_blank_lines_are_not_headings():
    text = "普通正文\n\n还有一行正文\n\n# 真标题\n"
    assert find_headings(text) == [(5, 1, "真标题")]


def test_indented_heading_still_counts():
    assert find_headings("   ## 缩进的标题") == [(1, 2, "缩进的标题")]


def test_text_without_any_heading_returns_empty():
    assert find_headings("纯文本\n\n没有任何井号\n") == []


# ===========================================================================
# 第二层：compute_block_bounds
# ===========================================================================


def test_computes_ten_blocks_for_handbook():
    blocks = compute_block_bounds(find_headings(EMPLOYEE_HANDBOOK), HANDBOOK_TOTAL)
    assert [(b.start_line, b.end_line) for b in blocks] == EXPECTED_RANGES


def test_anchor_blocks_match_task_spec():
    """两个锚点：第 3 个块是 5-10，第 6 个块是 18-26。"""
    blocks = compute_block_bounds(find_headings(EMPLOYEE_HANDBOOK), HANDBOOK_TOTAL)
    assert (blocks[2].start_line, blocks[2].end_line) == (5, 10)
    assert (blocks[5].start_line, blocks[5].end_line) == (18, 26)


def test_blocks_are_contiguous_and_cover_everything():
    """首尾相连不重不漏，最后一块结束行 == 文档总行数。"""
    blocks = compute_block_bounds(find_headings(EMPLOYEE_HANDBOOK), HANDBOOK_TOTAL)
    expected_start = 1
    for block in blocks:
        assert block.start_line == expected_start
        expected_start = block.end_line + 1
    assert expected_start == HANDBOOK_TOTAL + 1


def test_block_ends_at_line_before_next_heading():
    """第 3 个块结束于第 10 行，因为下一个标题在第 11 行。

    这条钉住「结束行 = 下一个标题行的**前一行**」这个容易差一行的规则。
    差一行 citation 就错了，而且很难用眼睛看出来。
    """
    blocks = compute_block_bounds(find_headings(EMPLOYEE_HANDBOOK), HANDBOOK_TOTAL)
    headings = find_headings(EMPLOYEE_HANDBOOK)
    assert blocks[2].end_line == headings[3][0] - 1 == 10


def test_no_headings_returns_empty_list():
    """没有标题 → 返回空列表，这是给调用方的「请走降级」信号。"""
    assert compute_block_bounds([], 42) == []


def test_preamble_before_first_heading_becomes_its_own_block():
    """第一个标题之前的内容要单独成块（level=0 表示没有标题）。"""
    text = "这是文档开头的说明文字。\n\n# 第一章\n\n正文。\n"
    blocks = compute_block_bounds(find_headings(text), len(text.splitlines()))
    assert len(blocks) == 2
    assert blocks[0].is_preamble
    assert (blocks[0].start_line, blocks[0].end_line) == (1, 2)
    assert blocks[1].title == "第一章"


def test_block_bound_rejects_invalid_ranges():
    with pytest.raises(ValueError):
        BlockBound(start_line=0, end_line=5, level=1, title="x")
    with pytest.raises(ValueError):
        BlockBound(start_line=5, end_line=3, level=1, title="x")
    with pytest.raises(ValueError):
        BlockBound(start_line=1, end_line=3, level=7, title="x")


# ===========================================================================
# 第三层：MarkdownHeadingStrategy
# ===========================================================================


@pytest.mark.parametrize(
    "path",
    ["handbook.md", "docs/手册.MD", "notes.markdown"],
)
def test_is_markdown_path_accepts_md_variants(path: str):
    assert is_markdown_path(path)


@pytest.mark.parametrize("path", ["client.py", "app.ini", "notes.txt", "readme"])
def test_is_markdown_path_rejects_others(path: str):
    assert not is_markdown_path(path)


def test_strategy_splits_handbook_into_ten_blocks():
    """max_lines 足够大时不触发二级切分，正好 10 个块。"""
    chunks = STRATEGY.split(path="handbook.md", text=EMPLOYEE_HANDBOOK, max_lines=50)
    assert len(chunks) == 10
    assert [c.citation for c in chunks] == [
        f"handbook.md:{start}-{end}" for start, end in EXPECTED_RANGES
    ]


def test_strategy_content_round_trips_to_source():
    """把块的 content 按行号拼回去，必须和原文逐字对上。

    这一条是「行号有没有错位」的硬证据。错位时 citation 会指向错误位置，
    而看块的预览文字是看不出来的（文字本身是对的，只是行号错了）。
    """
    chunks = STRATEGY.split(path="handbook.md", text=EMPLOYEE_HANDBOOK, max_lines=50)

    rebuilt: list[str | None] = [None] * HANDBOOK_TOTAL
    for chunk in chunks:
        for offset, line in enumerate(chunk.content.splitlines()):
            rebuilt[chunk.start_line - 1 + offset] = line

    for index, original in enumerate(HANDBOOK_LINES):
        if rebuilt[index] is not None:
            assert rebuilt[index] == original, f"第 {index + 1} 行错位"


def test_strategy_falls_back_for_non_markdown_path():
    """降级 1：非 Markdown 路径 → 退回固定行数。"""
    code = "import os\n\n\ndef f():\n    return 1\n"
    via_md = STRATEGY.split(path="service.py", text=code, max_lines=2)
    via_fixed = FixedLinesStrategy().split(path="service.py", text=code, max_lines=2)
    assert [(c.start_line, c.end_line) for c in via_md] == [
        (c.start_line, c.end_line) for c in via_fixed
    ]


def test_strategy_falls_back_when_no_headings():
    """降级 2：一个标题都没有 → 退回固定行数。"""
    plain = "纯文本第一行\n纯文本第二行\n纯文本第三行\n"
    chunks = STRATEGY.split(path="notes.md", text=plain, max_lines=2)
    assert len(chunks) == 2


def test_strategy_returns_empty_for_blank_text():
    """降级 3：空文本 → 空列表。"""
    assert STRATEGY.split(path="notes.md", text="", max_lines=6) == []
    assert STRATEGY.split(path="notes.md", text="   \n\n  \t ", max_lines=6) == []


def test_strategy_does_not_emit_whitespace_only_chunks():
    """整块都是空白的，不生成 Chunk（Chunk 本身也会拒绝空内容）。"""
    text = "# 标题\n\n\n\n\n# 第二个\n"
    chunks = STRATEGY.split(path="notes.md", text=text, max_lines=50)
    assert all(c.content.strip() for c in chunks)


def test_unknown_strategy_raises():
    from repo_qa.chunking.strategies import get_strategy

    with pytest.raises(ValueError, match="unknown strategy"):
        get_strategy("does_not_exist")


# ===========================================================================
# 第四层：split_oversized_block（题 4）
# ===========================================================================


def test_no_split_when_block_fits():
    lines = ["a", "b", "c"]
    assert split_oversized_block(lines, start_line=1, max_lines=5) == [(1, 3)]


def test_every_piece_respects_max_lines():
    lines = [f"line {i}" for i in range(1, 21)]
    spans = split_oversized_block(lines, start_line=1, max_lines=6)
    for start, end in spans:
        assert end - start + 1 <= 6


def test_pieces_are_contiguous_and_cover_the_block():
    lines = [f"line {i}" for i in range(1, 21)]
    spans = split_oversized_block(lines, start_line=1, max_lines=6)
    expected_start = 1
    for start, end in spans:
        assert start == expected_start
        expected_start = end + 1
    assert expected_start == 21


def test_prefers_blank_line_as_break_point():
    """优先在空行（段落边界）断开，而不是硬切。"""
    lines = [
        "## 标题", "", "段落一第一行", "段落一第二行", "",
        "段落二第一行", "段落二第二行", "", "段落三第一行", "段落三第二行",
    ]
    spans = split_oversized_block(lines, start_line=1, max_lines=6)
    # 第一个断点应落在第 5 行（空行）上，而不是第 6 行（段落二中间）
    assert spans[0] == (1, 5)


def test_heading_is_not_left_alone():
    """标题不能单独成块——否则等于白做这个策略。"""
    lines = [
        "### 2.1 差旅报销", "", "正文一", "正文二", "正文三", "正文四",
        "正文五", "正文六", "",
    ]
    spans = split_oversized_block(lines, start_line=18, max_lines=6)
    first_start, first_end = spans[0]
    assert first_start == 18
    assert first_end > 19, "第一个子块必须包含标题之后的正文"


def test_handbook_long_block_splits_into_two():
    """手册里 18-26 那 9 行，按 max_lines=6 切成 18-23 和 24-26。"""
    lines = HANDBOOK_LINES[17:26]
    spans = split_oversized_block(lines, start_line=18, max_lines=6)
    assert spans == [(18, 23), (24, 26)]


def test_max_lines_one_does_not_hang():
    """max_lines=1 时每行一块，不能死循环。

    这是边界测试：如果 min_fill 或断点逻辑写错，max_lines=1 最容易触发死循环。
    """
    lines = [f"line {i}" for i in range(1, 11)]
    spans = split_oversized_block(lines, start_line=1, max_lines=1)
    assert len(spans) == 10
    assert all(end == start for start, end in spans)


def test_empty_lines_returns_empty():
    assert split_oversized_block([], start_line=1, max_lines=6) == []


def test_invalid_max_lines_raises():
    with pytest.raises(ValueError, match="max_lines must be at least 1"):
        split_oversized_block(["a"], start_line=1, max_lines=0)


# ===========================================================================
# 端到端：策略 + 二级切分
# ===========================================================================


def test_tight_max_lines_splits_only_the_long_block():
    """max_lines=6 时，只有 18-26 那块被切开，其余 9 块不动。"""
    chunks = STRATEGY.split(path="handbook.md", text=EMPLOYEE_HANDBOOK, max_lines=6)
    ranges = [(c.start_line, c.end_line) for c in chunks]

    assert len(ranges) == 11
    assert (18, 23) in ranges
    assert (24, 26) in ranges
    assert (18, 26) not in ranges
    # 其余块原样保留
    for original in EXPECTED_RANGES:
        if original != (18, 26):
            assert original in ranges


def test_all_blocks_respect_max_lines_end_to_end():
    for max_lines in (1, 2, 3, 6, 9, 50):
        chunks = STRATEGY.split(
            path="handbook.md", text=EMPLOYEE_HANDBOOK, max_lines=max_lines
        )
        for chunk in chunks:
            size = chunk.end_line - chunk.start_line + 1
            assert size <= max_lines, f"max_lines={max_lines} 时 {chunk.citation} 有 {size} 行"


# ===========================================================================
# 第五层：标题路径（heading_path）
#
# 这一层解决的是「空壳块被过滤掉之后，结构信息去哪了」。
# 核心论断：**把结构信息从「块」搬到「字段」，空壳块就可以放心丢掉。**
# ===========================================================================


def test_heading_paths_follow_the_document_tree():
    paths = build_heading_paths(find_headings(EMPLOYEE_HANDBOOK))
    assert paths == [
        "员工手册",
        "员工手册 > 第一章 考勤管理",
        "员工手册 > 第一章 考勤管理 > 1.1 上班时间",
        "员工手册 > 第一章 考勤管理 > 1.2 迟到处理",
        "员工手册 > 第二章 报销制度",
        "员工手册 > 第二章 报销制度 > 2.1 差旅报销",
        "员工手册 > 第二章 报销制度 > 2.2 办公用品",
        "员工手册 > 第三章 假期管理",
        "员工手册 > 第三章 假期管理 > 3.1 年假",
        "员工手册 > 第三章 假期管理 > 3.2 病假",
    ]


def test_sibling_heading_replaces_previous_sibling():
    """同级标题应该替换掉前一个同级，而不是叠加。

    ``### 1.1`` 读到 ``### 1.2`` 时，栈里要弹出 ``1.1``——
    它们是兄弟，不是父子。这条错了会拼出
    「员工手册 > 第一章 > 1.1 上班时间 > 1.2 迟到处理」这种荒谬的路径。
    """
    text = "# 根\n\n## 章\n\n### 甲\n\n### 乙\n"
    paths = build_heading_paths(find_headings(text))
    assert paths[2] == "根 > 章 > 甲"
    assert paths[3] == "根 > 章 > 乙", "乙不该把甲当成自己的父节点"


def test_higher_level_heading_pops_the_whole_subtree():
    """读到更浅的标题时，要一直弹到合适的层级。

    ``### 1.2`` 后面读到 ``## 第二章``，栈里要弹出 ``1.2`` **和** ``第一章``——
    因为第二章和第一章是兄弟，都属于根节点。
    """
    text = "# 根\n\n## 甲章\n\n### 甲节\n\n## 乙章\n"
    paths = build_heading_paths(find_headings(text))
    assert paths[1] == "根 > 甲章"
    assert paths[2] == "根 > 甲章 > 甲节"
    assert paths[3] == "根 > 乙章", "乙章不该把甲章当成父节点"


def test_skipped_level_still_works():
    """层级跳跃（从 1 级直接到 3 级）不崩，路径按实际栈拼。"""
    text = "# 根\n\n### 跳级的小节\n"
    paths = build_heading_paths(find_headings(text))
    assert paths[1] == "根 > 跳级的小节"


def test_empty_headings_gives_empty_paths():
    assert build_heading_paths([]) == []


def test_chunks_carry_heading_path():
    chunks = STRATEGY.split(path="handbook.md", text=EMPLOYEE_HANDBOOK, max_lines=50)
    by_citation = {c.citation: c for c in chunks}

    assert by_citation["handbook.md:11-15"].heading_path == (
        "员工手册 > 第一章 考勤管理 > 1.2 迟到处理"
    )
    assert by_citation["handbook.md:18-26"].heading_path == (
        "员工手册 > 第二章 报销制度 > 2.1 差旅报销"
    )


def test_dropped_empty_shell_block_loses_no_structure_information():
    """**这是整个 heading_path 设计的核心证据。**

    事实：``# 员工手册``（第 1-2 行）那个块只有标题、没有正文，
    内容只有 6 个字符，会被 ``too_short`` 过滤规则丢掉。

    问题：丢掉它，是不是就丢了「这份文档叫员工手册」这个信息？

    答案：**没有丢。** 因为它的信息已经被所有子块继承了——
    每一个保留块的 ``heading_path`` 都以 ``员工手册`` 开头。

    所以结论是：**空壳块可以放心丢，只要标题路径算出来了。**
    这就是「把结构信息从块搬到字段」的效果。
    """
    result = chunk_text_result(
        path="handbook.md",
        text=EMPLOYEE_HANDBOOK,
        config=ChunkConfig(strategy="markdown_heading", max_lines=50),
    )

    # 确认前提：确实有一块被丢了
    assert len(result.dropped) == 1
    dropped = result.dropped[0]
    assert dropped.chunk.citation == "handbook.md:1-2"
    assert dropped.rule == "too_short"

    # 核心断言：被丢的那块的标题，在每一个保留块的路径里都能找到
    lost_title = dropped.chunk.heading_path  # "员工手册"
    assert lost_title == "员工手册"
    for chunk in result.kept:
        assert lost_title in chunk.heading_path, (
            f"{chunk.citation} 的路径 {chunk.heading_path!r} 里没有 {lost_title!r}，"
            "说明丢空壳块造成了结构信息丢失"
        )


def test_dropped_chapter_shell_blocks_also_lose_nothing():
    """三个章节空壳块（``## 第X章``）即便被丢，信息也在子块里。

    当前它们因为恰好 11 个字符（阈值 10）而侥幸存活，
    但这个测试**不依赖它们是否存活**——它验证的是「即便丢了也不丢信息」。

    这样设计的原因：那三个块能活下来纯属巧合（只比阈值多 1 个字符）。
    测试如果依赖「它们活着」，将来文档改一个字就会红，
    而红的原因跟被测的性质无关。所以断言要写成「无论死活，信息都在」。
    """
    result = chunk_text_result(
        path="handbook.md",
        text=EMPLOYEE_HANDBOOK,
        config=ChunkConfig(strategy="markdown_heading", max_lines=50),
    )

    for chapter in ("第一章 考勤管理", "第二章 报销制度", "第三章 假期管理"):
        carriers = [c for c in result.kept if chapter in c.heading_path]
        assert carriers, f"{chapter!r} 在任何保留块的路径里都找不到"


def test_sub_blocks_share_the_same_heading_path():
    """二级切分出来的子块共用同一个标题路径。

    第二个子块尤其需要它——它的正文里没有标题（标题留在了第一个子块），
    标题路径是它唯一能知道「我属于哪一节」的地方。
    """
    chunks = STRATEGY.split(path="handbook.md", text=EMPLOYEE_HANDBOOK, max_lines=6)
    by_citation = {c.citation: c for c in chunks}

    first = by_citation["handbook.md:18-23"]
    second = by_citation["handbook.md:24-26"]

    assert first.heading_path == second.heading_path
    assert first.heading_path == "员工手册 > 第二章 报销制度 > 2.1 差旅报销"
    assert "###" not in second.content, "第二个子块里确实没有标题"


def test_preamble_block_has_empty_heading_path():
    """第一个标题之前的内容没有标题，路径是空的。"""
    text = "开头的说明文字。\n\n# 第一章\n\n正文。\n"
    chunks = STRATEGY.split(path="notes.md", text=text, max_lines=50)
    assert chunks[0].heading_path == ""


def test_non_markdown_strategies_leave_heading_path_empty():
    """fixed_lines 和 code_ast 没有标题概念，路径永远是空字符串。

    这暴露了一个设计事实：**只有 markdown_heading 能填这个字段。**
    这是「接口被一个实现绑架」的信号——但因为字段带默认值，
    另外两个策略不用改一行代码，所以代价可以接受。
    """
    code = "import os\n\n\ndef f():\n    return 1\n"
    fixed_chunks = FixedLinesStrategy().split(path="a.py", text=code, max_lines=3)
    ast_chunks = STRATEGIES["code_ast"].split(path="a.py", text=code, max_lines=3)

    assert all(c.heading_path == "" for c in fixed_chunks)
    assert all(c.heading_path == "" for c in ast_chunks)


def test_as_prompt_text_prepends_path_without_changing_content():
    """``as_prompt_text()`` 拼出给模型看的版本，但不改 ``content``。

    这是「入库的文本」和「给模型看的文本」分开的落点：
    - ``content`` 保持忠实原文（citation 要对得上）
    - ``as_prompt_text()`` 临时拼一份带路径的，只在送给模型那一刻用
    """
    chunks = STRATEGY.split(path="handbook.md", text=EMPLOYEE_HANDBOOK, max_lines=50)
    target = next(c for c in chunks if c.citation == "handbook.md:11-15")

    prompt_text = target.as_prompt_text()

    assert prompt_text.startswith("【员工手册 > 第一章 考勤管理 > 1.2 迟到处理】")
    assert target.content in prompt_text, "原文内容必须原样保留在里面"
    assert "【" not in target.content, "content 本身不该被污染"


def test_as_prompt_text_is_content_when_no_path():
    """没有路径时，拼给模型的文本就是原文。"""
    chunk = Chunk(path="a.py", start_line=1, end_line=1, content="x = 1")
    assert chunk.as_prompt_text() == "x = 1"


def test_content_round_trip_still_works_with_heading_path():
    """加了字段之后，「content 拼回原文」这条不变量必须仍然成立。

    这是回归保护：如果有人把标题路径拼进 content 来实现 heading_path，
    这条测试会立刻红。
    """
    chunks = STRATEGY.split(path="handbook.md", text=EMPLOYEE_HANDBOOK, max_lines=6)

    rebuilt: list[str | None] = [None] * HANDBOOK_TOTAL
    for chunk in chunks:
        for offset, line in enumerate(chunk.content.splitlines()):
            rebuilt[chunk.start_line - 1 + offset] = line

    for index, original in enumerate(HANDBOOK_LINES):
        if rebuilt[index] is not None:
            assert rebuilt[index] == original, f"第 {index + 1} 行错位"
