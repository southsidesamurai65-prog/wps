"""QSS 样式：本地工具箱的现代浅色主题（较大字号，便于长时间使用）。"""

from __future__ import annotations

QSS = """
* {
    font-family: "Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC",
                 "Source Han Sans SC", "Segoe UI", sans-serif;
    font-size: 15px;
    color: #1f2329;
}

QMainWindow, QDialog { background: #f3f5f9; }

/* ---- 顶部工具栏 ---- */
QToolBar {
    background: #ffffff;
    border: none;
    border-bottom: 1px solid #e4e8ef;
    spacing: 8px;
    padding: 8px 10px;
}
QToolBar QToolButton {
    padding: 7px 14px;
    border: 1px solid transparent;
    border-radius: 7px;
    background: transparent;
}
QToolBar QToolButton:hover { background: #eef2f8; }
QToolBar QToolButton:pressed { background: #e2e8f2; }

/* ---- 输入控件 ---- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #d7dce6;
    border-radius: 7px;
    padding: 6px 10px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #2563eb;
}
QLineEdit:disabled, QComboBox:disabled { background: #f1f3f7; color: #9aa1ad; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #d7dce6;
    border-radius: 7px;
    padding: 4px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: 0;
}

/* ---- 按钮 ---- */
QPushButton {
    padding: 8px 18px;
    border-radius: 7px;
    background: #eef1f6;
    border: 1px solid #d7dce6;
    font-weight: 500;
}
QPushButton:hover { background: #e2e8f2; }
QPushButton:pressed { background: #d5dceb; }
QPushButton:default {
    background: #2563eb;
    color: #ffffff;
    border: 1px solid #1d4ed8;
}
QPushButton:default:hover { background: #1d4ed8; }
QPushButton:disabled { color: #9aa1ad; background: #f1f3f7; border-color: #e4e8ef; }

/* ---- 表格 ---- */
QTableWidget {
    background: #ffffff;
    border: 1px solid #e4e8ef;
    border-radius: 10px;
    gridline-color: #eef1f6;
    outline: 0;
}
QTableWidget::item { padding: 7px 6px; }
QTableWidget::item:selected { background: #e8efff; color: #1f2329; }
QHeaderView::section {
    background: #f7f9fc;
    color: #5a6270;
    border: none;
    border-bottom: 1px solid #e4e8ef;
    padding: 8px 6px;
    font-weight: 600;
}

/* ---- 结果区 ---- */
QTextEdit {
    background: #ffffff;
    border: 1px solid #e4e8ef;
    border-radius: 10px;
    padding: 8px;
}

/* ---- 进度条 ---- */
QProgressBar {
    border: 1px solid #e4e8ef;
    border-radius: 8px;
    background: #ffffff;
    text-align: center;
    height: 22px;
}
QProgressBar::chunk { background: #2563eb; border-radius: 7px; }

/* ---- 拖拽区 ---- */
#DropArea {
    border: 2px dashed #c3cad6;
    border-radius: 12px;
    background: #fafbfd;
}
#DropArea[dragOver="true"] { border-color: #2563eb; background: #eef2ff; }

/* ---- 状态栏 ---- */
QStatusBar {
    background: #ffffff;
    border-top: 1px solid #e4e8ef;
    color: #5a6270;
}

/* ---- 滚动条 ---- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #cfd6e2; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #b6bfce; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #cfd6e2; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #b6bfce; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""


def apply_theme(app) -> None:
    app.setStyleSheet(QSS)


__all__ = ["QSS", "apply_theme"]
