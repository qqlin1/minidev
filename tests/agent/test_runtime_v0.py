"""Agent Runtime 的依赖注入与消息回填测试。

职责：验证 Agent Loop 只依赖抽象的 chat() 调用，Fake Client 可以驱动直接回答和
工具回合；不访问真实模型、不需要 API Key，也不承担 Provider 重试测试。
"""
import json
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace

import httpx2
from openai import APITimeoutError

from agent.llm.errors import ModelRetryExhaustedError
from agent.runtime.v0 import MAX_STEPS, StopReason, run_turn


def _assistant_message(content: str | None = None, tool_calls: list | None = None):
    return SimpleNamespace(content=content, tool_calls=tool_calls or [])


def _tool_call(call_id: str, name: str, arguments: dict):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


class FakeLLMClient:
    """按预设顺序返回消息，模拟注入到 Agent Loop 的模型客户端。"""

    def __init__(self, responses: list) -> None:
        self._responses = iter(responses)
        self.calls: list[dict] = []

    def chat(self, messages, tools=None, temperature=0.3):
        self.calls.append({
            "messages": list(messages),
            "tools": tools,
            "temperature": temperature,
        })
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


def test_run_turn_uses_injected_client_for_direct_answer():
    fake = FakeLLMClient([_assistant_message(content="直接回答")])
    output = StringIO()

    with redirect_stdout(output):
        result = run_turn("你好", fake)

    assert "直接回答" in output.getvalue()
    assert result.stop_reason == StopReason.FINAL_ANSWER
    assert result.final_output == "直接回答"
    assert result.agent_steps == 1
    assert len(fake.calls) == 1


def test_run_turn_injected_client_drives_tool_round_trip():
    fake = FakeLLMClient([
        _assistant_message(
            tool_calls=[
                _tool_call("call-1", "read_file", {"path": "apps/hello_api.py"}),
            ]
        ),
        _assistant_message(content="已读取文件"),
    ])
    output = StringIO()

    with redirect_stdout(output):
        result = run_turn("读取 apps/hello_api.py", fake)

    assert "已读取文件" in output.getvalue()
    assert result.stop_reason == StopReason.FINAL_ANSWER
    assert result.final_output == "已读取文件"
    assert result.agent_steps == 2
    assert len(fake.calls) == 2
    tool_message = fake.calls[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert "def main" in tool_message["content"]


def test_run_turn_executes_multiple_tool_calls_in_model_order():
    """同一模型回合的多个 Tool Call 当前必须串行执行并按原顺序回填。"""
    fake = FakeLLMClient([
        _assistant_message(
            tool_calls=[
                _tool_call("call-A", "read_file", {"path": "apps/hello_api.py"}),
                _tool_call("call-B", "list_dir", {"path": "."}),
            ]
        ),
        _assistant_message(content="两个工具都已完成"),
    ])
    output = StringIO()

    with redirect_stdout(output):
        run_turn("读取文件并列出目录", fake)

    assert "两个工具都已完成" in output.getvalue()
    assert len(fake.calls) == 2
    tool_messages = [
        message
        for message in fake.calls[1]["messages"]
        if isinstance(message, dict) and message["role"] == "tool"
    ]
    assert [message["tool_call_id"] for message in tool_messages] == ["call-A", "call-B"]


def test_run_turn_returns_invalid_json_error_to_model():
    """模型给出非法 JSON 参数时，Runtime 不崩溃而是把可读错误作为 Tool Result 回填。"""
    invalid_call = SimpleNamespace(
        id="call-invalid-json",
        function=SimpleNamespace(name="list_dir", arguments="{not valid json}"),
    )
    fake = FakeLLMClient([
        _assistant_message(tool_calls=[invalid_call]),
        _assistant_message(content="已根据错误修正"),
    ])

    with redirect_stdout(StringIO()):
        run_turn("列目录", fake)

    tool_message = fake.calls[1]["messages"][-1]
    assert tool_message["tool_call_id"] == "call-invalid-json"
    assert "参数不是合法 JSON" in tool_message["content"]


def test_run_turn_returns_unknown_tool_error_to_model():
    """模型编造工具名时，Runtime 回填可用工具列表而不是抛出 KeyError。"""
    fake = FakeLLMClient([
        _assistant_message(tool_calls=[_tool_call("call-unknown", "delete_everything", {})]),
        _assistant_message(content="已改用可用工具"),
    ])

    with redirect_stdout(StringIO()):
        run_turn("清理项目", fake)

    tool_message = fake.calls[1]["messages"][-1]
    assert tool_message["tool_call_id"] == "call-unknown"
    assert "工具 delete_everything 不存在" in tool_message["content"]
    assert "read_file" in tool_message["content"]
    assert "list_dir" in tool_message["content"]


def test_run_turn_returns_tool_execution_error_to_model():
    """工具业务执行失败时，错误作为对应 Tool Result 回填，Loop 仍可继续。"""
    fake = FakeLLMClient([
        _assistant_message(
            tool_calls=[
                _tool_call("call-missing-file", "read_file", {"path": "file_that_does_not_exist.py"}),
            ]
        ),
        _assistant_message(content="文件不存在，无法读取"),
    ])

    with redirect_stdout(StringIO()):
        run_turn("读取不存在的文件", fake)

    tool_message = fake.calls[1]["messages"][-1]
    assert tool_message["tool_call_id"] == "call-missing-file"
    assert "工具执行出错" in tool_message["content"]
    assert "file_that_does_not_exist.py" in tool_message["content"]


def test_run_turn_stops_after_max_steps():
    """模型持续请求工具时，MAX_STEPS 后 Runtime 必须熔断，而不是无限调用模型。"""
    fake = FakeLLMClient([
        _assistant_message(
            tool_calls=[_tool_call(f"call-{step}", "made_up_tool", {})],
        )
        for step in range(MAX_STEPS)
    ])
    output = StringIO()

    with redirect_stdout(output):
        result = run_turn("永远不要结束", fake)

    assert len(fake.calls) == MAX_STEPS
    assert result.stop_reason == StopReason.MAX_STEPS_EXCEEDED
    assert result.agent_steps == MAX_STEPS
    assert result.error_message == "达到最大步数，熔断退出。"
    assert "达到最大步数，熔断退出" in output.getvalue()


def test_run_turn_converts_model_retry_exhaustion_to_stop_reason():
    """Runtime 将 Client 的稳定异常转为用户可读、机器可判定的 Agent 终态。"""
    timeout_after_client_retries = APITimeoutError(
        request=httpx2.Request("POST", "https://api.deepseek.com/chat/completions"),
    )
    fake = FakeLLMClient([
        ModelRetryExhaustedError(last_error=timeout_after_client_retries, attempts=3),
    ])
    output = StringIO()

    with redirect_stdout(output):
        result = run_turn("请求模型", fake)

    assert result.stop_reason == StopReason.MODEL_RETRY_EXHAUSTED
    assert result.agent_steps == 1
    assert result.final_output is None
    assert result.error_type == "APITimeoutError"
    assert result.error_message == "模型服务暂时不可用，已在 3 次尝试后停止。请稍后重试。"
    assert "模型服务暂时不可用" in output.getvalue()
    assert "APITimeoutError" not in output.getvalue()
    assert len(fake.calls) == 1
