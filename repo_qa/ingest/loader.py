"""读取层 —— 把磁盘上的文件变成一个可切块的文档对象。

这一步看着简单（打开文件、读出来），实际埋着三个坑：

坑 1：编码
---------
``Path.read_text()`` 默认用系统编码。在中文 Windows 上那是 GBK，
在 Linux 上是 UTF-8。同一条命令在两个平台结果不同，这是最容易踩的坑。

本项目统一强制 UTF-8，并且**试都不试 GBK**——因为本项目的语料是
自己写的 Markdown（见 docs/），统一 UTF-8 是可控的。
读到 UTF-8 解不开的字节，就当读失败处理（见下）。

什么时候该考虑多编码试探：接入**来源不可控**的文档时（用户上传、老系统导出）。
那时顺序一般是 UTF-8 → GBK → latin-1 兜底，且必须记录用了哪个编码——
因为同一个文件用不同编码解出来是**不同的文本**，切块结果也不同。

坑 2：换行符
-----------
Windows 存文件是 ``\\r\\n``（CRLF），Linux 是 ``\\n``（LF）。
肉眼看着一模一样，字节数差一倍。而 hash 是**对字节算的**，
所以同一份内容在两个系统上会算出两个完全不同的 doc_id。

后果是「假更新」：同事把同一份文档从 Windows 传到 Linux，
你的系统认为「来了份新文档」，于是重新切块、重新 embedding、重新花钱。
**一个字都没改。**

所以本模块先做**规范化**：``\\r\\n`` 统一成 ``\\n``，再去首尾空白，
然后才算 hash。这样「内容变没变」这个判断才是干净的。

代价：如果有文件**唯一的变化**就是换行符，系统会认为它没变。
这在企业文档场景里可以接受——没有人会专门改换行符然后说「我更新了文档」。

坑 3：doc_id 该算在哪份文本上
---------------------------
答案：算在**规范化之后、且和最终存进知识库的文本完全一致**的那份文本上。
如果一处规范化了、另一处没规范化，就会出现「同一个 doc_id 对应两份不同文本」
这种自相矛盾的状态。

所以本模块的顺序是固定的::

    原始字节 -> 解码(UTF-8) -> 规范化换行 -> 去首尾空白 -> 得到 text
                                                            |
                                        doc_id = sha256(text) <-+

**text 和 doc_id 来自同一个字符串**，这个不变量必须保持。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .models import IngestedDoc

# doc_id 取 sha256 前 16 个十六进制字符（= 64 bit）。
# 为什么不全用 64 个字符：文档级去重不需要密码学强度，
# 16 位在几万份文档规模下碰撞概率可以忽略，而短 ID 在日志和调试时好读得多。
DOC_ID_LENGTH = 16


def normalize_text(raw: str) -> str:
    """把文本规范化成「跨平台一致」的形状。

    做两件事：

    1. 换行符统一成 ``\\n``——消掉 Windows/Linux 差异，避免假更新
    2. 去掉首尾空白——避免「文件末尾多一个空行」被当成内容变化
    """
    return raw.replace("\r\n", "\n").replace("\r", "\n").strip()


def compute_doc_id(text: str) -> str:
    """对规范化后的文本算内容指纹。

    输入必须是 ``normalize_text`` 的输出，不要传原始文本——
    否则 CRLF 差异会漏进来，同一个内容算出两个 ID。
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:DOC_ID_LENGTH]


def load_document(path: Path, *, display_path: str | None = None) -> IngestedDoc | None:
    """读取一个文件，成功返回 ``IngestedDoc``，失败返回 ``None``。

    为什么失败返回 ``None`` 而不是抛异常
    ------------------------------------
    摄取是**批量**操作。一份目录里 50 个文件，其中 1 个编码坏了，
    如果直接抛异常，另外 49 个都白扫了。

    真实系统的要求是：**坏文件不能拖垮整批**。所以这里吞掉异常，
    由调用方（``pipeline.ingest``）记录它为什么坏。

    为什么不用 ``path.read_text(encoding="utf-8")`` 直接读
    ------------------------------------------------------
    因为它抛的是 ``UnicodeDecodeError``，是 ``ValueError`` 的子类，
    和「文件不存在」「权限不足」这类 ``OSError`` 不是一个体系。
    统一捕获 ``Exception`` 更省事，但会掩盖真正的编程错误（比如拼错属性名）。

    这里选择捕获 ``(OSError, UnicodeDecodeError)`` 两类——
    这两类才是「环境问题」，其余异常应当继续向上抛，让人看到。
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    text = normalize_text(raw)
    if not text:
        # 全是空白字符：编码能解开，但没有任何内容可切。
        # 归到「读取失败」而不是「准入拒绝」，因为准入层只看得到字节数，
        # 看不到「前面 1KB 全是空格」这种情况。
        return None

    return IngestedDoc(
        path=display_path if display_path is not None else str(path),
        doc_id=compute_doc_id(text),
        text=text,
        line_count=len(text.splitlines()),
    )
