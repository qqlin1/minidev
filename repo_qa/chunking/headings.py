"""Markdown 结构解析 —— 找出标题行、算出块的边界。

这一层只做「读结构」：

    输入：一段 Markdown 文本
    输出：行号区间

**它不知道 ``Chunk`` 是什么**，也不生成任何块对象。这是刻意的分工：

- ``headings.py``（本模块）：这份文档的结构长什么样？
- ``strategies.py``：把结构变成 ``Chunk``，并处理降级

分开的好处是「读结构」这件事可以单独测——喂 42 行文本，断言 10 个标题、
10 个行号区间，不需要构造任何 ``Chunk``。结构解析错了，测试立刻指出是哪一步错；
混在一起写，你只能看到「切出来的块不对」，查起来要绕一圈。

核心规则（整个 markdown_heading 策略的地基）
--------------------------------------------
**每个标题行之前，断开。**

一个块 = 一个标题行 + 它下面的正文，一直到**下一个标题行（不管几级）**的前一行为止。

注意两件事：

1. **层级不参与切分决策。** 不管 ``#`` 还是 ``######``，只要出现标题就切一刀。
   层级只用来记录父子关系（拼标题路径、判断空壳块），不用来决定在哪里切。
   反直觉但正确：如果按层级嵌套着切，子节内容会在父块里重复出现一遍。

2. **块的结束行是「下一个标题行的前一行」，不是「下一个标题行的行」。**
   差一行，citation 就错了，而且这种错很难用眼睛看出来。
"""

from __future__ import annotations

from dataclasses import dataclass

# Markdown 标准只定义到 6 级。``#######``（7 个 #）按标准不是标题，
# 而且 ``str.lstrip("#")`` 那种写法会把 7 个 # 也吃掉——所以这里显式挡住。
MAX_HEADING_LEVEL = 6

# 哪些扩展名走这套结构解析。``.md`` 和 ``.markdown`` 是两个不同的字符串，
# 计算机比对扩展名是逐字符比，不会「举一反三」。
MARKDOWN_SUFFIXES: tuple[str, ...] = (".md", ".markdown")


def is_markdown_path(path: str) -> bool:
    """这个路径看起来是 Markdown 吗？

    用 ``lower()`` 是因为 Windows 上文件名大小写不敏感，
    ``README.MD`` 也该被认出来。
    """
    lowered = path.lower()
    return any(lowered.endswith(suffix) for suffix in MARKDOWN_SUFFIXES)


