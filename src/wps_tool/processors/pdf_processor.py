"""PDF 处理器。

Layer (a) TODO：下面 6 个函数体（merge/split/rotate/extract_pages/to_images/extract_text）。
PdfProcessor 类已写好当分派胶水，学生不要改它。

实现顺序提示：先 extract_pdf_text（最简，单测直接驱动），再 merge/split，最后 to_images。
每个函数的测试在 tests/test_pdf_processor.py，是 spec：实现到测试转绿即完成。

库 API 要点（pypdf 6.x / PyMuPDF 1.28，已按 venv 已装版本核对）：
- pypdf：PdfReader(path) 读、PdfWriter() 写；合并可用 writer.append(reader)（保书签）
  或循环 writer.add_page(page)；写出用 with open(out, "wb") as f: writer.write(f)；
  旋转 page.rotate(angle) 是原地修改，须把页加到新 writer；
  加密是 PdfWriter.encrypt(user_password, owner_password=None, use_128bit=True)
  ——没有 add_encryption（那是 PyPDF2 旧名）。
- fitz（PyMuPDF）：page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)) 渲染；
  pix.save(path) 按扩展名定格式；page.get_text() 返回 str。
"""

from __future__ import annotations

from typing import Any

import fitz
from pypdf import PdfReader, PdfWriter

from wps_tool.core.errors import UnsupportedActionError
from wps_tool.processors.base import FileProcessor

# ===== Layer (a) TODO：学生实现以下函数体 =====


def merge_pdfs(input_paths: list[str], output_path: str) -> str:
    """[学习·Layer (a) TODO] 合并多个 PDF 为一个，写出后返回 output_path。

    契约：
      - 依次把每个 input 的所有页加进同一个 PdfWriter；
      - 写到 output_path（用 ``with open(output_path, "wb") as f: writer.write(f)``）；
      - input_paths 为空时写出空 PDF（0 页）；
      - 返回 output_path。

    提示：
      - writer.append(PdfReader(p)) 一行搞定一个文件全部页（保书签）；
        也可 for page in PdfReader(p).pages: writer.add_page(page)。
      - 测试断言：输出页数 == 各输入页数之和。
    """
    writer = PdfWriter()
    for p in input_paths:
        writer.append(PdfReader(p))
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path
    raise NotImplementedError("TODO(Layer a): 实现 merge_pdfs")


def split_pdf(input_path: str, output_dir: str) -> list[str]:
    """[学习·Layer (a) TODO] 把 PDF 每页拆成一个单独 PDF，返回有序路径列表。

    契约：
      - 第 i 页（从 1 计）写出为 output_dir/page_{i}.pdf；
      - 返回按页序排列的输出路径列表。

    提示：
      - 遍历 PdfReader(input_path).pages（或 enumerate(..., start=1)）；
      - 每页 new 一个 PdfWriter、add_page(page)、写出。
    """
    reader = PdfReader(input_path)
    paths = []
    for i, page in enumerate(reader.pages, start=1):
        # 每页独立 writer，否则页会累积（page_2 会含 page_1，page_3 含 1+2）。
        writer = PdfWriter()
        writer.add_page(page)
        out = f"{output_dir}/page_{i}.pdf"
        with open(out, "wb") as f:
            writer.write(f)
        paths.append(out)
    return paths
    raise NotImplementedError("TODO(Layer a): 实现 split_pdf")


def rotate_pdf(input_path: str, output_path: str, angle: int = 90) -> str:
    """[学习·Layer (a) TODO] 旋转所有页，写出后返回 output_path。

    契约：
      - angle 只接受 {90, 180, 270}；其它值 raise UnsupportedActionError 或 ValueError；
      - 把每页旋转后加到新 PdfWriter，写出 output_path；
      - 返回 output_path。

    提示：page.rotate(angle) 原地修改并返回 page；把它 add_page 到新 writer。
    """
    if angle!=90 and angle!=180 and angle!=270:
        raise UnsupportedActionError("请使用正确的旋转角度(90,180,270)")
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(angle)
        writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path     
    raise NotImplementedError("TODO(Layer a): 实现 rotate_pdf")


def extract_pdf_pages(input_path: str, page_indices: list[int], output_path: str) -> str:
    """[学习·Layer (a) TODO] 按 0-based 页码抽取页面合并为新 PDF，返回 output_path。

    契约：
      - page_indices 是 0-based 索引列表；
      - 把这些页按给定顺序加进新 PdfWriter，写出 output_path；
      - 返回 output_path。

    提示：pages = PdfReader(input_path).pages; writer.add_page(pages[i])。
    """
    writer = PdfWriter()
    for i in page_indices:
        writer.add_page(PdfReader(input_path).pages[i])
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path  
    raise NotImplementedError("TODO(Layer a): 实现 extract_pdf_pages")


def pdf_to_images(
    input_path: str, output_dir: str, zoom: float = 2.0, fmt: str = "png"
) -> list[str]:
    """[学习·Layer (a) TODO] 逐页渲染为图片，返回有序路径列表。

    契约：
      - 第 i 页（从 1 计）渲染为 output_dir/page_{i}.{fmt}；
      - zoom 控制清晰度（Matrix(zoom, zoom)）；
      - 返回按页序排列的输出路径列表。

    提示：
      - import fitz; doc = fitz.open(input_path);
      - page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)) → pix.save(path)；
      - pix.save 按扩展名定格式，所以 path 后缀用 .{fmt}。
    """
    doc = fitz.open(input_path)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        pix.save(f"{output_dir}/page_{i+1}.{fmt}")
    return [f"{output_dir}/page_{i+1}.{fmt}" for i in range(len(doc))]
    raise NotImplementedError("TODO(Layer a): 实现 pdf_to_images")


def extract_pdf_text(input_path: str) -> str:
    """[学习·Layer (a) TODO] 提取全文，页间用 \\n 分隔，返回 str。

    契约：把每页 page.get_text() 用 "\\n" 拼接；无文本层返回空串不报错。

    提示：fitz.open(input_path) 后遍历 doc，page.get_text()。也可用 pypdf 的
    page.extract_text()，但 fitz 对中文/排版更稳，推荐 fitz。
    """
    doc = fitz.open(input_path)
    text = ""
    for page in doc:
        text += page.get_text()
        text += "\n"
    return text
    raise NotImplementedError("TODO(Layer a): 实现 extract_pdf_text")


# ===== 已写好：PdfProcessor 分派胶水（学生不要改） =====


class PdfProcessor(FileProcessor):
    supported_extensions = {".pdf"}

    def run(self, file_path: str, action: str, options: dict) -> Any:
        match action:
            case "merge":
                return merge_pdfs(options["inputs"], options["output"])
            case "split":
                return split_pdf(file_path, options["output_dir"])
            case "rotate":
                return rotate_pdf(file_path, options["output"], options.get("angle", 90))
            case "extract_pages":
                return extract_pdf_pages(file_path, options["pages"], options["output"])
            case "to_images":
                return pdf_to_images(
                    file_path,
                    options["output_dir"],
                    options.get("zoom", 2.0),
                    options.get("fmt", "png"),
                )
            case "extract_text":
                return extract_pdf_text(file_path)
            case _:
                raise UnsupportedActionError(f"PdfProcessor 不支持操作: {action}")


__all__ = [
    "PdfProcessor",
    "extract_pdf_pages",
    "extract_pdf_text",
    "merge_pdfs",
    "pdf_to_images",
    "rotate_pdf",
    "split_pdf",
]
