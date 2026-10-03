"""日志配置（已写好，学生不要改）。

用 loguru 统一输出，并内置隐私脱敏 filter：把日志消息里的手机号 / 邮箱替换成占位符。
注意：脱敏是兜底，调用方仍应避免把文档正文 / 完整路径中的敏感段写进日志。
"""

from __future__ import annotations

import contextlib
import os
import re
import sys
from pathlib import Path

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


def _log_file_path() -> Path | None:
    """打包成 exe 后额外写一份日志文件，便于用户排查（未打包时返回 None）。"""
    custom = os.getenv("WPS_LOG_FILE")
    if custom:
        return Path(custom)
    if not getattr(sys, "frozen", False):
        return None
    for folder in (Path(sys.executable).resolve().parent, Path.home() / ".wps-tool"):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            return folder / "wps-tool.log"
        except OSError:
            continue
    return None


def setup_logging(level: str | None = None) -> logger:
    """配置 loguru：移除默认 handler、加带脱敏的 stderr handler（打包后另加文件日志）。"""
    effective_level = (
        level or os.getenv("WPS_LOG_LEVEL") or os.getenv("LOG_LEVEL") or "INFO"
    ).upper()
    logger.remove()
    logger.add(sys.stderr, level=effective_level, filter=_privacy_filter)
    log_path = _log_file_path()
    if log_path is not None:
        with contextlib.suppress(OSError):
            logger.add(
                str(log_path),
                level=effective_level,
                filter=_privacy_filter,
                rotation="1 MB",
                retention=3,
                encoding="utf-8",
            )
    return logger


__all__ = ["logger", "redact", "setup_logging"]
