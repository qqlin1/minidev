"""导入编排 —— 把「摄取、比对、切块、存块、改状态」串成一次操作。

按状态机走，一共七步
--------------------
::

    docs/ 目录
      │
      ├─ 1. 摄取        ingest()              扫文件、过准入、读文本、算 doc_id
      │
      ├─ 2. 读账本      manifest_store.load()
      │     防线 1      store_id 校验（换库检测）
      │     防线 2      和库对账（账本说有、库里没有的剔掉）
      │
      ├─ 3. 比对        plan_import()         每个文档该做什么
      │
      ├─ 4. 抢占        <<< 先把要处理的标成 PROCESSING，写一次账本 >>>
      │
      ├─ 5. 干活        切块 -> 写块（覆盖）-> 成功记 READY / 失败记 FAILED
      │
      ├─ 6. 清孤儿      库里不在新账本里的，删掉
      │
      └─ 7. 收尾        <<< 写最终账本 >>>

**第 4 步和第 7 步是关键：账本会被写两次。**

为什么写两次
------------
第一次写的是「**我要开始做 X 了**」，第二次写的是「**X 做完了**」。

中间隔着的第 5 步（真正干活）是可能崩溃的地方。有了这个中间状态，
崩溃后的表现是「状态卡在 PROCESSING」，而不是「记录说做完了、实际没做」。

::

    只有一次写（做完才写）：
      崩 -> 账本没记录 -> 下次判「新增」-> 重做
      问题：重做时不知道「是不是有别的进程正在做同一件事」

    两次写（先声明、后确认）：
      崩 -> 状态卡在 PROCESSING
        -> 未超时：别的进程看到会跳过（不重复花钱）
        -> 已超时：视为僵尸，接管重做（不会永远卡住）

第二个能力（并发安全）是单次写给不了的 —— 这也是这个设计比我原来的
「先写块后写账本」更好的地方。

三种状态各自的含义
------------------
::

    PROCESSING  正在处理。**这个状态本身就是一把锁**，挡住其他进程。
    READY       处理完成，块已入库。下次看到就跳过。
    FAILED      处理失败。保留它让失败可见，下次会重试。

``PROCESSING`` 必须有超时
-------------------------
否则进程崩了状态永远卡住，「不重复处理」就变成「永远不处理」。
超时时间见 ``ImportConfig.processing_timeout_seconds``。

那为什么不干脆用数据库事务
--------------------------
因为 v1 还没有数据库 —— 账本在文件里、块在内存里，不在同一个事务边界内。
**生产环境的标准答案是用事务**（或者用数据库的行锁 + 状态字段，
那正是这套状态机在真实系统里的落地形态）。
v1 的做法是「退而求其次」：用「可重跑」+「状态机」替代「原子性」。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from ..chunking import ChunkConfig, chunk_text
from ..ingest import ingest
from .models import (
    DocStatus,
    ImportAction,
    ImportReport,
    ImportedDoc,
    Manifest,
)
from .planner import (
    DEFAULT_MAX_REMOVAL_RATIO,
    DEFAULT_PROCESSING_TIMEOUT_SECONDS,
    plan_import,
)
from .store import ChunkStore, ManifestStore


@dataclass(frozen=True, slots=True)
class ImportConfig:
    """导入配置。

    ``chunk``
        切块配置。默认用 ``markdown_heading`` —— 因为 v1 的语料以文档为主。
        它在非 Markdown 文件上会自动退回 ``fixed_lines``，所以这个默认值是安全的。

    ``max_removal_ratio``
        删除比例阈值，见 ``models.MassRemovalRefusedError``。

    ``processing_timeout_seconds``
        处理超时时间（秒）。状态是 PROCESSING 且超过它，视为僵尸任务、允许接管。
        默认 30 分钟 —— 见 ``planner.DEFAULT_PROCESSING_TIMEOUT_SECONDS`` 的说明。
    """

    chunk: ChunkConfig = ChunkConfig(strategy="markdown_heading", max_lines=50)
    max_removal_ratio: float = DEFAULT_MAX_REMOVAL_RATIO
    processing_timeout_seconds: int = DEFAULT_PROCESSING_TIMEOUT_SECONDS


def import_documents(
    root: Path | str,
    *,
    chunk_store: ChunkStore,
    manifest_store: ManifestStore,
    config: ImportConfig | None = None,
    now: str | None = None,
    display_root: str = "docs",
) -> ImportReport:
    """把一个目录下的文档**幂等地**导入知识库。

    幂等的意思是：**跑一次和跑多次，库里的结果完全一样。**

    参数
    ----
    root
        要导入的目录（通常是项目根下的 ``docs/``）。
    chunk_store
        块存储。v1 用 ``InMemoryChunkStore``。
    manifest_store
        账本存储。v1 用 ``JsonManifestStore``（跨进程保留），
        测试用 ``InMemoryManifestStore``。
    config
        导入配置。不传用默认。
    now
        当前时间（ISO 格式字符串）。不传用当前时间。
        **为什么让调用方能传**：测试要可复现 —— 如果时间戳是「现在」，
        同一份输入两次跑出来的账本就不一样，而且僵尸检测没法测。
    display_root
        报告和路径里显示的目录名。

    抛出
    ----
    MassRemovalRefusedError
        检测到大规模删除，拒绝执行（安全阀）。
    """
    config = config or ImportConfig()
    timestamp = now or datetime.now().isoformat(timespec="seconds")

    # ---- 第 1 步：摄取 ----
    ingest_report = ingest(root, display_root=display_root)
    docs_by_path = {doc.path: doc for doc in ingest_report.docs}

    # ---- 第 2 步：读账本 ----
    manifest = manifest_store.load()

    # 防线 1：账本属于当前这个块存储吗？
    # 账本描述的是「某个块存储里现在有什么」。块存储换了实例，
    # 账本就成了过期地图 —— 它说的东西在那个库里不存在。
    invalidated = False
    invalidation_reason = ""
    if manifest.docs and manifest.store_id != chunk_store.store_id:
        invalidated = True
        invalidation_reason = (
            f"账本记录的块存储是 {manifest.store_id or '(未记录)'!r}，"
            f"当前块存储是 {chunk_store.store_id!r}，两者不是同一个库"
        )
        manifest = Manifest(store_id=chunk_store.store_id)

    # 防线 2：和库对账，剔掉「账本说有、库里没有」的条目。
    # 防线 1 抓不到这种情况：还是同一个库，但内容被改动过（有人手工删了）。
    manifest, repaired_doc_ids = reconcile_manifest(manifest, chunk_store)

    # ---- 第 3 步：比对 ----
    plan = plan_import(
        ingest_report.docs,
        manifest,
        now=timestamp,
        max_removal_ratio=config.max_removal_ratio,
        processing_timeout_seconds=config.processing_timeout_seconds,
    )

    # ---- 第 4 步：抢占 —— 把要处理的文档标成 PROCESSING，先写一次账本 ----
    #
    # 这一步是**先写记录**。在只有「一次写」的设计里，先写记录是危险的
    # （崩了会变成「记录说做完了、实际没做」-> 下次静默跳过）。
    #
    # 但这里写的是 **PROCESSING**，不是 READY —— 语义是「我要开始做了」。
    # 所以崩了之后状态卡在 PROCESSING，下次能发现、能重做。
    # **中间状态让「先写记录」变安全了。**
    pending = dict(manifest.docs)
    for decision in plan.decisions:
        if not decision.action.needs_processing:
            continue
        pending[decision.doc_id] = ImportedDoc(
            doc_id=decision.doc_id,
            path=decision.path,
            status=DocStatus.PROCESSING,
            chunk_count=0,
            started_at=timestamp,
        )
    manifest_store.save(Manifest(docs=pending, store_id=chunk_store.store_id))

    # ---- 第 5 步：干活 ----
    final = dict(manifest.docs)
    failed_doc_ids: list[str] = []

    for decision in plan.decisions:
        if decision.action.needs_processing:
            doc = docs_by_path.get(decision.path)
            if doc is None:
                raise AssertionError(
                    f"计划里要处理 {decision.path}，但扫描结果里没有这个路径"
                )

            # 更新时先把旧身份的记录和块清掉。
            # 不管后面成功还是失败都要清 —— 否则账本里会有两条记录指向同一个路径，
            # 按路径查就歧义了（planner 会因此报「账本已损坏」）。
            if decision.action is ImportAction.UPDATED:
                chunk_store.delete_document(decision.previous_doc_id)
                final.pop(decision.previous_doc_id, None)

            try:
                chunks = chunk_text(path=doc.path, text=doc.text, config=config.chunk)
                # put_document 是覆盖语义 —— 这是「重跑一次就修好」的前提
                chunk_store.put_document(doc.doc_id, chunks)
            except Exception as exc:  # noqa: BLE001 - 任何失败都要记下来，不能让整批挂掉
                # 失败不让整批挂掉：一份文档的 embedding 服务挂了，
                # 不该让另外几百份都白扫一遍。
                final[doc.doc_id] = ImportedDoc(
                    doc_id=doc.doc_id,
                    path=doc.path,
                    status=DocStatus.FAILED,
                    chunk_count=0,
                    started_at=timestamp,
                )
                failed_doc_ids.append(doc.doc_id)
                continue

            final[doc.doc_id] = ImportedDoc(
                doc_id=doc.doc_id,
                path=doc.path,
                status=DocStatus.READY,
                chunk_count=len(chunks),
                started_at=timestamp,
                ready_at=timestamp,
            )

        elif decision.action is ImportAction.RENAMED:
            # 块的内容不动，**但块里记的 path 必须跟着改** ——
            # Chunk.citation 是 f"{path}:{start}-{end}"，path 存在块自己身上。
            # 只改账本不改块，用户点击引用会跳到不存在的文件。
            old_chunks = chunk_store.get_document(decision.doc_id)
            if old_chunks:
                chunk_store.put_document(
                    decision.doc_id,
                    tuple(replace(chunk, path=decision.path) for chunk in old_chunks),
                )
            old_record = manifest.docs[decision.doc_id]
            # 状态和 ready_at 都不动 —— 改名没有重新入库。
            final[decision.doc_id] = replace(old_record, path=decision.path)

        elif decision.action in (ImportAction.UNCHANGED, ImportAction.LOCKED):
            # 原样保留。
            # LOCKED 也要保留 —— 那个文档正被别的进程处理，
            # 它的记录不能因为「本次没动它」就从账本里消失。
            continue

        elif decision.action is ImportAction.REMOVED:
            chunk_store.delete_document(decision.doc_id)
            final.pop(decision.doc_id, None)

    # ---- 第 6 步：清理孤儿块 ----
    # 库里存在、但新账本不认的 doc_id。留着会污染检索结果
    # （用户搜到一份已经不存在的文档的内容）。
    orphans_removed = _remove_orphans(chunk_store, valid_ids=set(final))

    # ---- 第 7 步：写最终账本 ----
    manifest_store.save(Manifest(docs=final, store_id=chunk_store.store_id))

    return ImportReport(
        plan=plan,
        store_document_count=chunk_store.document_count(),
        store_chunk_count=chunk_store.chunk_count(),
        root=display_root,
        manifest_invalidated=invalidated,
        invalidation_reason=invalidation_reason,
        repaired_doc_ids=repaired_doc_ids,
        orphans_removed=orphans_removed,
        failed_doc_ids=tuple(failed_doc_ids),
    )


def reconcile_manifest(
    manifest: Manifest,
    chunk_store: ChunkStore,
) -> tuple[Manifest, tuple[str, ...]]:
    """和块存储对账，剔掉「账本说有、库里没有」的条目。

    返回 ``(修复后的账本, 被剔掉的 doc_id 列表)``。

    这是**防线 2**。防线 1（``store_id`` 校验）只抓「换了一个库」，
    抓不到「还是同一个库，但库里的某个文档被删掉了」。

    不修的话后果很隐蔽：

    ::

        账本说：有 A、B、C
        库里实际：只有 A、B          <- C 被删了
        下次导入：A、B、C 都在账本里、路径也没变 -> 全判「跳过」
        -> C 永远补不回来，而且不报错

    被剔掉的条目会在本次比对里判成「新增」，自然重建。

    **只有 READY 的记录参与对账。**
    -----------------------------
    ``PROCESSING`` 和 ``FAILED`` 的记录**不参与**，因为它们的「库里没有块」
    是**预期之内**的，不是数据丢了：

    ::

        PROCESSING  正做到一半，块本来就还没写
        FAILED      上次失败了，块本来就没写成

    把它们也剔掉的话，会有一个很隐蔽的后果：
    ``FAILED`` 记录会被当成「意外丢失」剔出账本，
    于是下次判成「新增」而不是「重试」—— 状态机里的 ``FAILED`` 就白设了。

    **判据：对账只抓「意外」，不碰「已知状态」。**
    """
    present = set(chunk_store.doc_ids())
    missing = tuple(
        sorted(
            doc_id
            for doc_id, record in manifest.docs.items()
            # 只有「声称已经导完」的记录，库里没有才叫丢了
            if doc_id not in present and record.is_ready
        )
    )

    if not missing:
        return manifest, ()

    missing_set = set(missing)
    kept = {
        doc_id: record
        for doc_id, record in manifest.docs.items()
        if doc_id not in missing_set
    }
    return Manifest(docs=kept, store_id=manifest.store_id), missing


def _remove_orphans(chunk_store: ChunkStore, *, valid_ids: set[str]) -> int:
    """删掉库里那些「不在本次新账本里」的文档。返回删掉几个。"""
    removed = 0
    for doc_id in chunk_store.doc_ids():
        if doc_id not in valid_ids:
            chunk_store.delete_document(doc_id)
            removed += 1
    return removed
