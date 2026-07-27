"""端到端集成 spec。

UI job → TaskRunner.submit → Registry.get_processor → Processor.run → Layer a 函数。
三层 TODO 任一未实现时本测试会失败——xfail(strict=False) 让它在增量期不尖叫，
三层就绪后自动转绿（XPASS）。
"""

from __future__ import annotations

import pytest

from wps_tool.core.registry import ProcessorRegistry
from wps_tool.core.task import TaskRunner
from wps_tool.processors import register_default_processors
from wps_tool.ui.widgets import build_job_func


@pytest.mark.xfail(reason="需 Layer a/b/c 均实现后自动转绿", strict=False)
def test_end_to_end_extract_text(qapp, sample_pdf):
    reg = ProcessorRegistry()
    register_default_processors(reg)
    runner = TaskRunner(max_workers=1)

    results: dict = {}
    runner.signals.finished.connect(lambda j, r: results.__setitem__("r", r))
    runner.signals.failed.connect(lambda j, m: results.__setitem__("err", m))

    job = build_job_func(reg, str(sample_pdf), "extract_text", {})
    runner.submit("e2e", job)
    runner._futures["e2e"].result(timeout=10)
    qapp.processEvents()

    assert "Hello PDF World" in results.get("r", "")
    runner.shutdown()
