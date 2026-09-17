"""模型适配层：负责“Agent 怎么稳定地调用模型”，不负责“Agent 怎么思考”。

职责：
- 读取模型连接配置（API Key、Base URL、模型名）；
- 统一封装 Chat/流式调用，并整理模型返回消息；
- 承载模型请求参数（当前是 model、temperature）；
- 处理模型调用层的暂时性故障：429、连接错误、超时、指数退避和重试；
- 将重试耗尽归一为 ModelRetryExhaustedError，保留技术原因和尝试次数；
- 为测试注入 Fake SDK，避免测试访问真实 Provider。

明确不负责：
- 不决定用户问题如何拆解、是否调用工具或何时结束；
- 不注册、授权或执行工具，也不处理工具业务错误；
- 不保存 Agent 的消息状态、Checkpoint 或长期记忆；
- 不把 reasoning_effort 等 Provider 私有参数无条件发送给所有模型。

调用边界：Agent Loop 调用本类的 chat()/chat_stream()；本类再调用 OpenAI 兼容 SDK。
**重试责任：只在本层。** SDK 内部重试已显式关闭（`max_retries=0`），
`max_retries` 参数就是一次调用的真实总尝试次数上限，不与 SDK 相乘。
Agent Loop 的步骤预算与工具副作用重放策略必须由上层负责。
"""
import logging
import os
import random
import time
from collections.abc import Iterator

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessage

from .errors import ModelRetryExhaustedError

logger = logging.getLogger(__name__)


def _retry_after_seconds(exc: RateLimitError) -> float | None:
    """读 429 响应里的 Retry-After 头（单位秒）。没有或解析失败返回 None。"""
    try:
        value = exc.response.headers.get("retry-after")
        return float(value) if value else None
    except Exception:
        return None


class LLMClient:
    """OpenAI 兼容接口的封装类。

    支持注入现成的 client（参数 client）——单测时塞一个"假客户端"进去，
    就能模拟 429 而不打真实 API（见 tests/test_llm_client.py）。这叫依赖注入。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        client: OpenAI | None = None,
    ) -> None:
        # 只在真正创建客户端时加载配置；导入本模块不会初始化 SDK 或要求 API Key。
        load_dotenv()
        if max_retries < 1:
            raise ValueError("max_retries 必须至少为 1")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._client = client or OpenAI(
            api_key=api_key or os.getenv("LLM_API_KEY"),
            base_url=base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            # 关掉 SDK 的内部重试（默认 2，即总共 3 次尝试）。
            # 否则 SDK 的 3 次 × 应用层的 max_retries(3) = 最坏 9 次真实请求：
            # 账单翻三倍、延迟也翻三倍，而且「到底试了几次」说不清。
            # 重试预算只能由一处承担 —— 就是本类的 _call_with_retry。
            max_retries=0,
        )

    # ---------- 内部：带重试的调用核心 ----------

    def _call_with_retry(self, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return self._client.chat.completions.create(**kwargs)
            except RateLimitError as exc:
                # 429 特殊处理：优先听服务端的 Retry-After，没有才指数退避。
                last_exc = exc
                if attempt + 1 == self.max_retries:
                    break  # 最后一次失败后不应再无意义地 sleep。
                wait = _retry_after_seconds(exc) or self.base_delay * (2**attempt) + random.uniform(0, 0.5)
                logger.warning("触发限流(429)，等待 %.1f 秒后重试 %d/%d", wait, attempt + 1, self.max_retries)
                time.sleep(wait)
            except (APITimeoutError, APIConnectionError) as exc:
                last_exc = exc
                if attempt + 1 == self.max_retries:
                    break
                wait = self.base_delay * (2**attempt) + random.uniform(0, 0.5)
                logger.warning("%s，等待 %.1f 秒后重试 %d/%d", exc.__class__.__name__, wait, attempt + 1, self.max_retries)
                time.sleep(wait)

        # 只会到达这里：某个可重试错误连续失败，并且已耗尽所有请求尝试。
        assert last_exc is not None
        raise ModelRetryExhaustedError(last_error=last_exc, attempts=self.max_retries) from last_exc

    # ---------- 对外：两种调用方式 ----------

    def chat(
        self,
        messages: list[dict],
        tools: list | None = None,
        temperature: float = 0.3,
    ) -> ChatCompletionMessage:
        """非流式对话：返回完整的 assistant 消息对象（含 tool_calls / content）。

        Agent 主循环用这个——循环需要拿到 msg.tool_calls 来决定下一步动作。
        """
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools is not None:  # 不把 tools=None 发给服务端，避免兼容性问题
            kwargs["tools"] = tools
        resp = self._call_with_retry(**kwargs)
        return resp.choices[0].message

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> Iterator[str]:
        """流式对话：逐段产出（yield）文本增量，调用方边收边打印。

        适合"最终回答"场景——用户看着字一个个蹦出来，体验好、首字延迟低。
        注意：这里只产出纯文本；"流式 + 工具调用"需要把分片到达的 tool_call
        增量按 index 拼装，是 W2 的活。
        """
        stream = self._call_with_retry(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
            stream_options={"include_usage": True},  # 让最后一个 chunk 携带 token 用量
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if getattr(chunk, "usage", None):
                logger.info(
                    "token 用量：输入 %s / 输出 %s",
                    chunk.usage.prompt_tokens, chunk.usage.completion_tokens,
                )
