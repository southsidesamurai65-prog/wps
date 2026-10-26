"""主窗口参数区按功能动态显示的 spec。"""

from __future__ import annotations

import pytest

from wps_tool.core.registry import ProcessorRegistry
from wps_tool.core.runner_iface import SyncTaskRunner
from wps_tool.models.settings import Settings
from wps_tool.processors import register_default_processors
from wps_tool.ui.main_window import MainWindow


@pytest.fixture
def window(qapp):
    registry = ProcessorRegistry()
    register_default_processors(registry)
    win = MainWindow(
        registry=registry,
        runner=SyncTaskRunner(),
        settings=Settings(_env_file=None),
    )
    yield win
    win.close()


def test_params_follow_selected_action(window):
    cases = {
        "extract_text": set(),
        "scan": set(),
        "compress": {"quality"},
        "resize": {"size"},
        "rotate": {"angle"},
        "rotate_image": {"angle"},
        "extract_pages": {"pages"},
        "to_images": {"zoom"},
        "encrypt": {"password"},
        "decrypt": {"password"},
        "watermark": {"watermark"},
        "remove_watermark": {"watermark"},
        "convert": {"format"},
        "replace": {"replace"},
        "replace_tokens": {"replace"},
    }
    for action, expected in cases.items():
        index = window.action_combo.findData(action)
        assert index >= 0, f"功能下拉缺少 {action}"
        window.action_combo.setCurrentIndex(index)
        visible = {
            key
            for key, widget in window._param_widgets.items()
            if not widget.isHidden()
        }
        assert visible == expected, action
        assert window._row2_box.isHidden() == (not expected), action
        assert window.param_hint.text(), action
