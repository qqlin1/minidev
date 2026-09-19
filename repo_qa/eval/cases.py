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
# 员工手册夹具：42 行，三级标题，用来验证「标题和正文是否在同一块」
#
# 为什么把它内嵌在代码里，而不是运行时读 _unit3_employee_handbook.md：
# 评测集必须**自包含**。如果它依赖项目根目录下的一个文件，那个文件被改名、
# 被移动、或内容被改动，评测数字会静默变化，而你看不出来原因。
# 内嵌之后，「评测用的是什么语料」这件事锁死在代码里。
#
# 测试 test_handbook_fixture_matches_source_file 会拿它和源文件逐字节比对，
# 保证内嵌的这份没有抄错。
# ---------------------------------------------------------------------------

EMPLOYEE_HANDBOOK = """\
# 员工手册

## 第一章 考勤管理

### 1.1 上班时间

公司实行弹性工作制，标准上班时间为每天 9:00 至 18:00，
午休 12:00 至 13:30。员工可在 8:30 至 10:00 之间自主选择上班时间，
但每日实际工作时长不得少于 8 小时。

### 1.2 迟到处理

迟到 15 分钟以内不计入考勤异常。迟到超过 15 分钟但不满 1 小时的，
按事假处理。单月累计迟到超过 3 次的，扣除当月全勤奖。

## 第二章 报销制度

### 2.1 差旅报销

单次差旅报销上限为 5000 元，超出部分需部门负责人审批后执行。
住宿标准按城市分级：一线城市每晚不超过 600 元，
二线城市不超过 400 元，其他城市不超过 300 元。
交通费凭票据实报销，市内交通单日不超过 100 元。
出差期间伙食补助按每天 80 元标准包干。
国际差旅需提前 15 个工作日提交申请，并附行程说明。

### 2.2 办公用品

日常办公用品由行政统一采购，员工无需自行报销。
单价超过 500 元的设备需提前提交采购申请。

## 第三章 假期管理

### 3.1 年假

入职满一年的员工享有 5 天带薪年假，每满一年增加 1 天，
上限 15 天。年假需提前 3 个工作日申请。

### 3.2 病假

病假需提供二级以上医院开具的证明。全年累计病假超过 15 天的，
超出部分按基本工资的 70% 计发。
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
    # —— 文档：标题与正文是否同块（markdown_heading 的靶子） ——
    #
    # 这三条的期望区间**都从标题行开始**。为什么不是「只要答案那几行」：
    # 因为要测的正是「标题和答案在不在同一个块里」。
    # 用户问题里的关键词（「迟到」「差旅」「年假」）出现在标题里，
    # 答案在正文里；如果标题和正文被切开，检索时关键词和答案就不在同一块，
    # 两块都答不了这个问题。
    ScenarioCase(
        id="doc_handbook_late_policy",
        question="迟到超过 15 分钟怎么处理？",
        path="handbook.md",
        source_text=EMPLOYEE_HANDBOOK,
        # 第 11 行是标题 ### 1.2 迟到处理，第 13-14 行是答案正文
        expect_start_line=11,
        expect_end_line=14,
        family="doc_section",
        failure_mode=(
            "固定行数(max_lines=6)切成 7-12 和 13-18 两块："
            "标题（第 11 行）落在 7-12，答案（第 13-14 行）落在 13-18。"
            "用户问「迟到」，关键词在标题里、答案在另一块，两块都答不了"
        ),
    ),
    ScenarioCase(
        id="doc_handbook_travel_cap",
        question="差旅报销上限是多少？",
        path="handbook.md",
        source_text=EMPLOYEE_HANDBOOK,
        # 第 18 行是标题 ### 2.1 差旅报销，第 20 行是答案正文
        expect_start_line=18,
        expect_end_line=20,
        family="doc_section",
        failure_mode=(
            "固定行数切成 13-18 和 19-24 两块："
            "标题（第 18 行）卡在 13-18 块的**最后一行**，答案（第 20 行）在 19-24 块。"
            "这是最隐蔽的一种坏法——标题看起来「有归属」，但和正文分属两块"
        ),
    ),
    ScenarioCase(
        id="doc_handbook_annual_leave",
        question="年假有多少天？",
        path="handbook.md",
        source_text=EMPLOYEE_HANDBOOK,
        # 第 34 行是标题 ### 3.1 年假，第 36-37 行是答案正文
        expect_start_line=34,
        expect_end_line=37,
        family="doc_section",
        failure_mode=(
            "固定行数切成 31-36 和 37-42 两块："
            "正文被**腰斩**——第 36 行（「每满一年增加 1 天，」）在上一块，"
            "第 37 行（「上限 15 天。」）在下一块。答案本身被切成两半，"
            "两块各自都读不出完整答案"
        ),
    ),
)


def scenarios_by_family(family: str) -> tuple[ScenarioCase, ...]:
    return tuple(s for s in ALL_SCENARIOS if s.family == family)
