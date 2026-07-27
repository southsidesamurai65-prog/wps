"""PPTX 处理器。

Layer (a) TODO：extract_pptx_text / extract_pptx_images / analyze_pptx_structure /
replace_pptx_tokens 函数体。PptxProcessor 类已写好当分派胶水。

库 API 要点（python-pptx 1.0.2）：
- 遍历：for slide in Presentation(path).slides; for shape in slide.shapes；
  判文本用 if shape.has_text_frame（避免对 Group/GraphicFrame 误访问 .text 抛错）。
- 取标题：slide.shapes.title（直接拿 title placeholder）。
- 图片提取：shape.shape_type == MSO_SHAPE_TYPE.PICTURE 时，shape.image.blob（bytes）、
  shape.image.ext（"png"/"jpeg"）。组合图/SmartArt 内图不暴露 .image——
  测试夹具用 add_picture 加简单图保证可用。
- 结构分析：靠 slide.slide_layout.name 判页型（默认模板英文标准名）。
- 备注：slide.notes_slide.notes_text_frame.text（惰性创建，无备注返回 ""）。
- 替换：同样要遍历 text_frame 的 runs 做替换，别用 paragraph.text=。
"""

from __future__ import annotations

from typing import Any

from wps_tool.core.errors import UnsupportedActionError
from wps_tool.processors.base import FileProcessor

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


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
      n 可用 enumerate 从 1 计；ext 形如 "png"/"jpeg"。
    """
    prs=Presentation(input_path)
    rst=[]
    for i, slide in enumerate(prs.slides, start=1):
        for j, shape in enumerate(slide.shapes, start=1):
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                with open(f"{output_dir}/image_{i}_{j}.{shape.image.ext}", "wb") as f:
                    f.write(shape.image.blob)
                rst.append(f"{output_dir}/image_{i}_{j}.{shape.image.ext}")
    return rst


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
