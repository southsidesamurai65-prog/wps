"""处理器注册表。

Layer (b) TODO：ProcessorRegistry.get_processor 的调度逻辑。
其余（register / can_handle 胶水）已写好。

为什么 get_processor 是 TODO：它是「按文件类型分派到正确处理器」的核心调度，
学会这步就理解了注册表 + 策略模式。用 tests/_fakes.py::FakeProcessor 注入，
无需任何真实处理器即可独立测试（见 test_registry.py）。
"""

from __future__ import annotations

from wps_tool.core.errors import NoProcessorError
from wps_tool.processors.base import FileProcessor


class ProcessorRegistry:
    """已注册处理器的列表 + 按 file_path 派发。"""

    def __init__(self) -> None:
        self._processors: list[FileProcessor] = []

    def register(self, processor: FileProcessor) -> None:
        """注册一个处理器（已写好，学生不要改）。后注册的优先级靠前查找。"""
        self._processors.append(processor)

    def get_processor(self, file_path: str) -> FileProcessor:
        """[学习·Layer (b) TODO] 返回首个能处理 file_path 的处理器，否则抛 NoProcessorError。

        契约：
          - 遍历 self._processors，调用每个 p.can_handle(file_path)；
          - 命中第一个就返回它；
          - 全部不命中时 raise NoProcessorError(file_path)。

        提示：
          - can_handle 已在 FileProcessor 基类写好默认实现（按扩展名命中），
            你只要遍历 + 调它即可，不用自己判断扩展名。
          - 不要缓存结果：注册顺序可能变化。
          - 想让后注册的处理器优先（覆盖默认），可倒序遍历 self._processors[::-1]。
        """
        for p in self._processors:
            if p.can_handle(file_path):
                return p
        raise NoProcessorError(file_path)

    def can_handle(self, file_path: str) -> bool:
        """是否任一已注册处理器能处理该文件（已写好胶水，学生不要改）。"""
        try:
            self.get_processor(file_path)
            return True
        except NoProcessorError:
            return False


__all__ = ["ProcessorRegistry"]
