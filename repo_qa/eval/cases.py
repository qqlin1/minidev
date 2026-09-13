"""Chunking 场景库 — 从 Repo QA 产品问题反推的固定评测集。

枚举方法（按轴交叉，不靠拍脑袋）：

  轴 A  文件形态：python 代码 / markdown 文档 / 配置式文本
  轴 B  用户问题类型：符号定位 / 行为理解 / 配置取值 / 文档要点
  轴 C  已知失败模式：拦腰切断符号 / 空块污染 / 引用不可定位 / 切得过碎
  轴 D  边界：空文件 / 纯空白 / 单行 / 非法配置（配置在 pipeline 测）

每条场景必须能回答：
  「用户问了什么 → 答案应落在哪个 path 的哪一段行号 → 一个合格 chunk 是否覆盖它」

覆盖判定：存在某个 chunk，其 [start_line, end_line] 包含期望区间。
这是「chunking 层」的上限：切不开，后面 embedding 再好也救不回。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScenarioCase:
    """一条固定评测。期望的是「行号区间被某个 chunk 完整覆盖」。"""

    id: str
    question: str
    path: str
    source_text: str
    expect_start_line: int
    expect_end_line: int
    family: str  # code_symbol | code_config | doc_section | edge
    failure_mode: str  # 这条 case 钉死的失败模式说明


# ---------------------------------------------------------------------------
# 夹具源码：故意做成「会在 max_lines=3 的固定行数下被切坏」的形状
# ---------------------------------------------------------------------------

PYTHON_SERVICE = '''\
import os

DEFAULT_TIMEOUT = 30


def load_config():
    """Load config from env."""
    return {
        "timeout": int(os.getenv("TIMEOUT", DEFAULT_TIMEOUT)),
        "debug": os.getenv("DEBUG") == "1",
    }


def connect_db(url: str) -> str:
    # connection details intentionally long so fixed-line chunking often
    # splits the signature from the body when max_lines is small
    if not url:
        raise ValueError("url required")
    host = url.split("/")[0]
    return host


class App:
    def run(self) -> str:
        return "ok"
'''

MARKDOWN_GUIDE = '''\
# Chunking 指南

## 为什么不是「一个函数」

Chunking 由四层组成：Schema、Strategy、Config、Quality Gate。

## 代码怎么切

Python 优先按 def/class 符号切，避免函数签名和函数体分家。

## 配置示例

max_lines 控制固定行数基线；AST 策略通常不依赖它。
'''

CONFIG_INI = """\
[llm]
base_url = https://api.deepseek.com
model = deepseek-chat
temperature = 0.2

[agent]
max_steps = 10
"""


# ---------------------------------------------------------------------------
# 场景定义
# ---------------------------------------------------------------------------

ALL_SCENARIOS: tuple[ScenarioCase, ...] = (
    # —— 代码：符号定位（AST 应稳赢，固定行数在 max_lines=3 时会挂） ——
    ScenarioCase(
        id="code_load_config_symbol",
        question="load_config 在哪定义？完整函数体是什么？",
        path="service.py",
        source_text=PYTHON_SERVICE,
        # def load_config(): 到 return 块结束（含 docstring）—— 1-based
        expect_start_line=6,
        expect_end_line=11,
        family="code_symbol",
        failure_mode="固定行数把 def 签名和 body 切开，检索只能命中半截函数",
    ),
    ScenarioCase(
        id="code_connect_db_symbol",
        question="connect_db 的入参校验逻辑在哪？",
        path="service.py",
        source_text=PYTHON_SERVICE,
        expect_start_line=14,
        expect_end_line=20,
        family="code_symbol",
        failure_mode="同上：签名在 A 块、raise 在 B 块，单 chunk 无法回答「怎么校验」",
    ),
    ScenarioCase(
        id="code_app_class_run",
        question="App.run 返回什么？",
        path="service.py",
        source_text=PYTHON_SERVICE,
        expect_start_line=23,
        expect_end_line=25,
        family="code_symbol",
        failure_mode="class 头与方法体分离时，问「类上有什么方法」会漏",
    ),
    # —— 代码：配置取值（固定行数碰巧也能中，作对照） ——
    ScenarioCase(
        id="code_default_timeout_const",
        question="DEFAULT_TIMEOUT 默认是多少？",
        path="service.py",
        source_text=PYTHON_SERVICE,
        expect_start_line=3,
        expect_end_line=3,
        family="code_config",
        failure_mode="若整文件只切成一大块，embedding 语义被稀释；过碎则引用噪声大",
    ),
    # —— 文档：章节完整性 ——
    ScenarioCase(
        id="doc_four_layers",
        question="Chunking 为什么不是一个函数？四层是什么？",
        path="guide.md",
        source_text=MARKDOWN_GUIDE,
        # 标题行 + 空行 + 正文：必须同块，否则「关键词+答案」无法一起检索
        expect_start_line=3,
        expect_end_line=5,
        family="doc_section",
        failure_mode="标题「为什么不是」与正文分离后，问题里的关键词无法同块命中",
    ),
    ScenarioCase(
        id="doc_code_guidance",
        question="代码应该怎么切？",
        path="guide.md",
        source_text=MARKDOWN_GUIDE,
        expect_start_line=7,
        expect_end_line=9,
        family="doc_section",
        failure_mode="跨标题粘连：上一节尾巴和下一节标题进同一 chunk，检索答非所问",
    ),
    # —— 配置文件：短文件应整体可引用 ——
    ScenarioCase(
        id="config_base_url",
        question="LLM base_url 配的是什么？",
        path="app.ini",
        source_text=CONFIG_INI,
        expect_start_line=2,
        expect_end_line=2,
        family="code_config",
        failure_mode="配置被切开后，[llm] section 名不在同一 chunk，上下文丢失",
    ),
    ScenarioCase(
        id="config_max_steps",
        question="agent max_steps 是多少？",
        path="app.ini",
        source_text=CONFIG_INI,
        expect_start_line=7,
        expect_end_line=7,
        family="code_config",
        failure_mode="section 头与 key 分离，值能命中但「属于哪个 section」说不清",
    ),
)


def scenarios_by_family(family: str) -> tuple[ScenarioCase, ...]:
    return tuple(s for s in ALL_SCENARIOS if s.family == family)
