"""统一异常体系。

所有 wps_tool 抛出的异常都继承 WpsError，UI 层可以统一捕获并展示。
学生不需要改本文件。
"""

from __future__ import annotations


class WpsError(Exception):
    """所有 wps_tool 业务异常的基类。"""


class NoProcessorError(WpsError):
    """没有已注册处理器能处理该文件（类型不支持 / 扩展名未命中）。"""


class UnsupportedActionError(WpsError):
    """处理器不支持该 action（例如 PdfProcessor 不存在 'ocr' 操作）。"""


class ConversionError(WpsError):
    """外部转换失败（LibreOffice 转 PDF 失败 / 字体缺失等）。"""


class ApiUnavailableError(WpsError):
    """外部 API 不可用（未配置 / 隐私开关关闭 / 网络失败）。"""
