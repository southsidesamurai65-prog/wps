"""任务执行器 spec（Layer c）。

- test_sync_task_runner_smoke：SyncTaskRunner（已写好兜底）首日即绿——证明接口与夹具本身无误。
- 其余用学生 TaskRunner，未实现时因 NotImplementedError 红。
"""

from __future__ import annotations

import time

import pytest
from _fakes import failing_job, fake_job

from wps_tool.core.runner_iface import SyncTaskRunner
from wps_tool.core.task import TaskRunner


def test_sync_task_runner_smoke(qapp):
    """绿色基线：SyncTaskRunner 同步执行并 emit 全套信号。"""
    runner = SyncTaskRunner()
    events: list[tuple] = []
    runner.signals.started.connect(lambda j: events.append(("start", j)))
    runner.signals.progress.connect(lambda f, m: events.append(("p", f, m)))
    runner.signals.finished.connect(lambda j, r: events.append(("done", r)))
    runner.signals.failed.connect(lambda j, m: events.append(("fail", m)))

    runner.submit("s1", fake_job, args=(21,))
    assert ("start", "s1") in events
    assert ("p", 0.5, "half") in events
    assert ("done", 42) in events
    assert not any(e[0] == "fail" for e in events)


def test_taskrunner_emits_progress_and_finished(qapp):
    runner = TaskRunner(max_workers=1)
    events: list[tuple] = []
    runner.signals.progress.connect(lambda f, m: events.append(("p", f, m)))
    runner.signals.finished.connect(lambda j, r: events.append(("done", r)))
    runner.signals.failed.connect(lambda j, m: events.append(("fail", m)))

    runner.submit("j1", fake_job, args=(21,))
    runner._futures["j1"].result(timeout=5)
    qapp.processEvents()  # 把跨线程 queued 信号 flush 到主线程槽

    assert ("p", 0.5, "half") in events
    assert ("done", 42) in events
    assert not any(e[0] == "fail" for e in events)
    runner.shutdown()


def test_taskrunner_failed_signal(qapp):
    runner = TaskRunner(max_workers=1)
    events: list[tuple] = []
    runner.signals.failed.connect(lambda j, m: events.append(("fail", m)))
    runner.signals.finished.connect(lambda j, r: events.append(("done", r)))

    runner.submit("f1", failing_job)
    fut = runner._futures["f1"]
    with pytest.raises(RuntimeError):
        fut.result(timeout=5)
    qapp.processEvents()

    assert any(e[0] == "fail" for e in events)
    assert not any(e[0] == "done" for e in events)
    runner.shutdown()


def test_taskrunner_cancel_queued(qapp):
    """max_workers=1 时，第二个任务应排在队列里，cancel 返回 True。"""
    runner = TaskRunner(max_workers=1)

    def long_job(progress):
        progress(0.0, "start")
        time.sleep(0.3)
        return "done"

    runner.submit("j1", long_job)
    runner.submit("j2", long_job)  # 排在 j1 后面，尚未开跑
    assert runner.cancel("j2") is True
    runner._futures["j1"].result(timeout=5)
    runner.shutdown()
