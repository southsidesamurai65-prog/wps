"""图片处理器 spec（Layer a）。"""

from __future__ import annotations

import pytest
from PIL import Image
from pypdf import PdfReader

from wps_tool.core.errors import ConversionError
from wps_tool.processors.image_processor import (
    ImageProcessor,
    compress_image,
    convert_image,
    images_to_pdf,
    resize_image,
    rotate_image,
)
from wps_tool.services.ocr_service import ocr_available


def test_images_to_pdf(sample_pngs, tmp_output_dir):
    out = tmp_output_dir / "out.pdf"
    images_to_pdf([str(p) for p in sample_pngs], str(out))
    assert out.exists()
    assert len(PdfReader(str(out)).pages) == 3


def test_compress_image(sample_png, tmp_output_dir):
    out = tmp_output_dir / "compressed.jpg"
    compress_image(str(sample_png), str(out), quality=60)
    assert out.exists()
    img = Image.open(str(out))
    assert img.size[0] > 0


def test_resize_image_explicit(sample_png, tmp_output_dir):
    out = tmp_output_dir / "small.png"
    resize_image(str(sample_png), str(out), width=30, height=20)
    assert Image.open(str(out)).size == (30, 20)


def test_resize_image_keeps_aspect(sample_png, tmp_output_dir):
    out = tmp_output_dir / "half.png"
    resize_image(str(sample_png), str(out), width=50)  # 100x100 → 50x50
    assert Image.open(str(out)).size == (50, 50)


def test_convert_image_png_to_jpeg(sample_png, tmp_output_dir):
    out = tmp_output_dir / "converted.jpg"
    convert_image(str(sample_png), str(out))
    assert Image.open(str(out)).format == "JPEG"


def test_rotate_image(sample_png, tmp_output_dir):
    out = tmp_output_dir / "rotated.png"
    rotate_image(str(sample_png), str(out), angle=90)
    assert Image.open(str(out)).size == (100, 100)


def test_image_extract_text_uses_ocr(sample_png):
    """图片提取文本走 OCR：能用则返回 str，缺依赖则抛清晰的 ConversionError。"""
    proc = ImageProcessor()
    if ocr_available():
        assert isinstance(proc.run(str(sample_png), "extract_text", {}), str)
    else:
        with pytest.raises(ConversionError):
            proc.run(str(sample_png), "extract_text", {})
