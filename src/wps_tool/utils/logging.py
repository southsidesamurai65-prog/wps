"""日志配置（已写好，学生不要改）。

用 loguru 统一输出，并内置隐私脱敏 filter：把日志消息里的手机号 / 邮箱替换成占位符。
注意：脱敏是兜底，调用方仍应避免把文档正文 / 完整路径中的敏感段写进日志。
"""

from __future__ import annotations

import re
import sys

from loguru import logger

# 敏感模式：手机号、邮箱。可按需扩展（身份证、银行卡等）。
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"1[3-9]\d{9}"), "[phone]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
]


def redact(text: str) -> str:
    """把文本中的手机号 / 邮箱替换成占位符。"""
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _privacy_filter(record: dict) -> bool:
    """loguru filter：脱敏后再写。返回 True 表示放行。"""
    record["message"] = redact(record["message"])
    return True


def setup_logging(level: str = "INFO") -> logger:
    """配置 loguru：移除默认 handler、加带脱敏的 stderr handler。"""
    logger.remove()
    logger.add(sys.stderr, level=level, filter=_privacy_filter)
    return logger


__all__ = ["logger", "redact", "setup_logging"]