def find_headings(text: str) -> list[tuple[int, int, str]]:
    """找出文本里所有标题行，返回 ``[(行号, 层级, 标题文字), ...]``。

    - **行号**：从 1 开始数（Python 的 ``enumerate`` 默认从 0，这里显式传 ``start=1``）
    - **层级**：``#`` 的个数，1 到 6
    - **标题文字**：去掉 ``#`` 和它后面的空格之后剩下的文字

    判定规则
    --------
    去掉行首空格后，必须满足：

    1. 以 ``#`` 开头，且 ``#`` 的个数在 1 到 6 之间
    2. ``#`` 后面**紧跟空格**，或者**直接到行尾**
    3. 去掉空格后**还有文字**（只有 ``###`` 没有文字的空标题不算）

    第 2 条是关键决定：``#员工手册``（# 后没有空格）**不认**。

    理由不是「标准这么规定」（那是诉诸权威），而是**误判的代价不可逆**：
    真实技术文档里 ``#!/usr/bin/env python``、``#include <stdio.h>``、``#TODO:``、
    ``#region`` 这类行大量存在，且都不是标题。认了它们，切块策略会在这些行切一刀，
    **把完整的代码块从中间切开，而且修不回来**；漏判的代价只是「块大一点，信息没丢」。
    宁可少切一刀，不可错切一刀。

    真有人漏写空格，那是文档不规范，该在**摄取层规范化**或**直接拒收**，
    不该让切块策略去猜。

    第 3 条的理由：空标题不携带任何语义信息，却会制造一个必然被过滤掉的空块，
    还会让标题路径里出现空段。跳过它，让后面的内容归到上一节，更合理。
    """
    headings: list[tuple[int, int, str]] = []

    for line_no, line in enumerate(text.splitlines(), start=1):
        # 行首可以有空格（缩进），但 # 之后不能再有前导空格以外的干扰
        candidate = line.lstrip(" ")
        if not candidate.startswith("#"):
            continue

        # 数 # 的个数。用显式循环而不是 lstrip("#")，因为后者会把
        # #######（7 个）也当成标题，而且拿不到「到底是几个」。
        level = 0
        for char in candidate:
            if char != "#":
                break
            level += 1

        if level == 0 or level > MAX_HEADING_LEVEL:
            continue

        rest = candidate[level:]
        # 规则 2：# 后面必须紧跟分隔符（空格或制表符），或直接到行尾。
        #
        # 为什么同时认制表符：CommonMark 规范写的是「spaces or tabs」。
        # 只认空格的话，一份用 Tab 对齐的文档里所有标题都会漏掉，
        # 而漏掉的表现是「块变大了」，不是报错——这种静默降级最难查。
        #
        # 已知边界：全角空格（U+3000）不认。中文文档里偶尔会出现
        # ``#　标题``（全角空格）。不认它的理由是和 CommonMark 保持一致，
        # 而且这种写法属于文档不规范——应该在摄取层规范化，不该让切块策略猜。
        if rest and rest[0] not in " \t":
            continue

        title = rest.strip()
        # 规则 3：空标题不算
        if not title:
            continue

        headings.append((line_no, level, title))

    return headings


@dataclass(frozen=True, slots=True)
class BlockBound:
    """一个块的行号边界，以及它头顶上的标题信息。

    ``level == 0`` 是一个哨兵值，表示**这个块没有标题**——
    用在文档开头的说明文字上（第一个标题之前的内容）。
    这种块也要单独成块，否则那段说明会被丢掉。

    ``heading_path`` 是这一块所属的标题路径（祖先链），形如
    ``员工手册 > 第一章 考勤管理 > 1.2 迟到处理``。

    **它是这个模块存在的第二个理由。** 第一个理由是「在标题处断开」，
    第二个理由是「把结构信息搬到字段上」——这样即使某个块（比如只有标题、
    没有正文的空壳块）后来被过滤掉了，它携带的结构信息仍然留在子块的
    ``heading_path`` 里，不会丢。
    """

    start_line: int
    end_line: int
    level: int
    title: str
    heading_path: str = ""

    def __post_init__(self) -> None:
        if self.start_line < 1:
            raise ValueError("start_line must be at least 1")
        if self.end_line < self.start_line:
            raise ValueError("end_line must not be before start_line")
        if not 0 <= self.level <= MAX_HEADING_LEVEL:
            raise ValueError(f"level must be between 0 and {MAX_HEADING_LEVEL}")

    @property
    def line_count(self) -> int:
        """这个块占多少行。"""
        return self.end_line - self.start_line + 1

    @property
    def is_preamble(self) -> bool:
        """是不是「第一个标题之前」的那一段。"""
        return self.level == 0

    def citation_range(self) -> str:
        """只显示行号区间的形式，方便和期望值对照。"""
        return f"{self.start_line}-{self.end_line}"


# 标题路径里的分隔符。用 " > " 而不是 "/"，因为 "/" 在路径里已经有了
# （``docs/手册.md``），混在一起会读不清。
HEADING_PATH_SEPARATOR = " > "


