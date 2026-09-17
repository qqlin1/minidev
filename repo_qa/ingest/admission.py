"""准入层 —— 决定「这个文件该不该进知识库」。

它和 ``chunking/filters.py`` 的区别（最容易搞混的地方）
--------------------------------------------------------
两个都叫「过滤」，但挡的东西完全不同，所以必须在不同的地方：

+------------------+------------------------+--------------------------+
|                  | 准入层（本模块）        | 块级过滤 filters.py      |
+==================+========================+==========================+
| 过滤对象         | 整个**文件**            | 切出来的**块**           |
| 时机             | 摄取之后、切块之前      | 切块之后、入库之前       |
| 典型拦截         | .env 密钥、二进制、     | 页码、空块、太短的块、   |
|                  | 超大文件、空文件        | 重复块                   |
| 回答的问题       | 「这文件该进库吗」      | 「这块有信息量吗」       |
+------------------+------------------------+--------------------------+

**为什么块级过滤挡不住 .env**：``filters.py`` 的四条规则是
``no_text`` / ``page_furniture`` / ``too_short`` / ``duplicate``。
一个 ``.env`` 文件的内容是这样的::

    LLM_API_KEY=sk-abc123def456
    LLM_BASE_URL=https://api.deepseek.com

它有文字字符（不是纯符号）、长度超阈值（不短）、只出现一次（不重复）——
**四条规则一条都拦不住**。它会顺利切块、顺利进向量库、顺利被送去
外部 embedding API。**密钥就是这么泄漏的。**

所以准入层不是「顺手加的一道"，它是**安全边界**。

规则契约
--------
每条规则实现 ``check(entry) -> str | None``：

- 返回 ``None``：放行，交给下一条规则
- 返回字符串：拒收，字符串就是拒收原因（会写进账单给人看）

外加两个「跳过」判断（``is_candidate``），它们不算拒收：
扩展名不匹配的文件是**不相关**，不是**有问题**。混淆这两者会让账单
充满噪音，真正的故障被淹掉。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


# 收哪些扩展名。注意 ".md" 和 ".markdown" 是两个不同的字符串——
# 计算机比对扩展名是逐字符比，不会「举一反三」。
DEFAULT_SUFFIXES: tuple[str, ...] = (".md", ".markdown")

# 明确的拒收名单：这类文件即使被改名成 .md 也不收。
# 这是「按内容判断会不够快，就先按名字挡一道」的粗筛，
# 真正的兜底是读取后的内容检查（见 PRIVACY_PATTERNS）。
_SECRET_SUFFIXES: frozenset[str] = frozenset(
    {".env", ".key", ".pem", ".p12", ".pfx", ".crt", ".der", ".kdbx"}
)
_SECRET_NAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\.env(\..+)?$"),          # .env / .env.local / .env.production
    re.compile(r"credentials?.*", re.I),     # credential.json / credentials.yaml
    re.compile(r"secrets?.*", re.I),         # secret.txt / secrets.yml
    re.compile(r".*_rsa$", re.I),            # id_rsa
    re.compile(r".*\.(key|pem|crt|p12|pfx)$", re.I),
)

# 即使扩展名对得上，内容里出现这些形状，也要拒收。
# 这是「改名绕过」的兜底：有人把 .env 改名成 notes.md，扩展名检查拦不住，
# 但内容里的 "API_KEY=" 拦得住。
_PRIVACY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "疑似 API Key（sk- 开头）"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "疑似 AWS Access Key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "疑似私钥内容"),
    (re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+"), "疑似明文密码"),
    (re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"), "疑似密钥赋值"),
)

# 扫描时忽略的目录：这些目录里的东西不是「文档」，是工具链产物。
_IGNORED_DIR_NAMES: frozenset[str] = frozenset(
    {".git", ".venv", "venv", "node_modules", "__pycache__", ".idea", ".mypy_cache", ".pytest_cache"}
)


@dataclass(frozen=True, slots=True)
class AdmissionConfig:
    """准入层的配置。每个字段对应一条可开关的规则。"""

    suffixes: tuple[str, ...] = DEFAULT_SUFFIXES
    max_bytes: int = 2 * 1024 * 1024  # 单文件上限 2MB；超了通常是拼接文件或数据导出
    min_bytes: int = 1  # 0 字节文件切不出任何东西
    block_secret_filenames: bool = True
    scan_content_for_secrets: bool = True
    ignored_dir_names: frozenset[str] = _IGNORED_DIR_NAMES

    def __post_init__(self) -> None:
        if self.max_bytes < 1:
            raise ValueError("max_bytes must be at least 1")
        if self.min_bytes < 0:
            raise ValueError("min_bytes must not be negative")
        if self.min_bytes > self.max_bytes:
            raise ValueError("min_bytes must not exceed max_bytes")


class AdmissionRule(Protocol):
    """一条准入规则的契约。只读文件的元信息，不读内容（内容检查单独一步）。"""

    name: str

    def check(self, path: Path, size: int) -> str | None:
        ...


class SecretFilenameRule:
    """文件名看着就是密钥 —— 直接挡，连读都不读。"""

    name = "secret_filename"

    def check(self, path: Path, size: int) -> str | None:
        if path.suffix.lower() in _SECRET_SUFFIXES:
            return f"文件名后缀 {path.suffix} 属于密钥/证书类，不进知识库"
        name = path.name
        for pattern in _SECRET_NAME_PATTERNS:
            if pattern.fullmatch(name) or pattern.match(name):
                return f"文件名 {name} 命中密钥文件命名规则"
        return None


class EmptyFileRule:
    """0 字节文件切不出任何东西，收录它只会让账单多一行噪音。"""

    name = "empty_file"

    def check(self, path: Path, size: int) -> str | None:
        if size == 0:
            return "文件是空的（0 字节），切不出任何块"
        return None


class TooLargeRule:
    """超大文件会切出海量块，embedding 成本失控，且通常是误收录。"""

    name = "too_large"

    def __init__(self, *, max_bytes: int) -> None:
        self.max_bytes = max_bytes

    def check(self, path: Path, size: int) -> str | None:
        if size > self.max_bytes:
            mb = self.max_bytes / 1024 / 1024
            return f"文件 {size / 1024 / 1024:.1f}MB 超过上限 {mb:.1f}MB"
        return None


def is_candidate(path: Path, config: AdmissionConfig) -> bool:
    """这个文件的扩展名在收取范围内吗？

    这不是「拒收」，是「不相关」。分清楚很重要：
    拒收意味着有问题、要记进账单；不相关意味着只是没被选中、不必报警。
    """
    return path.suffix.lower() in config.suffixes


def should_descend(path: Path, config: AdmissionConfig) -> bool:
    """扫描时要不要进入这个目录？"""
    return path.name not in config.ignored_dir_names and not path.name.startswith(".")


def check_admission(path: Path, config: AdmissionConfig) -> str | None:
    """按顺序跑完所有准入规则，返回第一条拒收理由；全过则返回 None。

    顺序是刻意排的，从「最确定」到「最需要计算」：

    1. 文件名像密钥 —— 一条字符串比对，最便宜，先跑
    2. 空文件 —— 一次 stat，也很便宜
    3. 超大文件 —— 一次 stat

    先跑便宜的，能在坏文件很多时省下大量无谓的读取。
    """
    try:
        size = path.stat().st_size
    except OSError as exc:
        # 连 stat 都失败（权限、路径过长、符号链接断开），
        # 这属于「读取阶段」的失败，不在这里报。
        return f"无法读取文件元信息：{exc.__class__.__name__}"

    rules: list[AdmissionRule] = [SecretFilenameRule(), EmptyFileRule()]
    rules.append(TooLargeRule(max_bytes=config.max_bytes))

    for rule in rules:
        reason = rule.check(path, size)
        if reason is not None:
            return reason
    return None


def scan_content_for_secrets(text: str) -> str | None:
    """改名绕过检查：扩展名是 .md，内容却是密钥 —— 也得挡。

    为什么单独一步而不是塞进 check_admission：
    内容检查需要先把文件读出来，成本高得多。所以它排在准入的最后，
    只对「名字过关」的文件执行。
    """
    for pattern, label in _PRIVACY_PATTERNS:
        if pattern.search(text):
            return f"文件内容{label}，不进知识库"
    return None
