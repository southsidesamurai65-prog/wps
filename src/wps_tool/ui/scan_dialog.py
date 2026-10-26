"""文档扫描窗口：导入照片 → 拖角裁边 → 滤镜 → 排序 → 签名 → 导出。

界面只负责交互与预览；真正算法在 ``processors/scan_processor.py``。
导出放 QThread，避免长任务卡住窗口。
"""

from __future__ import annotations

import time
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wps_tool.core.errors import ConversionError
from wps_tool.processors.scan_processor import (
    FILTERS,
    ScanPage,
    Signature,
    detect_document_corners,
    export_scan_images,
    export_scan_pdf,
    full_frame_corners,
    load_image,
    render_page,
)
from wps_tool.utils.logging import logger

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def _rgb_to_qimage(rgb: np.ndarray) -> QImage:
    array = np.ascontiguousarray(rgb)
    height, width = array.shape[:2]
    return QImage(
        array.data, width, height, 3 * width, QImage.Format.Format_RGB888
    ).copy()


def _pil_to_qimage(img: Image.Image) -> QImage:
    return _rgb_to_qimage(np.asarray(img.convert("RGB")))


class CornerEditor(QWidget):
    """在原图上显示四个手柄，拖动即可调整裁边。"""

    corners_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(420, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._image: QImage | None = None
        self._corners = full_frame_corners()
        self._display_rect = QRectF()
        self._drag_index = -1

    def set_image(self, rgb: np.ndarray, corners: np.ndarray) -> None:
        self._image = _rgb_to_qimage(rgb)
        self.set_corners(corners)

    def set_corners(self, corners: np.ndarray) -> None:
        self._corners = np.asarray(corners, dtype=np.float32).reshape(4, 2).copy()
        self.update()

    def corners(self) -> np.ndarray:
        return self._corners.copy()

    def reset_corners(self) -> None:
        self._corners = full_frame_corners()
        self.update()
        self.corners_changed.emit()

    def sizeHint(self) -> QSize:
        return QSize(560, 460)

    def _update_geometry(self) -> None:
        if self._image is None or self._image.isNull():
            return
        margin = 14
        available_w = max(1, self.width() - 2 * margin)
        available_h = max(1, self.height() - 2 * margin)
        scale = min(
            available_w / self._image.width(),
            available_h / self._image.height(),
        )
        width = self._image.width() * scale
        height = self._image.height() * scale
        self._display_rect = QRectF(
            (self.width() - width) / 2,
            (self.height() - height) / 2,
            width,
            height,
        )

    def _to_widget(self, point) -> QPointF:
        return QPointF(
            self._display_rect.left() + float(point[0]) * self._display_rect.width(),
            self._display_rect.top() + float(point[1]) * self._display_rect.height(),
        )

    def _to_normalized(self, point: QPointF) -> np.ndarray:
        rect = self._display_rect
        if rect.width() <= 0 or rect.height() <= 0:
            return np.zeros(2, dtype=np.float32)
        return np.array(
            [
                (point.x() - rect.left()) / rect.width(),
                (point.y() - rect.top()) / rect.height(),
            ],
            dtype=np.float32,
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#eef1f8"))
        if self._image is None or self._image.isNull():
            painter.setPen(QColor("#6b7280"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "添加图片后在这里裁边")
            return
        self._update_geometry()
        painter.drawImage(self._display_rect, self._image)

        points = [self._to_widget(point) for point in self._corners]
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        painter.setPen(QPen(QColor("#2563eb"), 2))
        painter.setBrush(QColor(37, 99, 235, 26))
        painter.drawPath(path)

        for index, point in enumerate(points):
            active = index == self._drag_index
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QPen(QColor("#f59e0b" if active else "#2563eb"), 2))
            painter.drawEllipse(point, 8, 8)
            painter.setBrush(QColor("#f59e0b" if active else "#2563eb"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(point, 3, 3)

        painter.setPen(QColor("#6b7280"))
        hint_text = "拖动四个圆点，让边框贴住纸张四角"
        metrics = painter.fontMetrics()
        box_width = metrics.horizontalAdvance(hint_text) + 22
        hint_rect = QRectF(
            (self.width() - box_width) / 2, self.height() - 34, box_width, 24
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 215))
        painter.drawRoundedRect(hint_rect, 8, 8)
        painter.setPen(QColor("#4b5563"))
        painter.drawText(hint_rect, Qt.AlignmentFlag.AlignCenter, hint_text)

    def _hit_corner(self, position: QPointF) -> int:
        for index in range(4):
            point = self._to_widget(self._corners[index])
            if (point - position).manhattanLength() <= 18:
                return index
        return -1

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._image is None:
            return
        self._update_geometry()
        index = self._hit_corner(event.position())
        if index >= 0:
            self._drag_index = index
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()

    def mouseMoveEvent(self, event) -> None:
        self._update_geometry()
        if self._drag_index >= 0:
            normalized = self._to_normalized(event.position())
            self._corners[self._drag_index] = np.clip(normalized, 0.0, 1.0)
            self.update()
            return
        index = self._hit_corner(event.position())
        self.setCursor(
            Qt.CursorShape.OpenHandCursor
            if index >= 0
            else Qt.CursorShape.ArrowCursor
        )

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_index >= 0 and event.button() == Qt.MouseButton.LeftButton:
            self._drag_index = -1
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
            self.corners_changed.emit()

    def resizeEvent(self, event) -> None:
        self._update_geometry()
        super().resizeEvent(event)


class ImagePreview(QLabel):
    """自适应缩放的结果预览。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            "background:#eef1f8;border:1px solid #e4e8ef;border-radius:8px;"
        )
        self._pixmap: QPixmap | None = None

    def set_image(self, rgb: np.ndarray) -> None:
        self._pixmap = QPixmap.fromImage(_rgb_to_qimage(rgb))
        self._refresh()

    def clear_image(self) -> None:
        self._pixmap = None
        self.clear()

    def _refresh(self) -> None:
        if self._pixmap is None:
            return
        area = self.size() - QSize(16, 16)
        if area.width() < 20 or area.height() < 20:
            return
        self.setPixmap(
            self._pixmap.scaled(
                area,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:
        self._refresh()
        super().resizeEvent(event)


class SignatureCanvas(QWidget):
    """手写签名画板；导出透明 PNG 时会去掉白底。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 230)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._strokes: list[list[QPointF]] = []
        self._pen_width = 4
        self._color = QColor("#1f2329")
        self._drawing = False

    def set_pen_width(self, width: int) -> None:
        self._pen_width = max(1, int(width))

    def set_pen_color(self, color: QColor) -> None:
        self._color = QColor(color)

    def clear(self) -> None:
        self._strokes.clear()
        self.update()

    def has_strokes(self) -> bool:
        return any(self._strokes)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QPen(QColor("#e4e8ef"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.setPen(QPen(self._color, self._pen_width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for stroke in self._strokes:
            if len(stroke) == 1:
                painter.setBrush(self._color)
                painter.drawEllipse(stroke[0], self._pen_width / 2, self._pen_width / 2)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                continue
            path = QPainterPath(stroke[0])
            for point in stroke[1:]:
                path.lineTo(point)
            painter.drawPath(path)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drawing = True
        self._strokes.append([event.position()])
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if not self._drawing or not self._strokes:
            return
        point = event.position()
        if (point - self._strokes[-1][-1]).manhattanLength() >= 1.5:
            self._strokes[-1].append(point)
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = False
            self.update()

    def png_bytes(self) -> bytes | None:
        points = [point for stroke in self._strokes for point in stroke]
        if not points:
            return None
        xs = [point.x() for point in points]
        ys = [point.y() for point in points]
        padding = self._pen_width / 2 + 4
        left, right = min(xs) - padding, max(xs) + padding
        top, bottom = min(ys) - padding, max(ys) + padding
        box_w = max(1.0, right - left)
        box_h = max(1.0, bottom - top)
        scale = min(3.0, 1600 / max(box_w, box_h))
        canvas_w = max(1, round(box_w * scale))
        canvas_h = max(1, round(box_h * scale))
        image = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = (self._color.red(), self._color.green(), self._color.blue(), 255)
        width = max(1, round(self._pen_width * scale))
        for stroke in self._strokes:
            coords = [
                ((point.x() - left) * scale, (point.y() - top) * scale)
                for point in stroke
            ]
            if len(coords) == 1:
                x, y = coords[0]
                radius = width / 2
                draw.ellipse(
                    (x - radius, y - radius, x + radius, y + radius), fill=color
                )
                continue
            draw.line(coords, fill=color, width=width, joint="curve")
            for x, y in (coords[0], coords[-1]):
                radius = width / 2
                draw.ellipse(
                    (x - radius, y - radius, x + radius, y + radius), fill=color
                )
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


class SignatureDialog(QDialog):
    """手写签名 + 位置/大小/透明度设置。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("手写签名")
        self.resize(820, 620)
        self._signature: Signature | None = None

        root = QVBoxLayout(self)
        tip = QLabel("在白色画板上手写签名；确认后按下方设置叠加到扫描页。")
        tip.setStyleSheet("color:#5a6270;")
        root.addWidget(tip)

        self.canvas = SignatureCanvas(self)
        root.addWidget(self.canvas, stretch=1)

        pen_row = QHBoxLayout()
        pen_row.addWidget(QLabel("笔宽:"))
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(2, 12)
        self.width_slider.setValue(5)
        self.width_slider.valueChanged.connect(self.canvas.set_pen_width)
        pen_row.addWidget(self.width_slider, stretch=1)
        self.color_btn = QPushButton("颜色…")
        self.color_btn.clicked.connect(self._pick_color)
        pen_row.addWidget(self.color_btn)
        clear_btn = QPushButton("清除")
        clear_btn.clicked.connect(self.canvas.clear)
        pen_row.addWidget(clear_btn)
        root.addLayout(pen_row)

        options = QGroupBox("放置方式")
        form = QFormLayout(options)
        self.anchor_combo = QComboBox()
        for label, value in (
            ("右下角", "bottom-right"),
            ("左下角", "bottom-left"),
            ("右上角", "top-right"),
            ("左上角", "top-left"),
            ("居中", "center"),
        ):
            self.anchor_combo.addItem(label, value)
        form.addRow("位置:", self.anchor_combo)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(10, 60)
        self.size_slider.setValue(28)
        self.size_label = QLabel("28% 页宽")
        self.size_slider.valueChanged.connect(
            lambda value: self.size_label.setText(f"{value}% 页宽")
        )
        size_row = QHBoxLayout()
        size_row.addWidget(self.size_slider, stretch=1)
        size_row.addWidget(self.size_label)
        form.addRow("大小:", size_row)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(100)
        self.opacity_label = QLabel("100%")
        self.opacity_slider.valueChanged.connect(
            lambda value: self.opacity_label.setText(f"{value}%")
        )
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.opacity_slider, stretch=1)
        opacity_row.addWidget(self.opacity_label)
        form.addRow("透明度:", opacity_row)

        self.apply_all = QCheckBox("应用到所有页")
        form.addRow("", self.apply_all)
        root.addWidget(options)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self.canvas._color, self, "选择签名颜色")
        if color.isValid():
            self.canvas.set_pen_color(color)
            self.color_btn.setStyleSheet(
                f"border:2px solid {color.name()};"
            )

    @property
    def signature(self) -> Signature | None:
        return self._signature

    def accept(self) -> None:
        png = self.canvas.png_bytes()
        if not png:
            QMessageBox.warning(self, "签名为空", "请先在画板上手写签名。")
            return
        self._signature = Signature(
            png=png,
            anchor=str(self.anchor_combo.currentData()),
            width_ratio=self.size_slider.value() / 100.0,
            opacity=self.opacity_slider.value() / 100.0,
        )
        super().accept()


class _ExportThread(QThread):
    progress = Signal(int, int)
    ok = Signal(object)
    failed = Signal(str)

    def __init__(self, pages: list[ScanPage], options: dict, parent=None) -> None:
        super().__init__(parent)
        self._pages = pages
        self._options = options

    def run(self) -> None:
        try:
            if self._options["format"] == "pdf":
                result = export_scan_pdf(
                    self._pages,
                    self._options["path"],
                    dpi=self._options["dpi"],
                    paper=self._options["paper"],
                    quality=self._options["quality"],
                    progress=lambda done, total: self.progress.emit(done, total),
                )
            else:
                result = export_scan_images(
                    self._pages,
                    self._options["path"],
                    fmt=self._options["format"],
                    dpi=self._options["dpi"],
                    paper=self._options["paper"],
                    quality=self._options["quality"],
                    progress=lambda done, total: self.progress.emit(done, total),
                )
            self.ok.emit(result)
        except Exception as exc:  # noqa: BLE001 - 转成 UI 错误提示
            logger.exception("扫描导出失败")
            self.failed.emit(str(exc))


class ScanDialog(QDialog):
    """文档扫描主窗口。"""

    def __init__(
        self,
        paths: list[str] | None = None,
        output_dir: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("文档扫描 — 生成扫描件 PDF")
        self.resize(1280, 880)
        self.setAcceptDrops(True)
        self._pages: list[ScanPage] = []
        self._output_dir = output_dir
        self._current_source: np.ndarray | None = None
        self._current_source_path = ""
        self._exported_result = None
        self._export_thread: _ExportThread | None = None

        self._build_ui()
        self._update_actions()
        if paths:
            self.add_paths(paths)

    # ---- 构建界面 ----

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("添加图片…")
        self.add_btn.clicked.connect(self._on_add_images)
        toolbar.addWidget(self.add_btn)
        self.delete_btn = QPushButton("删除本页")
        self.delete_btn.clicked.connect(self._on_delete_page)
        toolbar.addWidget(self.delete_btn)
        self.up_btn = QPushButton("上移")
        self.up_btn.clicked.connect(lambda: self._move_page(-1))
        toolbar.addWidget(self.up_btn)
        self.down_btn = QPushButton("下移")
        self.down_btn.clicked.connect(lambda: self._move_page(1))
        toolbar.addWidget(self.down_btn)
        self.left_btn = QPushButton("左转")
        self.left_btn.clicked.connect(lambda: self._rotate_page(-90))
        toolbar.addWidget(self.left_btn)
        self.right_btn = QPushButton("右转")
        self.right_btn.clicked.connect(lambda: self._rotate_page(90))
        toolbar.addWidget(self.right_btn)
        toolbar.addStretch(1)
        hint = QLabel("拖入图片，或点「添加图片」")
        hint.setStyleSheet("color:#5a6270;")
        toolbar.addWidget(hint)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.pages_list = QListWidget()
        self.pages_list.setViewMode(QListWidget.ViewMode.ListMode)
        self.pages_list.setIconSize(QSize(86, 114))
        self.pages_list.setSpacing(4)
        self.pages_list.setUniformItemSizes(True)
        self.pages_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self.pages_list.currentRowChanged.connect(self._on_row_changed)
        self.pages_list.setMinimumWidth(150)
        self.pages_list.setMaximumWidth(190)
        splitter.addWidget(self.pages_list)
        splitter.addWidget(self._build_tabs())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)

        root.addWidget(self._build_export_box())
        self.status_label = QLabel("导入图片开始扫描。")
        self.status_label.setStyleSheet("color:#5a6270;")
        root.addWidget(self.status_label)

    def _build_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()

        crop_page = QWidget()
        crop_layout = QVBoxLayout(crop_page)
        self.corner_editor = CornerEditor()
        self.corner_editor.corners_changed.connect(self._on_corners_changed)
        crop_layout.addWidget(self.corner_editor, stretch=1)
        crop_row = QHBoxLayout()
        self.detect_btn = QPushButton("自动检测")
        self.detect_btn.clicked.connect(self._auto_detect)
        crop_row.addWidget(self.detect_btn)
        self.reset_btn = QPushButton("重置四角")
        self.reset_btn.clicked.connect(self.corner_editor.reset_corners)
        crop_row.addWidget(self.reset_btn)
        crop_row.addStretch(1)
        note = QLabel("蓝色边框内为保留区域")
        note.setStyleSheet("color:#5a6270;")
        crop_row.addWidget(note)
        crop_layout.addLayout(crop_row)
        self.tabs.addTab(crop_page, "裁边")

        result_page = QWidget()
        result_layout = QVBoxLayout(result_page)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("滤镜:"))
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        for key, label in FILTERS.items():
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("filter_key", key)
            self.filter_group.addButton(button)
            filter_row.addWidget(button)
        self.filter_group.buttonClicked.connect(self._on_filter_clicked)
        filter_row.addStretch(1)
        result_layout.addLayout(filter_row)
        preview_note = QLabel(
            "预览按裁切后的比例显示；纸张、DPI、质量只影响导出结果。"
        )
        preview_note.setStyleSheet("color:#5a6270;")
        preview_note.setWordWrap(True)
        result_layout.addWidget(preview_note)

        self.result_preview = ImagePreview()
        result_layout.addWidget(self.result_preview, stretch=1)
        sign_row = QHBoxLayout()
        self.sign_btn = QPushButton("手写签名…")
        self.sign_btn.clicked.connect(self._on_sign)
        sign_row.addWidget(self.sign_btn)
        self.clear_sign_btn = QPushButton("清除签名")
        self.clear_sign_btn.clicked.connect(self._on_clear_signature)
        sign_row.addWidget(self.clear_sign_btn)
        sign_row.addStretch(1)
        self.page_info = QLabel("")
        self.page_info.setStyleSheet("color:#5a6270;")
        sign_row.addWidget(self.page_info)
        result_layout.addLayout(sign_row)
        self.tabs.addTab(result_page, "效果")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        return self.tabs

    def _build_export_box(self) -> QGroupBox:
        box = QGroupBox("导出")
        root = QVBoxLayout(box)
        row = QHBoxLayout()
        row.addWidget(QLabel("格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItem("PDF", "pdf")
        self.format_combo.addItem("JPG", "jpg")
        row.addWidget(self.format_combo)
        row.addSpacing(10)
        row.addWidget(QLabel("纸张:"))
        self.paper_combo = QComboBox()
        self.paper_combo.addItem("A4 竖向", "a4")
        self.paper_combo.addItem("A4 横向", "a4-landscape")
        self.paper_combo.addItem("自动（按图片）", "auto")
        self.paper_combo.setToolTip(
            "导出纸张：竖向/横向 A4 会加白边；自动按图片比例，保留原始像素。"
        )
        row.addWidget(self.paper_combo)
        row.addSpacing(10)
        row.addWidget(QLabel("DPI:"))
        self.dpi_combo = QComboBox()
        for dpi in (150, 200, 300):
            self.dpi_combo.addItem(str(dpi), dpi)
        self.dpi_combo.setCurrentIndex(2)
        self.dpi_combo.setToolTip(
            "导出像素密度：150 适合屏幕阅读，200 均衡，300 适合打印。"
            "DPI 越高文件越大，但不会凭空增加原图没有的细节。"
        )
        row.addWidget(self.dpi_combo)
        row.addSpacing(10)
        row.addWidget(QLabel("质量:"))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(60, 95)
        self.quality_spin.setValue(90)
        self.quality_spin.setSuffix(" %")
        self.quality_spin.setToolTip(
            "JPEG 压缩质量：越高越清晰、文件越大；85–90 通常就够了。"
        )
        row.addWidget(self.quality_spin)
        row.addStretch(1)
        root.addLayout(row)
        hint = QLabel(
            "DPI：导出像素密度（150 屏幕 / 200 均衡 / 300 打印）；"
            "质量：JPEG 压缩质量，85–90 推荐。"
            "A4 会缩放/留白到标准页，想保留原始像素请选「自动」。"
            "需要密码/水印：先导出，再回主界面用「加密 PDF / 加文字水印」。"
        )
        hint.setStyleSheet("color:#5a6270;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        bottom = QHBoxLayout()
        self.output_label = QLabel("")
        self.output_label.setStyleSheet("color:#5a6270;")
        bottom.addWidget(self.output_label, stretch=1)
        self.export_btn = QPushButton("导出…")
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self._on_export)
        bottom.addWidget(self.export_btn)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(close_btn)
        root.addLayout(bottom)
        return box

    # ---- 页面数据 ----

    def _current_page(self) -> ScanPage | None:
        row = self.pages_list.currentRow()
        if 0 <= row < len(self._pages):
            return self._pages[row]
        return None

    @property
    def exported_result(self):
        return self._exported_result

    def _default_output_dir(self) -> Path:
        if self._output_dir:
            return Path(self._output_dir)
        if self._pages:
            return Path(self._pages[0].source_path).parent / "processed"
        return Path.home() / "Documents"

    def _update_output_label(self) -> None:
        self.output_label.setText(f"默认输出目录：{self._default_output_dir()}")

    def _update_actions(self) -> None:
        page = self._current_page()
        row = self.pages_list.currentRow()
        has_page = page is not None
        for widget in (
            self.delete_btn,
            self.left_btn,
            self.right_btn,
            self.detect_btn,
            self.reset_btn,
            self.sign_btn,
            self.clear_sign_btn,
            self.export_btn,
        ):
            widget.setEnabled(has_page)
        self.up_btn.setEnabled(has_page and row > 0)
        self.down_btn.setEnabled(has_page and row < len(self._pages) - 1)
        for button in self.filter_group.buttons():
            button.setEnabled(has_page)
        self._update_output_label()

    # ---- 添加/删除/排序 ----

    def add_paths(self, paths: list[str]) -> None:
        existing = {page.source_path for page in self._pages}
        added = 0
        errors: list[str] = []
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for path in paths:
                suffix = Path(path).suffix.lower()
                if suffix not in IMAGE_SUFFIXES:
                    continue
                if path in existing:
                    continue
                try:
                    preview = load_image(path, max_dim=1600)
                    corners = detect_document_corners(preview)
                    if corners is None:
                        corners = full_frame_corners()
                    page = ScanPage(source_path=path, corners=corners)
                    self._pages.append(page)
                    existing.add(path)
                    self._append_item(page)
                    added += 1
                except ConversionError as exc:
                    errors.append(f"{Path(path).name}: {exc}")
                except Exception as exc:  # noqa: BLE001 - 单张失败不影响其余
                    logger.exception("扫描添加图片失败: {}", path)
                    errors.append(f"{Path(path).name}: {exc}")
        finally:
            QApplication.restoreOverrideCursor()
        if added:
            self.pages_list.setCurrentRow(len(self._pages) - 1)
            self.status_label.setText(f"已添加 {added} 页。")
        if errors:
            QMessageBox.warning(
                self,
                "部分图片未能导入",
                "\n".join(errors[:8]) + ("\n…" if len(errors) > 8 else ""),
            )
        if not added and not errors:
            self.status_label.setText("没有可导入的新图片。")
        self._update_actions()

    def _append_item(self, page: ScanPage) -> None:
        item = QListWidgetItem()
        item.setIcon(self._thumbnail_icon(page))
        item.setSizeHint(QSize(150, 126))
        self.pages_list.addItem(item)
        self._renumber()

    def _thumbnail_icon(self, page: ScanPage) -> QIcon:
        try:
            source = load_image(page.source_path, max_dim=500)
            img = render_page(
                page, dpi=72, paper="auto", source_rgb=source
            )
            img.thumbnail((104, 136), Image.Resampling.LANCZOS)
            return QIcon(QPixmap.fromImage(_pil_to_qimage(img)))
        except Exception:  # noqa: BLE001 - 缩略图失败不影响主流程
            return QIcon()

    def _refresh_thumbnail(self, row: int) -> None:
        if 0 <= row < len(self._pages):
            item = self.pages_list.item(row)
            if item is not None:
                item.setIcon(self._thumbnail_icon(self._pages[row]))

    def _renumber(self) -> None:
        for index in range(self.pages_list.count()):
            item = self.pages_list.item(index)
            if item is not None:
                item.setText(f"第 {index + 1} 页")

    def _on_row_changed(self, row: int) -> None:
        page = self._current_page()
        if page is None:
            self.corner_editor.set_image(
                np.full((10, 10, 3), 255, dtype=np.uint8), full_frame_corners()
            )
            self.result_preview.clear_image()
            self.page_info.setText("")
            self._update_actions()
            return

        try:
            self._current_source = load_image(page.source_path, max_dim=2000)
            self._current_source_path = page.source_path
            self.corner_editor.set_image(self._current_source, page.corners)
        except Exception as exc:  # noqa: BLE001 - 失败时清空预览
            self._current_source = None
            self._current_source_path = ""
            self.result_preview.clear_image()
            self.status_label.setText(f"读取图片失败：{exc}")

        self._sync_filter_buttons()
        self._refresh_result(update_thumb=False)
        self._update_actions()

    def _on_delete_page(self) -> None:
        row = self.pages_list.currentRow()
        if not (0 <= row < len(self._pages)):
            return
        self._pages.pop(row)
        self.pages_list.takeItem(row)
        self._renumber()
        if self._pages:
            self.pages_list.setCurrentRow(min(row, len(self._pages) - 1))
        else:
            self._on_row_changed(-1)
        self._update_actions()

    def _move_page(self, delta: int) -> None:
        row = self.pages_list.currentRow()
        target = row + delta
        if not (0 <= row < len(self._pages) and 0 <= target < len(self._pages)):
            return
        self._pages[row], self._pages[target] = self._pages[target], self._pages[row]
        item = self.pages_list.takeItem(row)
        self.pages_list.insertItem(target, item)
        self.pages_list.setCurrentRow(target)
        self._renumber()
        self._update_actions()

    def _rotate_page(self, delta: int) -> None:
        page = self._current_page()
        if page is None:
            return
        page.rotation = (page.rotation + delta) % 360
        self._refresh_result()
        self.status_label.setText(f"已旋转到 {page.rotation}°。")

    # ---- 裁边 / 滤镜 ----

    def _on_corners_changed(self) -> None:
        page = self._current_page()
        if page is None:
            return
        page.corners = self.corner_editor.corners()
        self._refresh_result()
        self.status_label.setText("裁边已更新。")

    def _auto_detect(self) -> None:
        page = self._current_page()
        if page is None or self._current_source is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            corners = detect_document_corners(self._current_source)
        finally:
            QApplication.restoreOverrideCursor()
        if corners is None:
            self.status_label.setText("没有识别到清晰的纸张边界，请手动拖动四角。")
            return
        page.corners = corners
        self.corner_editor.set_corners(corners)
        self._refresh_result()
        self.status_label.setText("已自动识别纸张边界。")

    def _sync_filter_buttons(self) -> None:
        page = self._current_page()
        key = page.filter if page is not None else "enhance"
        for button in self.filter_group.buttons():
            button.setChecked(button.property("filter_key") == key)

    def _on_filter_clicked(self, button) -> None:
        page = self._current_page()
        if page is None:
            return
        page.filter = str(button.property("filter_key"))
        self.tabs.setCurrentIndex(1)
        self._refresh_result()
        self.status_label.setText(f"滤镜：{FILTERS.get(page.filter, page.filter)}")

    def _paper(self) -> str:
        return str(self.paper_combo.currentData())

    def _refresh_result(self, update_thumb: bool = True) -> None:
        page = self._current_page()
        if page is None:
            self.result_preview.clear_image()
            return
        source = None
        if (
            self._current_source is not None
            and self._current_source_path == page.source_path
        ):
            source = self._current_source
        try:
            img = render_page(
                page,
                dpi=150,
                paper="auto",
                source_rgb=source,
            )
            if max(img.size) > 1800:
                img.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
            self.result_preview.set_image(np.asarray(img))
            self.page_info.setText(
                f"{FILTERS.get(page.filter, page.filter)} · {page.rotation}°"
                + (" · 已签名" if page.signature else "")
            )
            if update_thumb:
                self._refresh_thumbnail(self.pages_list.currentRow())
        except Exception as exc:  # noqa: BLE001 - 预览失败给出提示
            self.result_preview.clear_image()
            self.status_label.setText(f"预览失败：{exc}")

    def _on_tab_changed(self, index: int) -> None:
        page = self._current_page()
        if page is None:
            return
        if index == 1:
            self._refresh_result(update_thumb=False)
        elif index == 0:
            try:
                if (
                    self._current_source is None
                    or self._current_source_path != page.source_path
                ):
                    self._current_source = load_image(page.source_path, max_dim=2000)
                    self._current_source_path = page.source_path
                self.corner_editor.set_image(self._current_source, page.corners)
            except Exception as exc:  # noqa: BLE001 - 读取失败提示用户
                self.status_label.setText(f"读取图片失败：{exc}")

    # ---- 签名 ----

    def _on_sign(self) -> None:
        page = self._current_page()
        if page is None:
            return
        dialog = SignatureDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.signature is None:
            return
        signature = dialog.signature
        if dialog.apply_all.isChecked():
            current = self.pages_list.currentRow()
            for index, item in enumerate(self._pages):
                item.signature = signature
                if index != current:
                    self._refresh_thumbnail(index)
            self.status_label.setText("签名已应用到所有页。")
        else:
            page.signature = signature
            self.status_label.setText("签名已添加。")
        self._refresh_result()

    def _on_clear_signature(self) -> None:
        page = self._current_page()
        if page is None:
            return
        page.signature = None
        self._refresh_result()
        self.status_label.setText("已清除本页签名。")

    # ---- 导出 ----

    def _on_export(self) -> None:
        if not self._pages:
            return
        fmt = str(self.format_combo.currentData())
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base_dir = self._default_output_dir()
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        if fmt == "pdf":
            default = base_dir / f"扫描件_{stamp}.pdf"
            path, _ = QFileDialog.getSaveFileName(
                self, "导出扫描 PDF", str(default), "PDF (*.pdf)"
            )
            if not path:
                return
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            target = path
        else:
            directory = QFileDialog.getExistingDirectory(
                self, "选择导出文件夹", str(base_dir)
            )
            if not directory:
                return
            target = directory
            self._output_dir = directory

        if self._export_thread is not None and self._export_thread.isRunning():
            return
        pages = [
            replace(page, corners=np.asarray(page.corners).copy())
            for page in self._pages
        ]
        options = {
            "format": fmt,
            "path": target,
            "dpi": int(self.dpi_combo.currentData()),
            "paper": self._paper(),
            "quality": self.quality_spin.value(),
        }
        progress = QProgressDialog(
            "正在导出扫描件…", None, 0, len(pages), self
        )
        progress.setWindowTitle("导出")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(300)
        progress.setValue(0)
        progress.show()

        self._export_thread = _ExportThread(pages, options, self)
        self._export_thread.progress.connect(
            lambda done, total: progress.setValue(done)
        )
        self._export_thread.ok.connect(
            lambda result: self._on_export_done(result, progress)
        )
        self._export_thread.failed.connect(
            lambda message: self._on_export_failed(message, progress)
        )
        self._export_thread.finished.connect(self._export_thread.deleteLater)
        self.export_btn.setEnabled(False)
        self._export_thread.start()

    def _on_export_done(self, result, progress: QProgressDialog) -> None:
        progress.close()
        self._export_thread = None
        self._exported_result = result
        self.export_btn.setEnabled(True)
        first = result[0] if isinstance(result, list) and result else result
        if first:
            self._output_dir = str(Path(first).parent)
        self._update_output_label()
        if isinstance(result, list):
            shown = "\n".join(str(path) for path in result[:10])
            if len(result) > 10:
                shown += "\n…"
        else:
            shown = str(result)
        logger.info("扫描导出完成: {}", result)
        QMessageBox.information(self, "导出完成", f"已导出：\n{shown}")
        self.status_label.setText("导出完成。")

    def _on_export_failed(self, message: str, progress: QProgressDialog) -> None:
        progress.close()
        self._export_thread = None
        self.export_btn.setEnabled(True)
        QMessageBox.critical(self, "导出失败", message)

    # ---- 拖拽 / 关闭 ----

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self.add_paths(paths)
            event.acceptProposedAction()

    def reject(self) -> None:
        if self._export_thread is not None and self._export_thread.isRunning():
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self._export_thread is not None and self._export_thread.isRunning():
            event.ignore()
            return
        super().closeEvent(event)

    def _on_add_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择扫描图片",
            str(self._default_output_dir()),
            "图片 (*.jpg *.jpeg *.png *.bmp *.webp *.tif *.tiff);;所有文件 (*.*)",
        )
        if paths:
            self.add_paths(paths)


__all__ = ["ScanDialog"]
