"""比对逻辑 —— 决定每个文档该做什么。

这是整个幂等导入的核心，也是**唯一需要动脑的地方**。
执行部分（切块、写库、改状态）是机械的。

输入输出
--------
::

    输入：本次扫描到的文档列表 + 上次的账本（带状态）+ 当前时间
    输出：每个文档该做什么（ImportPlan）

**纯函数**：不碰存储、不碰磁盘。时间通过参数传进来（不自己读时钟），
所以能单独测 —— 不用造假的存储、不用等真实时间流逝。

状态机
------
账本里每条记录有一个 ``status``（见 ``models.DocStatus``）::

    PROCESSING   某个进程正在处理（这个状态本身就是一把锁）
    READY        处理完成，块已入库
    FAILED       处理失败，可以重试

比对时**先看状态，再看两个键**：

::

    第 1 问：这个文档被别的进程锁着吗？
      （同一个 doc_id 或同一个路径上，有一个「未超时」的 PROCESSING）
      是 -> LOCKED，本次不动它

    第 2 问：按内容查，doc_id 在账本里吗？
      在 -> 看状态：
             READY                -> 再看路径变没变（UNCHANGED / RENAMED）
             PROCESSING（超时了）  -> RESUMED，接管重做
             FAILED               -> RESUMED，重试
      不在 -> 按路径查，看这个路径被别的 doc_id 占着吗？
                占着 -> UPDATED
                没占 -> ADDED

第五种情况「删除」不在表里
--------------------------
因为它看的是「**上次有什么**」，不是「这次有什么」：

    账本里有、这次没扫到  ->  REMOVED

**但正在处理中（PROCESSING 且未超时）的文档不删** —— 它可能马上就处理完了。
删了的话，那个进程还在写块，结果就是「库里有块、账本没记录」的孤儿。

为什么必须有超时机制
--------------------
``PROCESSING`` 是锁，但**锁必须有超时**。

场景：进程 A 开始处理文档 X，把状态置成 PROCESSING，然后机器断电了。
下次启动，状态还是 PROCESSING，但没有任何进程在做它 —— **僵尸锁**。

如果不对超时的 PROCESSING 做特殊处理，这份文档**永远处理不完**，
而且不报错。这就是「不重复处理」变成「永远不处理」的原因。

所以：``started_at`` 距今超过 ``processing_timeout_seconds`` 的，
视为僵尸，允许接管（``RESUMED``）。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from ..ingest.models import IngestedDoc
from .models import (
    DocStatus,
    ImportAction,
    ImportDecision,
    ImportedDoc,
    ImportPlan,
    Manifest,
    MassRemovalRefusedError,
)

# 默认的删除比例阈值。
# 超过这个比例的文档被判定为「消失」时，拒绝执行并要求人工确认。
# 取 0.5 的理由：正常情况下一次导入最多删掉一半文档已经很激进；
# 而「目录配错 / 磁盘没挂载」这类事故通常会让比例接近 100%。
DEFAULT_MAX_REMOVAL_RATIO = 0.5

# 默认的处理超时时间：30 分钟。
#
# 为什么是 30 分钟：一次导入里单个文档的处理（切块 + 向量化 + 写库）
# 通常是秒级到分钟级。30 分钟远超正常耗时，所以：
#   - 真崩了 -> 30 分钟后能自动接管，不会永远卡住
#   - 还在跑 -> 30 分钟内不会被误抢
#
# 调这个值的判据：
#   调大 -> 僵尸恢复更慢，但误抢风险更低
#   调小 -> 恢复更快，但如果某个文档处理特别久，可能被误抢（白做一遍）
DEFAULT_PROCESSING_TIMEOUT_SECONDS = 30 * 60


def plan_import(
    docs: Iterable[IngestedDoc],
    manifest: Manifest,
    *,
    now: str | None = None,
    max_removal_ratio: float = DEFAULT_MAX_REMOVAL_RATIO,
    processing_timeout_seconds: int = DEFAULT_PROCESSING_TIMEOUT_SECONDS,
) -> ImportPlan:
    """比对本次扫描结果和上次账本，得出每个文档该做什么。

    参数
    ----
    docs
        本次扫描到的文档（``ingest`` 的输出）。
    manifest
        上次的账本。第一次导入时传 ``Manifest()``（空账本）。
    now
        当前时间（ISO 格式字符串）。**测试必须显式传**，
        否则依赖真实时钟，结果不可复现。
        传 ``None`` 时用当前时间。
    max_removal_ratio
        删除比例阈值。要删除的文档占账本总数的比例超过它，
        就抛 ``MassRemovalRefusedError``。设成 1.0 等于关掉这道保护。
    processing_timeout_seconds
        处理超时时间。状态是 PROCESSING 且 ``started_at`` 距今超过它，
        就视为僵尸任务，允许接管。

    抛出
    ----
    MassRemovalRefusedError
        检测到大规模删除，拒绝出计划。
    ValueError
        账本里有两条记录的路径相同（不该出现的状态）。
    """
    if not 0.0 <= max_removal_ratio <= 1.0:
        raise ValueError("max_removal_ratio must be between 0 and 1")
    if processing_timeout_seconds < 0:
        raise ValueError("processing_timeout_seconds must not be negative")

    current_time = now or datetime.now().isoformat(timespec="seconds")
    doc_list = list(docs)

    # 账本必须满足「一个路径只属于一个 doc_id」，否则下面的按路径查会歧义。
    by_path = manifest.by_path()
    if len(by_path) != len(manifest.docs):
        duplicates = _duplicate_paths(manifest)
        raise ValueError(
            f"账本里有多个 doc_id 指向同一个路径：{duplicates}。"
            "账本已损坏，需要先修复。"
        )

    decisions: list[ImportDecision] = []
    consumed_old_ids: set[str] = set()

    # ---- 遍历本次扫描到的文档 ----
    for doc in doc_list:
        # 第 1 问：被锁着吗？
        holder = _active_lock(
            doc, manifest, by_path, current_time, processing_timeout_seconds
        )
        if holder is not None:
            decisions.append(
                ImportDecision(
                    action=ImportAction.LOCKED,
                    path=doc.path,
                    doc_id=doc.doc_id,
                    previous_path=holder.path,
                    previous_doc_id=holder.doc_id,
                    chunk_count=holder.chunk_count,
                    reason=f"已被 {holder.started_at} 开始的处理任务占用，未超时",
                )
            )
            continue

        # 第 2 问：按内容查
        previous = manifest.docs.get(doc.doc_id)

        if previous is not None:
            if previous.is_ready:
                # 处理完成过 —— 再看路径变没变
                if previous.path == doc.path:
                    decisions.append(
                        ImportDecision(
                            action=ImportAction.UNCHANGED,
                            path=doc.path,
                            doc_id=doc.doc_id,
                            previous_path=previous.path,
                            previous_doc_id=previous.doc_id,
                            chunk_count=previous.chunk_count,
                        )
                    )
                else:
                    decisions.append(
                        ImportDecision(
                            action=ImportAction.RENAMED,
                            path=doc.path,
                            doc_id=doc.doc_id,
                            previous_path=previous.path,
                            previous_doc_id=previous.doc_id,
                            chunk_count=previous.chunk_count,
                        )
                    )
            else:
                # PROCESSING（已超时，未超时的在上面被 LOCKED 拦掉了）或 FAILED
                if previous.is_failed:
                    reason = "上次处理失败，重试"
                else:
                    reason = f"上次处理未完成（{previous.started_at} 开始，已超时），接管重做"
                decisions.append(
                    ImportDecision(
                        action=ImportAction.RESUMED,
                        path=doc.path,
                        doc_id=doc.doc_id,
                        previous_path=previous.path,
                        previous_doc_id=previous.doc_id,
                        chunk_count=previous.chunk_count,
                        reason=reason,
                    )
                )
            continue

        # 第 3 问：这个路径被别的 doc_id 占着吗？
        occupant = by_path.get(doc.path)
        if occupant is not None:
            consumed_old_ids.add(occupant.doc_id)
            decisions.append(
                ImportDecision(
                    action=ImportAction.UPDATED,
                    path=doc.path,
                    doc_id=doc.doc_id,
                    previous_path=occupant.path,
                    previous_doc_id=occupant.doc_id,
                    chunk_count=occupant.chunk_count,
                )
            )
        else:
            decisions.append(
                ImportDecision(
                    action=ImportAction.ADDED,
                    path=doc.path,
                    doc_id=doc.doc_id,
                )
            )

    # ---- 遍历账本：删除检测 ----
    new_doc_ids = {doc.doc_id for doc in doc_list}
    removals: list[ImportDecision] = []

    for doc_id, record in manifest.docs.items():
        if doc_id in new_doc_ids:
            continue
        if doc_id in consumed_old_ids:
            continue
        # 正在处理中、且没超时的，不删 —— 它可能马上就处理完了。
        # 删了的话那个进程还在写块，会产生「库里有块、账本没记录」的孤儿。
        if record.is_processing and not _is_expired(
            record, current_time, processing_timeout_seconds
        ):
            continue
        removals.append(
            ImportDecision(
                action=ImportAction.REMOVED,
                path=record.path,
                doc_id=record.doc_id,
                previous_path=record.path,
                previous_doc_id=record.doc_id,
                chunk_count=record.chunk_count,
            )
        )

    # ---- 安全阀：拒绝大规模删除 ----
    total_known = len(manifest.docs)
    if removals and total_known:
        ratio = len(removals) / total_known
        if ratio > max_removal_ratio:
            raise MassRemovalRefusedError(
                to_remove=len(removals),
                total_known=total_known,
                threshold=max_removal_ratio,
            )

    decisions.extend(removals)
    decisions.sort(key=lambda d: (d.path, d.action.value))

    return ImportPlan(decisions=tuple(decisions))


def _active_lock(
    doc: IngestedDoc,
    manifest: Manifest,
    by_path: dict[str, ImportedDoc],
    now: str,
    timeout_seconds: int,
) -> ImportedDoc | None:
    """这个文档被别的进程锁着吗？被锁就返回那个占用者的记录。

    两个方向都查，因为「同一个文档」有两种识别方式：

    - 按 ``doc_id``（内容）：另一个进程正在处理**同一份内容**
    - 按 ``path``（路径）：另一个进程正在处理**同一个文件**

    两个都要查。只查一个的话，可能出现「两个进程同时在处理同一个文件」
    （一个用旧 doc_id、一个用新 doc_id），白花一倍的钱。
    """
    candidates = (manifest.docs.get(doc.doc_id), by_path.get(doc.path))
    for candidate in candidates:
        if candidate is None or not candidate.is_processing:
            continue
        if not _is_expired(candidate, now, timeout_seconds):
            return candidate
    return None


def _is_expired(record: ImportedDoc, now: str, timeout_seconds: int) -> bool:
    """这个处理任务是不是已经超时（僵尸）了。

    判定不出时间的一律视为**已超时** —— 宁可重做一遍，
    也不要因为时间戳坏掉而永远卡住。重做只是花一次钱，卡住是文档永远进不了库。
    """
    if not record.started_at:
        return True
    try:
        started = datetime.fromisoformat(record.started_at)
        current = datetime.fromisoformat(now)
    except ValueError:
        return True
    return (current - started).total_seconds() > timeout_seconds


def _duplicate_paths(manifest: Manifest) -> list[str]:
    """找出账本里被多个 doc_id 占用的路径（用于报错信息）。"""
    seen: dict[str, int] = {}
    for record in manifest.docs.values():
        seen[record.path] = seen.get(record.path, 0) + 1
    return sorted(path for path, count in seen.items() if count > 1)
