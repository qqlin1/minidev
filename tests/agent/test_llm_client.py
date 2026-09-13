"""Provider Adapter 的离线单元测试。

职责：验证 agent/llm/client.py 的重试、Retry-After 和异常传播边界；通过注入假 SDK
模拟 Provider 故障，不访问真实 API、不验证 OpenAI SDK 本身。测试必须快、稳、可重复。

统一入口：`uv run pytest -q`。本文件只声明 pytest 可发现的 `test_*` 函数，
不提供手工执行入口，避免测试集遗漏或受终端编码影响。
"""
import httpx2  # openai 3.x 的底层 HTTP 库（构造假 429 响应用它的 Response）
import pytest
from openai import APIConnectionError, APITimeoutError, RateLimitError
from openai.types.chat import ChatCompletionMessage

from agent.llm.client import LLMClient, _retry_after_seconds
from agent.llm.errors import ModelRetryExhaustedError


def _request() -> httpx2.Request:
    """构造异常对象所需的请求元数据；不发送真实网络请求。"""
    return httpx2.Request("POST", "https://api.deepseek.com/chat/completions")


def _rate_limit_exc(retry_after: str | None = None) -> RateLimitError:
    """手工构造一个真的 429 异常对象（带可选的 Retry-After 头）。"""
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx2.Response(429, headers=headers, request=_request())
    return RateLimitError("rate limited", response=response, body=None)


def _timeout_exc() -> APITimeoutError:
    """构造 SDK 超时异常；只用于离线故障注入。"""
    return APITimeoutError(request=_request())


def _connection_exc() -> APIConnectionError:
    """构造 SDK 连接异常；只用于离线故障注入。"""
    return APIConnectionError(request=_request())


# ---------- 假客户端：长得像 openai client，行为按剧本走 ----------

class _FakeChoice:
    def __init__(self, message: ChatCompletionMessage) -> None:
        self.message = message


class _FakeResponse:
    def __init__(self, message: ChatCompletionMessage) -> None:
        self.choices = [_FakeChoice(message)]


class _FakeChat:
    def __init__(self, fail_times: int, failures: list[Exception] | None) -> None:
        self.completions = FakeCompletions(fail_times, failures)


class FakeCompletions:
    """按预设故障剧本模拟 chat.completions，之后返回成功。"""

    def __init__(self, fail_times: int, failures: list[Exception] | None) -> None:
        self.failures = failures or [_rate_limit_exc() for _ in range(fail_times)]
        self.calls = 0  # 记录被调用了几次，用来断言"确实重试了"

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= len(self.failures):
            raise self.failures[self.calls - 1]
        return _FakeResponse(ChatCompletionMessage(role="assistant", content="恢复后的回答"))


class FakeClient:
    """最小假客户端：只实现 LLMClient 实际会碰的属性链 client.chat.completions.create。"""

    def __init__(self, fail_times: int = 0, failures: list[Exception] | None = None) -> None:
        self.chat = _FakeChat(fail_times, failures)


# ---------- 三个测试 ----------

def test_max_retries_must_be_positive():
    """零次尝试没有明确语义，配置错误应在初始化阶段立即失败。"""
    with pytest.raises(ValueError, match="max_retries 必须至少为 1"):
        LLMClient(max_retries=0, client=FakeClient())


def test_retry_recovers_after_429():
    """前 2 次 429、第 3 次成功：应该自动重试并拿到结果，总共调用 3 次。"""
    client = LLMClient(max_retries=3, base_delay=0.01, client=FakeClient(fail_times=2))
    msg = client.chat([{"role": "user", "content": "hi"}])
    assert msg.content == "恢复后的回答"
    assert client._client.chat.completions.calls == 3


def test_retry_exhausts_and_raises():
    """一直 429：耗尽后转换为模型适配层的稳定异常，并保留原始技术原因。"""
    client = LLMClient(max_retries=3, base_delay=0.01, client=FakeClient(fail_times=99))
    try:
        client.chat([{"role": "user", "content": "hi"}])
        raise AssertionError("应该抛出 ModelRetryExhaustedError 却没有")
    except ModelRetryExhaustedError as exc:
        assert isinstance(exc.last_error, RateLimitError)
        assert exc.attempts == 3
        assert client._client.chat.completions.calls == 3


def test_retry_after_header_is_honored():
    """服务端给了 Retry-After: 7 就等 7 秒；没给就返回 None（走指数退避）。"""
    assert _retry_after_seconds(_rate_limit_exc(retry_after="7")) == 7.0
    assert _retry_after_seconds(_rate_limit_exc()) is None


def test_retry_recovers_after_timeout():
    """前两次请求超时、第 3 次成功：超时属于可重试的暂时性模型错误。"""
    client = LLMClient(
        max_retries=3,
        base_delay=0.01,
        client=FakeClient(failures=[_timeout_exc(), _timeout_exc()]),
    )

    msg = client.chat([{"role": "user", "content": "hi"}])

    assert msg.content == "恢复后的回答"
    assert client._client.chat.completions.calls == 3


def test_retry_recovers_after_connection_error():
    """连接建立失败后重试成功：断连也属于客户端层的可重试错误。"""
    client = LLMClient(
        max_retries=3,
        base_delay=0.01,
        client=FakeClient(failures=[_connection_exc()]),
    )

    msg = client.chat([{"role": "user", "content": "hi"}])

    assert msg.content == "恢复后的回答"
    assert client._client.chat.completions.calls == 2


def test_timeout_retry_exhausts_and_raises():
    """连续超时耗尽后，LLMClient 交出带原始原因的稳定异常给 Agent Runtime。"""
    client = LLMClient(
        max_retries=3,
        base_delay=0.01,
        client=FakeClient(failures=[_timeout_exc(), _timeout_exc(), _timeout_exc()]),
    )

    try:
        client.chat([{"role": "user", "content": "hi"}])
        raise AssertionError("应该抛出 ModelRetryExhaustedError 却没有")
    except ModelRetryExhaustedError as exc:
        assert isinstance(exc.last_error, APITimeoutError)
        assert exc.attempts == 3
        assert client._client.chat.completions.calls == 3
