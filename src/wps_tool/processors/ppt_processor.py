"""PPTX 处理器。

Layer (a) TODO：extract_pptx_text / extract_pptx_images / analyze_pptx_structure /
replace_pptx_tokens 函数体。PptxProcessor 类已写好当分派胶水。

库 API 要点（python-pptx 1.0.2）：
- 遍历：for slide in Presentation(path).slides; for shape in slide.shapes；
  判文本用 if shape.has_text_frame（避免对 Group/GraphicFrame 误访问 .text 抛错）。
- 取标题：slide.shapes.title（直接拿 title placeholder）。
- 图片提取：shape.shape_type == MSO_SHAPE_TYPE.PICTURE 时，shape.image.blob（bytes）、
  shape.image.ext（"png"/"jpeg"）。组合 shape 内的图要递归进 shape.shapes；纯 SVG 图
  shape.image 会抛 ValueError("no embedded image")，需回退到 <asvg:svgBlip r:embed>。
- 结构分析：靠 slide.slide_layout.name 判页型（默认模板英文标准名）。
- 备注：slide.notes_slide.notes_text_frame.text（惰性创建，无备注返回 ""）。
- 替换：同样要遍历 text_frame 的 runs 做替换，别用 paragraph.text=。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from wps_tool.core.errors import UnsupportedActionError
from wps_tool.processors.base import FileProcessor
from wps_tool.utils.logging import logger

#: SVG 图片命名空间：纯 SVG 图在 <a:blip><a:extLst> 里用 <asvg:svgBlip r:embed> 引用，
#: python-pptx 的 shape.image 只认标准 r:embed，遇到纯 SVG 会抛 ValueError("no embedded image")。
_SVG_NS = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _iter_pictures(shapes):
    """递归遍历图片（含组合 shape 内嵌的图片）。"""
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_pictures(shape.shapes)
        elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            yield shape


def _picture_bytes(shape) -> tuple[bytes | None, str | None]:
    """读取图片字节，返回 ``(blob, ext)``；读不到返回 ``(None, None)``。

    优先标准嵌入图；纯 SVG 图回退到 ``<asvg:svgBlip r:embed>`` 指向的图片部件。
    """
    try:
        image = shape.image
        return image.blob, image.ext
    except (ValueError, KeyError, AttributeError):
        pass
    svg = shape._element.find(f".//{{{_SVG_NS}}}svgBlip")
    r_id = svg.get(f"{{{_R_NS}}}embed") if svg is not None else None
    if not r_id:
        return None, None
    try:
        return shape.part.related_part(r_id).blob, "svg"
    except (KeyError, AttributeError, ValueError):
        return None, None


def extract_pptx_text(input_path: str) -> list[dict]:
    """[学习·Layer (a) TODO] 提取每页文本，返回 list[dict]。

    契约：每页一个 {"slide": i, "texts": [...]}，texts 是该页各文本框的非空文本。
    顺序按 slide 出现顺序。

    提示：
      - for i, slide in enumerate(Presentation(input_path).slides, start=1):
          texts = [shape.text_frame.text.strip()
                   for shape in slide.shapes if shape.has_text_frame]
          texts = [t for t in texts if t]
    """
    #要按段返回，不要整个文本框
    prs = Presentation(input_path)
    rst=[]
    for i, slide in enumerate(prs.slides, start=1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        texts.append(run.text)
        rst.append({"slide": i, "texts": texts})
    return rst


def extract_pptx_images(input_path: str, output_dir: str) -> list[str]:
    """[学习·Layer (a) TODO] 提取所有页的图片，保存到 output_dir，返回路径列表。

    契约：
      - 遍历所有 slide 的 shapes，找 shape.shape_type == MSO_SHAPE_TYPE.PICTURE；
      - 用 shape.image.blob 写出，文件名 image_{n}.{ext}（ext = shape.image.ext）；
      - 返回写出路径列表（顺序不限）。

    提示：from pptx.enum.shapes import MSO_SHAPE_TYPE；
      n 可用 enumerate 从 1 计；ext 形如 "png"/"jpeg"/"svg"。

    纯 SVG 图、组合 shape 内嵌图片都能提取；无法读取的图（如外链图）跳过并告警，不中断。
    """
    prs = Presentation(input_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    n = 0
    for i, slide in enumerate(prs.slides, start=1):
        for shape in _iter_pictures(slide.shapes):
            blob, ext = _picture_bytes(shape)
            if blob is None:
                logger.warning(
                    "PPT 提取图片: 跳过无法读取的图: slide={} name={}", i, shape.name
                )
                continue
            n += 1
            out = out_dir / f"image_{n}.{ext}"
            out.write_bytes(blob)
            paths.append(str(out))
    return paths


def analyze_pptx_structure(input_path: str) -> list[dict]:
    """[学习·Layer (a) TODO] 分析每页页型，返回 list[dict]。

    契约：每页一个 {"slide": i, "layout": layout_name, "page_type": page_type}，
      page_type 取值：
        "title"    —— layout 名含 "Title Slide"
        "section"  —— layout 名含 "Section Header"
        "content"  —— 其它（含 "Title and Content" 等）
      顺序按 slide 出现顺序。

    提示：
      - layout_name = slide.slide_layout.name
      - 用 layout_name 的字符串包含判定 page_type（见契约）。
      - 测试夹具用默认模板：slide1 是 "Title Slide"，slide2 是 "Title and Content"。
    """
    prs = Presentation(input_path)
    rst = []
    for i, slide in enumerate(prs.slides, start=1):
        layout_name = slide.slide_layout.name
        if "Title Slide" in layout_name:
            page_type = "title"
        elif "Section Header" in layout_name:
            page_type = "section"
        else:
            page_type = "content"
        rst.append({"slide": i, "layout": layout_name, "page_type": page_type})
    return rst


def replace_pptx_tokens(input_path: str, output_path: str, mapping: dict[str, str]) -> str:
    """[学习·Layer (a) TODO] 按 mapping 替换 PPTX 文本中的 token，保存，返回 output_path。

    契约：
      - 遍历每页每个 text_frame 的每个 paragraph 的 runs；
      - run.text = run.text.replace(old, new)（old/new 来自 mapping）；
      - ⚠️ 不要用 paragraph.text=（同样会丢 run 样式）；
      - Presentation.save(output_path)；返回 output_path。

    提示：和 docx 的 replace 同理，逐 run 替换。
    """
    prs = Presentation(input_path)
    for i, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        for old, new in mapping.items():
                            run.text = run.text.replace(old, new)
    prs.save(output_path)
    return output_path


class PptxProcessor(FileProcessor):
    supported_extensions = {".pptx"}

    def run(self, file_path: str, action: str, options: dict) -> Any:
        match action:
            case "extract_text":
                return extract_pptx_text(file_path)
            case "extract_images":
                return extract_pptx_images(file_path, options["output_dir"])
            case "analyze_structure":
                return analyze_pptx_structure(file_path)
            case "replace_tokens":
                return replace_pptx_tokens(file_path, options["output"], options["mapping"])
            case _:
                raise UnsupportedActionError(f"PptxProcessor 不支持操作: {action}")


__all__ = [
    "PptxProcessor",
    "analyze_pptx_structure",
    "extract_pptx_images",
    "extract_pptx_text",
    "replace_pptx_tokens",
]
