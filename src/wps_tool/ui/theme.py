"""QSS 样式（已写好，学生不要改）。给主窗口一套简洁的暗/亮中性配色。"""

from __future__ import annotations

QSS = """
QWidget { font-size: 13px; }
QMainWindow, QDialog { background: #f5f5f7; }
QToolBar { background: #ffffff; border-bottom: 1px solid #e2e2e6; spacing: 6px; padding: 4px; }
QListWidget, QTableWidget { background: #ffffff; border: 1px solid #e2e2e6; border-radius: 4px; }
QTableWidget::item { padding: 4px; }
QGroupBox { font-weight: 600; border: 1px solid #e2e2e6; border-radius: 4px; margin-top: 10px; padding-top: 10px; }
QGroupBox::title { left: 10px; padding: 0 4px; }
QPushButton { padding: 6px 14px; border-radius: 4px; background: #e8e8ed; border: 1px solid #d4d4da; }
QPushButton:default { background: #2563eb; color: #ffffff; border: 1px solid #1d4ed8; }
QPushButton:disabled { color: #9aa0a6; background: #eeeeef; }
QProgressBar { border: 1px solid #e2e2e6; border-radius: 4px; text-align: center; height: 18px; }
QProgressBar::chunk { background: #2563eb; border-radius: 3px; }
#DropArea { border: 2px dashed #b9b9c0; border-radius: 6px; background: #fafafa; }
#DropArea[dragOver="true"] { border-color: #2563eb; background: #eef2ff; }
QStatusBar { background: #ffffff; border-top: 1px solid #e2e2e6; }
"""


def apply_theme(app) -> None:
    app.setStyleSheet(QSS)


__all__ = ["QSS", "apply_theme"]
