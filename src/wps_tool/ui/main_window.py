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

import contextlib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wps_tool.models.settings import Settings
from wps_tool.ui.widgets import DropArea, FileTable, build_job_func


class MainWindow(QMainWindow):
    def __init__(
        self,
        registry,
        runner,
        settings: Settings,
        beautify_client=None,
    ) -> None:
        super().__init__()
        self.registry = registry
        self.runner = runner
        self.settings = settings
        # PPT 美化外部 API 客户端（由 app.py 依配置注入；未启用时为 None）。
        # 为 None 时「美化」按钮只提示未配置，不触发任何网络请求。
        self.beautify_client = beautify_client
        self.setWindowTitle("WPS 工具 — 本地 Office/PDF 处理")
        self.resize(960, 760)

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
        right.addWidget(self._build_result(), stretch=1)
        root.addLayout(right, stretch=1)

        self.setCentralWidget(central)

    def _build_params(self) -> QWidget:
        box = QWidget()
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(4)

        # 第一行：操作 / 输出目录 / 替换映射
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("操作:"))
        self.action_combo = QComboBox()
        self.action_combo.addItems(
            [
                "extract_text",
                "analyze_structure",
                "extract_images",
                "replace",
                "replace_tokens",
                "split",
                "rotate",
                "extract_pages",
                "to_images",
                "to_pdf",
                "compress",
            ]
        )
        row1.addWidget(self.action_combo)
        row1.addSpacing(12)
        row1.addWidget(QLabel("输出目录:"))
        self.output_edit = QLineEdit(self.settings.default_output_dir or "")
        self.output_edit.setPlaceholderText("留空 = 源文件旁 processed/")
        row1.addWidget(self.output_edit, stretch=1)
        row1.addSpacing(12)
        row1.addWidget(QLabel("替换映射:"))
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("旧文本=新文本（多个用 ; 分隔，仅 replace/replace_tokens 用）")
        row1.addWidget(self.replace_edit, stretch=1)
        outer.addLayout(row1)

        # 第二行：动作参数（按选用动作生效；不用到就忽略）
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("角度:"))
        self.angle_combo = QComboBox()
        self.angle_combo.addItems(["90", "180", "270"])
        row2.addWidget(self.angle_combo)
        row2.addSpacing(12)
        row2.addWidget(QLabel("质量:"))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 95)
        self.quality_spin.setValue(85)
        self.quality_spin.setSuffix(" %")
        row2.addWidget(self.quality_spin)
        row2.addSpacing(12)
        row2.addWidget(QLabel("倍率:"))
        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(0.5, 5.0)
        self.zoom_spin.setSingleStep(0.5)
        self.zoom_spin.setValue(2.0)
        self.zoom_spin.setSuffix(" ×")
        row2.addWidget(self.zoom_spin)
        row2.addSpacing(12)
        row2.addWidget(QLabel("页码:"))
        self.pages_edit = QLineEdit()
        self.pages_edit.setPlaceholderText(
            "0,2（0-based，逗号分隔；留空=第1页，仅 extract_pages）"
        )
        row2.addWidget(self.pages_edit, stretch=1)
        outer.addLayout(row2)

        # 第三行：动作按钮
        row3 = QHBoxLayout()
        self.run_btn = QPushButton("处理选中行")
        self.run_btn.setDefault(True)
        self.run_btn.clicked.connect(self._on_run_selected)
        row3.addWidget(self.run_btn)
        self.merge_btn = QPushButton("合并选中 PDF")
        self.merge_btn.clicked.connect(self._on_merge_selected)
        row3.addWidget(self.merge_btn)
        self.beautify_btn = QPushButton("美化选中 PPT")
        self.beautify_btn.clicked.connect(self._on_beautify_selected)
        row3.addWidget(self.beautify_btn)
        row3.addStretch(1)
        outer.addLayout(row3)
        return box

    def _build_result(self) -> QWidget:
        """结果查看区：extract_text / analyze_structure 等返回的内容显示在这里。"""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(2)
        lay.addWidget(QLabel("结果（extract_text / analyze_structure / 路径等）"))
        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setPlaceholderText("处理完成后，结果会显示在这里。")
        lay.addWidget(self.result_view)
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
        self.result_view.clear()

    def _on_run_selected(self) -> None:
        rows = {i.row() for i in self.table.selectedIndexes()}
        if not rows:
            self.statusBar().showMessage("请先在表格里选中要处理的行。")
            return
        action = self.action_combo.currentText()
        raw_out = self.output_edit.text().strip()
        if action in ("replace", "replace_tokens") and not self._parse_mapping(
            self.replace_edit.text()
        ):
            self.statusBar().showMessage(
                "请在「替换映射」里填 旧文本=新文本（多个用 ; 分隔）后再处理。"
            )
            return
        submitted = 0
        for row in sorted(rows):
            job_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            file_path = self.table.path_for(job_id)
            if not file_path:
                continue
            options = self._build_options(action, file_path, raw_out)
            self._submit_job(job_id, file_path, action, options)
            submitted += 1
        self.statusBar().showMessage(f"已提交 {submitted} 个任务。")

    def _build_options(self, action: str, file_path: str, raw_out: str) -> dict:
        """按动作构造 ``processor.run`` 需要的 options。

        动作特有参数从参数区取：
          - rotate → ``angle``（角度下拉 90/180/270）；
          - to_images → ``zoom``（渲染倍率）；
          - compress → ``quality``（压缩质量）；
          - extract_pages → ``pages``（0-based 页码列表）；
          - replace / replace_tokens → ``mapping``（替换映射输入）。
        输出目录留空 → 回退到源文件旁 ``processed/``（与占位提示一致）并 ``mkdir``，
        避免往根 ``/`` 写触发 ``OSError 30`` / ``fzerror``。
        """
        if action in ("extract_text", "analyze_structure"):
            return {}
        out_dir = raw_out or str(Path(file_path).parent / "processed")
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        stem = Path(file_path).stem
        suffix = Path(file_path).suffix
        if action in ("split", "extract_images"):
            return {"output_dir": out_dir}
        if action == "to_images":
            return {"output_dir": out_dir, "zoom": self.zoom_spin.value()}
        if action == "rotate":
            return {
                "output": str(Path(out_dir) / f"{stem}_rotated.pdf"),
                "angle": int(self.angle_combo.currentText()),
            }
        if action == "extract_pages":
            return {
                "pages": self._parse_pages(self.pages_edit.text()),
                "output": str(Path(out_dir) / f"{stem}_pages.pdf"),
            }
        if action == "to_pdf":  # 图片：多图合 PDF
            return {"inputs": [file_path], "output": str(Path(out_dir) / f"{stem}.pdf")}
        if action == "compress":
            return {
                "output": str(Path(out_dir) / f"{stem}_compressed{suffix}"),
                "quality": self.quality_spin.value(),
            }
        if action in ("replace", "replace_tokens"):
            return {
                "output": str(Path(out_dir) / f"{stem}_replaced{suffix}"),
                "mapping": self._parse_mapping(self.replace_edit.text()),
            }
        return {"output_dir": out_dir}

    def _parse_mapping(self, text: str) -> dict[str, str]:
        """解析「旧文本=新文本」对，多个用 ``;`` 分隔。

        例：``{{COMPANY}}=Acme; T1=标题一`` → ``{"{{COMPANY}}": "Acme", "T1": "标题一"}``。
        空 / 无 ``=`` 的段跳过；旧文本为空也跳过。
        """
        mapping: dict[str, str] = {}
        for part in text.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            old, new = part.split("=", 1)
            old, new = old.strip(), new.strip()
            if old:
                mapping[old] = new
        return mapping

    def _parse_pages(self, text: str) -> list[int]:
        """解析「0,2,5」式 0-based 页码列表。空 → ``[0]``（第 1 页）。

        非数字段跳过；用于 extract_pages 的 ``pages`` 参数。
        """
        pages: list[int] = []
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                pages.append(int(part))
            except ValueError:
                continue
        return pages or [0]

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

    def _on_beautify_selected(self) -> None:
        """美化选中的 PPT：本地解析 → 文本发 LLM 拿 spec → 本地渲染重建 deck。

        走 ``beautify_client.beautify_file(input, output, style)``：pptx 二进制不出本机，
        只把每页文本发给 LLM，再用 python-pptx 本地重建一套干净 deck，写到
        ``processed/<文件名>_beautified.pptx``。服务方法未就绪时由 Runner 转 failed 信号提示——UI 不崩。
        """
        if self.beautify_client is None:
            self.statusBar().showMessage(
                "美化 LLM 未配置：在 .env 设 ENABLE_API_UPLOAD=true 并填写"
                " LLM_PROVIDER=openai / LLM_API_KEY（可选 LLM_MODEL）后重启。"
            )
            return
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            self.statusBar().showMessage("请先在表格里选中一个 .pptx 文件。")
            return
        if len(rows) != 1:
            self.statusBar().showMessage("美化一次只处理一个 .pptx，请只选中一行。")
            return
        job_id = self.table.item(rows[0], 0).data(Qt.ItemDataRole.UserRole)
        file_path = self.table.path_for(job_id)
        if not file_path or Path(file_path).suffix.lower() != ".pptx":
            self.statusBar().showMessage("选中的文件不是 .pptx，无法美化。")
            return

        import uuid

        client = self.beautify_client
        out_dir = self.output_edit.text().strip() or str(
            Path(file_path).parent / "processed"
        )
        output = str(Path(out_dir) / f"{Path(file_path).stem}_beautified.pptx")

        def job(progress):
            progress(0.0, "美化 PPT（本地解析 → LLM → 本地渲染）")
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            result = client.beautify_file(file_path, output, style="business")
            progress(1.0, "美化完成")
            return result

        new_job_id = uuid.uuid4().hex[:8]
        self.runner.submit(new_job_id, job)
        self.statusBar().showMessage(f"已提交美化任务 {new_job_id}。")

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
        self._show_result(result)
        self.statusBar().showMessage(f"{job_id} 完成。")

    def _show_result(self, result) -> None:
        """把 job 结果显示在结果区。

        - ``str``（PDF/DOCX 的 extract_text、或 rotate/merge 的输出路径）直接显示；
        - ``list`` / ``dict``（PPTX extract_text、analyze_structure、路径列表等）
          走 JSON 美化；
        - 其它 ``repr``。
        """
        import json

        if result is None:
            text = ""
        elif isinstance(result, str):
            text = result
        elif isinstance(result, (list, dict)):
            text = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            text = repr(result)
        self.result_view.setPlainText(text)

    def _on_failed(self, job_id: str, msg: str) -> None:
        self.table.set_status(job_id, f"失败: {msg[:40]}")
        self.statusBar().showMessage(f"{job_id} 失败：{msg}")

    def closeEvent(self, event) -> None:
        try:
            self.runner.shutdown()
        except NotImplementedError:
            # SyncTaskRunner 已写好不会抛；学生 TaskRunner 未实现 shutdown 时跳过。
            pass
        if self.beautify_client is not None:
            with contextlib.suppress(Exception):
                # 关窗时关掉 httpx 连接池；即使学生注入的假实现抛错也不阻塞关闭。
                self.beautify_client.close()
        super().closeEvent(event)


__all__ = ["MainWindow"]
