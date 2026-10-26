"""主窗口（已写好，学生不要改）。

布局：
    +------------------------------------------------+
    | 顶部工具栏：打开文件 / 输出目录 / 清空列表      |
    +------------------------------------------------+
    | 主工作区                                        |
    |  拖拽区                                          |
    |  文件表                                          |
    |  参数区（功能 / 输出目录 / 参数）               |
    |  进度区                                          |
    |  结果区                                          |
    +------------------------------------------------+
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
from wps_tool.ui.widgets import DropArea, FileTable, action_label, build_job_func
from wps_tool.utils.logging import logger

# 每个功能实际会用到的参数 key；参数区据此只显示相关项。
_ACTION_PARAMS: dict[str, set[str]] = {
    "extract_text": set(),
    "extract_images": set(),
    "analyze_structure": set(),
    "to_word": set(),
    "split": set(),
    "page_numbers": set(),
    "to_pdf": set(),
    "scan": set(),
    "rotate": {"angle"},
    "rotate_image": {"angle"},
    "extract_pages": {"pages"},
    "to_images": {"zoom"},
    "compress": {"quality"},
    "encrypt": {"password"},
    "decrypt": {"password"},
    "watermark": {"watermark"},
    "remove_watermark": {"watermark"},
    "resize": {"size"},
    "convert": {"format"},
    "replace": {"replace"},
    "replace_tokens": {"replace"},
}

# 功能下拉切换时显示的一行说明。
_ACTION_HINTS: dict[str, str] = {
    "extract_text": "直接提取文本，无需额外参数。",
    "extract_images": "把内嵌图片提取到输出目录。",
    "analyze_structure": "直接分析结构，无需额外参数。",
    "to_word": "基于 PDF 文本层转 Word；纯扫描件请先 OCR。",
    "split": "每页拆成一个单独的 PDF。",
    "page_numbers": "在每页底部居中加页码。",
    "to_pdf": "每张勾选图片分别生成一个 PDF。",
    "scan": "文档扫描：在弹出窗口中裁边、滤镜、签名并导出；输出目录作为默认位置。",
    "rotate": "顺时针旋转 PDF 的所有页。",
    "rotate_image": "顺时针旋转图片。",
    "extract_pages": "0-based 页码，如 0,2,5；留空 = 第 1 页。",
    "to_images": "倍率越高越清晰，文件也越大。",
    "compress": "JPEG 质量越低，文件越小。",
    "encrypt": "给 PDF 设置打开密码。",
    "decrypt": "输入原密码后移除加密。",
    "watermark": "留空默认使用 CONFIDENTIAL。",
    "remove_watermark": "留空自动识别；填文字则只删该文字。",
    "resize": "高度填 0 = 按宽度等比缩放。",
    "convert": "按目标格式重新编码。",
    "replace": "格式：旧=新; 旧2=新2。",
    "replace_tokens": "格式：旧=新; 旧2=新2。",
}


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
        # job_id -> 中文操作名，用于状态显示「xx成功 / xx失败」。
        self._job_actions: dict[str, str] = {}
        self.setWindowTitle("WPS 工具箱 — 本地 Office/PDF/扫描处理")
        self.resize(1180, 880)

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
        tb.addAction("文档扫描…", self._on_scan)
        tb.addAction("设置输出目录…", self._on_pick_output_dir)
        tb.addSeparator()
        tb.addAction("全选/全不选", self._on_toggle_check_all)
        tb.addAction("删除勾选", self._on_delete_checked)
        tb.addAction("清空列表", self._on_clear_list)

    # ---- 中央区 ----
    def _build_central(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)

        self.drop_area = DropArea()
        root.addWidget(self.drop_area)

        self.table = FileTable()
        root.addWidget(self.table, stretch=1)

        root.addWidget(self._build_params())
        root.addWidget(self._build_progress())
        root.addWidget(self._build_result(), stretch=1)

        self.setCentralWidget(central)

    def _make_param(
        self, label_text: str, *widgets, tooltip: str | None = None
    ) -> QWidget:
        """把「标签 + 控件」包成一个可整体显示/隐藏的小组件。"""
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(label_text)
        layout.addWidget(label)
        for widget in widgets:
            layout.addWidget(widget)
        if tooltip:
            wrapper.setToolTip(tooltip)
            label.setToolTip(tooltip)
            for widget in widgets:
                if not widget.toolTip():
                    widget.setToolTip(tooltip)
        return wrapper

    def _build_params(self) -> QWidget:
        box = QWidget()
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(6)

        self._param_widgets: dict[str, QWidget] = {}

        self.action_combo = QComboBox()
        self._populate_actions()
        self.action_combo.setMinimumWidth(190)
        self.action_combo.setToolTip("选择功能；下方只显示该功能用得到的参数。")
        self.action_combo.currentIndexChanged.connect(self._on_action_changed)

        self.output_edit = QLineEdit(self.settings.default_output_dir or "")
        self.output_edit.setPlaceholderText("留空 = 源文件旁 processed/")
        output_wrap = self._make_param(
            "输出目录:",
            self.output_edit,
            tooltip="留空 = 源文件旁 processed/；文档扫描用它作为默认导出位置。",
        )

        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("旧文本=新文本，多个用 ; 分隔")
        self._param_widgets["replace"] = self._make_param(
            "替换映射:",
            self.replace_edit,
            tooltip="仅替换文本/占位符使用：旧=新; 旧2=新2。",
        )

        row1 = QHBoxLayout()
        row1.setSpacing(14)
        row1.addWidget(QLabel("功能:"))
        row1.addWidget(self.action_combo)
        row1.addWidget(output_wrap, 1)
        row1.addWidget(self._param_widgets["replace"], 1)
        outer.addLayout(row1)

        self.angle_combo = QComboBox()
        self.angle_combo.addItems(["90", "180", "270"])
        self._param_widgets["angle"] = self._make_param(
            "角度:", self.angle_combo, tooltip="顺时针旋转角度。"
        )

        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 95)
        self.quality_spin.setValue(85)
        self.quality_spin.setSuffix(" %")
        self._param_widgets["quality"] = self._make_param(
            "质量:",
            self.quality_spin,
            tooltip="仅「压缩图片」使用：JPEG 质量越低文件越小。",
        )

        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(0.5, 5.0)
        self.zoom_spin.setSingleStep(0.5)
        self.zoom_spin.setValue(2.0)
        self.zoom_spin.setSuffix(" ×")
        self._param_widgets["zoom"] = self._make_param(
            "倍率:",
            self.zoom_spin,
            tooltip="仅「转成图片」使用：倍率越高越清晰、文件越大。",
        )

        self.pages_edit = QLineEdit()
        self.pages_edit.setPlaceholderText("0,2（0-based，逗号分隔；留空=第1页）")
        self._param_widgets["pages"] = self._make_param(
            "页码:",
            self.pages_edit,
            tooltip="仅「抽取页面」使用：0-based 页码，留空 = 第 1 页。",
        )

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("加密/解密用")
        self._param_widgets["password"] = self._make_param(
            "密码:", self.password_edit, tooltip="仅 PDF 加密/解密使用。"
        )

        self.watermark_edit = QLineEdit()
        self.watermark_edit.setPlaceholderText("水印文字（默认 CONFIDENTIAL）")
        self._param_widgets["watermark"] = self._make_param(
            "水印:",
            self.watermark_edit,
            tooltip="仅 PDF 加水印/去水印使用；去水印留空 = 自动识别。",
        )

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 20000)
        self.width_spin.setValue(800)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 20000)
        self.height_spin.setValue(0)
        self.height_spin.setSpecialValueText("自动")
        self.height_spin.setToolTip("0 = 按宽度等比缩放")
        self._param_widgets["size"] = self._make_param(
            "宽×高:",
            self.width_spin,
            QLabel("×"),
            self.height_spin,
            tooltip="仅「缩放图片」使用；高度 0 = 按宽度等比。",
        )

        self.format_combo = QComboBox()
        self.format_combo.addItems(["png", "jpg", "jpeg", "webp", "bmp"])
        self._param_widgets["format"] = self._make_param(
            "格式:", self.format_combo, tooltip="仅「转换格式」使用。"
        )

        self._row2_box = QWidget()
        row2 = QHBoxLayout(self._row2_box)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(16)
        for key in (
            "angle",
            "quality",
            "zoom",
            "pages",
            "password",
            "watermark",
            "size",
            "format",
        ):
            stretch = 1 if key in ("pages", "watermark") else 0
            row2.addWidget(self._param_widgets[key], stretch)
        row2.addStretch(1)
        outer.addWidget(self._row2_box)

        self.param_hint = QLabel("")
        self.param_hint.setStyleSheet("color:#5a6270;")
        self.param_hint.setWordWrap(True)
        outer.addWidget(self.param_hint)

        # 第三行：动作按钮（勾选 = 表格第一列）
        row3 = QHBoxLayout()
        self.run_btn = QPushButton("处理勾选")
        self.run_btn.setDefault(True)
        self.run_btn.clicked.connect(self._on_run_selected)
        row3.addWidget(self.run_btn)
        self.run_all_btn = QPushButton("处理全部")
        self.run_all_btn.clicked.connect(self._on_run_all)
        row3.addWidget(self.run_all_btn)
        self.merge_btn = QPushButton("合并勾选 PDF")
        self.merge_btn.clicked.connect(self._on_merge_selected)
        row3.addWidget(self.merge_btn)
        self.beautify_btn = QPushButton("美化勾选 PPT")
        self.beautify_btn.clicked.connect(self._on_beautify_selected)
        row3.addWidget(self.beautify_btn)
        self.delete_btn = QPushButton("删除勾选")
        self.delete_btn.clicked.connect(self._on_delete_checked)
        row3.addWidget(self.delete_btn)
        row3.addStretch(1)
        outer.addLayout(row3)

        self._update_param_visibility()
        return box

    def _on_action_changed(self, _index: int) -> None:
        self._update_param_visibility()

    def _update_param_visibility(self) -> None:
        """只显示当前功能用得到的参数，并更新一行说明。"""
        action = self.action_combo.currentData() or ""
        keys = _ACTION_PARAMS.get(action, set())
        for key, widget in self._param_widgets.items():
            widget.setVisible(key in keys)
        self._row2_box.setVisible(bool(keys))
        hint = _ACTION_HINTS.get(action, "")
        self.param_hint.setText(hint)
        self.param_hint.setVisible(bool(hint))


    def _populate_actions(self) -> None:
        """按文档类型分区填充功能下拉：普通条目 + 分隔线，标签自带类型名。

        用 QComboBox 默认模型（不用禁用项当分区标题），否则弹出列表会收不回去。
        内部仍通过 itemData 存 action id（读取用 currentData()）。
        """
        groups: list[list[tuple[str, str]]] = [
            [
                ("提取文本（通用）", "extract_text"),
                ("提取图片（PDF / Word / PPT）", "extract_images"),
            ],
            [
                ("PDF 转 Word", "to_word"),
                ("拆分 PDF", "split"),
                ("旋转 PDF", "rotate"),
                ("抽取页面", "extract_pages"),
                ("转成图片", "to_images"),
                ("加密 PDF", "encrypt"),
                ("解密 PDF", "decrypt"),
                ("加文字水印", "watermark"),
                ("去水印", "remove_watermark"),
                ("加页码", "page_numbers"),
            ],
            [
                ("分析结构（PPT）", "analyze_structure"),
                ("替换占位符（PPT）", "replace_tokens"),
            ],
            [("替换文本（Word）", "replace")],
            [
                ("文档扫描（生成 PDF）", "scan"),
                ("图片转 PDF", "to_pdf"),
                ("压缩图片", "compress"),
                ("缩放图片", "resize"),
                ("转换格式", "convert"),
                ("旋转图片", "rotate_image"),
            ],
        ]
        for gi, group in enumerate(groups):
            if gi:
                self.action_combo.insertSeparator(self.action_combo.count())
            for display, action in group:
                self.action_combo.addItem(display, action)
        self.action_combo.setCurrentIndex(0)

    def _build_result(self) -> QWidget:
        """结果查看区：extract_text / analyze_structure 等返回的内容显示在这里。"""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(2)
        lay.addWidget(QLabel("结果（提取文本 / 结构分析 / 输出路径等）"))
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

    def _on_scan(self) -> None:
        """工具栏「文档扫描」：优先用勾选的图片，没勾选就打开空扫描窗口。"""
        paths = []
        for job_id in self.table.checked_job_ids():
            file_path = self.table.path_for(job_id)
            if file_path:
                paths.append(file_path)
        self._open_scan_dialog(paths, self.output_edit.text().strip())

    def _open_scan_dialog(self, paths: list[str], output_dir: str) -> None:
        """打开文档扫描窗口；只接受图片，导出后把结果加回文件表。"""
        from wps_tool.ui.scan_dialog import ScanDialog

        suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
        image_paths = [p for p in paths if Path(p).suffix.lower() in suffixes]
        if paths and not image_paths:
            self.statusBar().showMessage(
                "文档扫描只支持 jpg / png / bmp / webp / tif 图片。"
            )
            return
        if not output_dir and image_paths:
            output_dir = str(Path(image_paths[0]).parent / "processed")
        try:
            dialog = ScanDialog(
                paths=image_paths, output_dir=output_dir, parent=self
            )
            dialog.exec()
        except Exception as exc:  # noqa: BLE001 - UI 异常统一提示
            logger.exception("打开文档扫描窗口失败")
            self.statusBar().showMessage(f"打开扫描窗口失败：{exc}")
            return
        result = dialog.exported_result
        if not result:
            return
        self._show_result(result)
        exported = result if isinstance(result, list) else [result]
        added = self.table.add_files([str(p) for p in exported if Path(p).exists()])
        self.statusBar().showMessage(f"扫描导出完成，已加入 {len(added)} 个文件。")

    def _on_files_dropped(self, paths: list[str]) -> None:
        added = self.table.add_files(paths)
        self.statusBar().showMessage(f"已加入 {len(added)} 个文件。")

    def _on_pick_output_dir(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.output_edit.setText(d)

    def _on_clear_list(self) -> None:
        self.table.setRowCount(0)
        self._job_actions.clear()
        self.progress_bar.setValue(0)
        self.progress_label.setText("等待任务")
        self.result_view.clear()

    def _on_run_selected(self) -> None:
        rows = self.table.checked_rows()
        if not rows:
            self.statusBar().showMessage("请先勾选要处理的文件（表格第一列）。")
            return
        self._run_rows(rows)

    def _on_toggle_check_all(self) -> None:
        total = self.table.rowCount()
        if not total:
            return
        all_checked = len(self.table.checked_rows()) == total
        self.table.set_all_checked(not all_checked)

    def _on_delete_checked(self) -> None:
        job_ids = self.table.checked_job_ids()
        if not job_ids:
            self.statusBar().showMessage("请先勾选要删除的文件（表格第一列）。")
            return
        removed = self.table.remove_jobs(job_ids)
        for job_id in job_ids:
            self._job_actions.pop(job_id, None)
        self.statusBar().showMessage(f"已删除 {removed} 个文件。")

    def _on_run_all(self) -> None:
        """对列表里所有文件执行当前操作（批量处理）。"""
        rows = list(range(self.table.rowCount()))
        if not rows:
            self.statusBar().showMessage("列表为空，先拖入文件。")
            return
        self._run_rows(rows)

    def _run_rows(self, rows: list[int]) -> None:
        """对给定行集合提交当前操作的任务（选中行 / 全部共用）。"""
        action = self.action_combo.currentData()
        if not action:
            self.statusBar().showMessage("请先选择一个操作。")
            return
        raw_out = self.output_edit.text().strip()
        if action == "scan":
            paths = []
            for row in rows:
                job_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                file_path = self.table.path_for(job_id)
                if file_path:
                    paths.append(file_path)
            self._open_scan_dialog(paths, raw_out)
            return
        if action in ("replace", "replace_tokens") and not self._parse_mapping(
            self.replace_edit.text()
        ):
            self.statusBar().showMessage(
                "请在「替换映射」里填 旧文本=新文本（多个用 ; 分隔）后再处理。"
            )
            return
        if action in ("encrypt", "decrypt") and not self.password_edit.text():
            self.statusBar().showMessage("请在「密码」里填密码后再加/解密。")
            return
        submitted = 0
        for row in rows:
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
        if action == "to_word":
            return {"output": str(Path(out_dir) / f"{stem}.docx")}
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
        if action == "encrypt":
            return {
                "output": str(Path(out_dir) / f"{stem}_encrypted.pdf"),
                "password": self.password_edit.text(),
            }
        if action == "decrypt":
            return {
                "output": str(Path(out_dir) / f"{stem}_decrypted.pdf"),
                "password": self.password_edit.text(),
            }
        if action == "watermark":
            return {
                "output": str(Path(out_dir) / f"{stem}_watermark.pdf"),
                "text": self.watermark_edit.text().strip() or "CONFIDENTIAL",
            }
        if action == "remove_watermark":
            return {
                "output": str(Path(out_dir) / f"{stem}_clean.pdf"),
                "text": self.watermark_edit.text().strip() or None,
            }
        if action == "page_numbers":
            return {"output": str(Path(out_dir) / f"{stem}_numbered.pdf")}
        if action == "resize":
            return {
                "output": str(Path(out_dir) / f"{stem}_resized{suffix}"),
                "width": self.width_spin.value(),
                "height": self.height_spin.value() or None,
            }
        if action == "convert":
            return {"output": str(Path(out_dir) / f"{stem}.{self.format_combo.currentText()}")}
        if action == "rotate_image":
            return {
                "output": str(Path(out_dir) / f"{stem}_rotated{suffix}"),
                "angle": int(self.angle_combo.currentText()),
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
        job_ids = self.table.checked_job_ids()
        inputs = [p for p in (self.table.path_for(jid) for jid in job_ids) if p]
        if len(inputs) < 2:
            self.statusBar().showMessage("合并至少需要勾选 2 个 PDF（可勾选不连续的行）。")
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

        self._job_actions[job_id] = "合并"
        self.runner.submit(job_id, job)
        self.statusBar().showMessage(f"已提交合并任务 {job_id}。")

    def _on_beautify_selected(self) -> None:
        """美化选中的 PPT：本地解析 → 文本发 LLM 拿 spec → 本地渲染重建 deck。

        走 ``beautify_client.beautify_file(input, output, style)``：pptx 二进制不出本机，
        只把每页文本发给 LLM，再用 python-pptx 本地重建一套干净 deck，写到
        ``processed/<文件名>_beautified.pptx``。服务方法未就绪时由 Runner 转 failed 信号提示——UI 不崩。
        """
        logger.info(
            "PPT 美化按钮点击: beautify_client_ready={}",
            self.beautify_client is not None,
        )
        if self.beautify_client is None:
            logger.warning("PPT 美化未提交: beautify_client=None")
            self.statusBar().showMessage(
                "美化 LLM 未配置：在 .env 设 ENABLE_API_UPLOAD=true 并填写"
                " LLM_PROVIDER=opencode-go / LLM_API_KEY（LLM_BASE_URL=/LLM_MODEL"
                " 可选）后重启。"
            )
            return
        job_ids = self.table.checked_job_ids()
        if not job_ids:
            logger.warning("PPT 美化未提交: 未勾选文件")
            self.statusBar().showMessage("请先勾选一个 .pptx 文件（表格第一列）。")
            return
        if len(job_ids) != 1:
            logger.warning("PPT 美化未提交: 勾选行数={}", len(job_ids))
            self.statusBar().showMessage("美化一次只处理一个 .pptx，请只勾选一个。")
            return
        job_id = job_ids[0]
        file_path = self.table.path_for(job_id)
        if not file_path or Path(file_path).suffix.lower() != ".pptx":
            logger.warning(
                "PPT 美化未提交: 文件类型不支持 suffix={}",
                Path(file_path).suffix.lower() if file_path else "",
            )
            self.statusBar().showMessage("选中的文件不是 .pptx，无法美化。")
            return

        import uuid

        client = self.beautify_client
        out_dir = self.output_edit.text().strip() or str(
            Path(file_path).parent / "processed"
        )
        output = str(Path(out_dir) / f"{Path(file_path).stem}_beautified.pptx")

        def job(progress):
            logger.info(
                "PPT 美化任务开始: job_id={} input_name={} output={}",
                new_job_id,
                Path(file_path).name,
                output,
            )
            progress(0.0, "美化 PPT（本地解析 → LLM → 本地渲染）")
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            try:
                result = client.beautify_file(file_path, output, style="business")
            except Exception:
                logger.exception("PPT 美化任务失败: job_id={}", new_job_id)
                raise
            else:
                logger.info(
                    "PPT 美化任务完成: job_id={} output={}",
                    new_job_id,
                    result,
                )
                progress(1.0, "美化完成")
                return result

        new_job_id = uuid.uuid4().hex[:8]
        logger.info(
            "PPT 美化任务提交: job_id={} input_name={} output={}",
            new_job_id,
            Path(file_path).name,
            output,
        )
        self._job_actions[new_job_id] = "美化"
        self.runner.submit(new_job_id, job)
        self.statusBar().showMessage(f"已提交美化任务 {new_job_id}。")

    def _submit_job(self, job_id: str, file_path: str, action: str, options: dict) -> None:
        job = build_job_func(self.registry, file_path, action, options)
        self._job_actions[job_id] = action_label(action)
        self.runner.submit(job_id, job)

    # ---- Runner 信号回调（在主线程执行） ----
    def _on_started(self, job_id: str) -> None:
        self.table.set_status(job_id, "处理进行中")

    def _on_progress(self, frac: float, msg: str) -> None:
        self.progress_bar.setValue(int(frac * 100))
        self.progress_label.setText(msg)

    def _on_finished(self, job_id: str, result) -> None:
        self.table.set_status(job_id, f"{self._job_actions.get(job_id, '操作')}成功")
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
        logger.error("任务失败信号: job_id={} msg={}", job_id, msg)
        self.table.set_status(job_id, f"{self._job_actions.get(job_id, '操作')}失败")
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
