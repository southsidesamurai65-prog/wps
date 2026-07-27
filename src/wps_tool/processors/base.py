"""文件处理器抽象基类（已写好，学生不要改）。

FileProcessor 定义统一接口：can_handle（默认按扩展名命中）+ run（按 action 分派）。
所有具体处理器（Pdf/Docx/Pptx/Image）继承它，run 体内分派到 Layer (a) 的 TODO 函数。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class FileProcessor(ABC):
    """所有文件处理器的统一接口。"""

    #: 该处理器能处理的扩展名集合（小写，含点，如 {".pdf"}）。
    supported_extensions: set[str] = set()

    def can_handle(self, file_path: str) -> bool:
        """是否处理该文件。默认按扩展名命中（已写好，学生不要改）。

        子类一般不用重写它，只要把 supported_extensions 填对即可。
        """
        return Path(file_path).suffix.lower() in self.supported_extensions

    @abstractmethod
    def run(self, file_path: str, action: str, options: dict) -> Any:
        """执行 action，返回结果（路径 str / 路径列表 / 文本 str 等，依 action 而定）。

        具体处理器的 run 已写好为「分派胶水」：用 match action 把请求路由到
        本模块的 Layer (a) TODO 函数。学生实现那些函数即可，不用改 run。
        """
        raise NotImplementedError


__all__ = ["FileProcessor"]
