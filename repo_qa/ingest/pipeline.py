"""摄取编排 —— 把「扫描、准入、读取」串成一次完整操作。

数据流
------
::

    root 目录
      │
      ├─ 1. 扫描：找出所有 .md / .markdown（含子目录）
      │     忽略 .git / .venv / node_modules 等目录
      │     扩展名不匹配的 -> skipped（不算失败）
      │
      ├─ 2. 准入：这个文件该不该进库？
      │     文件名像密钥 / 空文件 / 超大文件 -> rejected(stage="admission")
      │     内容里含密钥 -> rejected(stage="admission")
      │
      ├─ 3. 读取：解码 + 规范化 + 算 doc_id
      │     编码坏 / 权限不足 / 全是空白 -> rejected(stage="loading")
      │
      └─ 4. 汇总：IngestReport（收下的 + 被拒的 + 跳过的）

三个必须讲清楚的设计点
----------------------
**第一，为什么扫描阶段要 ``list()``**

``Path.glob()`` 返回的是迭代器（本环境实测是 ``map`` 对象），
**只能遍历一遍**。第二次遍历拿到 0 个结果，而且**不报错**。

这不是理论问题——它是「假绿」：程序不崩，只是悄悄少读了文件。
本模块在 ``iter_document_paths`` 里就把结果收成 ``list``，
对外承诺 ``list[Path]``，说到做到。

**第二，为什么准入在读取之前，但内容检查在读取之后**

顺序是「先便宜后昂贵」：

    stat() 拿文件大小   -> 极其便宜，可以跑几千次
    read_text() 读内容  -> 昂贵，要碰磁盘

所以：文件名/大小这类判断排前面，一组文件里坏的越多，省下的 IO 越多。
内容里的密钥检查没法提前，只能读完之后做——但那时已经付过 IO 成本了，
所以它排在准入的最末尾。

**第三，为什么 rejected 要分 stage**

排障时问的是「它死在哪一步」：

- ``admission`` 拒收 -> 规则判定不该收（改规则就能收）
- ``loading`` 失败  -> 文件本身有问题（改规则也没用，得修文件）

两种情况处理方式完全不同，混在一个字段里就查不出来了。
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .admission import (
    AdmissionConfig,
    check_admission,
    is_candidate,
    scan_content_for_secrets,
    should_descend,
)
from .loader import load_document
from .models import IngestReport, RejectedFile


def iter_document_paths(
    root: Path,
    config: AdmissionConfig,
) -> list[Path]:
    """列出 root 下所有待处理的文件路径，**已排序**。

    这里返回的是「**所有**文件」，不只 .md —— 因为密钥文件（.env 等）
    必须被看到，才能被准入层拒收并留痕。如果在这里就按扩展名滤掉，
    .env 会以「不相关」的名义溜走，账单上什么都不显示。

    过滤分两层：

    - 这里：只排除**忽略目录**（.git / .venv / node_modules）和隐藏路径，
      不按扩展名筛
    - ``ingest`` 里：先查密钥文件名，再判扩展名（不匹配记 skipped）

    排序是为了让输出可复现：同一份目录跑两次，账单顺序一致，
    比对两次结果时不会因为遍历顺序不同而误报差异。
    """
    if not root.exists() or not root.is_dir():
        return []

    found: list[Path] = []
    for path in root.glob("**/*"):
        if not path.is_file():
            continue
        # 检查路径里任意一段是否命中忽略名单（不能只看 parent，那只管一层）。
        # 注意排除最后一段（文件名本身），否则 docs/.env 会因为以点开头被误跳过。
        parent_parts = path.relative_to(root).parts[:-1]
        if any(
            part in config.ignored_dir_names or part.startswith(".")
            for part in parent_parts
        ):
            continue
        found.append(path)

    return sorted(set(found))


def ingest(
    root: Path | str,
    *,
    config: AdmissionConfig | None = None,
    display_root: str = "docs",
) -> IngestReport:
    """把一个目录下的文档读进内存，返回完整账单。

    参数
    ----
    root
        要扫描的目录（通常是项目根下的 ``docs/``）。
    config
        准入配置。不传就用默认（收 .md / .markdown，上限 2MB，挡密钥）。
    display_root
        账单和 doc.path 里显示的目录名。默认 ``"docs"``。
        为什么需要它：绝对路径（``E:\\code\\...\\docs\\手册.md``）又长又不好看，
        进了向量库还会跟着每次都算一遍。统一成相对路径更清爽。
        注意它**不影响 doc_id**——doc_id 只跟内容有关，跟路径无关。
    """
    if config is None:
        config = AdmissionConfig()

    root_path = Path(root)
    report_root = display_root

    # 先把所有候选文件列出来（含被忽略目录外的所有 .md）
    candidates = _list_all_markdown(root_path, config)

    scanned = 0
    skipped = 0
    docs = []
    rejected: list[RejectedFile] = []
    seen_text: dict[str, str] = {}  # doc_id -> 第一次出现的显示路径，用于发现重复内容

    for path in candidates:
        display_path = _display_path(path, root_path, report_root)
        scanned += 1

        # ---- 第 2 步：准入 ----
        # 先跑「文件名像密钥」这一条，再判断扩展名是否在收取范围。
        # 顺序很关键：如果先判扩展名，.env 会被归到「不相关」直接跳过，
        # 账单上什么都看不到——但它是被安全规则挡下的，必须留痕。
        secret_reason = _check_secret_filename(path, config)
        if secret_reason is not None:
            rejected.append(
                RejectedFile(path=display_path, stage="admission", reason=secret_reason)
            )
            continue

        # 扩展名不在收取范围：这是「不相关」，不是「有问题」，计入 skipped 而不是 rejected。
        if not is_candidate(path, config):
            skipped += 1
            continue

        reason = check_admission(path, config)
        if reason is not None:
            rejected.append(RejectedFile(path=display_path, stage="admission", reason=reason))
            continue

        # ---- 第 3 步：读取 ----
        doc = load_document(path, display_path=display_path)
        if doc is None:
            rejected.append(
                RejectedFile(
                    path=display_path,
                    stage="loading",
                    reason="读取失败：编码不是 UTF-8、权限不足，或内容全是空白",
                )
            )
            continue

        # ---- 第 3.5 步：内容里的密钥（只有读完之后才能查） ----
        if config.scan_content_for_secrets:
            secret_reason = scan_content_for_secrets(doc.text)
            if secret_reason is not None:
                rejected.append(
                    RejectedFile(path=display_path, stage="admission", reason=secret_reason)
                )
                continue

        # ---- 第 3.6 步：同名内容去重（不同路径、相同 doc_id） ----
        if doc.doc_id in seen_text:
            rejected.append(
                RejectedFile(
                    path=display_path,
                    stage="admission",
                    reason=f"内容与 {seen_text[doc.doc_id]} 完全相同（doc_id={doc.doc_id}），只收第一次",
                )
            )
            continue
        seen_text[doc.doc_id] = display_path

        docs.append(doc)

    return IngestReport(
        root=report_root,
        scanned=scanned,
        skipped=skipped,
        docs=tuple(docs),
        rejected=tuple(rejected),
    )


def _list_all_markdown(root: Path, config: AdmissionConfig) -> list[Path]:
    """列出候选文件。如果 root 不存在，返回空列表（不抛异常）。

    为什么不抛：``docs/`` 目录不存在是**正常的初始状态**，
    不该让整个流程崩掉。返回空列表 + 账单里 scanned=0，调用方一眼就能看出。
    """
    return iter_document_paths(root, config)


def _check_secret_filename(path: Path, config: AdmissionConfig) -> str | None:
    """只跑「文件名像密钥」这一条规则。

    单独抽出来是因为它的执行顺序在扩展名判断**之前**：
    一个 ``.env`` 文件的扩展名不在收取范围内，如果先判扩展名，
    它会被归入「不相关」静默跳过——安全上结果碰巧是对的，
    但**过程不对**：它应该是被安全规则明确拒收并留痕的。
    """
    if not config.block_secret_filenames:
        return None
    from .admission import SecretFilenameRule

    return SecretFilenameRule().check(path, 0)


def _display_path(path: Path, root: Path, display_root: str) -> str:
    """把绝对路径转成 ``docs/子目录/文件.md`` 这种相对形式。"""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return str(path)
    return f"{display_root}/{rel.as_posix()}"
