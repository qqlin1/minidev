"""Indexing 层的数据结构 —— 幂等导入的词汇表。

这一层解决一个问题：**同一批文档导入多次，结果必须一样。**

为什么需要它
------------
摄取（``ingest``）负责「把文件读进内存」，切块（``chunking``）负责「把文本切成块」，
但两者都不负责「**记住上次导入了什么**」。

没有这一层会怎样：每次导入都往库里插新块，导两次库里就有两份，
用户搜同一个问题会看到两遍答案，而且每次都白做一遍 embedding（按量计费）。
最危险的是文档更新之后：旧块还在、新块又插进来，用户可能搜到**过期答案**。

核心思路
--------
导入之前先问一句：「这个东西我上次见过没有？」

要回答它需要两样东西：

1. 给每个文档一个**稳定的身份** —— ``doc_id``（内容 hash），来自 ingest 层
2. **记住**上次导入了什么 —— ``Manifest``（账本），就是本模块定义的

两个键，缺一不可
----------------
- ``doc_id``（内容指纹）回答：「**内容变没变**」
- ``path``（文件路径）回答：「**是哪个文件**」

只看一个会误判：

- 只看 ``doc_id``：内容改了会被误判成「新文档」，旧的没删 → 新旧并存
- 只看 ``path``：改名会被误判成「新文档」，白做一次 embedding

四个动作 + 一个删除
-------------------
``ImportAction`` 的五个取值对应「比对结果」，不是「存储操作」。
**存储层不该听懂这些词** —— 它只提供「按 doc_id 存/删/查」这类数据操作。
「改名」这个动作在存储层是**什么都不做**（只改账本里的路径），
所以它不该出现在存储层的接口里。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class DocStatus(str, Enum):
    """一个文档在导入流水线里处于哪个阶段。

    这是**状态机**，不是布尔标记。三个状态的意义：

    ``PROCESSING``
        某个进程正在处理它（正在切块 / 向量化 / 写库）。
        **这个状态本身就是一把锁** —— 别的进程看到它就不该再动这份文档。

    ``READY``
        处理完成，块已经写进库里了。下次导入看到它就跳过。

    ``FAILED``
        处理过程中出错了（切块失败、embedding 服务挂了、磁盘满了）。
        保留这个状态是为了**让失败可见**，并且允许重试。

    为什么需要 ``PROCESSING`` 这个中间状态
    --------------------------------------
    它一次解决两个问题：

    1. **并发安全**：两个进程同时导入同一批文档时，先抢到锁的把状态置为
       ``PROCESSING``，后到的看到就知道「有人在做，我别重复做」。
       没有这个状态，两个进程会同时切块、同时做 embedding —— 白花一倍的钱。

    2. **让「先写记录」变安全**：如果不带状态，「先写记录」意味着
       「记录说导完了，但块可能没写」，下次会静默跳过。
       带上状态之后，记录写的是「我正在做」而不是「我做完了」，
       崩了就是 ``PROCESSING`` 卡住 —— 下次能发现、能重做。

    **但 ``PROCESSING`` 必须有超时机制。** 否则进程崩了状态永远卡住，
    「不重复处理」就变成了「永远不处理」。见 ``plan_import`` 的
    ``processing_timeout_seconds`` 参数。
    """

    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ImportAction(str, Enum):
    """一次比对得出的结论：这个文档该做什么。

    取值用字符串枚举而不是裸字符串，是为了让日志和报告里打出来的
    是 ``added`` 这种可读形式，同时代码里能用 ``ImportAction.ADDED`` 引用，
    避免拼错（拼错字符串是运行时才发现的错误，枚举是静态的）。
    """

    ADDED = "added"
    """内容没见过、路径也没见过 —— 全新文档。要重新做 embedding。"""

    UPDATED = "updated"
    """内容没见过、但路径见过 —— 这个文件的内容变了。
    旧 doc_id 的块要删掉，新 doc_id 的块要插进去。要重新做 embedding。"""

    RENAMED = "renamed"
    """内容见过、但路径变了 —— 只是改了文件名或挪了目录，内容一个字没改。
    只更新账本里的路径和块里的路径，**不用重新做 embedding**。
    这是用内容 hash 当 doc_id 的最大回报。"""

    UNCHANGED = "unchanged"
    """内容和路径都见过，状态是 READY —— 完全没变。什么都不做，不花钱。
    这是重复导入时最常见的路径，也是幂等带来的最大收益。"""

    REMOVED = "removed"
    """账本里有、这次没扫到 —— 文档消失了。
    库里的块也要删掉，否则用户还能搜到已经不存在的文档的内容。"""

    LOCKED = "locked"
    """别的进程正在处理它（状态是 ``PROCESSING`` 且没超时）。
    **本次不动它** —— 重复处理会白花一倍 embedding 的钱。"""

    RESUMED = "resumed"
    """接管一个没做完的任务。两种来源：

    1. 状态是 ``PROCESSING`` 但**已经超时** —— 说明那个进程崩了，
       状态卡住了。不接管的话这份文档永远处理不完。
    2. 状态是 ``FAILED`` —— 上次处理失败了，重试一次。
    """

    @property
    def needs_embedding(self) -> bool:
        """这个动作要不要重新算向量（也就是要不要花钱）。"""
        return self in (
            ImportAction.ADDED,
            ImportAction.UPDATED,
            ImportAction.RESUMED,
        )

    @property
    def needs_processing(self) -> bool:
        """这个动作要不要真的走一遍「切块 -> 向量化 -> 写库」。"""
        return self.needs_embedding

    @property
    def blocks_progress(self) -> bool:
        """这个动作会不会挡住其他进程（占着锁不放）。"""
        return self is ImportAction.LOCKED


@dataclass(frozen=True, slots=True)
class ImportedDoc:
    """账本里的一条记录：这个文档现在处于什么状态。

    只记「元信息」，不记块的内容 —— 块的内容存在块存储里。
    账本是**索引**，不是数据本身。

    三个时间戳/字段的分工
    ---------------------
    - ``status``：现在处于哪个阶段（见 ``DocStatus``）
    - ``started_at``：这一轮处理是**什么时候开始的**。
      **僵尸检测靠它** —— 状态是 ``PROCESSING`` 且 ``started_at`` 已经很久，
      说明那个进程崩了，可以接管。
    - ``ready_at``：**内容最后一次入库的时间**。
      改名不刷新它（改名没有重新入库）。
    """

    doc_id: str
    path: str
    status: DocStatus = DocStatus.READY
    chunk_count: int = 0
    started_at: str = ""
    ready_at: str = ""

    def __post_init__(self) -> None:
        if not self.doc_id:
            raise ValueError("doc_id must not be empty")
        if not self.path:
            raise ValueError("path must not be empty")
        if self.chunk_count < 0:
            raise ValueError("chunk_count must not be negative")
        if self.status is DocStatus.PROCESSING and not self.started_at:
            raise ValueError("PROCESSING 状态的记录必须有 started_at，否则无法做僵尸检测")

    def to_json(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "path": self.path,
            "status": self.status.value,
            "chunk_count": self.chunk_count,
            "started_at": self.started_at,
            "ready_at": self.ready_at,
        }

    @classmethod
    def from_json(cls, data: Mapping) -> "ImportedDoc":
        # 兼容旧格式：早期版本没有 status / started_at / ready_at，
        # 只有 imported_at。旧数据都是「处理完成」的，所以默认 READY。
        raw_status = str(data.get("status", DocStatus.READY.value))
        try:
            status = DocStatus(raw_status)
        except ValueError:
            status = DocStatus.READY

        ready_at = str(data.get("ready_at") or data.get("imported_at") or "")

        return cls(
            doc_id=str(data["doc_id"]),
            path=str(data["path"]),
            status=status,
            chunk_count=int(data.get("chunk_count", 0)),
            started_at=str(data.get("started_at", "")),
            ready_at=ready_at,
        )

    @property
    def is_ready(self) -> bool:
        return self.status is DocStatus.READY

    @property
    def is_processing(self) -> bool:
        return self.status is DocStatus.PROCESSING

    @property
    def is_failed(self) -> bool:
        return self.status is DocStatus.FAILED


@dataclass(frozen=True, slots=True)
class Manifest:
    """导入账本 —— 记住上次导入了哪些文档。

    用 ``doc_id`` 做主键（因为内容才是身份），另外提供 ``by_path()``
    按路径查，因为比对的时候两个键都要用。

    空账本（``docs={}``）是合法的初始状态：第一次导入时就是空账本，
    所有文档都会判成 ADDED。

    ``store_id``：账本属于哪个块存储
    ---------------------------------
    这是**必须的**，不是可选的元数据。

    账本描述的是「**某个块存储里现在有什么**」。如果块存储换了一个
    （新进程的内存实例、被重建的向量库、连到了另一个数据库），
    那这份账本就成了**过期地图** —— 它说的东西在那个库里根本不存在。

    后果（真实复现过）::

        账本（落盘）说：有 1 个文档
        块存储（内存）里：0 个块
        下次导入：doc_id 在账本里、路径也一样 -> 判「跳过」
        -> 这份文档永远不会被重新导入，而且不报错

    所以账本记下 ``store_id``，加载时对不上就**作废**（触发全量重建）。
    宁可贵一次（重建），也不要静默少一份文档。
    """

    docs: Mapping[str, ImportedDoc] = field(default_factory=dict)
    store_id: str = ""

    def by_path(self) -> dict[str, ImportedDoc]:
        """按路径建索引：路径 -> 记录。

        注意理论上「一个路径对应多个 doc_id」是可能出现的
        （历史遗留数据不一致）。这里取**最后一条**，并在
        ``planner`` 里通过「路径唯一性」的断言把它挡住。
        """
        return {record.path: record for record in self.docs.values()}

    def __len__(self) -> int:
        return len(self.docs)

    def summary(self) -> str:
        return f"账本：{len(self.docs)} 个文档"


@dataclass(frozen=True, slots=True)
class ImportDecision:
    """针对一个文档的比对结论。

    ``previous_*`` 字段记录「上一次是什么样」，用来在报告里说清
    「从什么变成了什么」——只报「更新了」是看不出问题的。
    """

    action: ImportAction
    path: str
    doc_id: str
    previous_path: str = ""
    previous_doc_id: str = ""
    chunk_count: int = 0
    reason: str = ""
    """为什么是这个动作。用在需要解释的场景（接管僵尸任务、被锁住等）。"""

    def describe(self) -> str:
        """一句人能读懂的话。"""
        if self.action is ImportAction.RENAMED:
            return f"{self.previous_path} -> {self.path}（内容未变）"
        if self.action is ImportAction.UPDATED:
            return f"{self.path}（内容已变，旧 doc_id {self.previous_doc_id}）"
        if self.action is ImportAction.REMOVED:
            return f"{self.path}（文档已消失）"
        if self.action is ImportAction.LOCKED:
            return f"{self.path}（被占用，本次不动）"
        if self.action is ImportAction.RESUMED:
            return f"{self.path}（{self.reason or '接管重做'}）"
        return self.path


@dataclass(frozen=True, slots=True)
class ImportPlan:
    """一次导入的完整计划：每个文档该做什么。

    分成「计划」和「执行」两步是刻意的：
    计划是**纯函数**（输入文档列表 + 账本，输出决策），不碰存储、不碰磁盘，
    所以能单独测。执行才有副作用。
    """

    decisions: tuple[ImportDecision, ...]

    def of(self, action: ImportAction) -> tuple[ImportDecision, ...]:
        return tuple(d for d in self.decisions if d.action is action)

    def count(self, action: ImportAction) -> int:
        return len(self.of(action))

    @property
    def needs_embedding(self) -> tuple[ImportDecision, ...]:
        """要重新算向量的决策（ADDED + UPDATED）——也就是要花钱的那些。"""
        return tuple(d for d in self.decisions if d.action.needs_embedding)

    @property
    def total(self) -> int:
        return len(self.decisions)

    def summary(self) -> str:
        parts = []
        for action, label in (
            (ImportAction.ADDED, "新增"),
            (ImportAction.UPDATED, "更新"),
            (ImportAction.RESUMED, "接管重做"),
            (ImportAction.RENAMED, "改名"),
            (ImportAction.UNCHANGED, "跳过"),
            (ImportAction.LOCKED, "被别的进程占着"),
            (ImportAction.REMOVED, "删除"),
        ):
            count = self.count(action)
            if count:
                parts.append(f"{label} {count}")
        if not parts:
            return "本次没有需要处理的文档"
        return "；".join(parts)


class MassRemovalRefusedError(RuntimeError):
    """本次要删的文档比例过高，拒绝执行。

    这不是「出错了」，而是**安全阀主动拦下**。

    为什么需要它：``REMOVED`` 的判断依据是「账本里有、这次没扫到」，
    但「没扫到」有三种原因：

    1. 文档真的被删了 —— 该删
    2. 扫描目录配错了 —— **不能删**
    3. 磁盘没挂载 / 权限变了 —— **不能删**

    最坏的情况：``docs/`` 路径打错一个字 → 扫到 0 个文件 →
    系统认为「所有文档都被删了」→ **清空整个知识库**，
    而且恢复要重新花钱做 embedding。

    所以加一道比例阈值：超过就拒绝，要求人工确认。
    真实系统里基本都有这一道。
    """

    def __init__(self, *, to_remove: int, total_known: int, threshold: float) -> None:
        self.to_remove = to_remove
        self.total_known = total_known
        self.threshold = threshold
        ratio = to_remove / total_known if total_known else 0.0
        super().__init__(
            f"本次检测到 {to_remove}/{total_known} 个文档消失（{ratio:.0%}），"
            f"超过阈值 {threshold:.0%}，已拒绝执行删除。"
            "请确认扫描目录是否正确、磁盘是否挂载；确认无误后调高阈值或显式允许。"
        )


@dataclass(frozen=True, slots=True)
class ImportReport:
    """一次导入的结果：计划 + 执行后的库状态。

    带上库状态是为了让「重复导入」这件事可验证：
    第二次导入之后 ``document_count`` 和 ``chunk_count`` 必须和第一次一样。

    ``manifest_invalidated``
        账本因为「不属于当前块存储」被作废了（防线 1）。
        这时本次导入会把所有文档当新增处理（全量重建）。
        **必须报出来**——它意味着一次意外的全量 embedding 开销，
        静默发生的话用户只会看到账单变高，不知道原因。

    ``repaired_doc_ids``
        账本里有、但库里实际不存在的文档（防线 2 抓到的）。
        它们被剔出账本、重新导入。
        这抓的是防线 1 抓不到的情况：**还是同一个库，但内容被改动过**
        （有人手工删了文档、上次写块时崩了）。
        不修的话：账本说有、下次判「跳过」、**永远补不回来**。

    ``orphans_removed``
        库里有、但账本不认的文档，被清掉了。
        这些是「孤儿块」——没人认领，会污染检索结果
        （用户搜到一份已经不存在的文档的内容）。
    """

    plan: ImportPlan
    store_document_count: int
    store_chunk_count: int
    root: str = "docs"
    manifest_invalidated: bool = False
    invalidation_reason: str = ""
    repaired_doc_ids: tuple[str, ...] = ()
    orphans_removed: int = 0
    failed_doc_ids: tuple[str, ...] = ()
    """本次处理失败的文档。它们的状态被置成 FAILED，下次导入会重试。
    **必须报出来** —— 不然失败就静默了。"""

    @property
    def embedded_document_count(self) -> int:
        """本次真正重新算了向量的文档数。"""
        return len(self.plan.needs_embedding)

    def summary(self) -> str:
        parts: list[str] = []
        if self.manifest_invalidated:
            parts.append(f"账本已作废：{self.invalidation_reason}")
        if self.repaired_doc_ids:
            parts.append(f"账本修复 {len(self.repaired_doc_ids)} 条（库里已不存在）")
        if self.orphans_removed:
            parts.append(f"清理孤儿文档 {self.orphans_removed} 个")
        parts.append(self.plan.summary())
        parts.append(
            f"库中现有 {self.store_document_count} 个文档 / {self.store_chunk_count} 个块"
        )
        parts.append(f"本次需重新向量化 {self.embedded_document_count} 个文档")
        if self.failed_doc_ids:
            parts.append(f"处理失败 {len(self.failed_doc_ids)} 个（下次会重试）")
        return "；".join(parts)
