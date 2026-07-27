"""任务执行器接口层（已写好，是三层 TODO 解耦的锚点）。

本文件定义：
- TaskSignals：跨线程通信的 Qt 信号面，UI 连接这些信号更新界面；
- Runner：执行器的稳定 Protocol，UI 依赖此类型；
- SyncTaskRunner：已写好的同步兜底执行器，实现 Runner。

学生实现 core/task.py::TaskRunner 时照此接口填体。
线程安全不变量（UI 写死所依赖）：
  1. worker 线程只 emit 信号，绝不直接碰 QWidget / QAbstractItemModel；
  2. TaskSignals 是 QObject、在主线程构造，worker emit 的信号被 Qt 自动判为
     Queued 连接投递到主线程槽——无需手动 invokeMethod；
  3. submit 立即返回 job_id，不阻塞；失败只走 failed 信号，不向 submit 调用方抛异常。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from PySide6.QtCore import QObject, Signal


class TaskSignals(QObject):
    """任务执行过程中的信号面。UI 连接这些信号来更新进度条、状态、结果列表。"""

    started = Signal(str)            # job_id：任务开始
    progress = Signal(float, str)    # (fraction 0..1, human message)
    finished = Signal(str, object)   # (job_id, result)
    failed = Signal(str, str)        # (job_id, error message)


class Runner(Protocol):
    """任务执行器的稳定接口。UI 依赖此类型，TaskRunner / SyncTaskRunner 都满足它。"""

    signals: TaskSignals
    max_workers: int

    def submit(
        self,
        job_id: str,
        func: Callable[..., Any],
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> str:
        """提交一个任务，立即返回 job_id（不阻塞）。

        func 的签名必须是 ``func(progress, *args, **kwargs) -> Any``：
        执行器会把一个 progress 回调作为第一个位置参数注入。
        progress(frac: float, msg: str) 内部 emit signals.progress。
        不关心进度的 job 也得收下 progress 再忽略。
        """

    def cancel(self, job_id: str) -> bool:
        """取消任务。只能取消排队中尚未开始的；运行中任务尽力而为。返回是否成功取消。"""

    def shutdown(self) -> None:
        """关闭执行器，排空所有线程。"""


class SyncTaskRunner:
    """同步兜底执行器（已写好）。

    - submit 时在调用线程内同步执行 func、同步 emit 信号。
    - 用途：TaskRunner TODO 未实现时让 UI 仍能端到端跑通；也作学生参考对照。
    - 注意：同步执行会阻塞调用线程，真实并发执行请实现 core/task.py::TaskRunner。
    """

    def __init__(self, max_workers: int = 1) -> None:
        self.max_workers = max_workers
        self.signals = TaskSignals()

    def submit(
        self,
        job_id: str,
        func: Callable[..., Any],
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> str:
        kwargs = kwargs or {}
        self.signals.started.emit(job_id)

        def progress(frac: float, msg: str) -> None:
            self.signals.progress.emit(frac, msg)

        try:
            result = func(progress, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — 失败统一走 failed 信号
            self.signals.failed.emit(job_id, repr(exc))
            return job_id
        self.signals.finished.emit(job_id, result)
        return job_id

    def cancel(self, job_id: str) -> bool:
        # 同步执行无排队任务，无法取消正在执行中的任务。
        return False

    def shutdown(self) -> None:
        # 同步执行无需排空线程池。
        return None
