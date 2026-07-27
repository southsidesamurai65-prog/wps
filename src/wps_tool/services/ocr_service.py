"""OCR 服务（pytesseract）。

Layer (a) 服务算法 TODO：ocr_image 函数体。
可选导入与可用性检测已写好——test_ocr.py 在无 tesseract 二进制或缺 pytesseract 时 skip。

中文 OCR 建议：pytesseract 用 chi_sim 语种；若效果不佳可换 PaddleOCR（依赖更重，不在本项目范围）。
"""

from __future__ import annotations

import importlib.util
import shutil

# 用 find_spec 探测可选依赖，避免模块级 import 造成未用导入；
# 学生在 ocr_image 内部按提示自行 `import pytesseract` / `from PIL import Image`。
_HAS_PYTESSERACT = importlib.util.find_spec("pytesseract") is not None


def tesseract_available() -> bool:
    """系统是否安装了 tesseract 二进制。"""
    return shutil.which("tesseract") is not None


def ocr_available() -> bool:
    """OCR 是否可用（pytesseract 装了 + tesseract 二进制在）。"""
    return _HAS_PYTESSERACT and tesseract_available()


def ocr_image(image_path: str, lang: str = "chi_sim+eng") -> str:
    """[学习·Layer (a) TODO] 对图片做 OCR，返回识别文本。

    契约：
      - 打开图片（Image.open），调 pytesseract.image_to_string(image, lang=lang)；
      - 返回识别出的 str（可能含换行）。
      - lang 默认 "chi_sim+eng"（简中+英）。

    提示：
      - from PIL import Image; import pytesseract
      - image = Image.open(image_path); return pytesseract.image_to_string(image, lang=lang)
      - 不可用时由上层（UI/调用方）用 ocr_available() 先判，本函数不处理缺依赖。
    """
    raise NotImplementedError("TODO(Layer a): 实现 ocr_image")


__all__ = ["ocr_available", "ocr_image", "tesseract_available"]
