"""Indexing 子包 —— Knowledge Base 的第二段：块 -> 幂等入库。

对外 API：

- `ImportAction` / `ImportedDoc` / `Manifest`：账本的三个数据结构
- `ImportDecision` / `ImportPlan` / `ImportReport`：比对结论与导入结果
- `MassRemovalRefusedError`：大规模删除的安全阀异常
- `plan_import`：比对（纯函数，不碰存储）
- `ChunkStore` / `InMemoryChunkStore`：块存储契约与内存实现
- `ManifestStore` / `JsonManifestStore` / `InMemoryManifestStore`：账本存储
- `ImportConfig` / `import_documents`：编排入口

能力边界：

- 只管「这个文档该不该重新入库、库里的块要不要动」
- **不做切块**（那是 `chunking/` 的事）
- **不做向量化**（v1 还没做）
- **不做检索**

依赖方向：本包 import `ingest` 和 `chunking`（因为要读文档、要切块），
但 `ingest` 和 `chunking` **都不 import 本包**。单向，不成环。

幂等一句话
----------
**导入两次 = 导入一次。**

实现方式是「导入前先问一句：这个东西我上次见过没有」——
靠 `doc_id`（内容指纹）和 `path`（文件路径）两个键一起判断，
得出「新增 / 更新 / 改名 / 跳过 / 删除」五种结论。
"""

from .models import (
    DocStatus,
    ImportAction,
    ImportDecision,
    ImportPlan,
    ImportReport,
    ImportedDoc,
    Manifest,
    MassRemovalRefusedError,
)
from .pipeline import ImportConfig, import_documents
from .planner import (
    DEFAULT_MAX_REMOVAL_RATIO,
    DEFAULT_PROCESSING_TIMEOUT_SECONDS,
    plan_import,
)
from .store import (
    ChunkStore,
    InMemoryChunkStore,
    InMemoryManifestStore,
    JsonManifestStore,
    ManifestStore,
)

__all__ = [
    "DEFAULT_MAX_REMOVAL_RATIO",
    "DEFAULT_PROCESSING_TIMEOUT_SECONDS",
    "ChunkStore",
    "DocStatus",
    "ImportAction",
    "ImportConfig",
    "ImportDecision",
    "ImportPlan",
    "ImportReport",
    "ImportedDoc",
    "InMemoryChunkStore",
    "InMemoryManifestStore",
    "JsonManifestStore",
    "Manifest",
    "ManifestStore",
    "MassRemovalRefusedError",
    "import_documents",
    "plan_import",
]