def build_heading_paths(headings: list[tuple[int, int, str]]) -> list[str]:
    """为每个标题算出它的祖先路径（标题路径 / breadcrumb）。

    算法：**用一个栈维护当前的祖先链。**

    对每个标题，按顺序做三件事：

    1. 把栈里**层级 >= 当前标题层级**的项全部弹出去
       （它们不是我的祖先，是我之前的兄弟或更深的节点）
    2. 把当前标题压进栈
    3. 栈里剩下的就是「从根到当前标题」的完整链，用 `` > `` 连起来

    拿手册走一遍::

        读到 # 员工手册（1 级）
            栈空 -> 压入 -> [员工手册]
            路径 = 员工手册

        读到 ## 第一章 考勤管理（2 级）
            栈顶是 1 级，1 < 2，不弹
            压入 -> [员工手册, 第一章 考勤管理]
            路径 = 员工手册 > 第一章 考勤管理

        读到 ### 1.1 上班时间（3 级）
            栈顶是 2 级，2 < 3，不弹
            压入 -> [员工手册, 第一章 考勤管理, 1.1 上班时间]
            路径 = 员工手册 > 第一章 考勤管理 > 1.1 上班时间

        读到 ### 1.2 迟到处理（3 级）
            栈顶是 3 级，3 >= 3 -> 弹出 1.1 上班时间
            新栈顶是 2 级，2 < 3 -> 停
            压入 -> [员工手册, 第一章 考勤管理, 1.2 迟到处理]
            路径 = 员工手册 > 第一章 考勤管理 > 1.2 迟到处理

        读到 ## 第二章 报销制度（2 级）
            栈顶是 3 级，3 >= 2 -> 弹出 1.2 迟到处理
            新栈顶是 2 级，2 >= 2 -> 弹出 第一章 考勤管理
            新栈顶是 1 级，1 < 2 -> 停
            压入 -> [员工手册, 第二章 报销制度]
            路径 = 员工手册 > 第二章 报销制度

    **这个算法是「层级唯一参与决策」的地方。** 切分的时候层级不参与
    （只要出现标题就切），但拼路径的时候必须用层级——否则你不知道
    谁是爸爸、谁是兄弟。

    输入必须按行号升序（``find_headings`` 的输出天然满足）。
    """
    paths: list[str] = []
    stack: list[tuple[int, str]] = []  # [(层级, 标题文字), ...]

    for _line_no, level, title in headings:
        # 第 1 步：弹出所有「层级 >= 当前」的项
        while stack and stack[-1][0] >= level:
            stack.pop()
        # 第 2 步：压入当前标题
        stack.append((level, title))
        # 第 3 步：栈里就是完整的祖先链
        paths.append(HEADING_PATH_SEPARATOR.join(item[1] for item in stack))

    return paths


def compute_block_bounds(
    headings: list[tuple[int, int, str]],
    total_lines: int,
) -> list[BlockBound]:
    """按「每个标题行之前断开」算出每个块的行号区间。

    参数
    ----
    headings
        ``find_headings`` 的输出，必须按行号升序。
    total_lines
        文档总行数（``len(text.splitlines())``），用来给最后一个块收尾。

    返回
    ----
    块列表。**首尾相连、不重不漏**：第一个块从第 1 行开始，
    每个块从上一个块的结束行的下一行开始，最后一个块结束于 ``total_lines``。

    三条规则
    --------
    1. 每个块的结束行 = **下一个标题行的前一行**（不是下一个标题行本身）
    2. 第一个标题**之前**如果还有内容，单独成一个块（``level=0``，无标题）
    3. 文档一个标题都没有 → 返回空列表。这是给调用方的信号：
       「这份文档没有结构可用，请退回固定行数切」。本函数不替它做这个决定。

    为什么第 3 条返回空列表而不是「整篇算一块」：因为「没有标题」有两种可能——
    真的没有标题（比如纯文本），或者文档太短只有几行。
    两种情况都该由策略层统一走降级路径，本函数不该替它选。

    顺带算出 ``heading_path``
    -------------------------
    遍历标题的同时，用 ``build_heading_paths`` 算出每个标题的祖先链，
    填进每个块的 ``heading_path``。

    为什么**必须在这里**算、不能事后补：这一趟已经拿着完整的标题列表和层级，
    拼路径是零额外成本。事后补的话，要重新解析文档、再把块的行号和标题对上，
    很容易错位——而错位的表现是「路径指向了错误的章节」，非常难查。
    """
    if not headings:
        return []

    if total_lines < 1:
        raise ValueError("total_lines must be at least 1")

    heading_paths = build_heading_paths(headings)
    blocks: list[BlockBound] = []

    # 规则 2：第一个标题之前的内容。没有标题，所以路径是空的。
    first_heading_line = headings[0][0]
    if first_heading_line > 1:
        blocks.append(
            BlockBound(
                start_line=1,
                end_line=first_heading_line - 1,
                level=0,
                title="",
                heading_path="",
            )
        )

    for index, (line_no, level, title) in enumerate(headings):
        # 规则 1：结束行 = 下一个标题行的前一行
        if index + 1 < len(headings):
            end_line = headings[index + 1][0] - 1
        else:
            end_line = total_lines

        blocks.append(
            BlockBound(
                start_line=line_no,
                end_line=end_line,
                level=level,
                title=title,
                heading_path=heading_paths[index],
            )
        )

    return blocks


