"""Ingest 子包 —— Knowledge Base 的第一段：磁盘文件 -> 可切块的文档。

对外 API：

- `IngestedDoc` / `RejectedFile` / `IngestReport`：摄取的三个数据结构
- `AdmissionConfig`：准入规则配置（收哪些后缀、大小上限、是否查密钥）
- `ingest`：扫目录、过准入、读文本，返回完整账单
- `normalize_text` / `compute_doc_id`：换行规范化与内容指纹

能力边界：

- 只管「找到文件、判断该不该收、读成文本、算身份」
- **不做切块**（那是 `chunking/` 的事）
- **不做块级过滤**（那是 `chunking/filters.py` 的事）
- 不做向量化、入库、检索

和 `chunking/` 的关系：本包产出 `IngestedDoc.text`，
调用方把它交给 `chunk_text(path=doc.path, text=doc.text, config=...)` 即完成交接。
**本包不 import chunking**，因为摄取不需要知道 `Chunk` 长什么样——
依赖方向是单向的：调用方同时依赖两者，而两者互不依赖。
"""

from .admission import AdmissionConfig, scan_content_for_secrets
from .loader import compute_doc_id, load_document, normalize_text
from .models import IngestedDoc, IngestReport, RejectedFile
from .pipeline import ingest, iter_document_paths

__all__ = [
    "AdmissionConfig",
    "IngestReport",
    "IngestedDoc",
    "RejectedFile",
    "compute_doc_id",
    "ingest",
    "iter_document_paths",
    "load_document",
    "normalize_text",
    "scan_content_for_secrets",
]
