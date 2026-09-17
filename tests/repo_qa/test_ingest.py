"""摄取层测试 —— 准入、读取、编排三条线的正反例。

覆盖三类：

1. **正常路径**：能扫到、能读、doc_id 稳定、行数对
2. **准入拦截**：密钥文件、改名绕过、空文件、超大文件、忽略目录
3. **边界与回归**：
   - 换行符规范化（CRLF/LF 算出同一个 doc_id）
   - 遍历可重复（不返回一次性迭代器）
   - 坏文件不拖垮整批
   - 摄取层不 import chunking（依赖方向）

全部离线：不访问网络、不读真实 docs/（用 tmp_path 造临时语料）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_qa.ingest import (
    AdmissionConfig,
    compute_doc_id,
    ingest,
    iter_document_paths,
    normalize_text,
)


# ---------- 夹具：往临时目录里造语料 ----------

@pytest.fixture
def docroot(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    root.mkdir()
    return root


def write(root: Path, name: str, content: str, *, encoding: str = "utf-8") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)
    return path


# ---------- 一、正常路径 ----------


def test_ingests_plain_markdown(docroot: Path):
    write(docroot, "手册.md", "# 标题\n\n正文内容，够长。\n")
    report = ingest(docroot)

    assert report.doc_count == 1
    assert report.rejected == ()
    assert report.total_lines == 3
    doc = report.docs[0]
    assert doc.path == "docs/手册.md"
    assert len(doc.doc_id) == 16


def test_ingests_nested_subdirectories(docroot: Path):
    write(docroot, "制度/差旅.md", "# 差旅\n\n报销流程说明。\n")
    write(docroot, "制度/人事/考勤.md", "# 考勤\n\n打卡规则说明。\n")
    report = ingest(docroot)

    assert report.doc_count == 2
    assert {d.path for d in report.docs} == {
        "docs/制度/差旅.md",
        "docs/制度/人事/考勤.md",
    }


def test_markdown_extension_is_accepted_too(docroot: Path):
    """``.markdown`` 和 ``.md`` 是两个不同的字符串，但都应在收取范围。

    这条钉住一个真实认知错误：「.markdown 不就是 .md？」——不是。
    """
    write(docroot, "手册.md", "# A\n\n内容甲。\n")
    write(docroot, "说明.markdown", "# B\n\n内容乙。\n")
    report = ingest(docroot)

    assert report.doc_count == 2


def test_missing_root_is_not_an_error(tmp_path: Path):
    """docs/ 不存在是正常初始状态，不该崩。"""
    report = ingest(tmp_path / "不存在")

    assert report.doc_count == 0
    assert report.scanned == 0
    assert report.rejected == ()


# ---------- 二、准入拦截 ----------


def test_env_file_is_rejected_by_filename_rule(docroot: Path):
    """密钥文件必须被**拒收并留痕**，不能被当成「不相关」静默跳过。

    这是一个真实的设计陷阱：如果先判扩展名，.env 会归入 skipped，
    账单上看不到任何记录。安全上结果碰巧一样，但过程不可审计。
    """
    write(docroot, "环境配置.env", "LLM_API_KEY=sk-abcdefghij1234567890\n")
    write(docroot, "手册.md", "# 标题\n\n正常文档内容。\n")
    report = ingest(docroot)

    assert report.doc_count == 1, "只该收下那份 markdown"
    rejected = [r for r in report.rejected if r.path.endswith(".env")]
    assert len(rejected) == 1
    assert rejected[0].stage == "admission"
    assert "密钥" in rejected[0].reason or "证书" in rejected[0].reason


def test_secret_content_in_normal_named_file_is_rejected(docroot: Path):
    """改名绕过的兜底：文件名完全正常，内容是 API Key —— 也得挡。

    这条覆盖的是「有人把 .env 改名成 notes.md」。扩展名检查拦不住，
    只有读完内容才能发现。
    """
    write(docroot, "运维速查.md", "# 速查\n\napi_key = sk-live9876543210zyxwvutsrq\n")
    write(docroot, "手册.md", "# 标题\n\n正常文档内容。\n")
    report = ingest(docroot)

    assert report.doc_count == 1
    rejected = [r for r in report.rejected if "速查" in r.path]
    assert len(rejected) == 1
    assert rejected[0].stage == "admission"
    assert "密钥" in rejected[0].reason or "Key" in rejected[0].reason


def test_private_key_block_is_rejected(docroot: Path):
    write(docroot, "证书说明.md", "# 说明\n\n-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n")
    report = ingest(docroot)

    assert report.doc_count == 0
    assert len(report.rejected) == 1


def test_empty_file_is_rejected(docroot: Path):
    write(docroot, "占位.md", "")
    report = ingest(docroot)

    assert report.doc_count == 0
    assert report.rejected[0].stage == "admission"
    assert "空" in report.rejected[0].reason


def test_whitespace_only_file_fails_at_loading(docroot: Path):
    """只有空白字符的文件：字节数不为 0，准入放行，但读取后没内容。

    它归到 loading 而不是 admission —— 因为准入层只看得到字节数，
    看不到「前面 1KB 全是空格」。
    """
    write(docroot, "空白.md", "   \n\n   \t  \n")
    report = ingest(docroot)

    assert report.doc_count == 0
    assert report.rejected[0].stage == "loading"


def test_oversized_file_is_rejected(docroot: Path):
    write(docroot, "巨大.md", "# 标题\n\n" + ("内容。" * 500))
    config = AdmissionConfig(max_bytes=100)
    report = ingest(docroot, config=config)

    assert report.doc_count == 0
    assert "超过上限" in report.rejected[0].reason


def test_ignored_directories_are_skipped(docroot: Path):
    """`.git` / `.venv` 里的文件不该被扫到——它们不是文档，是工具链产物。"""
    write(docroot, ".git/配置.md", "# 这是 git 内部文件，不该被收\n")
    write(docroot, "node_modules/包说明.md", "# 依赖包的说明，不该被收\n")
    write(docroot, "手册.md", "# 标题\n\n正常内容。\n")
    report = ingest(docroot)

    assert report.doc_count == 1
    assert report.docs[0].path == "docs/手册.md"


def test_non_markdown_file_counts_as_skipped_not_rejected(docroot: Path):
    """扩展名不匹配 = 不相关，不是有问题。

    分清楚很重要：混进 rejected 会让账单充满噪音，真正的故障被淹掉。
    """
    write(docroot, "说明.txt", "这是一份纯文本。\n")
    write(docroot, "手册.md", "# 标题\n\n正常内容。\n")
    report = ingest(docroot)

    assert report.doc_count == 1
    assert report.skipped == 1
    assert report.rejected == ()


# ---------- 三、边界与回归 ----------


def test_crlf_and_lf_produce_the_same_doc_id():
    """同一个内容，Windows 存的（CRLF）和 Linux 存的（LF）必须算出同一个 doc_id。

    否则同事换个系统传文件，你的系统就认为「来了份新文档」，
    重新切块、重新 embedding、重新花钱——而内容一个字都没改。这就是假更新。
    """
    lf = "第一行\n第二行\n"
    crlf = "第一行\r\n第二行\r\n"

    assert lf != crlf, "两种写法在字符串层面确实不同"
    assert compute_doc_id(normalize_text(lf)) == compute_doc_id(normalize_text(crlf))


def test_normalize_unifies_all_line_endings():
    assert normalize_text("a\r\nb") == "a\nb"
    assert normalize_text("a\rb") == "a\nb", "老 Mac 的单 \\r 也要处理"
    assert normalize_text("a\nb") == "a\nb"


def test_normalize_strips_leading_and_trailing_whitespace():
    """文件末尾多一个空行不该被当成内容变化。"""
    assert normalize_text("\n\n内容\n\n") == "内容"


def test_doc_id_changes_when_content_changes():
    assert compute_doc_id("原来是一千元") != compute_doc_id("原来是一万元")


def test_doc_id_is_stable_for_same_content():
    assert compute_doc_id("固定内容") == compute_doc_id("固定内容")


def test_same_content_in_two_paths_is_deduplicated(docroot: Path):
    """两份文件内容完全相同：只收第一次，第二次记进账单。

    这回答的是「同一个内容出现在多个路径」——比如某文档被复制了一份。
    只收一份能省下重复的 embedding 成本。
    """
    write(docroot, "甲.md", "# 同一份内容\n\n正文。\n")
    write(docroot, "乙.md", "# 同一份内容\n\n正文。\n")
    report = ingest(docroot)

    assert report.doc_count == 1
    assert len(report.rejected) == 1
    assert "完全相同" in report.rejected[0].reason


def test_paths_are_returned_as_a_resuable_list(docroot: Path):
    """``iter_document_paths`` 返回的真实 ``list``，不是一次性迭代器。

    背景：``Path.glob()`` 返回迭代器，**只能遍历一遍**，第二次拿到 0 个
    而且不报错。这是「假绿」的典型形态——程序不崩，只是悄悄少读了数据。
    本测试钉住「对外承诺的是 list」这个契约。
    """
    write(docroot, "甲.md", "# 甲\n\n内容。\n")
    write(docroot, "乙.md", "# 乙\n\n内容。\n")

    paths = iter_document_paths(docroot, AdmissionConfig())

    assert isinstance(paths, list), "必须是 list，不能是把迭代器直接交出去"
    assert len(paths) == 2
    assert len(paths) == 2, "遍历两遍结果必须一致"


def test_result_is_deterministic_across_runs(docroot: Path):
    """同一份目录跑两次，账单顺序一致——否则比对两次结果会误报差异。"""
    write(docroot, "丙.md", "# 丙\n\n内容。\n")
    write(docroot, "甲.md", "# 甲\n\n内容。\n")
    write(docroot, "乙.md", "# 乙\n\n内容。\n")

    first = [d.path for d in ingest(docroot).docs]
    second = [d.path for d in ingest(docroot).docs]

    assert first == second


def test_broken_encoding_does_not_break_the_batch(docroot: Path):
    """一个编码坏掉的文件，不能拖垮整批摄取。

    真实系统里 50 个文件坏 1 个，如果直接抛异常，另外 49 个都白扫了。
    """
    write(docroot, "好的.md", "# 好\n\n内容正常。\n")
    # 写一个不是 UTF-8 的字节序列
    (docroot / "坏的.md").write_bytes(b"\xff\xfe\x00\x00\x80\x81\x82")

    report = ingest(docroot)

    assert report.doc_count == 1, "好的那份必须被收下"
    assert report.docs[0].path == "docs/好的.md"
    assert len(report.rejected) == 1
    assert report.rejected[0].stage == "loading"


def test_rejected_paths_are_relative_to_display_root(docroot: Path):
    """账单里的路径必须是人能看懂的相对路径，不是绝对路径。

    绝对路径进了向量库会跟着每次算一遍，又长又丑。
    注意：这只影响 path 字段，**不影响 doc_id**——doc_id 只跟内容有关。
    """
    write(docroot, "手册.md", "# 标题\n\n正常内容。\n")
    report = ingest(docroot, display_root="docs")

    assert report.docs[0].path == "docs/手册.md"
    assert not report.docs[0].path.startswith("E:")


def test_doc_id_does_not_depend_on_path(docroot: Path):
    """同一份内容换个文件名，doc_id 必须不变——这是「改名不重做」的根据。"""
    content = "# 同一份内容\n\n正文。\n"
    write(docroot, "原名.md", content)
    write(docroot, "改名后.md", content)

    doc_ids = {compute_doc_id(normalize_text(content))}
    assert len(doc_ids) == 1

    report = ingest(docroot)
    # 路径不同、内容相同 -> 去重后只收一份，且它的 doc_id 就是内容指纹
    assert report.docs[0].doc_id == doc_ids.pop()


def test_large_document_with_many_headings(docroot: Path):
    """大文档（含多个标题层级）能正常摄取，行数统计准确。

    行数用**同一个算式**算出来，不手写数字——手数行数是本项目
    踩过两次的真实坑（漏掉空行、把标题数数错）。
    """
    lines = []
    for i in range(1, 21):
        lines.append(f"## 第 {i} 节")
        lines.append("")
        lines.append(f"这是第 {i} 节的正文内容。")
        lines.append("")
    content = "\n".join(lines)
    write(docroot, "长文档.md", content)

    report = ingest(docroot)

    expected_lines = len(content.strip().splitlines())
    assert report.doc_count == 1
    assert report.docs[0].line_count == expected_lines


def test_report_summary_contains_real_numbers(docroot: Path):
    """摘要里的数字必须来自真实统计，不能写死。"""
    content = "# 甲\n\n三行\n内容\n这里\n"
    write(docroot, "甲.md", content)
    report = ingest(docroot)

    expected = len(content.strip().splitlines())
    assert report.doc_count == 1
    assert report.total_lines == expected
    assert f"共 {expected} 行" in report.summary()


# ---------- 四、依赖方向 ----------


def test_ingest_package_does_not_import_chunking():
    """摄取层不该 import chunking —— 依赖方向是单向的。

    判据：摄取不需要知道 ``Chunk`` 长什么样。如果它 import 了切块，
    将来换切法就要改摄取层，两层耦合。

    调用方同时依赖两者，而两者互不依赖——这是 package-by-feature 的关键。
    注意：**上一层的 `repo_qa/__init__.py` 本来就应该同时导出两者**，
    这一条只约束 `repo_qa/ingest/` 包**内部**的文件。

    实现注意 1：**用 AST 解析真实的 import 语句，不要字符串匹配**。
    第一版用了 ``"import chunking" not in source``，结果在模块 docstring 的
    自然语言里匹配到了（docstring 里写着「本包不 import chunking」这句话）——
    测试把一句**说明**当成了**代码**。这是典型的自制测试工具缺陷：
    检查方式本身的严谨性，不能低于被检查对象的严谨性。

    实现注意 2：**用 importlib 按模块路径取包，不要 `import repo_qa.ingest as pkg`**。
    因为 `repo_qa/__init__.py` 里写了 `from .ingest import ingest`，
    于是 `repo_qa.ingest` 这个**属性**被同名函数覆盖了，
    `import repo_qa.ingest as pkg` 拿到的是**函数**而不是**包**。
    这是 Python 里「模块属性被同名对象遮蔽」的经典陷阱，
    用 `importlib.import_module("repo_qa.ingest")` 可以绕开属性查找。
    """
    import ast
    import importlib

    pkg = importlib.import_module("repo_qa.ingest")
    names = ("models.py", "admission.py", "loader.py", "pipeline.py", "__init__.py")
    package_dir = Path(pkg.__file__).parent

    for name in names:
        path = package_dir / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                # level=2 表示 `from ..xxx`，module 就是 xxx
                prefix = "." * (node.level or 0)
                imported.append(f"{prefix}{node.module or ''}")

        for target in imported:
            assert "chunking" not in target, (
                f"{name} 用 AST 解析出真实 import 了 {target!r}，摄取层不该依赖 chunking"
            )
