"""日志配置 spec：窗口化打包（console=False）时 sys.stderr 可能为 None，不能崩。"""

from __future__ import annotations


def test_setup_logging_without_stderr(monkeypatch, tmp_path):
    from wps_tool.utils import logging as wlogging

    log_file = tmp_path / "wps.log"
    monkeypatch.setattr(wlogging.sys, "stderr", None)
    monkeypatch.setenv("WPS_LOG_FILE", str(log_file))

    wlogging.setup_logging()  # 回归：以前这里抛 TypeError: Cannot log to 'NoneType'
    wlogging.logger.info("hello")

    assert log_file.exists()
    assert "hello" in log_file.read_text(encoding="utf-8")


def test_setup_logging_without_stderr_or_file(monkeypatch):
    from wps_tool.utils import logging as wlogging

    monkeypatch.setattr(wlogging.sys, "stderr", None)
    monkeypatch.delenv("WPS_LOG_FILE", raising=False)

    wlogging.setup_logging()  # 无 stderr 也无文件时不崩（消息直接丢弃）
