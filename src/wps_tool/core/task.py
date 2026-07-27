"""任务执行器。

Layer (c) TODO：TaskRunner 的 submit / _worker / cancel / shutdown。
接口契约见 core/runner_iface.py（TaskSignals / Runner Protocol / SyncTaskRunner）。

为什么 TaskRunner 是 TODO：它是「UI 不卡死 + 后台并发 + 进度回调」的核心。
学会这步就理解了 Qt 跨线程信号 + ThreadPoolExecutor。
用 tests/_fakes.py::fake_job 注入，无需 Registry/Processor 即可独立测试
（见 test_task_runner.py）。

实现时可参考 core/runner_iface.py::SyncTaskRunner 的同步版本，
区别在于你要用 ThreadPoolExecutor 让 func 在 worker 线程跑、submit 立即返回。
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from wps_tool.core.runner_iface import TaskSignals


class TaskRunner:
    """基于 ThreadPoolExecutor 的并发任务执行器（学生实现）。"""

    def __init__(self, max_workers: int = 2) -> None:
        self.max_workers = max_workers
        self.signals = TaskSignals()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: dict[str, Future] = {}

    def submit(
        self,
        job_id: str,
        func: Callable[..., Any],
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> str:
        """[学习·Layer (c) TODO] 排队 + 并发 + 进度回调，立即返回 job_id（不阻塞）。

        契约（照此实现，UI 已写好依赖这些行为）：
          1. self.signals.started.emit(job_id) 立即发；
          2. 构造 progress 回调：
                progress = lambda f, m: self.signals.progress.emit(f, m)
             注意 emit 是线程安全的（Queued 连接），worker 线程直接调即可；
          3. future = self._executor.submit(self._worker, job_id, func, args, kwargs or {}, progress)；
          4. self._futures[job_id] = future；
          5. 立即 return job_id（绝不在这里等待结果）。

        提示：不要在 submit 里 emit finished/failed，那是 _worker 的事。
        """
        self.signals.started.emit(job_id)
        progress = lambda f, m: self.signals.progress.emit(f, m)
        future = self._executor.submit(self._worker, job_id, func, args, kwargs or {}, progress)
        self._futures[job_id] = future
        return job_id

    def _worker(
        self,
        job_id: str,
        func: Callable[..., Any],
        args: tuple,
        kwargs: dict,
        progress: Callable[[float, str], None],
    ) -> Any:
        """[学习·Layer (c) TODO] worker 线程里真正执行 func，并把结果/失败转成信号。

        契约：
          try:
              result = func(progress, *args, **kwargs)
              self.signals.finished.emit(job_id, result)
              return result
          except Exception as exc:
              self.signals.failed.emit(job_id, repr(exc))
              raise   # 让 Future 标记为失败；submit 的调用方看不到这个异常（它只看信号）

        提示：except 里 raise 是有意的——让 future.result() 能感知失败，
        测试里用 future.result(timeout=...) 阻塞到完成。
        """
        try:
            result = func(progress, *args, **kwargs)
            self.signals.finished.emit(job_id, result)
            return result
        except Exception as exc:
            self.signals.failed.emit(job_id, repr(exc))
            raise   # 让 Future 标记为失败；submit 的调用方看不到这个异常（它只看信号）
        raise NotImplementedError("TODO(Layer c): 实现 TaskRunner._worker")

    def cancel(self, job_id: str) -> bool:
        """[学习·Layer (c) TODO] 取消排队中未开始的任务，返回是否成功。

        契约：future = self._futures.get(job_id); return future.cancel() if future else False。
        提示：Future.cancel() 只能取消尚未开跑的；运行中任务无法强杀（M1–M3 不要求）。
        """
        future = self._futures.get(job_id)
        return future.cancel() if future else False
        raise NotImplementedError("TODO(Layer c): 实现 TaskRunner.cancel")

    def shutdown(self) -> None:
        """[学习·Layer (c) TODO] 关闭线程池，排空所有任务。

        契约：self._executor.shutdown(wait=True)。
        """
        self._executor.shutdown(wait=True)


__all__ = ["TaskRunner"]