# ---------------------------------------------------------------------------
# 超长块的二级切分（题 4）
# ---------------------------------------------------------------------------


def split_oversized_block(
    lines: list[str],
    start_line: int,
    max_lines: int,
) -> list[tuple[int, int]]:
    """把一个超过 ``max_lines`` 的块再切开，返回 ``[(起始行, 结束行), ...]``。

    为什么需要这一步
    ----------------
    按标题切出来的块，长度完全由文档决定，不由你决定。
    一个 ``##`` 章节可能有 3000 行——直接入库会撑爆上下文窗口，
    而且 embedding 的语义会被稀释成「什么都沾一点」。

    策略：**优先在空行（段落边界）断开，实在找不到就硬切。**

    为什么要「优先空行」而不是直接按行数硬切
    ----------------------------------------
    空行是作者标出来的**语义边界**。在这里断开，句子是完整的；
    硬切会把一句话从中间切断，两个半句分别进两个块，
    **两个块都读不懂这句话**。

    为什么要保证「标题不单独成块」
    ------------------------------
    块里只有一行 ``### 2.1 差旅报销``、正文在下一块，等于把标题和它的正文又拆散了——
    那就白做这个策略了。所以本函数要求：**断点之前必须已经有标题 + 至少一行正文**。
    实现上体现为 ``min_fill`` 和 ``nonblank >= 2`` 两个条件。

    参数
    ----
    lines
        这个块包含的所有行（``lines[0]`` 就是块的起始行）。
    start_line
        ``lines[0]`` 在**原文**里的行号。返回的区间要换算回原文行号，
        否则 citation 会指向错误的位置。
    max_lines
        每个子块最多多少行。必须 >= 1。
    """
    if max_lines < 1:
        raise ValueError("max_lines must be at least 1")

    total = len(lines)
    if total == 0:
        return []
    if total <= max_lines:
        return [(start_line, start_line + total - 1)]

    # 至少积累这么多行才允许在空行处断开。
    # 取 max_lines 的一半（但不少于 2），目的是别在窗口开头就断掉、
    # 白白浪费剩下的空间。
    min_fill = max(2, max_lines // 2)

    spans: list[tuple[int, int]] = []
    cursor = 0

    while cursor < total:
        remaining = total - cursor
        if remaining <= max_lines:
            spans.append((start_line + cursor, start_line + total - 1))
            break

        count = 0
        nonblank = 0
        cut: int | None = None

        for index in range(cursor, total):
            count += 1
            if lines[index].strip():
                nonblank += 1

            # 到上限了，必须断
            if count >= max_lines:
                cut = index
                break

            # 空行 + 已经填得够多 + 标题后面已经有正文 → 这是个好的断点
            if not lines[index].strip() and count >= min_fill and nonblank >= 2:
                cut = index
                break

        if cut is None:
            # 循环走到文件末尾都没触发断点，兜底硬切
            cut = min(cursor + max_lines, total) - 1

        spans.append((start_line + cursor, start_line + cut))
        cursor = cut + 1

    return spans
