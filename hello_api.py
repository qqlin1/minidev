"""W0 验收脚本：验证 API Key、网络连通性、流式输出、token 统计是否全部正常。

运行：uv run hello_api.py
"""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def main() -> None:
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("LLM_MODEL", "deepseek-chat")

    if not api_key or "xxxx" in api_key:
        sys.exit(
            "未配置 LLM_API_KEY：\n"
            "  1. 复制 .env.example 为 .env\n"
            "  2. 填入你在 DeepSeek 开放平台申请的 API Key"
        )

    client = OpenAI(api_key=api_key, base_url=base_url)
    print(f">>> 模型: {model}")
    print(">>> 提问: 用一句话解释什么是 AI Agent")
    print(">>> 流式回复: ", end="", flush=True)

    usage = None
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "用一句话解释什么是 AI Agent"}],
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in stream:
        if chunk.usage:
            usage = chunk.usage
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)

    print()
    if usage:
        print(
            f">>> token 用量: 输入 {usage.prompt_tokens} + 输出 {usage.completion_tokens}"
        )
    print(">>> 环境就绪 ✅ 可以开始 W1")


if __name__ == "__main__":
    main()
