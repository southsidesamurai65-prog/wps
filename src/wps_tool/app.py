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

from wps_tool.core.errors import ApiUnavailableError
from wps_tool.core.registry import ProcessorRegistry
from wps_tool.core.runner_iface import Runner, SyncTaskRunner
from wps_tool.models.settings import Settings
from wps_tool.processors import register_default_processors
from wps_tool.services.ppt_beautify_api import PptBeautifyClient
from wps_tool.ui.main_window import MainWindow
from wps_tool.ui.theme import apply_theme
from wps_tool.utils.logging import logger, setup_logging


def build_runner(settings: Settings) -> Runner:
    """构造任务执行器。

    默认用 SyncTaskRunner 兜底。学生实现 TaskRunner 后改用：
        from wps_tool.core.task import TaskRunner
        return TaskRunner(max_workers=settings.task_max_workers)
    """
    logger.info(
        "构造任务执行器: runner=SyncTaskRunner max_workers={}",
        1,
    )
    return SyncTaskRunner(max_workers=1)


def build_beautify_client(settings: Settings) -> PptBeautifyClient | None:
    """构造 PPT 美化客户端（LLM + 本地渲染）。

    隐私原则：pptx 二进制不出本机，美化只把每页「文本」发给 LLM。
    ``ENABLE_API_UPLOAD`` 是「允许把内容发出本机」总开关（LLM 把文本发出本机，归它管）；
    只有 ``enable_api_upload=true`` **且** ``llm_configured()``（provider + key 都非空）
    时才构造客户端，否则返回 None——MainWindow 的「美化」按钮会提示未配置，不触发任何网络请求。
    """
    if not settings.enable_api_upload:
        logger.warning(
            "PPT 美化客户端未创建: ENABLE_API_UPLOAD=false, 不会发起 API 请求"
        )
        return None
    if not settings.llm_configured():
        logger.warning(
            "PPT 美化客户端未创建: LLM 配置不完整 provider_set={} api_key_set={}",
            bool(settings.llm_provider),
            bool(settings.llm_api_key),
        )
        return None
    logger.info(
        "PPT 美化客户端准备创建: provider={} model={} base_url={}",
        settings.llm_provider,
        settings.llm_model,
        settings.llm_base_url,
    )
    try:
        return PptBeautifyClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            provider=settings.llm_provider,
            base_url=settings.llm_base_url,
        )
    except ApiUnavailableError:
        logger.exception(
            "PPT 美化客户端创建失败: provider={} model={} base_url={}",
            settings.llm_provider,
            settings.llm_model,
            settings.llm_base_url,
        )
        return None


def main() -> int:
    setup_logging()
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)

    settings = Settings()
    logger.info(
        "应用配置加载: enable_api_upload={} llm_provider={} llm_model={} llm_base_url={} api_key_set={}",
        settings.enable_api_upload,
        settings.llm_provider,
        settings.llm_model,
        settings.llm_base_url,
        bool(settings.llm_api_key),
    )
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
