"""W1 主任务：手写第一版 Agent Loop（核心 30 行版）。

第 1 章概念红线在这里落地：模型只输出 tool_calls（调用意图），
真正的执行永远在客户端——所以权限、超时、确认才能做在我们这边。

你的任务：填满两处 TODO，跑通检查点：
    启动后输入「读一下 hello_api.py 并总结」→ agent 自己调 read_file → 给出总结
运行：uv run agent_v0.py
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

MAX_STEPS = 10  # 熔断：防死循环与成本失控（第 1 章 range(5) 的工程版）


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
                        "description": "要读取的文件路径（相对或绝对），例如 'hello_api.py'",
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


def run_turn(user_input: str) -> None:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    for _ in range(MAX_STEPS):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:  # 模型认为不需要工具了，直接给最终回答
            print(f"\nMiniDev > {msg.content}")
            return

        # TODO ②：工具调用分支——三步，缺一不可：
        # ① 把这条 assistant 消息原样回填（它已经"承诺"要调工具，历史里不能断）：
        #       messages.append(msg)
        # ② 遍历 msg.tool_calls，对每一条 tc：
        #       args = json.loads(tc.function.arguments)  # 注意：是 JSON 字符串，不是 dict
        #       执行 TOOLS[tc.function.name](**args)；
        #       出错不要抛异常，用 try/except 把错误文本当工具结果回填；
        #       回填格式：{"role": "tool", "tool_call_id": tc.id, "content": str(result)[:2000]}
        #    （截断 2000 字符 = 上下文保护的最简版，W6 上下文管理的伏笔）
        # ③ 然后什么都不做：for 的下一轮会带着完整历史再问模型，
        #    它要么继续要工具，要么给最终回答。
        raise NotImplementedError("按 TODO ② 的三步实现这里")

    print("\nMiniDev > 达到最大步数，熔断退出。（想想：什么任务会走到这里？）")


if __name__ == "__main__":
    print("MiniDev v0.1 · 输入 exit 退出")
    while True:
        try:
            user = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user or user.lower() in {"exit", "quit"}:
            break
        run_turn(user)
