"""摄取层的数据结构 —— 一次摄取产出的所有形状。

三个东西，各回答一个问题：

- ``IngestedDoc``：「一个成功读进来的文档，长什么样？」
- ``RejectedFile``：「一个被挡在外面的文件，是谁挡的、为什么？」
- ``IngestReport``：「这一次摄取，整体情况如何？」

为什么要单独建 ``RejectedFile`` 而不是「不收就不收了」
------------------------------------------------------
不收的文件必须有下落。理由有三个，一个比一个硬：

1. **排障**：语料明明放进去了，检索却查不到——是没收？是切坏了？是过滤丢了？
   没有记录就只能靠猜。
2. **安全审计**：如果 ``docs/`` 里混进一个 ``.env``，被准入层挡下这件事本身
   就是一条需要留痕的事件。没记录等于「不知道发生过」。
3. **阈值调参**：将来准入规则变松或变紧（比如文件大小上限从 1MB 调到 5MB），
   你需要知道「按新阈值，会多收进来哪些、少收出去哪些」。
   没有历史记录就只能拿当前语料重跑一遍，而语料会变。

这和已有 ``FilterResult`` 的设计是同一条原则：
**只返回「留下了什么」的接口，看不见问题。**
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IngestedDoc:
    """一个成功读进内存的文档。

    注意 ``doc_id`` 和 ``path`` 是两个字段，不是一回事：

    - ``doc_id`` 是**身份**，由内容 hash 得出，回答「这份内容我见过没有」
    - ``path`` 是**展示名**，回答「人眼该看到哪个文件名」

    改名不动内容时，``doc_id`` 不变（不会白重做一次 embedding）；
    改内容不动名字时，``doc_id`` 变（能发现知识库该更新了）。
    把这两个塞进同一个字段，上面两条性质就会同时失去。
    """

    path: str
    doc_id: str
    text: str
    line_count: int

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("path must not be empty")
        if not self.doc_id:
            raise ValueError("doc_id must not be empty")
        if self.line_count < 0:
            raise ValueError("line_count must not be negative")


@dataclass(frozen=True, slots=True)
class RejectedFile:
    """一个没能进入知识库的文件，以及是谁挡的、为什么。

    ``stage`` 区分它是在哪一步被挡下的——这个字段是排障的关键：

    - ``admission``：读都还没读，准入层就判定不该收（密钥文件、太大、空文件）
    - ``loading``：准入放行了，但读的时候失败（编码不认识、权限不足、是目录）
    """

    path: str
    stage: str
    reason: str

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("path must not be empty")
        if self.stage not in ("admission", "loading"):
            raise ValueError(f"unknown stage: {self.stage!r}")


@dataclass(frozen=True, slots=True)
class IngestReport:
    """一次完整摄取的账单。

    ``docs`` 是成功读进来的，``rejected`` 是被挡在外面的，两个都要有。
    ``scanned`` 是**准入层看过多少个文件**——注意它不等于
    ``len(docs) + len(rejected)`` 的全部含义：准入层看过的文件里，
    有一部分是因为扩展名不匹配被**跳过**的（skip ≠ reject），
    跳过的不算失败，所以单独计数。
    """

    root: str
    scanned: int
    skipped: int
    docs: tuple[IngestedDoc, ...]
    rejected: tuple[RejectedFile, ...]

    @property
    def doc_count(self) -> int:
        return len(self.docs)

    @property
    def total_lines(self) -> int:
        return sum(d.line_count for d in self.docs)

    def rejected_by_stage(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.rejected:
            counts[item.stage] = counts.get(item.stage, 0) + 1
        return counts

    def summary(self) -> str:
        """给人看的一行摘要。数字全部来自真实统计，不写死。"""
        parts = [
            f"扫描 {self.scanned} 个文件",
            f"跳过 {self.skipped} 个（类型不匹配）",
            f"收下 {self.doc_count} 个",
            f"共 {self.total_lines} 行",
        ]
        if self.rejected:
            by_stage = "，".join(
                f"{stage} {count} 个" for stage, count in sorted(self.rejected_by_stage().items())
            )
            parts.append(f"拒绝 {len(self.rejected)} 个（{by_stage}）")
        return "；".join(parts)
