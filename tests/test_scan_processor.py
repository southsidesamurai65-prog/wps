"""文档扫描核心算法测试（不依赖 UI）。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from wps_tool.processors.scan_processor import (
    ScanPage,
    Signature,
    detect_document_corners,
    enhance_document,
    export_scan_images,
    export_scan_pdf,
    full_frame_corners,
    load_image,
    order_corners,
    render_page,
    warp_document,
)

PHOTO_SIZE = (1200, 900)
DOC_QUAD = np.array(
    [[190, 130], [1020, 190], [960, 760], [140, 700]], dtype=np.int32
)


def _make_photo(path, quad: np.ndarray = DOC_QUAD, size=PHOTO_SIZE) -> None:
    width, height = size
    image = Image.new("RGB", (width, height), (45, 45, 45))
    draw = ImageDraw.Draw(image)
    points = [tuple(int(value) for value in point) for point in quad]
    draw.polygon(points, fill=(245, 245, 240))
    draw.line(points + [points[0]], fill=(20, 20, 20), width=8)
    for y in range(250, 720, 45):
        draw.line([(260, y), (900, y)], fill=(30, 30, 30), width=3)
    image.save(path, quality=92)


@pytest.fixture
def document_photo(tmp_path):
    path = tmp_path / "文档照片.jpg"
    _make_photo(path)
    return path


def _expected_corners() -> np.ndarray:
    expected = DOC_QUAD.astype(np.float32).copy()
    expected[:, 0] /= PHOTO_SIZE[0]
    expected[:, 1] /= PHOTO_SIZE[1]
    return order_corners(expected)


def _page(path, **kwargs) -> ScanPage:
    return ScanPage(
        source_path=str(path),
        corners=_expected_corners(),
        **kwargs,
    )


def test_load_image_handles_unicode_path(document_photo):
    rgb = load_image(str(document_photo), max_dim=800)
    assert rgb.shape[2] == 3
    assert max(rgb.shape[:2]) <= 800


def test_detect_document_corners(document_photo):
    rgb = load_image(str(document_photo))
    corners = detect_document_corners(rgb)
    assert corners is not None
    error = float(np.max(np.abs(corners - _expected_corners())))
    assert error < 0.03


def test_order_corners_handles_shuffle():
    points = np.array([[0, 0], [100, 0], [100, 80], [0, 80]], dtype=np.float32)
    shuffled = points[[2, 0, 3, 1]]
    ordered = order_corners(shuffled)
    assert np.allclose(ordered, points)


def test_warp_document_returns_upright_page(document_photo):
    rgb = load_image(str(document_photo))
    warped = warp_document(rgb, _expected_corners())
    height, width = warped.shape[:2]
    assert 700 < width < 950
    assert 500 < height < 700
    assert width > height


@pytest.mark.parametrize("mode", ["original", "enhance", "gray", "bw"])
def test_enhance_modes(document_photo, mode):
    rgb = load_image(str(document_photo))
    warped = warp_document(rgb, _expected_corners())
    result = enhance_document(warped, mode)
    assert result.shape == warped.shape
    assert result.dtype == np.uint8
    if mode == "gray":
        assert np.array_equal(result[:, :, 0], result[:, :, 1])
        assert np.array_equal(result[:, :, 1], result[:, :, 2])
    if mode == "bw":
        assert set(np.unique(result)).issubset({0, 255})
    if mode == "enhance":
        assert not np.array_equal(result, warped)


def test_render_page_rotates_and_pads(document_photo):
    page = _page(document_photo, filter="gray", rotation=90)
    image = render_page(page, dpi=150, paper="a4")
    assert image.mode == "RGB"
    assert image.size == (1240, 1754)


def test_render_page_a4_landscape(document_photo):
    image = render_page(_page(document_photo), dpi=150, paper="a4-landscape")
    assert image.size == (1754, 1240)


def test_apply_signature_changes_pixels(document_photo):
    png = BytesIO()
    signature = Image.new("RGBA", (400, 140), (0, 0, 0, 0))
    draw = ImageDraw.Draw(signature)
    draw.line(
        [(20, 100), (90, 30), (160, 110), (240, 20), (370, 90)],
        fill=(10, 10, 10, 255),
        width=16,
    )
    signature.save(png, format="PNG")
    signed = _page(
        document_photo,
        signature=Signature(png.getvalue(), anchor="bottom-right", width_ratio=0.3),
    )
    plain = _page(document_photo)
    base = np.asarray(render_page(plain, dpi=150, paper="a4"))
    result = np.asarray(render_page(signed, dpi=150, paper="a4"))
    assert base.shape == result.shape
    changed = int(np.count_nonzero(np.any(base != result, axis=2)))
    assert changed > 100


def test_export_pdf_multipage(document_photo, tmp_path):
    output = tmp_path / "扫描件.pdf"
    pages = [
        _page(document_photo, filter="original"),
        _page(document_photo, filter="enhance"),
        _page(document_photo, filter="bw", rotation=180),
    ]
    export_scan_pdf(pages, str(output), dpi=200, paper="a4")
    reader = PdfReader(str(output))
    assert len(reader.pages) == 3
    width = float(reader.pages[0].mediabox.width)
    height = float(reader.pages[0].mediabox.height)
    assert 590 < width < 600
    assert 835 < height < 850


def test_export_pdf_unicode_path(document_photo, tmp_path):
    directory = tmp_path / "中文目录"
    directory.mkdir()
    output = directory / "扫描结果.pdf"
    export_scan_pdf([_page(document_photo)], str(output), dpi=150)
    assert output.exists()
    assert output.stat().st_size > 0


def test_export_images(document_photo, tmp_path):
    output_dir = tmp_path / "图片导出"
    paths = export_scan_images(
        [_page(document_photo), _page(document_photo, filter="bw")],
        str(output_dir),
        fmt="jpg",
        dpi=150,
    )
    assert [Path(path).name for path in paths] == ["page_001.jpg", "page_002.jpg"]
    for path in paths:
        assert Path(path).exists()
        with Image.open(path) as image:
            assert image.width > 0


def test_full_frame_corners():
    corners = full_frame_corners()
    assert corners.shape == (4, 2)
    assert float(corners.min()) == 0.0
    assert float(corners.max()) == 1.0
