"""任务数据结构（已写好，学生不要改）。

FileJob 是一个文件处理任务的描述 + 状态，UI 用它驱动列表展示与进度。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    """任务生命周期状态。"""

    PENDING = "pending"    # 等待中
    RUNNING = "running"    # 处理中
    SUCCESS = "success"    # 成功
    FAILED = "failed"      # 失败


@dataclass
class FileJob:
    """一个文件处理任务。"""

    job_id: str
    file_path: str
    action: str
    options: dict = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    result: Any = None          # 成功时的输出（路径 / 路径列表 / 文本）
    error: str = ""             # 失败时的原因（已脱敏，不含正文）


__all__ = ["FileJob", "JobStatus"]
