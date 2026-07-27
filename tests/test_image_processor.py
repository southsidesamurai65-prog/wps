"""图片处理器 spec（Layer a）。"""

from __future__ import annotations

from PIL import Image
from pypdf import PdfReader

from wps_tool.processors.image_processor import compress_image, images_to_pdf


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
