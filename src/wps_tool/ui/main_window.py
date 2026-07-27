"""主窗口（已写好，学生不要改）。

布局（README 第 6 节）：
    +------------------------------------------------+
    | 顶部工具栏：打开文件 / 输出目录 / 设置          |
    +------------------+-----------------------------+
    | 左侧功能栏        | 主工作区                    |
    |  - PDF 工具      |  拖拽区                      |
    |  - Word 工具     |  文件表                      |
    |  - PPT 工具      |  参数区（操作/输出目录）     |
    |  - 批量任务      |  进度区                      |
    +------------------+-----------------------------+
    | 状态栏                                          |
    +------------------------------------------------+

接线点：MainWindow 持有 Registry + Runner（SyncTaskRunner 兜底），
点击「处理」时用 widgets.build_job_func 构造 job 交给 runner.submit，
通过 Runner 的 TaskSignals 回调更新文件表 / 进度条。三层 TODO 未实现时，
相关任务会经 failed 信号显示失败原因——UI 本身不阻塞、不崩。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from wps_tool.models.settings import Settings
from wps_tool.ui.widgets import DropArea, FileTable, build_job_func


class MainWindow(QMainWindow):
    def __init__(self, registry, runner, settings: Settings) -> None:
        super().__init__()
        self.registry = registry
        self.runner = runner
        self.settings = settings
        self.setWindowTitle("WPS 工具 — 本地 Office/PDF 处理")
        self.resize(960, 640)

        self._build_toolbar()
        self._build_central()
        self._wire_signals()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("就绪。把文件拖进来开始。")

    # ---- 顶部工具栏 ----
    def _build_toolbar(self) -> None:
        tb = self.addToolBar("主工具栏")
        tb.setMovable(False)
        tb.addAction("打开文件…", self._on_open_files)
        tb.addAction("设置输出目录…", self._on_pick_output_dir)
        tb.addSeparator()
        tb.addAction("清空列表", self._on_clear_list)

    # ---- 中央区 ----
    def _build_central(self) -> None:
        central = QWidget(self)
        root = QHBoxLayout(central)

        # 左侧功能栏（仅作分类提示，操作在参数区）
        self.sidebar = QListWidget()
        self.sidebar.setMaximumWidth(150)
        for label in ("PDF 工具", "Word 工具", "PPT 工具", "批量任务", "设置"):
            self.sidebar.addItem(label)
        root.addWidget(self.sidebar)

        # 右侧主工作区
        right = QVBoxLayout()
        self.drop_area = DropArea()
        right.addWidget(self.drop_area)

        self.table = FileTable()
        right.addWidget(self.table, stretch=1)

        right.addWidget(self._build_params())
        right.addWidget(self._build_progress())
        root.addLayout(right, stretch=1)

        self.setCentralWidget(central)

    def _build_params(self) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.addWidget(QLabel("操作:"))
        self.action_combo = QComboBox()
        self.action_combo.addItems(
            ["extract_text", "to_images", "split", "rotate", "to_pdf", "compress"]
        )
        row.addWidget(self.action_combo)
        row.addSpacing(12)
        row.addWidget(QLabel("输出目录:"))
        self.output_edit = QLineEdit(self.settings.default_output_dir or "")
        self.output_edit.setPlaceholderText("留空 = 源文件旁 processed/")
        row.addWidget(self.output_edit, stretch=1)
        self.run_btn = QPushButton("处理选中行")
        self.run_btn.setDefault(True)
        self.run_btn.clicked.connect(self._on_run_selected)
        row.addWidget(self.run_btn)
        self.merge_btn = QPushButton("合并选中 PDF")
        self.merge_btn.clicked.connect(self._on_merge_selected)
        row.addWidget(self.merge_btn)
        return box

    def _build_progress(self) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 4, 0, 4)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("等待任务")
        lay.addWidget(self.progress_bar)
        lay.addWidget(self.progress_label)
        return box

    # ---- 信号接线 ----
    def _wire_signals(self) -> None:
        self.drop_area.files_dropped.connect(self._on_files_dropped)
        sig = self.runner.signals
        sig.started.connect(self._on_started)
        sig.progress.connect(self._on_progress)
        sig.finished.connect(self._on_finished)
        sig.failed.connect(self._on_failed)

    # ---- 事件处理 ----
    def _on_open_files(self) -> None:
        self.drop_area._open_dialog()  # 复用 DropArea 的文件对话框

    def _on_files_dropped(self, paths: list[str]) -> None:
        added = self.table.add_files(paths)
        for job_id, _p in added:
            self.table.set_status(job_id, "等待中")
        self.statusBar().showMessage(f"已加入 {len(added)} 个文件。")

    def _on_pick_output_dir(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.output_edit.setText(d)

    def _on_clear_list(self) -> None:
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.progress_label.setText("等待任务")

    def _on_run_selected(self) -> None:
        rows = {i.row() for i in self.table.selectedIndexes()}
        if not rows:
            self.statusBar().showMessage("请先在表格里选中要处理的行。")
            return
        action = self.action_combo.currentText()
        out_dir = self.output_edit.text().strip()
        submitted = 0
        for row in sorted(rows):
            job_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            file_path = self.table.path_for(job_id)
            if not file_path:
                continue
            options = {} if action == "extract_text" else {"output_dir": out_dir}
            self._submit_job(job_id, file_path, action, options)
            submitted += 1
        self.statusBar().showMessage(f"已提交 {submitted} 个任务。")

    def _on_merge_selected(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        job_ids = [self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows]
        inputs = [self.table.path_for(jid) for jid in job_ids if jid]
        inputs = [p for p in inputs if p]
        if len(inputs) < 2:
            self.statusBar().showMessage("合并至少需要选中 2 个 PDF。")
            return
        out_dir = self.output_edit.text().strip() or str(Path(inputs[0]).parent / "processed")
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        output = str(Path(out_dir) / "merged.pdf")
        import uuid

        job_id = uuid.uuid4().hex[:8]
        # merge 的 job 不依赖单文件，直接构造
        def job(progress):
            progress(0.0, "开始合并")
            processor = self.registry.get_processor(inputs[0])
            result = processor.run(inputs[0], "merge", {"inputs": inputs, "output": output})
            progress(1.0, "合并完成")
            return result

        self.runner.submit(job_id, job)
        self.statusBar().showMessage(f"已提交合并任务 {job_id}。")

    def _submit_job(self, job_id: str, file_path: str, action: str, options: dict) -> None:
        job = build_job_func(self.registry, file_path, action, options)
        self.runner.submit(job_id, job)

    # ---- Runner 信号回调（在主线程执行） ----
    def _on_started(self, job_id: str) -> None:
        self.table.set_status(job_id, "处理中")

    def _on_progress(self, frac: float, msg: str) -> None:
        self.progress_bar.setValue(int(frac * 100))
        self.progress_label.setText(msg)

    def _on_finished(self, job_id: str, result) -> None:
        self.table.set_status(job_id, "成功")
        self.statusBar().showMessage(f"{job_id} 完成。")

    def _on_failed(self, job_id: str, msg: str) -> None:
        self.table.set_status(job_id, f"失败: {msg[:40]}")
        self.statusBar().showMessage(f"{job_id} 失败：{msg}")

    def closeEvent(self, event) -> None:
        try:
            self.runner.shutdown()
        except NotImplementedError:
            # SyncTaskRunner 已写好不会抛；学生 TaskRunner 未实现 shutdown 时跳过。
            pass
        super().closeEvent(event)


__all__ = ["MainWindow"]
