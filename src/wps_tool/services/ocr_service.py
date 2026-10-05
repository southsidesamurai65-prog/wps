"""OCR 服务（RapidOCR / onnxruntime，纯 pip，无需系统二进制）。

用 ``rapidocr-onnxruntime`` 做中英文 OCR：随依赖安装、可直接打进 exe，接收者无需另装引擎。
引擎首次调用时懒加载（加载模型较慢），之后复用同一实例。
"""

from __future__ import annotations

import importlib.util

# 用 find_spec 探测依赖，避免模块级 import 拉起 onnxruntime/opencv 等重库。
_HAS_RAPIDOCR = importlib.util.find_spec("rapidocr_onnxruntime") is not None

_engine = None


def ocr_available() -> bool:
    """OCR 是否可用（rapidocr-onnxruntime 已安装）。"""
    return _HAS_RAPIDOCR


def _get_engine():
    """懒加载并复用 RapidOCR 引擎（首次会加载模型，较慢）。"""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def ocr_image(image_path: str, lang: str = "chi_sim+eng") -> str:
    """对图片做 OCR，返回识别文本（行间用 ``\\n`` 连接）。

    用 RapidOCR（默认中英文模型）；``lang`` 仅为兼容旧签名，当前忽略。
    无文字时返回空串。需先确保 :func:`ocr_available` 为真。
    """
    engine = _get_engine()
    result, _elapse = engine(image_path)
    if not result:
        return ""
    return "\n".join(line[1] for line in result if len(line) > 1 and line[1])


__all__ = ["ocr_available", "ocr_image"]
