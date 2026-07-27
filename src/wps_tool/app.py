"""应用入口（已写好，学生不要改）。

装配 QApplication + 配置 + Registry + Runner + MainWindow。

关于 Runner 的选择（重要）：
  Layer (c) 的 TaskRunner（core/task.py）未实现前，这里用 SyncTaskRunner 兜底，
  保证「实现 a + b 后」UI 就能端到端跑通拖拽→处理。
  学生实现完 core/task.py::TaskRunner 后，把 build_runner 里换成
      return TaskRunner(max_workers=settings.task_max_workers)
  即可启用后台并发执行（UI 不卡死 + 进度条实时更新）。
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from wps_tool.core.registry import ProcessorRegistry
from wps_tool.core.runner_iface import Runner, SyncTaskRunner
from wps_tool.models.settings import Settings
from wps_tool.processors import register_default_processors
from wps_tool.services.ppt_beautify_api import PptBeautifyClient
from wps_tool.ui.main_window import MainWindow
from wps_tool.ui.theme import apply_theme
from wps_tool.utils.logging import setup_logging


def build_runner(settings: Settings) -> Runner:
    """构造任务执行器。

    默认用 SyncTaskRunner 兜底。学生实现 TaskRunner 后改用：
        from wps_tool.core.task import TaskRunner
        return TaskRunner(max_workers=settings.task_max_workers)
    """
    return SyncTaskRunner(max_workers=1)


def build_beautify_client(settings: Settings) -> PptBeautifyClient | None:
    """构造 PPT 美化外部 API 客户端。

    隐私原则：默认不上传任何内容到外部。只有当用户在 .env 里显式
    ``ENABLE_API_UPLOAD=true`` 且填写了 url + key 时才构造客户端，
    否则返回 None——MainWindow 的「美化」按钮会提示未配置，不触发任何网络请求。
    """
    if not settings.enable_api_upload:
        return None
    if not settings.api_configured():
        return None
    return PptBeautifyClient(
        base_url=settings.ppt_beautify_base_url,
        api_key=settings.ppt_beautify_api_key,
    )


def main() -> int:
    setup_logging()
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)

    settings = Settings()
    registry = ProcessorRegistry()
    register_default_processors(registry)
    runner = build_runner(settings)
    beautify_client = build_beautify_client(settings)

    win = MainWindow(
        registry=registry,
        runner=runner,
        settings=settings,
        beautify_client=beautify_client,
    )
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
