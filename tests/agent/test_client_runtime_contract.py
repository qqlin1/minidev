"""Client 与 Runtime 的跨组件契约回归测试。

职责：把「真实 LLMClient」和「真实 run_turn」连起来跑，验证两边对
**同一个返回值**的形状说法一致。

为什么单独有这个文件：`tests/agent/test_llm_client.py` 用 Fake SDK 单独测 Client，
`tests/agent/test_runtime_v0.py` 用 Fake Client 单独测 Runtime，两边各自都绿。
但两个 Fake 的返回形状曾经不一致——Client 交的是 message，Runtime 的 Fake 交的是带
`.choices` 的 response wrapper——于是真货一组合就在 `agent/runtime/v0.py:140` 崩。

这正是 2026-09-13 记录的 `DISCOVERED / UNFIXED` 假绿案例
（见 `badcases.md`）。本文件就是那次故障的常驻回归：
**任何一方把返回契约改回去，这里立刻变红。**

离线：不发网络请求、不需要 API Key、不花钱。
"""
from types import SimpleNamespace

import pytest
from openai.types.chat import ChatCompletionMessage

from agent.llm.client import LLMClient
from agent.runtime.v0 import StopReason, run_turn


# ---------- 假 SDK：形状抄真货，一个字段都不多不少 ----------


class _FakeChoice:
    """真 SDK 的 choices 列表元素，只有一个 .message 是 LLMClient 会碰的。"""

    def __init__(self, message) -> None:
        self.message = message


class _FakeResponse:
    """真 SDK 的 ChatCompletion：顶层就是一个 .choices 列表。"""

    def __init__(self, message) -> None:
        self.choices = [_FakeChoice(message)]


class _FakeCompletions:
    """按剧本依次交消息，并记录被调用了几次。"""

    def __init__(self, messages: list) -> None:
        self._messages = list(messages)
        self.calls = 0

    def create(self, **kwargs):
        message = self._messages[self.calls]
        self.calls += 1
        return _FakeResponse(message)


class FakeSDK:
    """最小假 SDK，只实现 LLMClient 实际会碰的属性链 chat.completions.create。

    注意：这里返回的是 **response**（带 .choices），不是 message。
    这个区分是本文件存在的全部理由。
    """

    def __init__(self, messages: list) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(messages))


def _assistant_message(content: str | None = None, tool_calls: list | None = None):
    """真货类型，不是随手捏的对象——契约要验的就是真货身上有什么。"""
    return ChatCompletionMessage(
        role="assistant",
        content=content,
        tool_calls=tool_calls or None,
    )


def _tool_call(call_id: str, name: str, arguments: str):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


# ---------- 契约本身：Client 交出来的到底是什么形状 ----------


def test_client_chat_returns_message_not_response():
    """Client.chat() 的返回契约：有 content / tool_calls，**没有** choices。

    这是全项目唯一的返回契约声明。谁改谁负责——改这一行会让本文件变红。
    """
    sdk = FakeSDK([_assistant_message(content="你好，我是模型")])
    client = LLMClient(api_key="sk-not-real", client=sdk)

    delivered = client.chat(messages=[{"role": "user", "content": "你好"}])

    assert hasattr(delivered, "content"), "Runtime 要靠 .content 取最终回答"
    assert hasattr(delivered, "tool_calls"), "Runtime 要靠 .tool_calls 判断是否调工具"
    assert not hasattr(delivered, "choices"), (
        "Client 已经去皮过了；再带 .choices 出来就是在骗调用方"
    )


def test_sdk_layer_retry_is_disabled_so_app_layer_owns_the_budget():
    """SDK 内部重试必须关掉，否则和应用的 max_retries 相乘。

    SDK 默认 max_retries=2（3 次尝试）× 应用层 max_retries=3 = 最坏 9 次真实请求。
    重试预算只能由一处承担：Client 的应用层。
    """
    client = LLMClient(api_key="sk-not-real", max_retries=3)

    assert client._client.max_retries == 0, (
        "SDK 内部重试必须为 0（应用层是唯一重试责任人）；"
        f"当前是 {client._client.max_retries}，会和应用的 3 次相乘"
    )


# ---------- 跨组件：真实 Client + 真实 Runtime ----------


def test_real_client_drives_real_runtime_for_direct_answer():
    """真实 Client 注入真实 Runtime：一次直接回答走通（2026-09-17 修复的那条路径）。

    修复前这里抛：
        AttributeError: 'ChatCompletionMessage' object has no attribute 'choices'
    位置：agent/runtime/v0.py:140
    """
    sdk = FakeSDK([_assistant_message(content="你好，我是模型")])
    client = LLMClient(api_key="sk-not-real", client=sdk)

    result = run_turn("你好", client)

    assert result.stop_reason == StopReason.FINAL_ANSWER
    assert result.final_output == "你好，我是模型"
    assert result.agent_steps == 1
    assert sdk.chat.completions.calls == 1


def test_real_client_drives_real_runtime_for_tool_round_trip():
    """真实 Client 注入真实 Runtime：一次 Tool Round Trip 走通。

    覆盖 tool_calls 分支——契约不光影响最终回答，也影响工具回填。
    """
    sdk = FakeSDK([
        _assistant_message(
            tool_calls=[
                _tool_call("call-1", "read_file", '{"path": "apps/hello_api.py"}'),
            ]
        ),
        _assistant_message(content="已读取文件"),
    ])
    client = LLMClient(api_key="sk-not-real", client=sdk)

    result = run_turn("读取 apps/hello_api.py", client)

    assert result.stop_reason == StopReason.FINAL_ANSWER
    assert result.final_output == "已读取文件"
    assert result.agent_steps == 2, "第一步调工具、第二步给最终回答"
    assert sdk.chat.completions.calls == 2


def test_runtime_does_not_reach_into_sdk_wrapper():
    """反向保护：Runtime 不该再对 Client 的返回值做第二次去皮。

    给 Runtime 一个**故意不带 .choices** 的 message：如果 Runtime 内部还有
    `resp.choices[0].message` 这种代码，这里会立刻抛 AttributeError。
    """
    sdk = FakeSDK([_assistant_message(content="直接回答")])
    client = LLMClient(api_key="sk-not-real", client=sdk)

    result = run_turn("你好", client)

    assert result.stop_reason == StopReason.FINAL_ANSWER
    assert not isinstance(result, Exception)


def test_missing_choices_raises_a_clear_attribute_error():
    """把当年那个崩溃的形状固定下来，供以后对照阅读。

    如果有人把 Client 改回「返回 response」，Runtime 会在同一个地方崩——
    本测试不阻止那种改法，只是把后果写清楚。
    """
    message = _assistant_message(content="你好")
    resp = _FakeResponse(message)

    assert hasattr(resp, "choices")
    assert not hasattr(message, "choices")

    with pytest.raises(AttributeError, match="choices"):
        _ = message.choices[0].message  # 这就是修复前 v0.py:140 干的事
