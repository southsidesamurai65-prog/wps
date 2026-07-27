"""测试替身（已写好，供 registry / task_runner 测试注入，不依赖任何真实处理器）。"""

from __future__ import annotations

from wps_tool.processors.base import FileProcessor


class FakeProcessor(FileProcessor):
    """可配置扩展名、run 返回固定值的假处理器。"""

    def __init__(self, ext: str = ".fake", result: str = "FAKE") -> None:
        self.supported_extensions = {ext}
        self._result = result

    def run(self, file_path: str, action: str, options: dict) -> str:
        return self._result


def fake_job(progress, x):
    """进度回调 + 简单计算。返回 x*2。"""
    progress(0.5, "half")
    return x * 2


def failing_job(progress):
    """先报进度再抛错，验证 failed 信号路径。"""
    progress(0.1, "before fail")
    raise RuntimeError("boom")
