"""幂等导入测试 —— 五种动作、幂等性、两个键的必要性、安全阀、写入顺序。

覆盖七层：

1. 五种动作各自的场景（新增 / 更新 / 改名 / 跳过 / 删除）
2. **幂等**：跑两次结果一样（这是整个能力的目的）
3. **两个键的必要性**：只用 doc_id 或只用 path 会怎么误判
4. 安全阀：大规模删除被拒绝
5. 存储层：put 的覆盖语义、delete、统计
6. 账本持久化：JSON 读写、原子写、文件不存在
7. 写入顺序：先写块后写账本，崩溃后能自愈

全部离线：不访问网络、不读项目根目录的 docs/（用 tmp_path 造语料）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_qa.chunking import Chunk, ChunkConfig
from repo_qa.indexing import (
    DEFAULT_MAX_REMOVAL_RATIO,
    ChunkStore,
    DocStatus,
    ImportAction,
    ImportConfig,
    ImportedDoc,
    InMemoryChunkStore,
    InMemoryManifestStore,
    JsonManifestStore,
    Manifest,
    MassRemovalRefusedError,
    import_documents,
    plan_import,
)
from repo_qa.ingest import ingest
from repo_qa.ingest.models import IngestedDoc

FIXED_NOW = "2026-09-19T00:00:00"

# 一份足够长的 markdown，保证切出来的块不会被 too_short 过滤掉
DOC_A = "# 员工手册\n\n## 第一章 考勤\n\n公司实行弹性工作制，标准上班时间为每天九点。\n\n### 1.1 迟到\n\n迟到十五分钟以内不计入考勤异常。\n"
DOC_B = "# 报销制度\n\n## 第一章 额度\n\n单次差旅报销上限为五千元，超出部分需审批。\n"
DOC_C = "# 假期管理\n\n## 第一章 年假\n\n入职满一年享有五天带薪年假，每满一年增加一天。\n"


# ===========================================================================
# 夹具与助手
# ===========================================================================


@pytest.fixture
def docroot(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    root.mkdir()
    return root


def write(root: Path, name: str, content: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def remove(root: Path, name: str) -> None:
    (root / name).unlink()


def make_config(**overrides) -> ImportConfig:
    base = {"chunk": ChunkConfig(strategy="markdown_heading", max_lines=50)}
    base.update(overrides)
    return ImportConfig(**base)


def run_import(root: Path, store: ChunkStore, manifest_store, **kwargs):
    return import_documents(
        root,
        chunk_store=store,
        manifest_store=manifest_store,
        now=FIXED_NOW,
        **kwargs,
    )


def actions(report) -> dict[str, str]:
    """把报告变成 ``{路径: 动作名}``，方便断言。"""
    return {d.path: d.action.value for d in report.plan.decisions}


# ===========================================================================
# 一、五种动作
# ===========================================================================


def test_first_import_adds_everything(docroot: Path):
    write(docroot, "a.md", DOC_A)
    write(docroot, "b.md", DOC_B)

    store = InMemoryChunkStore()
    report = run_import(docroot, store, InMemoryManifestStore())

    assert report.plan.count(ImportAction.ADDED) == 2
    assert report.plan.count(ImportAction.UNCHANGED) == 0
    assert report.store_document_count == 2
    assert report.store_chunk_count > 0
    assert report.embedded_document_count == 2, "新增的两份都要重新算向量"


def test_unchanged_when_nothing_changed(docroot: Path):
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()

    run_import(docroot, store, manifest_store)
    report = run_import(docroot, store, manifest_store)

    assert report.plan.count(ImportAction.UNCHANGED) == 1
    assert report.plan.count(ImportAction.ADDED) == 0
    assert report.embedded_document_count == 0, "没变就不该花钱"


def test_updated_when_content_changes(docroot: Path):
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()

    first = run_import(docroot, store, manifest_store)
    old_doc_id = next(iter(manifest_store.load().docs))

    # 改内容，路径不变
    write(docroot, "a.md", DOC_A + "\n### 1.2 早退\n\n早退按迟到处理。\n")
    report = run_import(docroot, store, manifest_store)

    assert report.plan.count(ImportAction.UPDATED) == 1
    assert report.plan.count(ImportAction.ADDED) == 0
    assert report.embedded_document_count == 1, "内容变了要重新算向量"

    # 旧 doc_id 必须从账本和存储里消失
    new_manifest = manifest_store.load()
    assert old_doc_id not in new_manifest.docs
    assert store.get_document(old_doc_id) == ()
    assert store.document_count() == 1, "更新不该产生第二份文档"


def test_updated_does_not_leave_the_old_document_behind(docroot: Path):
    """更新之后，库里不能有旧内容的块。

    这条是「新旧并存」这个危险的回归测试：
    如果旧块没删掉，用户可能搜到过期答案。

    注意：这里的新标题写得比较长（``# 完全不同的员工手册文档``，13 个字符），
    是刻意的——第一版用了 ``# 完全不同的文档``（9 个字符），
    结果那个标题块被 ``too_short``（阈值 10）丢掉了，断言就找不到它。

    **这正好复现了「空壳块 + 脆弱字符数边界」那个已知问题**：
    只有标题、没有正文的块能不能活下来，取决于标题有几个字符。
    测试要断言标题存在，就必须让标题长到能过阈值——否则测的是过滤规则，
    不是被测的幂等逻辑。
    """
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)

    write(
        docroot,
        "a.md",
        "# 完全不同的员工手册文档\n\n## 新的内容\n\n这里讲的完全是另一件事了。\n",
    )
    run_import(docroot, store, manifest_store)

    all_text = "\n".join(c.content for c in store.all_chunks())
    assert "迟到十五分钟" not in all_text, "旧内容还在库里，这是「新旧并存」"
    assert "完全不同的员工手册文档" in all_text


def test_renamed_when_only_the_filename_changes(docroot: Path):
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)
    chunks_before = store.all_chunks()

    # 只改名字，内容一个字不动
    (docroot / "a.md").rename(docroot / "改名后.md")
    report = run_import(docroot, store, manifest_store)

    assert report.plan.count(ImportAction.RENAMED) == 1
    assert report.plan.count(ImportAction.ADDED) == 0
    assert report.plan.count(ImportAction.REMOVED) == 0, "改名不是删除"
    assert report.embedded_document_count == 0, "改名不该花钱重新算向量"

    # 账本里的路径更新了
    record = next(iter(manifest_store.load().docs.values()))
    assert record.path == "docs/改名后.md"


def test_rename_updates_the_path_inside_the_chunks(docroot: Path):
    """**改名时块里记的 path 必须跟着改。**

    这是一个真实存在过的 bug。``Chunk.citation`` 是 ``f"{path}:{start}-{end}"``，
    path 存在块自己身上。如果只改账本的路径、块完全不动，就会出现：

        账本：docs/员工手册_v2.md
        块  ：docs/员工手册.md:3-5      <- 旧文件名

    **用户点击引用会跳到不存在的文件。**

    第一版实现就是「块完全不动」，当时的测试还把这个行为断言成正确
    （``assert store.all_chunks() == chunks_before``）——
    等于把 bug 钉成了契约。现在改成：内容一个字不改，但 path 要更新。
    """
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)
    before = store.all_chunks()

    (docroot / "a.md").rename(docroot / "b.md")
    run_import(docroot, store, manifest_store)
    after = store.all_chunks()

    # 内容一个字节都没改
    assert [c.content for c in after] == [c.content for c in before]
    # 行号区间也没变
    assert [(c.start_line, c.end_line) for c in after] == [
        (c.start_line, c.end_line) for c in before
    ]
    # 但 path 更新了
    assert all(c.path == "docs/b.md" for c in after)
    assert all("a.md" not in c.citation for c in after), "citation 里还留着旧文件名"
    assert all(c.citation.startswith("docs/b.md:") for c in after)


def test_renamed_keeps_original_ready_at(docroot: Path):
    """改名不刷新 ready_at —— 它的含义是「这份内容什么时候入的库」。"""
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store, )
    before = next(iter(manifest_store.load().docs.values())).ready_at

    (docroot / "a.md").rename(docroot / "b.md")
    import_documents(
        docroot, chunk_store=store, manifest_store=manifest_store, now="2027-01-01T00:00:00"
    )

    after = next(iter(manifest_store.load().docs.values())).ready_at
    assert after == before == FIXED_NOW


def test_removed_when_the_file_disappears(docroot: Path):
    write(docroot, "a.md", DOC_A)
    write(docroot, "b.md", DOC_B)
    write(docroot, "c.md", DOC_C)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)
    assert store.document_count() == 3

    remove(docroot, "b.md")
    # 3 个里删 1 个 = 33%，低于默认阈值 50%，不会被安全阀拦
    report = run_import(docroot, store, manifest_store)

    assert report.plan.count(ImportAction.REMOVED) == 1
    assert report.store_document_count == 2
    assert report.store_chunk_count == sum(
        len(c) for c in [store.all_chunks()]
    ) or report.store_chunk_count > 0

    all_text = "\n".join(c.content for c in store.all_chunks())
    assert "报销制度" not in all_text, "被删文档的内容还在库里"


def test_removed_document_disappears_from_manifest(docroot: Path):
    write(docroot, "a.md", DOC_A)
    write(docroot, "b.md", DOC_B)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)

    remove(docroot, "b.md")
    run_import(docroot, store, manifest_store)

    paths = {r.path for r in manifest_store.load().docs.values()}
    assert paths == {"docs/a.md"}


def test_all_five_actions_in_one_run(docroot: Path):
    """一次导入里同时出现五种动作——验证它们互不干扰。"""
    write(docroot, "unchanged.md", DOC_A)
    write(docroot, "to_update.md", DOC_B)
    write(docroot, "to_rename.md", DOC_C)
    write(docroot, "to_delete.md", "# 待删除\n\n## 内容\n\n这份文档待会会被删掉。\n")

    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)
    assert store.document_count() == 4

    # 制造四种变化
    write(docroot, "to_update.md", "# 报销制度\n\n## 第一章 额度\n\n上限改成八千元了，注意。\n")
    (docroot / "to_rename.md").rename(docroot / "renamed.md")
    remove(docroot, "to_delete.md")
    write(docroot, "brand_new.md", "# 新文档\n\n## 内容\n\n这是全新的一份文档内容。\n")

    report = run_import(docroot, store, manifest_store)
    result = actions(report)

    assert result["docs/brand_new.md"] == ImportAction.ADDED.value
    assert result["docs/to_update.md"] == ImportAction.UPDATED.value
    assert result["docs/renamed.md"] == ImportAction.RENAMED.value
    assert result["docs/unchanged.md"] == ImportAction.UNCHANGED.value
    assert result["docs/to_delete.md"] == ImportAction.REMOVED.value

    # 4 个原有文档 - 1 删除 + 1 新增 = 4
    assert report.store_document_count == 4


# ===========================================================================
# 二、幂等：这个能力存在的唯一理由
# ===========================================================================


def test_importing_twice_changes_nothing(docroot: Path):
    """**核心断言**：跑两次和跑一次，库里的结果完全一样。"""
    write(docroot, "a.md", DOC_A)
    write(docroot, "b.md", DOC_B)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()

    first = run_import(docroot, store, manifest_store)
    second = run_import(docroot, store, manifest_store)
    third = run_import(docroot, store, manifest_store)

    assert first.store_document_count == second.store_document_count == third.store_document_count
    assert first.store_chunk_count == second.store_chunk_count == third.store_chunk_count
    assert second.embedded_document_count == 0
    assert third.embedded_document_count == 0


def test_repeated_import_does_not_duplicate_chunks(docroot: Path):
    """**这是需求原文**：「重复导入不产生重复块」。"""
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()

    run_import(docroot, store, manifest_store)
    chunks_after_first = store.all_chunks()
    run_import(docroot, store, manifest_store)

    assert store.all_chunks() == chunks_after_first
    assert len(store.all_chunks()) == len(chunks_after_first)


def test_ten_imports_are_still_one_import(docroot: Path):
    """跑十次也一样——幂等的定义是「跑多次结果一样」，不只是两次。"""
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()

    run_import(docroot, store, manifest_store)
    baseline = (store.document_count(), store.chunk_count())

    for _ in range(9):
        run_import(docroot, store, manifest_store)

    assert (store.document_count(), store.chunk_count()) == baseline


# ===========================================================================
# 三、两个键的必要性
# ===========================================================================


def test_doc_id_alone_would_miss_content_updates():
    """只用 doc_id 判断，内容改了会被误判成「新文档」——旧的不会被清理。

    这条用 planner 的直接调用来演示，不经过存储层。
    """
    from repo_qa.ingest.models import IngestedDoc

    old = Manifest(
        docs={
            "aaa": ImportedDoc(doc_id="aaa", path="docs/x.md", chunk_count=3, ready_at=FIXED_NOW)
        }
    )
    # 同一个路径，内容变了 -> 新的 doc_id
    new_doc = IngestedDoc(path="docs/x.md", doc_id="bbb", text="新内容", line_count=1)

    plan = plan_import([new_doc], old)
    assert plan.count(ImportAction.UPDATED) == 1
    assert plan.count(ImportAction.ADDED) == 0, "不能因为 doc_id 变了就当成全新文档"


def test_path_alone_would_miss_renames():
    """只用 path 判断，改名会被误判成「新文档」——白做一次 embedding。

    这条钉住的是「为什么 doc_id 要用内容 hash 而不是文件路径」。
    """
    from repo_qa.ingest.models import IngestedDoc

    old = Manifest(
        docs={
            "aaa": ImportedDoc(doc_id="aaa", path="docs/旧名.md", chunk_count=3, ready_at=FIXED_NOW)
        }
    )
    # 内容完全一样（doc_id 还是 aaa），只是换了路径
    renamed = IngestedDoc(path="docs/新名.md", doc_id="aaa", text="同样的内容", line_count=1)

    plan = plan_import([renamed], old)
    assert plan.count(ImportAction.RENAMED) == 1
    assert plan.count(ImportAction.ADDED) == 0, "改名不是新增，不该重新算向量"
    assert plan.count(ImportAction.REMOVED) == 0, "改名不是删除"


def test_swap_paths_between_two_documents():
    """两份文档互换文件名——两边都该判成改名，不该判成新增+删除。"""
    from repo_qa.ingest.models import IngestedDoc

    old = Manifest(
        docs={
            "aaa": ImportedDoc(doc_id="aaa", path="docs/x.md", chunk_count=1, ready_at=FIXED_NOW),
            "bbb": ImportedDoc(doc_id="bbb", path="docs/y.md", chunk_count=1, ready_at=FIXED_NOW),
        }
    )
    docs = [
        IngestedDoc(path="docs/y.md", doc_id="aaa", text="A 的内容", line_count=1),
        IngestedDoc(path="docs/x.md", doc_id="bbb", text="B 的内容", line_count=1),
    ]

    plan = plan_import(docs, old)
    assert plan.count(ImportAction.RENAMED) == 2
    assert plan.count(ImportAction.ADDED) == 0
    assert plan.count(ImportAction.REMOVED) == 0


# ===========================================================================
# 四、安全阀：拒绝大规模删除
# ===========================================================================


def test_mass_removal_is_refused(docroot: Path):
    """扫到 0 个文件（比如目录配错了）时，拒绝清空整个知识库。

    这是真实事故场景：``docs/`` 路径打错一个字，扫到 0 个文件，
    系统认为「所有文档都被删了」，于是清空知识库——恢复要重新花钱。
    """
    write(docroot, "a.md", DOC_A)
    write(docroot, "b.md", DOC_B)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)

    # 模拟「目录配错」：换成一个空目录
    empty = docroot.parent / "empty_docs"
    empty.mkdir()

    with pytest.raises(MassRemovalRefusedError) as excinfo:
        run_import(empty, store, manifest_store)

    assert excinfo.value.to_remove == 2
    assert excinfo.value.total_known == 2
    # 关键：库必须原封不动
    assert store.document_count() == 2


def test_mass_removal_can_be_allowed_explicitly(docroot: Path):
    """确认无误时，调高阈值就能执行——安全阀不该是死路。"""
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)

    empty = docroot.parent / "empty_docs"
    empty.mkdir()

    report = run_import(
        empty, store, manifest_store, config=make_config(max_removal_ratio=1.0)
    )
    assert report.plan.count(ImportAction.REMOVED) == 1
    assert store.document_count() == 0


def test_small_removal_is_not_blocked(docroot: Path):
    """低于阈值的删除正常执行，不该被拦。"""
    for index in range(10):
        write(docroot, f"d{index}.md", f"# 文档 {index}\n\n## 内容\n\n这是第 {index} 份文档的正文内容。\n")

    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)

    # 删 1 个 = 10%，低于 50%
    remove(docroot, "d0.md")
    report = run_import(docroot, store, manifest_store)
    assert report.plan.count(ImportAction.REMOVED) == 1


def test_default_threshold_is_half():
    assert DEFAULT_MAX_REMOVAL_RATIO == 0.5


def test_invalid_removal_ratio_is_rejected():
    with pytest.raises(ValueError):
        plan_import([], Manifest(), max_removal_ratio=1.5)
    with pytest.raises(ValueError):
        plan_import([], Manifest(), max_removal_ratio=-0.1)


def test_corrupted_manifest_with_duplicate_paths_is_rejected():
    """账本里两条记录指向同一路径 -> 按路径查会歧义 -> 早点炸出来。"""
    broken = Manifest(
        docs={
            "aaa": ImportedDoc(doc_id="aaa", path="docs/x.md", chunk_count=1, ready_at=FIXED_NOW),
            "bbb": ImportedDoc(doc_id="bbb", path="docs/x.md", chunk_count=1, ready_at=FIXED_NOW),
        }
    )
    with pytest.raises(ValueError, match="同一个路径"):
        plan_import([], broken)


# ===========================================================================
# 五、存储层
# ===========================================================================


def _chunk(path: str, start: int, end: int, content: str) -> Chunk:
    return Chunk(path=path, start_line=start, end_line=end, content=content)


def test_put_document_overwrites_not_appends():
    """**这是整个「先写块后写账本」能自愈的前提。**

    ``put_document`` 必须是覆盖语义。如果是追加，
    重复导入就会在库里堆出多份同样的块。
    """
    store = InMemoryChunkStore()
    first = (_chunk("a.md", 1, 2, "第一版内容"),)
    second = (_chunk("a.md", 1, 3, "第二版内容，更长一点"),)

    store.put_document("doc-1", first)
    assert store.chunk_count() == 1

    store.put_document("doc-1", second)
    assert store.chunk_count() == 1, "覆盖语义下不该变成 2"
    assert store.get_document("doc-1") == second


def test_delete_document_returns_removed_count():
    store = InMemoryChunkStore()
    store.put_document("doc-1", (_chunk("a.md", 1, 1, "内容一"),))
    store.put_document("doc-2", (_chunk("b.md", 1, 1, "内容二"),))

    assert store.delete_document("doc-1") == 1
    assert store.delete_document("doc-1") == 0, "删不存在的文档返回 0，不报错"
    assert store.document_count() == 1


def test_store_counts_are_consistent():
    store = InMemoryChunkStore()
    store.put_document("doc-1", (_chunk("a.md", 1, 1, "一"), _chunk("a.md", 2, 2, "二")))
    store.put_document("doc-2", (_chunk("b.md", 1, 1, "三"),))

    assert store.document_count() == 2
    assert store.chunk_count() == 3
    assert len(store.all_chunks()) == 3
    assert store.get_document("不存在") == ()


def test_put_document_rejects_empty_doc_id():
    store = InMemoryChunkStore()
    with pytest.raises(ValueError):
        store.put_document("", ())


# ===========================================================================
# 六、账本持久化
# ===========================================================================


def test_json_manifest_round_trip(tmp_path: Path):
    path = tmp_path / "manifest.json"
    store = JsonManifestStore(path)

    manifest = Manifest(
        docs={
            "abc123": ImportedDoc(
                doc_id="abc123",
                path="docs/员工手册.md",
                chunk_count=9,
                ready_at=FIXED_NOW,
            )
        }
    )
    store.save(manifest)

    loaded = store.load()
    assert loaded.docs == manifest.docs


def test_json_manifest_handles_chinese_paths(tmp_path: Path):
    """中文路径要能正常存取——不能变成 ``\\u5458\\u5de5`` 那种转义。"""
    path = tmp_path / "manifest.json"
    store = JsonManifestStore(path)
    store.save(
        Manifest(
            docs={
                "abc": ImportedDoc(
                    doc_id="abc", path="docs/员工手册.md", chunk_count=1, ready_at=FIXED_NOW
                )
            }
        )
    )

    raw = path.read_text(encoding="utf-8")
    assert "员工手册" in raw, "中文被转义了，读起来没法看"


def test_json_manifest_missing_file_returns_empty(tmp_path: Path):
    """第一次导入没有账本是正常的，不是错误。"""
    store = JsonManifestStore(tmp_path / "不存在.json")
    assert store.load() == Manifest()
    assert len(store.load()) == 0


def test_json_manifest_creates_parent_directory(tmp_path: Path):
    path = tmp_path / "nested" / "deep" / "manifest.json"
    JsonManifestStore(path).save(Manifest())
    assert path.exists()


def test_json_manifest_write_is_atomic(tmp_path: Path):
    """写完不该留下临时文件。"""
    path = tmp_path / "manifest.json"
    store = JsonManifestStore(path)
    store.save(Manifest())
    store.save(Manifest())

    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "manifest.json"]
    assert leftovers == [], f"留下了临时文件：{leftovers}"


def test_json_manifest_survives_across_store_instances(tmp_path: Path):
    """换一个 JsonManifestStore 实例（模拟进程重启）也能读到同样的账本。"""
    path = tmp_path / "manifest.json"
    manifest = Manifest(
        docs={
            "abc": ImportedDoc(
                doc_id="abc", path="docs/a.md", chunk_count=1, ready_at=FIXED_NOW
            )
        }
    )
    JsonManifestStore(path).save(manifest)
    assert JsonManifestStore(path).load().docs == manifest.docs


def test_manifest_file_is_valid_json_with_version(tmp_path: Path):
    path = tmp_path / "manifest.json"
    JsonManifestStore(path).save(Manifest())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["docs"] == {}


# ===========================================================================
# 七、写入顺序：先写块后写账本，崩溃后能自愈
# ===========================================================================


class _CrashOnNthSaveManifestStore(InMemoryManifestStore):
    """在第 N 次写账本时崩溃。

    为什么需要「第 N 次」而不是「每次」：现在的导入流程**写两次账本**
    （第 4 步抢占写 PROCESSING、第 7 步收尾写 READY），
    两次崩溃点的后果完全不同，要分别测：

    ::

        第 1 次崩（抢占）-> 块没写、状态也没写 -> 下次判「新增」重做
        第 2 次崩（收尾）-> 块写了、状态卡在 PROCESSING
                          -> 未超时：别的进程跳过
                          -> 超时后：接管重做
    """

    def __init__(self, crash_on: int) -> None:
        super().__init__()
        self._crash_on = crash_on
        self._saves = 0

    def save(self, manifest: Manifest) -> None:
        self._saves += 1
        if self._saves == self._crash_on:
            raise RuntimeError(f"模拟：第 {self._crash_on} 次写账本时崩溃")
        super().save(manifest)


def test_crash_during_claim_self_heals(docroot: Path):
    """崩在「抢占」那一步（第 4 步）：块没写、状态也没写。

    下次导入判「新增」-> 重做 -> 覆盖 -> 一致。
    """
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    crashing = _CrashOnNthSaveManifestStore(crash_on=1)

    with pytest.raises(RuntimeError, match="第 1 次写账本时崩溃"):
        run_import(docroot, store, crashing)

    assert store.document_count() == 0, "抢占阶段就崩了，块不该写进去"
    assert len(crashing.load()) == 0, "状态也没写"

    # 恢复
    healthy = InMemoryManifestStore()
    report = run_import(docroot, store, healthy)

    assert report.plan.count(ImportAction.ADDED) == 1
    assert report.store_document_count == 1
    assert len(healthy.load()) == 1


def test_crash_during_finalize_leaves_processing_state(docroot: Path):
    """**崩在「收尾」那一步（第 7 步）：块写了，但状态卡在 PROCESSING。**

    这是状态机设计的核心场景。后果分两种情况：

    - **未超时**：别的进程看到 PROCESSING，跳过（不重复花钱）
    - **超时后**：视为僵尸任务，接管重做

    如果只有一个「写一次」的设计，这里会是「账本没记录」-> 判「新增」->
    重做。但重做时**不知道有没有别的进程正在做同一件事**。
    中间状态把「并发安全」这个能力补上了。
    """
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore(store_id="store-X")
    crashing = _CrashOnNthSaveManifestStore(crash_on=2)

    with pytest.raises(RuntimeError, match="第 2 次写账本时崩溃"):
        run_import(docroot, store, crashing)

    # 前提确认：块写了，但状态卡在 PROCESSING
    assert store.document_count() == 1, "块应该已经写进去了"
    stuck = next(iter(crashing.load().docs.values()))
    assert stuck.status is DocStatus.PROCESSING
    assert stuck.started_at == FIXED_NOW

    # 情况 A：紧接着再跑一次（没超时）-> 判 LOCKED，不动
    soon = "2026-09-19T00:01:00"  # 1 分钟后
    manifest_store = InMemoryManifestStore(crashing.load())
    blocked = import_documents(
        docroot, chunk_store=store, manifest_store=manifest_store, now=soon
    )
    assert blocked.plan.count(ImportAction.LOCKED) == 1, "没超时 -> 被锁住"
    assert blocked.plan.count(ImportAction.ADDED) == 0
    assert blocked.embedded_document_count == 0, "不该重复花钱"

    # 情况 B：过了超时时间再跑 -> 接管重做
    later = "2026-09-19T01:00:00"  # 1 小时后（超过默认 30 分钟）
    resumed = import_documents(
        docroot, chunk_store=store, manifest_store=manifest_store, now=later
    )
    assert resumed.plan.count(ImportAction.RESUMED) == 1, "超时了 -> 接管"
    record = next(iter(manifest_store.load().docs.values()))
    assert record.status is DocStatus.READY
    assert store.document_count() == 1, "覆盖语义 -> 没变成两份"


def test_locked_document_is_not_reprocessed(docroot: Path):
    """**并发安全**：别的进程正在处理时，本次不该重复处理。

    这是单次写账本的设计给不了的能力。重复处理 = 白花一倍 embedding 的钱。
    """
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore(store_id="store-Y")

    # 手工造出「另一个进程正在处理」的状态
    doc = ingest(docroot).docs[0]
    locked_manifest = Manifest(
        docs={
            doc.doc_id: ImportedDoc(
                doc_id=doc.doc_id,
                path=doc.path,
                status=DocStatus.PROCESSING,
                started_at=FIXED_NOW,
            )
        },
        store_id=store.store_id,
    )

    manifest_store = InMemoryManifestStore(locked_manifest)
    report = import_documents(
        docroot,
        chunk_store=store,
        manifest_store=manifest_store,
        now="2026-09-19T00:05:00",  # 5 分钟后，没超时
    )

    assert report.plan.count(ImportAction.LOCKED) == 1
    assert report.embedded_document_count == 0
    assert store.document_count() == 0, "别人在做，我不该写"
    # 关键：那条 PROCESSING 记录必须还在，不能被本次导入弄丢
    assert len(manifest_store.load()) == 1
    assert next(iter(manifest_store.load().docs.values())).status is DocStatus.PROCESSING


def test_processing_document_is_not_removed_by_scan(docroot: Path):
    """正在处理中的文档，不该因为「这次没扫到」就被删掉。

    它可能马上就处理完了。删了的话，那个进程还在写块，
    结果就是「库里有块、账本没记录」的孤儿。
    """
    doc = IngestedDoc(
        path="docs/正在处理.md",
        doc_id="inflight",
        text="内容",
        line_count=1,
    )
    manifest = Manifest(
        docs={
            "inflight": ImportedDoc(
                doc_id="inflight",
                path="docs/正在处理.md",
                status=DocStatus.PROCESSING,
                started_at=FIXED_NOW,
            )
        }
    )

    plan = plan_import([], manifest, now="2026-09-19T00:05:00")  # 没扫到任何文件

    assert plan.count(ImportAction.REMOVED) == 0, "处理中的文档不该被删"
    assert plan.total == 0


def test_failed_document_is_retried(docroot: Path):
    """**失败可见 + 可重试**：状态是 FAILED 的文档，下次导入会重试。

    保留 FAILED 状态的意义就在这 —— 失败不会静默消失。
    """
    write(docroot, "a.md", DOC_A)
    doc = ingest(docroot).docs[0]

    store = InMemoryChunkStore(store_id="store-Z")
    manifest_store = InMemoryManifestStore(
        Manifest(
            docs={
                doc.doc_id: ImportedDoc(
                    doc_id=doc.doc_id,
                    path=doc.path,
                    status=DocStatus.FAILED,
                    started_at=FIXED_NOW,
                )
            },
            store_id=store.store_id,
        )
    )

    report = run_import(docroot, store, manifest_store)

    assert report.plan.count(ImportAction.RESUMED) == 1
    assert report.embedded_document_count == 1
    record = next(iter(manifest_store.load().docs.values()))
    assert record.status is DocStatus.READY, "重试成功后要变成 READY"


class _FailingChunkStore(InMemoryChunkStore):
    """写块时抛异常，模拟 embedding 服务挂了。"""

    def put_document(self, doc_id, chunks) -> None:
        raise RuntimeError("模拟：embedding 服务不可用")


def test_processing_failure_is_recorded_not_swallowed(docroot: Path):
    """处理失败要**记下来**，不能让整批挂掉，也不能静默。

    一份文档失败，不该让另外几百份都白扫一遍。
    同时状态要置成 FAILED，让失败可见、下次能重试。
    """
    write(docroot, "a.md", DOC_A)
    write(docroot, "b.md", DOC_B)

    store = _FailingChunkStore(store_id="store-F")
    manifest_store = InMemoryManifestStore()

    report = run_import(docroot, store, manifest_store)

    assert len(report.failed_doc_ids) == 2, "两份都失败了"
    assert "处理失败 2 个" in report.summary()
    records = manifest_store.load().docs
    assert all(r.status is DocStatus.FAILED for r in records.values())

    # 再跑一次：应该重试
    retry = run_import(docroot, store, manifest_store)
    assert retry.plan.count(ImportAction.RESUMED) == 2


def test_one_failure_does_not_stop_the_others(docroot: Path):
    """一份失败不该拖垮整批 —— 其他的照常处理完。"""
    write(docroot, "good.md", DOC_A)
    write(docroot, "bad.md", DOC_B)

    class _FailOnlyBad(InMemoryChunkStore):
        def put_document(self, doc_id, chunks) -> None:
            if "报销" in chunks[0].content:
                raise RuntimeError("模拟：这一份挂了")
            super().put_document(doc_id, chunks)

    store = _FailOnlyBad(store_id="store-M")
    manifest_store = InMemoryManifestStore()
    report = run_import(docroot, store, manifest_store)

    assert len(report.failed_doc_ids) == 1
    assert store.document_count() == 1, "好的那份必须处理完"
    statuses = {r.path: r.status for r in manifest_store.load().docs.values()}
    assert statuses["docs/good.md"] is DocStatus.READY
    assert statuses["docs/bad.md"] is DocStatus.FAILED


def test_ready_status_is_written_after_successful_processing(docroot: Path):
    """处理成功后，状态必须是 READY，而且带上 ready_at 和 chunk_count。"""
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore(store_id="store-R")
    manifest_store = InMemoryManifestStore()

    run_import(docroot, store, manifest_store)

    record = next(iter(manifest_store.load().docs.values()))
    assert record.status is DocStatus.READY
    assert record.ready_at == FIXED_NOW
    assert record.chunk_count > 0


def test_processing_timeout_is_configurable(docroot: Path):
    """超时时间可以调 —— 调小之后，同样的状态会被判成僵尸。"""
    write(docroot, "a.md", DOC_A)
    doc = ingest(docroot).docs[0]

    manifest = Manifest(
        docs={
            doc.doc_id: ImportedDoc(
                doc_id=doc.doc_id,
                path=doc.path,
                status=DocStatus.PROCESSING,
                started_at=FIXED_NOW,
            )
        }
    )

    # 默认 30 分钟超时：5 分钟后不算僵尸
    plan = plan_import([doc], manifest, now="2026-09-19T00:05:00")
    assert plan.count(ImportAction.LOCKED) == 1

    # 把超时调到 60 秒：5 分钟后就算僵尸了
    plan = plan_import(
        [doc], manifest, now="2026-09-19T00:05:00", processing_timeout_seconds=60
    )
    assert plan.count(ImportAction.RESUMED) == 1


def test_record_without_started_at_is_treated_as_expired(docroot: Path):
    """时间戳缺失或坏掉 -> 视为僵尸 -> 允许接管。

    宁可重做一遍（花一次钱），也不要因为时间戳坏掉而永远卡住。
    """
    doc = IngestedDoc(path="docs/a.md", doc_id="x", text="内容", line_count=1)
    # 手工绕过 __post_init__ 的校验，造出一个「PROCESSING 但没有 started_at」的坏记录
    bad_record = object.__new__(ImportedDoc)
    object.__setattr__(bad_record, "doc_id", "x")
    object.__setattr__(bad_record, "path", "docs/a.md")
    object.__setattr__(bad_record, "status", DocStatus.PROCESSING)
    object.__setattr__(bad_record, "chunk_count", 0)
    object.__setattr__(bad_record, "started_at", "")
    object.__setattr__(bad_record, "ready_at", "")

    plan = plan_import([doc], Manifest(docs={"x": bad_record}), now=FIXED_NOW)
    assert plan.count(ImportAction.RESUMED) == 1


def test_processing_record_requires_started_at():
    """PROCESSING 状态必须有 started_at，否则僵尸检测无从下手。"""
    with pytest.raises(ValueError, match="started_at"):
        ImportedDoc(
            doc_id="x",
            path="docs/a.md",
            status=DocStatus.PROCESSING,
            started_at="",
        )


def test_manifest_written_twice_per_import(docroot: Path):
    """一次导入写两次账本：先 PROCESSING，后 READY。"""
    write(docroot, "a.md", DOC_A)

    saves: list[tuple[str, ...]] = []

    class _RecordingManifestStore(InMemoryManifestStore):
        def save(self, manifest: Manifest) -> None:
            saves.append(tuple(sorted(r.status.value for r in manifest.docs.values())))
            super().save(manifest)

    store = InMemoryChunkStore(store_id="store-2W")
    run_import(docroot, store, _RecordingManifestStore())

    assert saves == [("processing",), ("ready",)], (
        "第一次应该写 PROCESSING（抢占），第二次写 READY（收尾）"
    )


def test_opposite_order_is_now_caught_by_reconciliation(docroot: Path):
    """「先写账本后写块」的静默丢失，现在被防线 2（对账）兜住了。

    这个测试记录了一次**设计演进**，值得写清楚：

    ::

        第一版设计：只靠「排顺序」保证一致性
          先写账本 -> 崩溃 -> 账本说有、库里没有
          -> 下次判「跳过」-> 文档永远补不回来，不报错
          -> 所以当时断言「先写账本会静默丢失」

        加了防线 2 之后：导入前先和库对账
          账本里有、库里没有的条目 -> 从账本剔出去 -> 判「新增」-> 重建
          -> 静默丢失被兜住了

    所以现在的结论更准确：

    **加了防线 2 之后，「先写块还是先写账本」不再是正确性问题 —— 两种顺序都能自愈。**

    那为什么还保留「先写块」？理由是**纵深防御**：

    1. 防线 2 依赖「账本和库能对账」。如果对账本身出问题
       （``doc_ids()`` 实现有 bug、存储不支持列举），先写账本的静默丢失又回来了。
    2. 「库里有、账本没有」这个错误是**可见的**（库里有东西，一查就知道）；
       「账本有、库里没有」是**静默的**（不看对账结果根本发现不了）。
       让不一致偏向「可见」的那一侧，更安全。

    真正的答案是**用事务**。防线 1 和防线 2 都是「没有事务时的补偿手段」——
    它们是**事后修复**，而事务是**事前预防**。
    """
    write(docroot, "a.md", DOC_A)
    ingest_report = ingest(docroot)
    doc = ingest_report.docs[0]

    store = InMemoryChunkStore()  # 空存储
    manifest_store = InMemoryManifestStore(
        Manifest(
            docs={
                doc.doc_id: ImportedDoc(
                    doc_id=doc.doc_id,
                    path=doc.path,
                    chunk_count=1,
                    ready_at=FIXED_NOW,
                )
            },
            store_id=store.store_id,  # 关键：账本声称自己属于这个块存储
        )
    )

    report = run_import(docroot, store, manifest_store)

    assert not report.manifest_invalidated, "这条测的不是防线 1"
    # 防线 2 抓到了：账本说有的文档，库里其实没有
    assert report.repaired_doc_ids == (doc.doc_id,)
    assert report.plan.count(ImportAction.ADDED) == 1, "被剔出账本 -> 判新增 -> 重建"
    assert report.plan.count(ImportAction.UNCHANGED) == 0, "不能静默跳过"
    assert store.document_count() == 1, "文档真的补回来了"

    # 再跑一次：现在账本和库一致了，应该稳定在「跳过」
    again = run_import(docroot, store, manifest_store)
    assert again.plan.count(ImportAction.UNCHANGED) == 1
    assert again.repaired_doc_ids == ()
    assert store.document_count() == 1


# ===========================================================================
# 八、跨组件：和 ingest / chunking 衔接
# ===========================================================================


def test_import_uses_markdown_heading_by_default(docroot: Path):
    """默认配置用 markdown_heading —— 块应该带上标题路径。"""
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    run_import(docroot, store, InMemoryManifestStore())

    paths = {c.heading_path for c in store.all_chunks()}
    assert any("员工手册" in p for p in paths), f"块没带上标题路径：{paths}"


def test_import_respects_admission_layer(docroot: Path):
    """摄取层的准入规则依然生效：密钥文件不进库。"""
    write(docroot, "手册.md", DOC_A)
    write(docroot, "配置.env", "LLM_API_KEY=sk-abcdefghij1234567890\n")

    store = InMemoryChunkStore()
    report = run_import(docroot, store, InMemoryManifestStore())

    assert report.store_document_count == 1, "只该收下手册"
    assert all("sk-" not in c.content for c in store.all_chunks())


def test_import_of_empty_directory_is_not_an_error(tmp_path: Path):
    empty = tmp_path / "空目录"
    empty.mkdir()

    store = InMemoryChunkStore()
    report = run_import(empty, store, InMemoryManifestStore())

    assert report.store_document_count == 0
    assert report.plan.total == 0


def test_importing_indexing_package_does_not_break_chunking():
    """回归：indexing 层不该修改 chunking 的行为。"""
    import repo_qa.indexing  # noqa: F401

    from repo_qa.chunking.strategies import STRATEGIES

    assert "markdown_heading" in STRATEGIES


# ===========================================================================
# 九、账本与块存储的身份一致性
#
# 这一组是**两个真实 bug 的回归**。共同点：
# 账本和块存储说的不是同一件事，但系统没发现，于是静默出错。
# ===========================================================================


def test_new_store_instance_invalidates_the_stale_manifest(docroot: Path, tmp_path: Path):
    """**Bug 1 回归：账本持久、块存储不持久，会静默丢文档。**

    真实复现过的场景：

    ::

        第 1 次导入（进程 A）
          块  -> 进 InMemoryChunkStore（随进程消失）
          账本 -> 写进 JSON 文件（留在磁盘上）

        进程 A 退出

        第 2 次导入（进程 B，新的空内存存储）
          账本从文件读出来，说「有 1 个文档」
          扫描到同样的文档 -> doc_id 在账本里、路径也一样 -> 判「跳过」
          -> 库是空的，但账本说有 -> 这份文档永远不会被重新导入
          -> 而且不报错

    修法：账本记下它属于哪个块存储（``store_id``），
    加载时对不上就作废账本，触发全量重建。
    """
    write(docroot, "a.md", DOC_A)
    manifest_path = tmp_path / "manifest.json"

    # 进程 A：块进内存，账本落盘
    store_a = InMemoryChunkStore()
    first = run_import(docroot, store_a, JsonManifestStore(manifest_path))
    assert first.plan.count(ImportAction.ADDED) == 1
    assert manifest_path.exists()

    # 进程 B：新的空内存存储 + 从文件读出的旧账本
    store_b = InMemoryChunkStore()
    assert store_b.document_count() == 0, "新进程的块存储是空的"

    second = run_import(docroot, store_b, JsonManifestStore(manifest_path))

    # 关键：不能判成「跳过」
    assert second.manifest_invalidated, "账本应该被作废"
    assert second.plan.count(ImportAction.ADDED) == 1, "必须重新导入"
    assert second.plan.count(ImportAction.UNCHANGED) == 0, "不能静默跳过"
    assert store_b.document_count() == 1, "文档真的进了新库"


def test_manifest_invalidation_carries_a_reason(docroot: Path, tmp_path: Path):
    """账本作废必须报出来 —— 它意味着一次意外的全量 embedding 开销。

    静默发生的话，用户只会看到账单变高，不知道原因。
    """
    write(docroot, "a.md", DOC_A)
    manifest_path = tmp_path / "manifest.json"

    run_import(docroot, InMemoryChunkStore(), JsonManifestStore(manifest_path))
    report = run_import(docroot, InMemoryChunkStore(), JsonManifestStore(manifest_path))

    assert report.manifest_invalidated
    assert report.invalidation_reason
    assert "块存储" in report.invalidation_reason
    assert "账本已作废" in report.summary()


def test_same_store_instance_keeps_the_manifest_valid(docroot: Path):
    """同一个块存储实例内重复导入，账本不该被作废。"""
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore(store_id="stable-store")
    manifest_store = InMemoryManifestStore()

    run_import(docroot, store, manifest_store)
    second = run_import(docroot, store, manifest_store)

    assert not second.manifest_invalidated
    assert second.plan.count(ImportAction.UNCHANGED) == 1


def test_store_id_survives_json_round_trip(tmp_path: Path):
    path = tmp_path / "manifest.json"
    store = JsonManifestStore(path)
    store.save(Manifest(docs={}, store_id="my-store-42"))
    assert store.load().store_id == "my-store-42"


def test_empty_manifest_is_never_treated_as_invalidated(docroot: Path):
    """空账本没有「属于谁」的问题，不该报作废。"""
    write(docroot, "a.md", DOC_A)
    report = run_import(docroot, InMemoryChunkStore(), InMemoryManifestStore())

    assert not report.manifest_invalidated
    assert report.invalidation_reason == ""


def test_in_memory_store_gets_a_fresh_id_by_default():
    """内存存储每次创建都给新 ID —— 因为它的内容确实是全新的。"""
    assert InMemoryChunkStore().store_id != InMemoryChunkStore().store_id


def test_store_id_can_be_pinned_for_reproducible_tests():
    assert InMemoryChunkStore(store_id="fixed").store_id == "fixed"


def test_manifest_written_by_import_carries_the_store_id(docroot: Path):
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()

    run_import(docroot, store, manifest_store)

    assert manifest_store.load().store_id == store.store_id


def test_rename_then_reimport_is_stable(docroot: Path):
    """改名之后再跑一次，应该判「跳过」而不是又改一次名。"""
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore()
    manifest_store = InMemoryManifestStore()

    run_import(docroot, store, manifest_store)
    (docroot / "a.md").rename(docroot / "b.md")

    first = run_import(docroot, store, manifest_store)
    assert first.plan.count(ImportAction.RENAMED) == 1

    second = run_import(docroot, store, manifest_store)
    assert second.plan.count(ImportAction.UNCHANGED) == 1
    assert second.plan.count(ImportAction.RENAMED) == 0
    assert all(c.path == "docs/b.md" for c in store.all_chunks())


# ===========================================================================
# 十、防线 2：和库对账
#
# 防线 1（store_id）只抓「换了一个库」。
# 防线 2 抓「还是同一个库，但内容被改动过」。
# ===========================================================================


def test_reconciliation_detects_document_deleted_from_store(docroot: Path):
    """**防线 2 的核心场景**：同一个库，但库里的某个文档被删掉了。

    什么时候会这样：有人手工删了、上次写块时崩了、存储本身丢了数据。

    这时 ``store_id`` 是匹配的（还是同一个库），防线 1 抓不到。
    账本还说那份文档在 -> 下次导入判「跳过」-> **永远补不回来**。

    不修的话后果很隐蔽：不报错，只是知识库里少了一份文档。
    """
    write(docroot, "a.md", DOC_A)
    write(docroot, "b.md", DOC_B)

    store = InMemoryChunkStore(store_id="same-store")
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)
    assert store.document_count() == 2

    # 模拟人工删除：直接从库里删掉一个文档，store_id 不变
    victim = next(iter(manifest_store.load().docs))
    store.delete_document(victim)
    assert store.document_count() == 1
    assert len(manifest_store.load()) == 2, "账本还说有两个"

    report = run_import(docroot, store, manifest_store)

    assert not report.manifest_invalidated, "store_id 没变，防线 1 不该触发"
    assert report.repaired_doc_ids == (victim,), "防线 2 应该抓到丢的那一个"
    assert store.document_count() == 2, "文档补回来了"
    assert len(manifest_store.load()) == 2


def test_reconciliation_only_repairs_the_missing_ones(docroot: Path):
    """对账只剔除丢掉的，不该影响其他文档 —— 其他文档应该继续判「跳过」。"""
    for index in range(5):
        write(docroot, f"d{index}.md", f"# 文档 {index}\n\n## 内容\n\n这是第 {index} 份文档的正文内容。\n")

    store = InMemoryChunkStore(store_id="same-store")
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)

    victim = sorted(manifest_store.load().docs)[0]
    store.delete_document(victim)

    report = run_import(docroot, store, manifest_store)

    assert report.repaired_doc_ids == (victim,)
    assert report.plan.count(ImportAction.ADDED) == 1, "只有丢掉的那个要重建"
    assert report.plan.count(ImportAction.UNCHANGED) == 4, "其他四个照旧跳过"
    assert report.embedded_document_count == 1, "只花一个文档的钱"


def test_no_reconciliation_when_everything_matches(docroot: Path):
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore(store_id="same-store")
    manifest_store = InMemoryManifestStore()

    run_import(docroot, store, manifest_store)
    report = run_import(docroot, store, manifest_store)

    assert report.repaired_doc_ids == ()
    assert "账本修复" not in report.summary()


def test_reconciliation_is_reported_in_summary(docroot: Path):
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore(store_id="same-store")
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)

    victim = next(iter(manifest_store.load().docs))
    store.delete_document(victim)

    report = run_import(docroot, store, manifest_store)
    assert "账本修复 1 条" in report.summary()


def test_orphan_documents_are_removed(docroot: Path):
    """**孤儿块清理**：库里有、账本不认的文档，要被删掉。

    什么时候会出现：上次写块成功、写账本时崩溃（块留下了，账本没记上），
    而那份文档后来被删了 -> 它永远不会被判「新增」覆盖掉 -> 孤儿块永远留着。

    为什么必须清：孤儿块会**污染检索结果** ——
    用户可能搜到一份已经不存在的文档的内容。
    """
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore(store_id="same-store")
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)

    # 手工往库里塞一个账本不认的文档（模拟「写了块没写账本」）
    from repo_qa.chunking import Chunk

    store.put_document(
        "orphan-doc-id",
        (Chunk(path="docs/幽灵.md", start_line=1, end_line=1, content="这是一份孤儿块"),),
    )
    assert store.document_count() == 2

    report = run_import(docroot, store, manifest_store)

    assert report.orphans_removed == 1
    assert "orphan-doc-id" not in store.doc_ids()
    assert store.document_count() == 1
    assert all("幽灵" not in c.content for c in store.all_chunks())


def test_orphan_cleanup_does_not_touch_valid_documents(docroot: Path):
    """孤儿清理不能误伤正常文档。"""
    write(docroot, "a.md", DOC_A)
    write(docroot, "b.md", DOC_B)
    store = InMemoryChunkStore(store_id="same-store")
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)

    report = run_import(docroot, store, manifest_store)

    assert report.orphans_removed == 0
    assert store.document_count() == 2


def test_orphan_removal_is_reported_in_summary(docroot: Path):
    write(docroot, "a.md", DOC_A)
    store = InMemoryChunkStore(store_id="same-store")
    manifest_store = InMemoryManifestStore()
    run_import(docroot, store, manifest_store)

    from repo_qa.chunking import Chunk

    store.put_document(
        "ghost", (Chunk(path="docs/g.md", start_line=1, end_line=1, content="孤儿内容"),)
    )
    report = run_import(docroot, store, manifest_store)

    assert "清理孤儿文档 1 个" in report.summary()


def test_invariant_store_matches_manifest_after_import(docroot: Path):
    """**导入结束后的不变量**：库里的 doc_id 集合 == 新账本的 doc_id 集合。

    两道防线合起来保证这一条。这个不变量是「库和账本一致」的可测形式。
    """
    write(docroot, "a.md", DOC_A)
    write(docroot, "b.md", DOC_B)
    write(docroot, "c.md", DOC_C)

    store = InMemoryChunkStore(store_id="same-store")
    manifest_store = InMemoryManifestStore()

    # 造出各种不一致，再导入
    run_import(docroot, store, manifest_store)
    victim = sorted(manifest_store.load().docs)[0]
    store.delete_document(victim)  # 账本有、库里没有

    from repo_qa.chunking import Chunk

    store.put_document(
        "ghost", (Chunk(path="docs/g.md", start_line=1, end_line=1, content="孤儿内容"),)
    )  # 库里有、账本没有

    run_import(docroot, store, manifest_store)

    assert set(store.doc_ids()) == set(manifest_store.load().docs), (
        "导入结束后，库和账本必须完全一致"
    )
