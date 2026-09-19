"""RAG domain models — Chunk schema (①).

职责：定义「一块可引用的仓库文本」长什么样：路径、行号区间、内容、稳定 citation、
以及它所属的标题路径。

明确不负责：文件扫描、切分算法、embedding、检索或入库。
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chunk:
    """A citeable piece of text from one file in the indexed repository.

    关于 ``heading_path``（标题路径）这个字段
    -----------------------------------------
    它记录「这一块属于文档的哪个位置」，形如::

        员工手册 > 第一章 考勤管理 > 1.2 迟到处理

    为什么需要它：块的内容里通常只有正文，模型看不出这段属于哪一章。
    用户问「考勤相关的规定有哪些」，如果模型手上只有一段孤立的正文，
    它不知道这段属不属于考勤。

    为什么它是**独立字段**而不是拼进 ``content``：
    ``content`` 必须等于「原文对应行的原文」——这条不变量是两个东西的基础：

    1. **可验证性**：把块的 content 按行号拼回去，必须和原文逐字对上。
       这是检查「行号有没有错位」的唯一硬手段（文字本身是对的，只有行号错了，
       光看内容看不出来）。
    2. **可回溯性**：citation 是 ``path:11-15``，用户点击要能跳回原文。
       如果 content 里多了原文没有的一行，这个对应关系就断了。

    所以：``content`` 是给「入库和回溯」用的（忠实原文），
    ``heading_path`` 是给「检索后拼给模型看」用的（可以加工）。

    默认空字符串：``fixed_lines`` 和 ``code_ast`` 没有标题概念，
    它们产生的块这个字段永远是空的。**只有 ``markdown_heading`` 能填它。**
    """

    path: str
    start_line: int
    end_line: int
    content: str
    heading_path: str = ""

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("path must not be empty")
        if self.start_line < 1:
            raise ValueError("start_line must be at least 1")
        if self.end_line < self.start_line:
            raise ValueError("end_line must not be before start_line")
        if not self.content.strip():
            raise ValueError("content must not be empty")

    @property
    def citation(self) -> str:
        """The stable source location shown beside a future RAG answer."""
        return f"{self.path}:{self.start_line}-{self.end_line}"

    def as_prompt_text(self) -> str:
        """拼给模型看的文本：标题路径 + 原文内容。

        注意这个方法**不改 content**，只是临时拼一份给模型看的版本。
        入库的仍是 ``content``（忠实原文），这份拼好的文本只在
        「检索命中之后、送给模型之前」这一刻生成。

        为什么要区分：如果直接把标题路径写进 content 存库，
        将来标题路径变了（文档改名、章节调整），已经入库的内容就过期了，
        得重新做 embedding。而用这个方法，改路径只影响「拼给模型」这一步，
        不用重算向量。
        """
        if not self.heading_path:
            return self.content
        return f"【{self.heading_path}】\n\n{self.content}"
