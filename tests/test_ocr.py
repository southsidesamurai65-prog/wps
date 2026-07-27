"""OCR spec（pytesseract + tesseract 二进制，可选）。

无 tesseract 二进制或缺 pytesseract 时 skip。spec 只断言「实现后返回 str」
——OCR 识别精度受字体/清晰度影响，不在 spec 内强约束内容。
"""

from __future__ import annotations

import shutil

import pytest

pytesseract = pytest.importorskip("pytesseract")
pytestmark = pytest.mark.skipif(not shutil.which("tesseract"), reason="未安装 tesseract")


def test_ocr_image_returns_str(sample_png):
    from wps_tool.services.ocr_service import ocr_image

    result = ocr_image(str(sample_png))
    assert isinstance(result, str)
