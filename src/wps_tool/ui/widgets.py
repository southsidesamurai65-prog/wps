"""UI 组件（已写好，学生不要改）。

- DropArea：拖拽区，拖入文件后发 files_dropped 信号；
- FileTable：文件列表表格（文件/类型/操作/状态）；
- build_job_func：构造交给 Runner 的 job 函数（func(progress, ...) 签名），
  它内部走 Registry → Processor。是 UI 与三层 TODO 的接线点。

这些组件不直接处理文件，只负责界面与把任务交给 Runner（经 TaskSignals 回调）。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

# 扩展名 → 默认操作，供 UI 预填操作列。
_DEFAULT_ACTION: dict[str, str] = {
    ".pdf": "extract_text",
    ".docx": "extract_text",
    ".pptx": "extract_text",
    ".png": "to_pdf",
    ".jpg": "to_pdf",
    ".jpeg": "to_pdf",
}


def default_action_for(file_path: str) -> str:
    return _DEFAULT_ACTION.get(Path(file_path).suffix.lower(), "extract_text")


class DropArea(QFrame):
    """拖拽导入区：拖入文件后发 files_dropped(list[str])。"""

    files_dropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setAcceptDrops(True)
        self.setMinimumHeight(90)
        label = QLabel("把文件拖到这里，或点击「打开文件」选择")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn = QPushButton("打开文件…")
        btn.clicked.connect(self._open_dialog)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    # ---- 拖拽事件 ----
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragOver", True)
            self.style().polish(self)

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("dragOver", False)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("dragOver", False)
        self.style().polish(self)
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()

    def _open_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文件",
            "",
            "文档 (*.pdf *.docx *.pptx *.png *.jpg *.jpeg);;所有文件 (*.*)",
        )
        if paths:
            self.files_dropped.emit(paths)


class FileTable(QTableWidget):
    """文件列表：列 = [文件, 类型, 操作, 状态]。行存 job_id（用 Qt.UserRole）。"""

    COLUMNS = ["文件", "类型", "操作", "状态"]

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # job_id -> 完整路径（表格只显示文件名，真实路径存这里）
        self._paths: dict[str, str] = {}

    def add_files(self, paths: list[str]) -> list[tuple[str, str]]:
        """把文件加进表格，返回 [(job_id, file_path), ...] 供调用方建 job。"""
        added = []
        import uuid

        for p in paths:
            row = self.rowCount()
            self.insertRow(row)
            ext = Path(p).suffix.lower()
            job_id = uuid.uuid4().hex[:8]
            self._paths[job_id] = p
            name_item = QTableWidgetItem(Path(p).name)
            name_item.setData(Qt.ItemDataRole.UserRole, job_id)
            self.setItem(row, 0, name_item)
            self.setItem(row, 1, QTableWidgetItem(ext or "?"))
            self.setItem(row, 2, QTableWidgetItem(default_action_for(p)))
            self.setItem(row, 3, QTableWidgetItem("等待中"))
            added.append((job_id, p))
        return added

    def path_for(self, job_id: str) -> str | None:
        """返回该 job 对应的完整文件路径。"""
        return self._paths.get(job_id)

    def row_for_job(self, job_id: str) -> int:
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == job_id:
                return row
        return -1

    def set_status(self, job_id: str, status: str) -> None:
        row = self.row_for_job(job_id)
        if row >= 0:
            self.item(row, 3).setText(status)


def build_job_func(registry, file_path: str, action: str, options: dict):
    """构造交给 Runner 的 job 函数，签名 func(progress) -> Any。

    它是 UI 与三层 TODO 的接线点：内部 registry.get_processor(file_path)
    （Layer b）→ processor.run(file_path, action, options)（Layer a）。
    两层 TODO 未实现时这里会抛 NotImplementedError，由 Runner 转成 failed 信号。
    """

    def job(progress):
        progress(0.0, "开始处理")
        processor = registry.get_processor(file_path)
        result = processor.run(file_path, action, options)
        progress(1.0, "完成")
        return result

    return job


__all__ = ["DropArea", "FileTable", "build_job_func", "default_action_for"]
