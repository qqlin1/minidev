"""存储层 —— 存块、存账本。

两个存储，职责完全不同
----------------------
+------------------+------------------------+--------------------------+
|                  | ChunkStore             | ManifestStore            |
+==================+========================+==========================+
| 存什么           | 块的内容（文本）        | 元信息（doc_id、路径、   |
|                  |                        | 块数、导入时间）         |
| 回答的问题       | 「这一块讲的是什么」    | 「我上次导过哪些文档」   |
| 谁在用           | 检索时用               | 导入比对时用             |
| 大小             | 大（每块几百字）        | 小（每文档一行）         |
+------------------+------------------------+--------------------------+

**为什么接口里一个业务词都没有**
--------------------------------
存储层不认识「改名」「更新」这些词。那些是**决策层**的词汇
（见 ``planner.py``），是比对之后得出的结论。

比如「改名」这个动作，在存储层是**什么都不做** ——
只改账本里的路径，块完全不动。如果给存储层加一个 ``rename()`` 方法，
存储层就得知道「什么是改名」「改名时块要不要动」，
**业务逻辑就漏进存储层了**。

所以存储层只有三种操作：**存、删、查**。

``put_document`` 必须是「覆盖」语义，不能是「追加」
---------------------------------------------------
这不是风格问题，是**正确性**问题。

它决定了「先写块、后写账本」这个写入顺序安不安全：

::

    先写块成功、写账本时崩溃
      -> 库里有块，账本说没有
      -> 下次导入判成「新增」
      -> put 覆盖 -> 一致了，自动修复

    如果 put 是追加语义：
      -> 下次导入判成「新增」
      -> 追加 -> 库里两份块 -> 重复，而且越跑越多

「覆盖」让整个流程变成**可重跑**的。没有事务的时候，
「可重跑」就是「原子性」的替代品。
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from ..chunking.models import Chunk
from .models import ImportedDoc, Manifest


class ChunkStore(Protocol):
    """块存储的契约。

    v1 用内存实现（``InMemoryChunkStore``），
    将来换成向量库时只要满足这个契约，导入逻辑一行都不用改。

    ``store_id``：这个存储实例的身份
    --------------------------------
    它回答一个问题：「**你和你上次那个是同一个库吗？**」

    为什么必须有它：账本（``Manifest``）描述的是「某个块存储里现在有什么」。
    如果块存储换了一个，账本就成了过期地图 —— 它说的东西在新库里不存在。

    具体到这个项目：``InMemoryChunkStore`` 的内容**随进程消失**，
    而 ``JsonManifestStore`` 的账本**留在磁盘上**。两者持久性不一致，
    于是「账本说有、库里没有」这个状态必然出现 ——
    下次导入判「跳过」，文档**永远不会被重新导入，而且不报错**。

    修法就是让账本记下 ``store_id``，加载时对不上就作废。

    实现要求：

    - **易失的存储**（内存版）：每次创建实例给一个新 ID，
      这样新进程的账本自动失效，触发全量重建。
    - **持久的存储**（向量库/数据库）：ID 必须**跨重启稳定**
      （比如用集合名、或者把 ID 存在库里），否则每次重启都会全量重建，
      白花 embedding 的钱。
    """

    store_id: str

    def put_document(self, doc_id: str, chunks: Sequence[Chunk]) -> None:
        """把一个文档的所有块存进去（**覆盖**同一个 doc_id 的旧块）。"""
        ...

    def delete_document(self, doc_id: str) -> int:
        """删掉一个文档的所有块，返回删掉几块。文档不存在返回 0。"""
        ...

    def get_document(self, doc_id: str) -> tuple[Chunk, ...]:
        """取出一个文档的所有块。不存在返回空元组。"""
        ...

    def all_chunks(self) -> tuple[Chunk, ...]:
        """取出全部块（检索时用）。"""
        ...

    def doc_ids(self) -> tuple[str, ...]:
        """列出库里现存的所有 doc_id。

        用途是**和账本对账**：账本说有 A、B、C，库里只有 A、B，
        说明 C 丢了（有人手工删了、或者上次写块时崩了），
        必须把它从账本里剔出去，让它重新导入。

        没有这个方法，就只能看总量（``document_count()``）——
        而总量对不上时你不知道**是哪一个**丢了，没法修。
        """
        ...

    def document_count(self) -> int:
        ...

    def chunk_count(self) -> int:
        ...


class InMemoryChunkStore:
    """内存版块存储。

    为什么 v1 先用内存版：因为还没有向量库。
    但**接口先定下来**，将来换实现时导入逻辑不用改。

    内部结构是 ``{doc_id: [Chunk, ...]}`` —— 按文档分组，
    这样「删掉一个文档的所有块」是一次字典删除，
    而不是遍历所有块找哪些属于它。

    ``store_id`` 默认每次创建实例都生成一个新的随机值 ——
    因为内存存储的内容确实是全新的。这样「新进程 + 旧账本」
    会自动触发账本作废，不会静默丢文档。

    测试里需要可复现时，可以显式传 ``store_id="fixed"``。
    """

    def __init__(self, store_id: str | None = None) -> None:
        self.store_id = store_id or uuid.uuid4().hex[:12]
        self._by_doc: dict[str, tuple[Chunk, ...]] = {}

    def put_document(self, doc_id: str, chunks: Sequence[Chunk]) -> None:
        if not doc_id:
            raise ValueError("doc_id must not be empty")
        # 直接赋值 = 覆盖语义。同一个 doc_id 再存一次，旧的被替换掉。
        self._by_doc[doc_id] = tuple(chunks)

    def delete_document(self, doc_id: str) -> int:
        removed = self._by_doc.pop(doc_id, ())
        return len(removed)

    def get_document(self, doc_id: str) -> tuple[Chunk, ...]:
        return self._by_doc.get(doc_id, ())

    def all_chunks(self) -> tuple[Chunk, ...]:
        return tuple(chunk for chunks in self._by_doc.values() for chunk in chunks)

    def document_count(self) -> int:
        return len(self._by_doc)

    def chunk_count(self) -> int:
        return sum(len(chunks) for chunks in self._by_doc.values())

    def doc_ids(self) -> tuple[str, ...]:
        """列出所有 doc_id（调试和测试用，不属于契约的必需部分）。"""
        return tuple(sorted(self._by_doc))


class ManifestStore(Protocol):
    """账本存储的契约。

    v1 用 JSON 文件实现，生产环境换成数据库实现 —— 导入逻辑不用改。
    这就是「专业版存数据库」的正确落地方式：
    **不是现在就上数据库，而是现在就把接口留出来。**
    """

    def load(self) -> Manifest:
        """读账本。文件不存在时返回空账本（不是错误——第一次导入就是这情况）。"""
        ...

    def save(self, manifest: Manifest) -> None:
        """写账本。"""
        ...


class InMemoryManifestStore:
    """内存版账本存储。测试用——不需要碰磁盘，也不会有残留文件。"""

    def __init__(self, manifest: Manifest | None = None) -> None:
        self._manifest = manifest or Manifest()

    def load(self) -> Manifest:
        return self._manifest

    def save(self, manifest: Manifest) -> None:
        self._manifest = manifest


class JsonManifestStore:
    """把账本存成 JSON 文件。

    文件格式::

        {
          "version": 1,
          "store_id": "a3f9c2e1b7d4",
          "docs": {
            "a3f9c2e1b7d40856": {
              "doc_id": "a3f9c2e1b7d40856",
              "path": "docs/员工手册.md",
              "chunk_count": 9,
              "imported_at": "2026-09-18T04:37:29"
            }
          }
        }

    ``store_id`` 是账本属于哪个块存储的标记（见 ``ChunkStore`` 的注释）。
    **没有它，跨进程重启会静默丢文档**：账本说「有」，但新的内存存储是空的，
    下次导入判「跳过」，那份文档永远进不了库。

    为什么用「写临时文件 + 原子重命名」而不是直接覆盖写
    ---------------------------------------------------
    直接 ``write_text()`` 有个隐患：写到一半崩溃（磁盘满、进程被杀），
    文件就是**半截的**——JSON 解析不了，账本全丢。

    账本全丢的后果不是「从头再来」，而是「**下次导入判成全部新增**」——
    所有文档重新做一遍 embedding，白花一大笔钱。

    原子重命名（``os.replace``）保证：要么是完整的旧版本，
    要么是完整的新版本，**不存在半截状态**。
    ``os.replace`` 在 Windows 和 Linux 上都是原子的。
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> Manifest:
        if not self.path.exists():
            # 第一次导入：没有账本是正常的，不是错误。
            return Manifest()

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        docs = {
            str(doc_id): ImportedDoc.from_json(record)
            for doc_id, record in raw.get("docs", {}).items()
        }
        return Manifest(docs=docs, store_id=str(raw.get("store_id", "")))

    def save(self, manifest: Manifest) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": 1,
            "store_id": manifest.store_id,
            "docs": {
                doc_id: record.to_json()
                for doc_id, record in sorted(manifest.docs.items())
            },
        }

        # 先写临时文件，再原子替换。
        # delete=False 是因为 Windows 上不允许「已打开的文件被重命名」——
        # 必须先关掉句柄，才能 replace。
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self.path.parent),
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        )
        try:
            with handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())  # 逼操作系统真的写进磁盘
            os.replace(handle.name, self.path)
        except BaseException:
            # 出任何事都把临时文件清掉，不留垃圾
            Path(handle.name).unlink(missing_ok=True)
            raise


def manifest_from_records(records: Mapping[str, ImportedDoc]) -> Manifest:
    """从 ``{doc_id: ImportedDoc}`` 构造账本的小助手（测试常用）。"""
    return Manifest(docs=dict(records))
