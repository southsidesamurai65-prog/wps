"""图片处理器。

Layer (a) TODO：images_to_pdf / compress_image 函数体。
ImageProcessor 类已写好当分派胶水。

库 API 要点（Pillow 12.x）：
- images_to_pdf：first.save(out, save_all=True, append_images=rest)；
  所有图必须先 .convert("RGB")（RGBA/P 转 PDF 会抛错）。
- compress_image：.save(out, optimize=True, quality=q)；JPEG 用 quality，PNG 用 optimize。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from wps_tool.core.errors import UnsupportedActionError
from wps_tool.processors.base import FileProcessor


def images_to_pdf(image_paths: list[str], output_path: str) -> str:
    """[学习·Layer (a) TODO] 把多张图片合成一个 PDF，返回 output_path。

    契约：
      - 每张图 .convert("RGB") 后加入；
      - 用 first.save(output_path, save_all=True, append_images=rest) 写出；
      - 返回 output_path。

    提示：Image.open(p).convert("RGB")；空列表时可写空 Image 或 raise，测试会给非空。
    """
    # 多图合 PDF：所有图须 convert("RGB")，否则 RGBA/P 转 PDF 抛错
    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    imgs[0].save(output_path, save_all=True, append_images=imgs[1:])
    return output_path
    raise NotImplementedError("TODO(Layer a): 实现 images_to_pdf")


def compress_image(input_path: str, output_path: str, quality: int = 85) -> str:
    """[学习·Layer (a) TODO] 压缩图片，返回 output_path。

    契约：Image.open(input_path).convert("RGB").save(output_path, optimize=True, quality=quality)。

    提示：quality 1..95（JPEG）；PNG 忽略 quality 只用 optimize。
    """
    Image.open(input_path).convert("RGB").save(output_path, optimize=True, quality=quality)
    return output_path
    raise NotImplementedError("TODO(Layer a): 实现 compress_image")


# ===== 扩展功能：缩放 / 格式转换 / 旋转 =====


def resize_image(
    input_path: str,
    output_path: str,
    width: int,
    height: int | None = None,
) -> str:
    """把图片缩放到给定尺寸，返回 output_path。

    ``height`` 为 ``None``（或 0）时按宽度等比缩放。
    """
    img = Image.open(input_path)
    if not height:
        height = max(1, round(img.height * width / img.width))
    img.resize((width, height)).save(output_path)
    return output_path


def convert_image(input_path: str, output_path: str) -> str:
    """按 ``output_path`` 的扩展名转换图片格式，返回 output_path。

    JPEG/BMP 不支持 alpha，先 ``convert("RGB")``；PNG/WEBP 保留原模式。
    """
    img = Image.open(input_path)
    if Path(output_path).suffix.lower() in (".jpg", ".jpeg", ".bmp") and img.mode != "RGB":
        img = img.convert("RGB")
    img.save(output_path)
    return output_path


def rotate_image(input_path: str, output_path: str, angle: int = 90) -> str:
    """顺时针旋转图片（90/180/270），返回 output_path。"""
    if angle not in (90, 180, 270):
        raise UnsupportedActionError("图片旋转角度只支持 90/180/270")
    Image.open(input_path).rotate(-angle, expand=True).save(output_path)
    return output_path


class ImageProcessor(FileProcessor):
    supported_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

    def run(self, file_path: str, action: str, options: dict) -> Any:
        match action:
            case "to_pdf":
                return images_to_pdf(options["inputs"], options["output"])
            case "compress":
                return compress_image(
                    file_path,
                    options["output"],
                    options.get("quality", 85),
                )
            case "resize":
                return resize_image(
                    file_path,
                    options["output"],
                    options["width"],
                    options.get("height"),
                )
            case "convert":
                return convert_image(file_path, options["output"])
            case "rotate_image":
                return rotate_image(
                    file_path,
                    options["output"],
                    options.get("angle", 90),
                )
            case _:
                raise UnsupportedActionError(f"ImageProcessor 不支持操作: {action}")


__all__ = [
    "ImageProcessor",
    "compress_image",
    "convert_image",
    "images_to_pdf",
    "resize_image",
    "rotate_image",
]
