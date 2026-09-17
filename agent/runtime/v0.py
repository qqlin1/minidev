"""Agent Runtime v0 — W1 学习版：单 Agent Loop + 临时工具（含 CLI）。

职责：
- 接收终端用户输入，组装 system/user/tool 消息；
- 调用注入的 LLMClient，依据模型返回决定继续还是结束；
- 将最终答案、模型重试耗尽和最大步数归一为机器可读的 AgentRunResult；
- 回填 assistant tool_calls 和 tool results，维护本轮临时消息历史；
- 在当前 W1 版本中组合 read_file/list_dir 工具，并执行基础错误回填；
- 用 MAX_STEPS 作为 Agent 循环预算，防止死循环和成本失控。

明确不负责：
- 不实现 Provider 连接、模型重试或流式传输，这些属于 agent/llm/client.py；
- 不把模型输出当成授权，不提供工作区沙箱、敏感文件保护或写操作审批；
- 不负责持久化 State、Checkpoint、Trace 或固定评测集。

当前文件故意把 CLI、工具和 Loop 放在一起，便于 W1 看完整调用流；后续按真实
场景拆成 runtime、tools 和 apps 入口，而不是为了模仿框架提前拆空目录。

检查点：uv run -m agent.runtime.v0，输入「读一下 apps/hello_api.py 并总结」→
Agent 调用 read_file → 回到模型 → 输出总结。
"""

import json
import os
from dataclasses import dataclass
from enum import StrEnum

from agent.llm.client import LLMClient
from agent.llm.errors import ModelRetryExhaustedError

MAX_STEPS = 10  # Agent 循环预算：防死循环与成本失控，不是模型请求重试次数


class StopReason(StrEnum):
    """本轮 Agent 终态的固定集合，供 CLI、测试和后续 Trace 统一识别。"""

    FINAL_ANSWER = "final_answer"
    MODEL_RETRY_EXHAUSTED = "model_retry_exhausted"
    MAX_STEPS_EXCEEDED = "max_steps_exceeded"


@dataclass(frozen=True)
class AgentRunResult:
    """一次 Agent 运行的最小结构化结果，不保存完整消息历史或 Trace。"""

    stop_reason: StopReason
    agent_steps: int
    final_output: str | None = None
    error_message: str | None = None
    error_type: str | None = None


# ---------- 1. 工具实现：客户端的"手" ----------

def read_file(path: str) -> str:
    """读文件。参数名 path 必须和下面 schema 里的参数名一致，模型按名传参。"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def list_dir(path: str = ".") -> str:
    """列目录。"""
    return "\n".join(sorted(os.listdir(path)))


TOOLS = {"read_file": read_file, "list_dir": list_dir}


# ---------- 2. 工具清单：告诉模型"你有哪些手" ----------
# 每个工具一项。注意两类字段的读者不同：
#   - type/name/parameters 是协议格式，给"程序"做路由用；
#   - description（工具的和参数的）是说明书，给"模型"读——模型选不选这个工具全看它。
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",  # 必须和 TOOLS 字典的键一致，否则执行时 KeyError
            "description": "读取指定路径的文本文件，返回文件全部内容。当需要查看某个文件的内容时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径（相对或绝对），例如 'apps/hello_api.py'",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出目录下的所有文件和子目录名。当需要知道项目里有哪些文件时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目录路径，默认当前目录 '.'",
                    }
                },
                "required": [],  # path 有默认值 '.'，模型可以不传
            },
        },
    },
]

SYSTEM_PROMPT = """你是 MiniDev，一个运行在终端里的编程助手。
需要查看文件或目录时调用工具，能直接回答的不要绕工具。
回答用中文，简洁。"""


# ---------- 3. 主循环：TAO 循环的工程实现 ----------

def run_turn(user_input: str, llm_client: LLMClient) -> AgentRunResult:
    """运行一轮 Agent 对话，返回可供调用方判断终态的结构化结果。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    for step in range(MAX_STEPS):
        try:
            resp = llm_client.chat(
                messages=messages,
                tools=TOOL_SCHEMAS,
            )
        except ModelRetryExhaustedError as exc:
            # 不展示底层 SDK 原始报错；保留 error_type 供后续 Trace/排障使用。
            user_message = f"模型服务暂时不可用，已在 {exc.attempts} 次尝试后停止。请稍后重试。"
            print(f"\nMiniDev > {user_message}")
            return AgentRunResult(
                stop_reason=StopReason.MODEL_RETRY_EXHAUSTED,
                agent_steps=step + 1,
                error_message=user_message,
                error_type=exc.last_error.__class__.__name__,
            )
        msg = resp

        if not msg.tool_calls:  # 模型认为不需要工具了，直接给最终回答
            final_output = msg.content or ""
            print(f"\nMiniDev > {final_output}")
            return AgentRunResult(
                stop_reason=StopReason.FINAL_ANSWER,
                agent_steps=step + 1,
                final_output=final_output,
            )

        # 第 ① 步：把带 tool_calls 的 assistant 消息原样回填。
        # 模型是无状态的，这条消息是"我承诺要调这些工具"的记录，
        # 少了它，下一轮模型看到凭空出现的工具结果会直接 400。
        messages.append(msg)

        # 第 ② 步：逐条执行工具。模型可一次请求多个；当前 Runtime 按返回顺序串行执行。
        for tc in msg.tool_calls:
            name = tc.function.name
            fn = TOOLS.get(name)
            if fn is None:
                # 兜底层 1：模型编造了不存在的工具名 → 把正确清单喂回去让它自行纠正
                result = f"错误：工具 {name} 不存在。可用工具：{', '.join(TOOLS)}"
            else:
                try:
                    args = json.loads(tc.function.arguments)  # 是 JSON 字符串，不是 dict
                except json.JSONDecodeError:
                    # 兜底层 2：参数不是合法 JSON → 原样退回让它重写
                    result = f"错误：参数不是合法 JSON：{tc.function.arguments}"
                else:
                    try:
                        result = fn(**args)  # 按名传参：args 的键必须与函数形参名一致
                    except Exception as exc:
                        # 兜底层 3：执行报错（如文件不存在）→ 错误文本当结果喂回，循环继续
                        result = f"工具执行出错：{exc}"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,           # 与 assistant 消息里的调用一一配对，缺了会 400
                "content": str(result)[:2000],   # 截断保护：大结果会撑爆上下文（W6 的最简版）
            })
        # 第 ③ 步：无需任何代码——for 的下一轮带着完整历史再问模型，
        # 它要么继续要工具，要么给出最终回答。

    user_message = "达到最大步数，熔断退出。"
    print(f"\nMiniDev > {user_message}")
    return AgentRunResult(
        stop_reason=StopReason.MAX_STEPS_EXCEEDED,
        agent_steps=MAX_STEPS,
        error_message=user_message,
    )


def main() -> None:
    """交互式 CLI 入口；业务 Loop 在 `run_turn`，便于 Fake Client 测试。"""
    print("MiniDev v0.1 · 输入 exit 退出")
    llm_client = LLMClient()
    while True:
        try:
            user = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user or user.lower() in {"exit", "quit"}:
            break
        run_turn(user, llm_client)


if __name__ == "__main__":
    main()
