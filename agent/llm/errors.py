"""模型适配层的错误契约。

职责：把“可重试的 Provider 请求最终耗尽预算”表达为稳定的应用级异常，保留原始异常
和尝试次数，供 Agent Runtime 决定 Stop Reason、Trace 和面向用户的提示。

明确不负责：不决定是否重试、不执行模型请求、不生成用户文案，也不处理工具失败。
"""


class ModelRetryExhaustedError(RuntimeError):
    """模型请求的可重试错误在允许次数内始终未恢复。"""

    def __init__(self, last_error: Exception, attempts: int) -> None:
        self.last_error = last_error
        self.attempts = attempts
        super().__init__(
            f"Model request failed after {attempts} attempts: "
            f"{last_error.__class__.__name__}"
        )
